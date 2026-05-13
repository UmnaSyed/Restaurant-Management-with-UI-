"""
orders.py — Order management routes
Handles placing, viewing, updating, and cancelling orders.
The AI engine sets priority and peak-hour flag on every new order.

All routes except POST / require a valid JWT token.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from db import SessionLocal
from models import Order, OrderItem, MenuItem, Customer, RestaurantTable
from routes.auth import token_required
from routes.ai_engine import prioritize_order, deduct_inventory, check_ingredient_availability

orders_bp = Blueprint('orders', __name__)


# ─────────────────────────────────────────────
#  Helper: serialize an Order object to a dict
#  so we can return it as JSON
# ─────────────────────────────────────────────
def serialize_order(order):
    return {
        'order_id':   order.order_id,
        'customer_id': order.customer_id,
        'table_id':   order.table_id,
        'order_type': order.order_type,
        'status':     order.status,
        'is_peak':    order.is_peak,
        'priority':   order.priority,
        'placed_at':  str(order.placed_at),
        'items': [
            {
                'order_item_id': oi.order_item_id,
                'item_id':       oi.item_id,
                'item_name':     oi.menu_item.name,
                'quantity':      oi.quantity,
                'unit_price':    float(oi.menu_item.price),
                'special_note':  oi.special_note
            }
            for oi in order.order_items
        ]
    }


# ─────────────────────────────────────────────
#  POST /api/orders/
#  Place a new order. AI sets priority + is_peak.
#  Inventory is checked BEFORE deducting.
#
#  Request body:
#  {
#    "customer_id": 1,
#    "order_type": "dine-in",      ← or "delivery"
#    "table_id": 2,                ← required for dine-in, omit for delivery
#    "items": [
#      { "item_id": 1, "quantity": 2, "special_note": "extra spicy" },
#      { "item_id": 4, "quantity": 1 }
#    ]
#  }
# ─────────────────────────────────────────────
@orders_bp.route('/', methods=['POST'])
def place_order():
    data = request.json

    # Validate required fields
    if not data.get('customer_id') or not data.get('order_type') or not data.get('items'):
        return jsonify({'error': 'customer_id, order_type, and items are required'}), 400

    if data['order_type'] == 'dine-in' and not data.get('table_id'):
        return jsonify({'error': 'table_id is required for dine-in orders'}), 400

    db = SessionLocal()
    try:
        # ── STEP 1: Check ingredient availability BEFORE touching the DB ──
        # This prevents placing an order we cannot fulfil
        is_available, missing = check_ingredient_availability(data['items'], db)
        if not is_available:
            return jsonify({
                'error': 'Insufficient ingredients for this order',
                'missing_ingredients': missing
            }), 409

        # ── STEP 2: Create the Order row ──
        order = Order(
            customer_id=data['customer_id'],
            table_id=data.get('table_id'),
            order_type=data['order_type']
        )

        # AI engine sets priority score and peak-hour flag
        order.priority, order.is_peak = prioritize_order(order, db)

        db.add(order)
        db.flush()  # get order_id without committing yet

        # ── STEP 3: Add order items ──
        for item in data['items']:
            oi = OrderItem(
                order_id=order.order_id,
                item_id=item['item_id'],
                quantity=item['quantity'],
                special_note=item.get('special_note')
            )
            db.add(oi)

        # ── STEP 4: Deduct inventory NOW (only after all items are added) ──
        # BUG FIX: inventory was deducted before commit in the original code.
        # If commit failed, inventory was still reduced. Now we deduct here
        # and commit everything together as one atomic transaction.
        deduct_inventory(data['items'], db)

        # ── STEP 5: Mark table as occupied for dine-in ──
        if data['order_type'] == 'dine-in' and data.get('table_id'):
            table = db.query(RestaurantTable).get(data['table_id'])
            if table:
                table.status = 'occupied'

        # ── STEP 6: Commit everything together ──
        db.commit()

        return jsonify({
            'message': 'Order placed successfully',
            'order_id': order.order_id,
            'priority': order.priority,
            'is_peak':  order.is_peak
        }), 201

    except Exception as e:
        db.rollback()  # if anything fails, undo ALL changes including inventory
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/orders/
#  List all orders — used by kitchen dashboard and admin.
#  Optional query params:
#    ?status=placed        ← filter by status
#    ?order_type=dine-in   ← filter by type
#
#  Example: GET /api/orders/?status=placed&order_type=dine-in
# ─────────────────────────────────────────────
@orders_bp.route('/', methods=['GET'])
@token_required
def get_orders(current_user):
    db = SessionLocal()
    try:
        query = db.query(Order)

        # Optional filters from query string
        status     = request.args.get('status')
        order_type = request.args.get('order_type')

        if status:
            query = query.filter(Order.status == status)
        if order_type:
            query = query.filter(Order.order_type == order_type)

        # Sort by priority (lowest number = highest urgency) then by time placed
        orders = query.order_by(Order.priority.asc(), Order.placed_at.asc()).all()

        return jsonify([serialize_order(o) for o in orders]), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/orders/<order_id>
#  Get full details of a single order
# ─────────────────────────────────────────────
@orders_bp.route('/<int:order_id>', methods=['GET'])
@token_required
def get_order(current_user, order_id):
    db = SessionLocal()
    try:
        order = db.query(Order).get(order_id)

        if not order:
            return jsonify({'error': f'Order {order_id} not found'}), 404

        return jsonify(serialize_order(order)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/orders/<order_id>/status
#  Update the status of an order.
#  The DB trigger auto-generates a bill when status → 'served' or 'delivered'.
#  The DB trigger auto-releases the table when status → 'served'.
#
#  Valid status transitions:
#    placed → preparing → ready → served   (dine-in)
#    placed → preparing → ready → delivered (delivery)
#
#  Request body:  { "status": "preparing" }
# ─────────────────────────────────────────────
@orders_bp.route('/<int:order_id>/status', methods=['PATCH'])
@token_required
def update_order_status(current_user, order_id):
    data = request.json
    new_status = data.get('status')

    valid_statuses = ['placed', 'preparing', 'ready', 'served', 'delivered', 'cancelled']
    if new_status not in valid_statuses:
        return jsonify({
            'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
        }), 400

    db = SessionLocal()
    try:
        order = db.query(Order).get(order_id)

        if not order:
            return jsonify({'error': f'Order {order_id} not found'}), 404

        if order.status == 'cancelled':
            return jsonify({'error': 'Cannot update a cancelled order'}), 400

        old_status = order.status
        order.status = new_status
        db.commit()

        # The DB trigger handles:
        # - Auto bill generation when status = 'served' or 'delivered'
        # - Auto table release when status = 'served'
        # Nothing extra needed here — the triggers do the work.

        return jsonify({
            'message': f'Order {order_id} status updated',
            'old_status': old_status,
            'new_status': new_status,
            'note': 'Bill auto-generated by DB trigger if status is served/delivered'
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  DELETE /api/orders/<order_id>
#  Cancel an order (sets status to 'cancelled').
#  We soft-delete (status = cancelled) rather than
#  deleting the row, so we keep history for reporting.
# ─────────────────────────────────────────────
@orders_bp.route('/<int:order_id>', methods=['DELETE'])
@token_required
def cancel_order(current_user, order_id):
    db = SessionLocal()
    try:
        order = db.query(Order).get(order_id)

        if not order:
            return jsonify({'error': f'Order {order_id} not found'}), 404

        if order.status in ['served', 'delivered']:
            return jsonify({'error': 'Cannot cancel an order that is already completed'}), 400

        if order.status == 'cancelled':
            return jsonify({'error': 'Order is already cancelled'}), 400

        order.status = 'cancelled'

        # If dine-in, release the table back to available
        if order.order_type == 'dine-in' and order.table_id:
            table = db.query(RestaurantTable).get(order.table_id)
            if table:
                table.status = 'available'

        db.commit()

        return jsonify({'message': f'Order {order_id} has been cancelled'}), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()