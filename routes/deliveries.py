"""
deliveries.py — Delivery management routes
THIS is where your AI rider-assignment algorithm is called.
When a delivery order is placed, the AI picks the first
available rider and marks them as unavailable.
When delivery completes, the DB trigger marks the rider available again.
"""

from flask import Blueprint, request, jsonify
from db import SessionLocal
from models import Delivery, Order, Rider
from routes.auth import token_required
from routes.ai_engine import assign_rider

deliveries_bp = Blueprint('deliveries', __name__)


# ─────────────────────────────────────────────
#  Helper: serialize a delivery to dict
# ─────────────────────────────────────────────
def serialize_delivery(delivery):
    return {
        'delivery_id': delivery.delivery_id,
        'order_id':    delivery.order_id,
        'rider_id':    delivery.rider_id,
        'rider_name':  delivery.rider.name  if delivery.rider  else 'Unassigned',
        'rider_phone': delivery.rider.phone if delivery.rider  else None,
        'address':     delivery.address,
        'status':      delivery.status,
        'assigned_at': str(delivery.assigned_at)
    }


# ─────────────────────────────────────────────
#  POST /api/deliveries/assign/<order_id>
#  Assign a rider to a delivery order using the AI engine.
#  Call this right after placing a delivery order.
#
#  Request body:
#  { "address": "123 Main Street, Karachi" }
# ─────────────────────────────────────────────
@deliveries_bp.route('/assign/<int:order_id>', methods=['POST'])
@token_required
def assign_delivery(current_user, order_id):
    data = request.json

    if not data.get('address'):
        return jsonify({'error': 'Delivery address is required'}), 400

    db = SessionLocal()
    try:
        # Verify the order exists and is a delivery order
        order = db.query(Order).get(order_id)
        if not order:
            return jsonify({'error': f'Order {order_id} not found'}), 404
        if order.order_type != 'delivery':
            return jsonify({'error': 'This order is not a delivery order'}), 400

        # Check delivery doesn't already exist for this order
        existing = db.query(Delivery).filter_by(order_id=order_id).first()
        if existing:
            return jsonify({'error': 'A delivery is already assigned for this order'}), 409

        # ── AI ENGINE CALLED HERE ──
        # assign_rider picks the first available rider
        # and marks them is_available = False inside the function
        rider_id = assign_rider(db)

        if rider_id is None:
            # Create the delivery record but without a rider
            # Staff will manually assign a rider when one becomes free
            delivery = Delivery(
                order_id=order_id,
                rider_id=None,
                address=data['address'],
                status='assigned'
            )
            db.add(delivery)
            db.commit()

            return jsonify({
                'message':     'Delivery created but no rider available right now',
                'delivery_id': delivery.delivery_id,
                'rider':       'Unassigned — a rider will be assigned when available',
                'address':     data['address']
            }), 201

        # A rider was found — create the delivery record with them
        delivery = Delivery(
            order_id=order_id,
            rider_id=rider_id,
            address=data['address'],
            status='assigned'
        )
        db.add(delivery)
        db.commit()

        rider = db.query(Rider).get(rider_id)

        return jsonify({
            'message':     'Rider assigned successfully',
            'delivery_id': delivery.delivery_id,
            'rider_id':    rider_id,
            'rider_name':  rider.name,
            'rider_phone': rider.phone,
            'address':     data['address'],
            'ai_note':     f'AI assigned {rider.name} (first available rider)'
        }), 201

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/deliveries/
#  List all active deliveries — for the dispatch dashboard.
#  Active means status is 'assigned' or 'picked_up'.
#  Add ?all=true to also include completed deliveries.
# ─────────────────────────────────────────────
@deliveries_bp.route('/', methods=['GET'])
@token_required
def get_deliveries(current_user):
    db = SessionLocal()
    try:
        query = db.query(Delivery)

        # By default only show active deliveries
        show_all = request.args.get('all', 'false').lower() == 'true'
        if not show_all:
            query = query.filter(Delivery.status.in_(['assigned', 'picked_up']))

        deliveries = query.order_by(Delivery.assigned_at.asc()).all()

        return jsonify([serialize_delivery(d) for d in deliveries]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/deliveries/<delivery_id>/status
#  Update delivery status: assigned → picked_up → delivered
#
#  When status becomes 'delivered':
#    - The DB trigger automatically sets rider.is_available = True
#    - The order status is NOT auto-updated here — call
#      PATCH /api/orders/<id>/status separately to mark it delivered
#
#  Request body:  { "status": "picked_up" }
# ─────────────────────────────────────────────
@deliveries_bp.route('/<int:delivery_id>/status', methods=['PATCH'])
@token_required
def update_delivery_status(current_user, delivery_id):
    data = request.json
    new_status = data.get('status')

    valid_statuses = ['assigned', 'picked_up', 'delivered']
    if new_status not in valid_statuses:
        return jsonify({
            'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
        }), 400

    db = SessionLocal()
    try:
        delivery = db.query(Delivery).get(delivery_id)

        if not delivery:
            return jsonify({'error': f'Delivery {delivery_id} not found'}), 404

        if delivery.status == 'delivered':
            return jsonify({'error': 'This delivery is already completed'}), 400

        old_status      = delivery.status
        delivery.status = new_status
        db.commit()

        # When status = 'delivered', the DB trigger trg_free_rider_on_delivery_complete
        # automatically runs and sets rider.is_available = True.
        # No extra code needed here — the trigger does the work.

        response = {
            'message':    f'Delivery {delivery_id} status updated',
            'old_status': old_status,
            'new_status': new_status
        }

        if new_status == 'delivered':
            response['note'] = 'DB trigger has automatically freed the rider for new assignments'

        return jsonify(response), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/deliveries/<delivery_id>/rider
#  Manually reassign a rider (e.g. when original rider is unavailable)
#
#  Request body:  { "rider_id": 2 }
# ─────────────────────────────────────────────
@deliveries_bp.route('/<int:delivery_id>/rider', methods=['PATCH'])
@token_required
def reassign_rider(current_user, delivery_id):
    data    = request.json
    rider_id = data.get('rider_id')

    if not rider_id:
        return jsonify({'error': 'rider_id is required'}), 400

    db = SessionLocal()
    try:
        delivery = db.query(Delivery).get(delivery_id)
        if not delivery:
            return jsonify({'error': f'Delivery {delivery_id} not found'}), 404

        rider = db.query(Rider).get(rider_id)
        if not rider:
            return jsonify({'error': f'Rider {rider_id} not found'}), 404
        if not rider.is_available:
            return jsonify({'error': f'Rider {rider.name} is currently on another delivery'}), 409

        # Free the old rider if there was one
        if delivery.rider_id:
            old_rider = db.query(Rider).get(delivery.rider_id)
            if old_rider:
                old_rider.is_available = True

        # Assign the new rider
        delivery.rider_id   = rider_id
        rider.is_available  = False
        db.commit()

        return jsonify({
            'message':   f'Rider reassigned to {rider.name}',
            'rider_id':  rider_id,
            'rider_name': rider.name
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()