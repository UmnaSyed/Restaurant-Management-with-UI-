import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, DateTime, Enum, ForeignKey, CheckConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from db import Base

# ─────────────────────────────────────────────
#  Customer
# ─────────────────────────────────────────────
class Customer(Base):
    __tablename__ = 'Customer'

    customer_id = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(100), nullable=False)
    email       = Column(String(150), unique=True, nullable=False)
    phone       = Column(String(20))
    password    = Column(String(255), nullable=False)
    created_at  = Column(DateTime, default=func.now())

    orders       = relationship('Order',       back_populates='customer')
    reservations = relationship('Reservation', back_populates='customer')
    feedbacks    = relationship('Feedback',    back_populates='customer')


# ─────────────────────────────────────────────
#  Staff
# ─────────────────────────────────────────────
class Staff(Base):
    __tablename__ = 'Staff'

    staff_id  = Column(Integer, primary_key=True, autoincrement=True)
    name      = Column(String(100), nullable=False)
    role      = Column(Enum('waiter', 'chef', 'admin'), nullable=False)
    email     = Column(String(150), unique=True, nullable=False)
    password  = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)


# ─────────────────────────────────────────────
#  Rider
# ─────────────────────────────────────────────
class Rider(Base):
    __tablename__ = 'Rider'

    rider_id     = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(100), nullable=False)
    phone        = Column(String(20), nullable=False)
    is_available = Column(Boolean, default=True)

    deliveries = relationship('Delivery', back_populates='rider')


# ─────────────────────────────────────────────
#  MenuItem
# ─────────────────────────────────────────────
class MenuItem(Base):
    __tablename__ = 'MenuItem'

    item_id      = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(150), nullable=False)
    description  = Column(Text)
    price        = Column(DECIMAL(8, 2), nullable=False)
    category     = Column(String(100))
    is_available = Column(Boolean, default=True)

    order_items  = relationship('OrderItem',         back_populates='menu_item')
    ingredients  = relationship('MenuItemIngredient', back_populates='menu_item')


# ─────────────────────────────────────────────
#  Ingredient
# ─────────────────────────────────────────────
class Ingredient(Base):
    __tablename__ = 'Ingredient'

    ingredient_id   = Column(Integer, primary_key=True, autoincrement=True)
    name            = Column(String(150), nullable=False)
    quantity        = Column(DECIMAL(10, 2), nullable=False, default=0)
    unit            = Column(String(30))
    low_stock_alert = Column(DECIMAL(10, 2), default=5.0)

    menu_items = relationship('MenuItemIngredient', back_populates='ingredient')


# ─────────────────────────────────────────────
#  MenuItemIngredient (junction table)
# ─────────────────────────────────────────────
class MenuItemIngredient(Base):
    __tablename__ = 'MenuItemIngredient'

    item_id       = Column(Integer, ForeignKey('MenuItem.item_id'),       primary_key=True)
    ingredient_id = Column(Integer, ForeignKey('Ingredient.ingredient_id'), primary_key=True)
    quantity_used = Column(DECIMAL(10, 2), nullable=False)

    menu_item  = relationship('MenuItem',    back_populates='ingredients')
    ingredient = relationship('Ingredient',  back_populates='menu_items')


# ─────────────────────────────────────────────
#  RestaurantTable
# ─────────────────────────────────────────────
class RestaurantTable(Base):
    __tablename__ = 'RestaurantTable'

    table_id     = Column(Integer, primary_key=True, autoincrement=True)
    table_number = Column(Integer, unique=True, nullable=False)
    capacity     = Column(Integer, nullable=False)
    status       = Column(Enum('available', 'occupied', 'reserved'), default='available')

    orders       = relationship('Order',       back_populates='table')
    reservations = relationship('Reservation', back_populates='table')


# ─────────────────────────────────────────────
#  Reservation
# ─────────────────────────────────────────────
class Reservation(Base):
    __tablename__ = 'Reservation'

    reservation_id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id    = Column(Integer, ForeignKey('Customer.customer_id'), nullable=False)
    table_id       = Column(Integer, ForeignKey('RestaurantTable.table_id'), nullable=True)
    party_size     = Column(Integer, nullable=False)
    date_time      = Column(DateTime, nullable=False)
    status         = Column(Enum('pending', 'confirmed', 'cancelled', 'completed'), default='pending')

    customer = relationship('Customer',         back_populates='reservations')
    table    = relationship('RestaurantTable',  back_populates='reservations')


# ─────────────────────────────────────────────
#  Order
# ─────────────────────────────────────────────
class Order(Base):
    __tablename__ = 'Order'

    order_id    = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey('Customer.customer_id'), nullable=False)
    table_id    = Column(Integer, ForeignKey('RestaurantTable.table_id'), nullable=True)
    order_type  = Column(Enum('dine-in', 'delivery'), nullable=False)
    status      = Column(Enum('placed', 'preparing', 'ready', 'served', 'delivered', 'cancelled'), default='placed')
    is_peak     = Column(Boolean, default=False)
    priority    = Column(Integer, default=5)
    placed_at   = Column(DateTime, default=func.now())

    customer    = relationship('Customer',        back_populates='orders')
    table       = relationship('RestaurantTable', back_populates='orders')
    order_items = relationship('OrderItem',       back_populates='order')
    delivery    = relationship('Delivery',        back_populates='order',   uselist=False)
    bill        = relationship('Bill',            back_populates='order',   uselist=False)
    feedback    = relationship('Feedback',        back_populates='order',   uselist=False)


# ─────────────────────────────────────────────
#  OrderItem
# ─────────────────────────────────────────────
class OrderItem(Base):
    __tablename__ = 'OrderItem'

    order_item_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id      = Column(Integer, ForeignKey('Order.order_id'), nullable=False)
    item_id       = Column(Integer, ForeignKey('MenuItem.item_id'), nullable=False)
    quantity      = Column(Integer, nullable=False, default=1)
    special_note  = Column(String(255))

    order     = relationship('Order',    back_populates='order_items')
    menu_item = relationship('MenuItem', back_populates='order_items')


# ─────────────────────────────────────────────
#  Delivery
# ─────────────────────────────────────────────
class Delivery(Base):
    __tablename__ = 'Delivery'

    delivery_id = Column(Integer, primary_key=True, autoincrement=True)
    order_id    = Column(Integer, ForeignKey('Order.order_id'), unique=True, nullable=False)
    rider_id    = Column(Integer, ForeignKey('Rider.rider_id'), nullable=True)
    address     = Column(Text, nullable=False)
    status      = Column(Enum('assigned', 'picked_up', 'delivered'), default='assigned')
    assigned_at = Column(DateTime, default=func.now())

    order = relationship('Order', back_populates='delivery')
    rider = relationship('Rider', back_populates='deliveries')


# ─────────────────────────────────────────────
#  Bill
# ─────────────────────────────────────────────
class Bill(Base):
    __tablename__ = 'Bill'

    bill_id        = Column(Integer, primary_key=True, autoincrement=True)
    order_id       = Column(Integer, ForeignKey('Order.order_id'), unique=True, nullable=False)
    subtotal       = Column(DECIMAL(10, 2), nullable=False)
    tax_rate       = Column(DECIMAL(5, 2), default=10.00)
    total          = Column(DECIMAL(10, 2), nullable=False)
    payment_status = Column(Enum('pending', 'paid'), default='pending')
    payment_method = Column(Enum('cash', 'card', 'online'), nullable=True)
    generated_at   = Column(DateTime, default=func.now())

    order = relationship('Order', back_populates='bill')


# ─────────────────────────────────────────────
#  Feedback
# ─────────────────────────────────────────────
class Feedback(Base):
    __tablename__ = 'Feedback'

    feedback_id  = Column(Integer, primary_key=True, autoincrement=True)
    customer_id  = Column(Integer, ForeignKey('Customer.customer_id'), nullable=False)
    order_id     = Column(Integer, ForeignKey('Order.order_id'), nullable=True)
    rating       = Column(Integer, CheckConstraint('rating BETWEEN 1 AND 5'))
    comment      = Column(Text)
    submitted_at = Column(DateTime, default=func.now())

    customer = relationship('Customer', back_populates='feedbacks')
    order    = relationship('Order',    back_populates='feedback')