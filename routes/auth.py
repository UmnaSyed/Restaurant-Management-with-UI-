"""
auth.py — Authentication routes
Handles customer registration and login.
Returns a JWT token on successful login that must be sent
with every protected request in the Authorization header.

Header format:  Authorization: Bearer <your_token_here>
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
import bcrypt
import jwt
import os
from datetime import datetime, timedelta
from functools import wraps
from db import SessionLocal
from models import Customer, Staff

auth_bp = Blueprint('auth', __name__)

# ─────────────────────────────────────────────
#  Helper: get secret key from environment
# ─────────────────────────────────────────────
def get_secret():
    return os.getenv('SECRET_KEY', 'fallback_secret_change_this')


# ─────────────────────────────────────────────
#  token_required decorator
#  Use this on any route that needs a logged-in user.
#
#  Example usage in another route file:
#    from routes.auth import token_required
#
#    @orders_bp.route('/', methods=['GET'])
#    @token_required
#    def get_orders(current_user):
#        ...
# ─────────────────────────────────────────────
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        # JWT is passed in the Authorization header as "Bearer <token>"
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': 'Token is missing. Please login first.'}), 401

        try:
            # Decode the token using our secret key
            data = jwt.decode(token, get_secret(), algorithms=['HS256'])

            db = SessionLocal()

            # Try to find the user as a Customer first, then Staff
            current_user = db.query(Customer).filter_by(
                customer_id=data.get('user_id')
            ).first()

            if not current_user:
                # Maybe it's a staff member logging in
                current_user = db.query(Staff).filter_by(
                    staff_id=data.get('user_id')
                ).first()

            db.close()

            if not current_user:
                return jsonify({'error': 'User not found. Token invalid.'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired. Please login again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid.'}), 401

        # Pass the current_user object into the route function
        return f(current_user, *args, **kwargs)

    return decorated


# ─────────────────────────────────────────────
#  POST /api/auth/register
#  Create a new customer account
#
#  Request body (JSON):
#    { "name": "Ali Khan", "email": "ali@example.com",
#      "phone": "03001234567", "password": "mypassword" }
#
#  Response:
#    201 { "message": "Account created", "customer_id": 1 }
# ─────────────────────────────────────────────
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.json

    # Validate required fields
    required = ['name', 'email', 'password']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    db = SessionLocal()
    try:
        # Check if email already exists
        existing = db.query(Customer).filter_by(email=data['email']).first()
        if existing:
            return jsonify({'error': 'Email already registered. Please login.'}), 409

        # Hash the password — bcrypt adds a random salt automatically
        # Never store plain-text passwords
        hashed_password = bcrypt.hashpw(
            data['password'].encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        new_customer = Customer(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),      # optional field
            password=hashed_password
        )

        db.add(new_customer)
        db.commit()

        return jsonify({
            'message': 'Account created successfully',
            'customer_id': new_customer.customer_id
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  POST /api/auth/login
#  Login with email + password, receive a JWT token
#
#  Request body (JSON):
#    { "email": "ali@example.com", "password": "mypassword",
#      "role": "customer" }   ← role can be "customer" or "staff"
#
#  Response:
#    200 { "token": "eyJ...", "user": { "id": 1, "name": "Ali Khan", "role": "customer" } }
# ─────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.json

    if not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required'}), 400

    role = data.get('role', 'customer')  # defaults to customer login

    db = SessionLocal()
    try:
        if role == 'staff':
            user = db.query(Staff).filter_by(email=data['email']).first()
        else:
            user = db.query(Customer).filter_by(email=data['email']).first()

        if not user:
            # Use a generic message — don't tell attackers which part was wrong
            return jsonify({'error': 'Invalid email or password'}), 401

        # bcrypt.checkpw compares the plain password against the stored hash
        password_matches = bcrypt.checkpw(
            data['password'].encode('utf-8'),
            user.password.encode('utf-8')
        )

        if not password_matches:
            return jsonify({'error': 'Invalid email or password'}), 401

        # Build the JWT payload
        user_id = user.customer_id if role == 'customer' else user.staff_id
        user_role = role if role == 'customer' else user.role  # waiter/chef/admin

        payload = {
            'user_id': user_id,
            'role': user_role,
            'exp': datetime.utcnow() + timedelta(hours=24)  # token expires in 24 hours
        }

        token = jwt.encode(payload, get_secret(), algorithm='HS256')

        return jsonify({
            'token': token,
            'user': {
                'id': user_id,
                'name': user.name,
                'email': user.email,
                'role': user_role
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()