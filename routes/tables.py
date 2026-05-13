"""
tables.py — Restaurant table management routes
Shows table status, details, and allows manual status updates.
The kitchen/host uses this to see which tables are free.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Blueprint, request, jsonify
from db import SessionLocal
from models import RestaurantTable, Order
from routes.auth import token_required

tables_bp = Blueprint('tables', __name__)


# ─────────────────────────────────────────────
#  Helper: serialize a table to dict
# ─────────────────────────────────────────────
def serialize_table(table):
    return {
        'table_id':     table.table_id,
        'table_number': table.table_number,
        'capacity':     table.capacity,
        'status':       table.status
    }


# ─────────────────────────────────────────────
#  GET /api/tables/
#  Return all tables with their current status.
#  Optional filter: ?status=available
#
#  This replicates the logic of your vw_table_occupancy
#  view but through the ORM so we can add filters.
# ─────────────────────────────────────────────
@tables_bp.route('/', methods=['GET'])
@token_required
def get_tables(current_user):
    db = SessionLocal()
    try:
        query = db.query(RestaurantTable)

        # Optional filter — e.g. ?status=available shows only free tables
        status = request.args.get('status')
        if status:
            query = query.filter(RestaurantTable.status == status)

        tables = query.order_by(RestaurantTable.table_number.asc()).all()

        # For each table, also pull the active order on it (if any)
        result = []
        for table in tables:
            table_dict = serialize_table(table)

            # Find the current active dine-in order on this table
            active_order = db.query(Order).filter(
                Order.table_id == table.table_id,
                Order.order_type == 'dine-in',
                Order.status.in_(['placed', 'preparing', 'ready', 'served'])
            ).first()

            if active_order:
                table_dict['active_order_id'] = active_order.order_id
                table_dict['occupied_since']  = str(active_order.placed_at)
            else:
                table_dict['active_order_id'] = None
                table_dict['occupied_since']  = None

            result.append(table_dict)

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/tables/<table_id>
#  Get details of a single table
# ─────────────────────────────────────────────
@tables_bp.route('/<int:table_id>', methods=['GET'])
@token_required
def get_table(current_user, table_id):
    db = SessionLocal()
    try:
        table = db.query(RestaurantTable).get(table_id)

        if not table:
            return jsonify({'error': f'Table {table_id} not found'}), 404

        return jsonify(serialize_table(table)), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/tables/<table_id>/status
#  Manually update a table's status.
#  Used by the host/waiter to mark tables manually
#  when needed (e.g. cleaning, reserved by phone).
#
#  Request body:  { "status": "available" }
#  Valid values: "available", "occupied", "reserved"
# ─────────────────────────────────────────────
@tables_bp.route('/<int:table_id>/status', methods=['PATCH'])
@token_required
def update_table_status(current_user, table_id):
    data = request.json
    new_status = data.get('status')

    valid_statuses = ['available', 'occupied', 'reserved']
    if new_status not in valid_statuses:
        return jsonify({
            'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
        }), 400

    db = SessionLocal()
    try:
        table = db.query(RestaurantTable).get(table_id)

        if not table:
            return jsonify({'error': f'Table {table_id} not found'}), 404

        old_status   = table.status
        table.status = new_status
        db.commit()

        return jsonify({
            'message':    f'Table {table.table_number} status updated',
            'old_status': old_status,
            'new_status': new_status
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()