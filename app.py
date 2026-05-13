"""
app.py — Main Flask application entry point
Run this file to start the server: python app.py

All routes are organized into blueprints (separate files).
The URL prefix maps each blueprint to a base URL:
  /api/auth          → routes/auth.py
  /api/orders        → routes/orders.py
  /api/tables        → routes/tables.py
  /api/reservations  → routes/reservations.py
  /api/deliveries    → routes/deliveries.py
  /api/menu          → routes/menu.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # ← ADD THIS
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'routes'))  # ← ADD THIS

from flask import Flask
from flask_cors import CORS

# Import all blueprints
from routes.auth         import auth_bp
from routes.orders       import orders_bp
from routes.tables       import tables_bp
from routes.reservations import reservations_bp
from routes.deliveries   import deliveries_bp
from routes.menu         import menu_bp

app = Flask(__name__)

# CORS allows your frontend (React, etc.) to call this API
# from a different port/domain without being blocked by the browser
CORS(app)

# Register all blueprints with their URL prefixes
app.register_blueprint(auth_bp,         url_prefix='/api/auth')
app.register_blueprint(orders_bp,       url_prefix='/api/orders')
app.register_blueprint(tables_bp,       url_prefix='/api/tables')
app.register_blueprint(reservations_bp, url_prefix='/api/reservations')
app.register_blueprint(deliveries_bp,   url_prefix='/api/deliveries')
app.register_blueprint(menu_bp,         url_prefix='/api/menu')


# ─────────────────────────────────────────────
#  Health check endpoint
#  Visit http://localhost:5000/api/health to confirm server is running
# ─────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health():
    return {'status': 'ok', 'message': 'Restaurant API is running'}, 200


if __name__ == '__main__':
    # debug=True: auto-restarts on code changes, shows detailed errors
    # Turn off debug=False in production
    app.run(debug=True, port=5000)