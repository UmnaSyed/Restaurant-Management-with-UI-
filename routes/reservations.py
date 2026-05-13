"""
reservations.py — Reservation management routes
THIS is where your AI table-allocation algorithm is called.
When a customer books a table, the AI picks the best fit
using greedy best-fit (smallest table that still fits the party).
"""

from flask import Blueprint, request, jsonify
from db import SessionLocal
from models import Reservation, RestaurantTable, Customer
from routes.auth import token_required
from routes.ai_engine import allocate_table

reservations_bp = Blueprint('reservations', __name__)


# ─────────────────────────────────────────────
#  Helper: serialize a reservation to dict
# ─────────────────────────────────────────────
def serialize_reservation(res):
    return {
        'reservation_id': res.reservation_id,
        'customer_id':    res.customer_id,
        'customer_name':  res.customer.name if res.customer else None,
        'table_id':       res.table_id,
        'table_number':   res.table.table_number if res.table else None,
        'party_size':     res.party_size,
        'date_time':      str(res.date_time),
        'status':         res.status
    }


# ─────────────────────────────────────────────
#  POST /api/reservations/
#  Customer makes a reservation.
#  AI engine runs allocate_table() to find the best table.
#
#  Request body:
#  {
#    "customer_id": 1,
#    "party_size": 4,
#    "date_time": "2025-07-15 19:30:00"
#  }
# ─────────────────────────────────────────────
@reservations_bp.route('/', methods=['POST'])
def make_reservation():
    data = request.json

    required = ['customer_id', 'party_size', 'date_time']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400

    party_size = int(data['party_size'])
    if party_size < 1:
        return jsonify({'error': 'Party size must be at least 1'}), 400

    db = SessionLocal()
    try:
        # Verify the customer exists
        customer = db.query(Customer).get(data['customer_id'])
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404

        # ── AI ENGINE CALLED HERE ──
        # allocate_table finds the smallest available table >= party_size
        # It also marks the table as 'reserved' inside the function
        table_id = allocate_table(party_size, db)

        if table_id is None:
            return jsonify({
                'error': 'No available tables for your party size at this time. Please try a different time.',
                'party_size': party_size
            }), 409

        # Create the reservation with the AI-assigned table
        reservation = Reservation(
            customer_id=data['customer_id'],
            table_id=table_id,
            party_size=party_size,
            date_time=data['date_time'],
            status='confirmed'  # auto-confirm since AI already assigned a table
        )

        db.add(reservation)
        db.commit()

        # Fetch the table number to return it in the response
        table = db.query(RestaurantTable).get(table_id)

        return jsonify({
            'message':        'Reservation confirmed',
            'reservation_id': reservation.reservation_id,
            'table_id':       table_id,
            'table_number':   table.table_number,
            'capacity':       table.capacity,
            'party_size':     party_size,
            'date_time':      str(reservation.date_time),
            'ai_note':        f'AI selected Table {table.table_number} (capacity {table.capacity}) for party of {party_size}'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/reservations/
#  List all reservations — for admin and front desk staff.
#  Optional filters: ?status=confirmed  or  ?customer_id=1
# ─────────────────────────────────────────────
@reservations_bp.route('/', methods=['GET'])
@token_required
def get_reservations(current_user):
    db = SessionLocal()
    try:
        query = db.query(Reservation)

        # Optional filters
        status      = request.args.get('status')
        customer_id = request.args.get('customer_id')

        if status:
            query = query.filter(Reservation.status == status)
        if customer_id:
            query = query.filter(Reservation.customer_id == int(customer_id))

        # Sort soonest reservation first
        reservations = query.order_by(Reservation.date_time.asc()).all()

        return jsonify([serialize_reservation(r) for r in reservations]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/reservations/<id>/status
#  Update a reservation's status.
#  When cancelled: the table is released back to available.
#
#  Request body:  { "status": "cancelled" }
#  Valid values: "pending", "confirmed", "cancelled", "completed"
# ─────────────────────────────────────────────
@reservations_bp.route('/<int:reservation_id>/status', methods=['PATCH'])
@token_required
def update_reservation_status(current_user, reservation_id):
    data = request.json
    new_status = data.get('status')

    valid_statuses = ['pending', 'confirmed', 'cancelled', 'completed']
    if new_status not in valid_statuses:
        return jsonify({
            'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
        }), 400

    db = SessionLocal()
    try:
        reservation = db.query(Reservation).get(reservation_id)

        if not reservation:
            return jsonify({'error': f'Reservation {reservation_id} not found'}), 404

        old_status           = reservation.status
        reservation.status   = new_status

        # If cancelled, release the table back to available
        # so other customers can book it
        if new_status == 'cancelled' and reservation.table_id:
            table = db.query(RestaurantTable).get(reservation.table_id)
            if table and table.status == 'reserved':
                table.status = 'available'

        db.commit()

        return jsonify({
            'message':    f'Reservation {reservation_id} updated',
            'old_status': old_status,
            'new_status': new_status
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()