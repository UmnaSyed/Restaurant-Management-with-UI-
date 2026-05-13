"""
menu.py — Menu management routes
Customers browse the menu. Staff/admins can update prices
and toggle item availability when ingredients run out.
"""

from flask import Blueprint, request, jsonify
from db import SessionLocal
from models import MenuItem, Ingredient, MenuItemIngredient
from routes.auth import token_required

menu_bp = Blueprint('menu', __name__)


# ─────────────────────────────────────────────
#  Helper: serialize a menu item to dict
# ─────────────────────────────────────────────
def serialize_item(item):
    return {
        'item_id':      item.item_id,
        'name':         item.name,
        'description':  item.description,
        'price':        float(item.price),
        'category':     item.category,
        'is_available': item.is_available
    }


# ─────────────────────────────────────────────
#  GET /api/menu/
#  Return all available menu items.
#  No auth required — customers can browse the menu freely.
#  Optional filters:
#    ?category=Main Course   ← filter by category
#    ?all=true               ← include unavailable items (for staff)
# ─────────────────────────────────────────────
@menu_bp.route('/', methods=['GET'])
def get_menu():
    db = SessionLocal()
    try:
        query = db.query(MenuItem)

        # By default only show available items to customers
        show_all = request.args.get('all', 'false').lower() == 'true'
        if not show_all:
            query = query.filter(MenuItem.is_available == True)

        # Optional category filter — e.g. ?category=Starters
        category = request.args.get('category')
        if category:
            query = query.filter(MenuItem.category == category)

        # Sort by category then name for a clean menu layout
        items = query.order_by(MenuItem.category.asc(), MenuItem.name.asc()).all()

        # Group items by category for easy frontend rendering
        grouped = {}
        for item in items:
            cat = item.category or 'Other'
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(serialize_item(item))

        return jsonify({
            'total_items': len(items),
            'menu':        grouped
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/menu/<item_id>
#  Get full details of a single menu item,
#  including which ingredients it uses.
#  Useful for the kitchen and for ingredient checks.
# ─────────────────────────────────────────────
@menu_bp.route('/<int:item_id>', methods=['GET'])
def get_menu_item(item_id):
    db = SessionLocal()
    try:
        item = db.query(MenuItem).get(item_id)

        if not item:
            return jsonify({'error': f'Menu item {item_id} not found'}), 404

        # Include ingredient breakdown for this dish
        item_dict = serialize_item(item)
        item_dict['ingredients'] = [
            {
                'ingredient_id':   usage.ingredient_id,
                'ingredient_name': usage.ingredient.name,
                'quantity_used':   float(usage.quantity_used),
                'unit':            usage.ingredient.unit,
                'in_stock':        float(usage.ingredient.quantity),
                'sufficient':      usage.ingredient.quantity >= usage.quantity_used
            }
            for usage in item.ingredients
        ]

        return jsonify(item_dict), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  PATCH /api/menu/<item_id>
#  Admin/staff updates a menu item.
#  Can update: price, description, category, is_available
#
#  Request body (send only fields you want to change):
#  {
#    "price": 500.00,
#    "is_available": false,
#    "description": "Updated description"
#  }
# ─────────────────────────────────────────────
@menu_bp.route('/<int:item_id>', methods=['PATCH'])
@token_required
def update_menu_item(current_user, item_id):
    data = request.json

    db = SessionLocal()
    try:
        item = db.query(MenuItem).get(item_id)

        if not item:
            return jsonify({'error': f'Menu item {item_id} not found'}), 404

        # Only update the fields that were sent in the request
        # This way you can send just { "is_available": false } without
        # needing to send the entire item object
        if 'price' in data:
            if float(data['price']) <= 0:
                return jsonify({'error': 'Price must be greater than 0'}), 400
            item.price = data['price']

        if 'description'  in data: item.description  = data['description']
        if 'category'     in data: item.category     = data['category']
        if 'is_available' in data: item.is_available = data['is_available']
        if 'name'         in data: item.name         = data['name']

        db.commit()

        return jsonify({
            'message': f'Menu item "{item.name}" updated successfully',
            'item':    serialize_item(item)
        }), 200

    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


# ─────────────────────────────────────────────
#  GET /api/menu/low-stock
#  Show menu items where at least one ingredient is low.
#  This mirrors your vw_low_stock_ingredients view
#  but also tells you WHICH menu items are affected.
# ─────────────────────────────────────────────
@menu_bp.route('/low-stock', methods=['GET'])
@token_required
def get_low_stock_items(current_user):
    db = SessionLocal()
    try:
        # Find all ingredients that are at or below their alert threshold
        low_ingredients = db.query(Ingredient).filter(
            Ingredient.quantity <= Ingredient.low_stock_alert
        ).all()

        if not low_ingredients:
            return jsonify({'message': 'All ingredients are adequately stocked', 'items': []}), 200

        low_ingredient_ids = {i.ingredient_id for i in low_ingredients}

        # Find which menu items use those low ingredients
        affected_links = db.query(MenuItemIngredient).filter(
            MenuItemIngredient.ingredient_id.in_(low_ingredient_ids)
        ).all()

        affected_item_ids = {link.item_id for link in affected_links}
        affected_items    = db.query(MenuItem).filter(
            MenuItem.item_id.in_(affected_item_ids)
        ).all()

        result = {
            'low_ingredients': [
                {
                    'ingredient_id':   ing.ingredient_id,
                    'name':            ing.name,
                    'quantity':        float(ing.quantity),
                    'unit':            ing.unit,
                    'threshold':       float(ing.low_stock_alert),
                    'stock_percent':   round((float(ing.quantity) / float(ing.low_stock_alert)) * 100)
                }
                for ing in low_ingredients
            ],
            'affected_menu_items': [serialize_item(i) for i in affected_items]
        }

        return jsonify(result), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()