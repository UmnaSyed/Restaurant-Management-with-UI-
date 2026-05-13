"""
AI Engine for Restaurant Management System
Contains algorithms for:
- Table allocation (greedy best-fit)
- Rider assignment (availability-based)
- Order prioritization (rule-based with peak hours)
- Inventory deduction and low-stock alerts
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models import RestaurantTable, Rider, MenuItemIngredient, Ingredient


def allocate_table(party_size, db):
    """
    Allocate the smallest available table that fits the party size.
    Uses greedy best-fit algorithm to minimize wasted seats.
    
    Args:
        party_size (int): Number of people in the party
        db: SQLAlchemy database session
        
    Returns:
        int or None: table_id if found, None if no tables available
    """
    # Find all available tables with sufficient capacity
    available_tables = db.query(RestaurantTable).filter(
        RestaurantTable.status == 'available',
        RestaurantTable.capacity >= party_size
    ).all()
    
    if not available_tables:
        return None
    
    # Greedy approach: pick the table with minimum wasted seats
    best_table = min(available_tables, key=lambda t: t.capacity - party_size)
    
    # Mark table as reserved
    best_table.status = 'reserved'
    db.commit()
    
    return best_table.table_id


def assign_rider(db):
    """
    Assign an available rider to a delivery order.
    Simple first-available strategy (can be extended to priority queue).
    
    Args:
        db: SQLAlchemy database session
        
    Returns:
        int or None: rider_id if available, None if all riders busy
    """
    # Find first available rider
    available_rider = db.query(Rider).filter(
        Rider.is_available == True
    ).first()
    
    if not available_rider:
        return None
    
    # Mark rider as unavailable
    available_rider.is_available = False
    db.commit()
    
    return available_rider.rider_id


def prioritize_order(order, db):
    """
    Calculate order priority based on:
    - Peak hours (lunch: 12-2pm, dinner: 6-9pm)
    - Order type (dine-in gets slight priority over delivery)
    
    Lower priority number = higher urgency (processed first)
    
    Args:
        order: Order object
        db: SQLAlchemy database session
        
    Returns:
        tuple: (priority_score, is_peak_hour)
    """
    current_hour = datetime.now().hour
    
    # Check if current time is peak hour
    is_peak = (12 <= current_hour <= 14) or (18 <= current_hour <= 21)
    
    # Base priority
    priority = 5
    
    # Reduce priority number (increase urgency) during peak hours
    if is_peak:
        priority -= 2
    
    # Delivery orders get slightly lower priority than dine-in
    if order.order_type == 'delivery':
        priority += 1
    
    return priority, is_peak


def deduct_inventory(items, db):
    """
    Deduct ingredients from inventory based on order items.
    Prints low-stock alerts if any ingredient falls below threshold.
    
    Args:
        items: List of dicts with 'item_id' and 'quantity'
        db: SQLAlchemy database session
    """
    for item in items:
        # Get all ingredients used by this menu item
        ingredient_usages = db.query(MenuItemIngredient).filter_by(
            item_id=item['item_id']
        ).all()
        
        for usage in ingredient_usages:
            # Fetch the ingredient
            ingredient = db.query(Ingredient).get(usage.ingredient_id)
            
            # Deduct the quantity
            total_usage = usage.quantity_used * item['quantity']
            ingredient.quantity -= total_usage
            
            # Check for low stock
            if ingredient.quantity <= ingredient.low_stock_alert:
                print(f"⚠️  LOW STOCK ALERT: {ingredient.name} — {ingredient.quantity:.2f} {ingredient.unit} remaining")
    
    db.commit()


def check_ingredient_availability(items, db):
    """
    Check if sufficient ingredients are available before placing order.
    
    Args:
        items: List of dicts with 'item_id' and 'quantity'
        db: SQLAlchemy database session
        
    Returns:
        tuple: (is_available: bool, missing_ingredients: list)
    """
    missing = []
    
    for item in items:
        ingredient_usages = db.query(MenuItemIngredient).filter_by(
            item_id=item['item_id']
        ).all()
        
        for usage in ingredient_usages:
            ingredient = db.query(Ingredient).get(usage.ingredient_id)
            required = usage.quantity_used * item['quantity']
            
            if ingredient.quantity < required:
                missing.append({
                    'ingredient': ingredient.name,
                    'required': float(required),
                    'available': float(ingredient.quantity),
                    'unit': ingredient.unit
                })
    
    return (len(missing) == 0, missing)


def release_rider(rider_id, db):
    """
    Mark a rider as available again after delivery completion.
    
    Args:
        rider_id (int): ID of the rider to release
        db: SQLAlchemy database session
    """
    rider = db.query(Rider).get(rider_id)
    if rider:
        rider.is_available = True
        db.commit()