DROP DATABASE IF EXISTS restaurant_db;

CREATE DATABASE restaurant_db;
USE restaurant_db;

CREATE TABLE Customer (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    phone       VARCHAR(20),
    password    VARCHAR(255) NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE Staff (
    staff_id   INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    role       ENUM('waiter','chef','admin') NOT NULL,
    email      VARCHAR(150) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL,
    is_active  BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE Rider (
    rider_id     INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(100) NOT NULL,
    phone        VARCHAR(20) NOT NULL,
    is_available BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE MenuItem (
    item_id      INT AUTO_INCREMENT PRIMARY KEY,
    name         VARCHAR(150) NOT NULL,
    description  TEXT,
    price        DECIMAL(8,2) NOT NULL,
    category     VARCHAR(100),
    is_available BOOLEAN DEFAULT TRUE
) ENGINE=InnoDB;

CREATE TABLE Ingredient (
    ingredient_id   INT AUTO_INCREMENT PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    quantity        DECIMAL(10,2) NOT NULL DEFAULT 0,
    unit            VARCHAR(30),
    low_stock_alert DECIMAL(10,2) DEFAULT 5.0
) ENGINE=InnoDB;

CREATE TABLE MenuItemIngredient (
    item_id       INT NOT NULL,
    ingredient_id INT NOT NULL,
    quantity_used DECIMAL(10,2) NOT NULL,
    PRIMARY KEY (item_id, ingredient_id),
    FOREIGN KEY (item_id)       REFERENCES MenuItem(item_id)       ON DELETE CASCADE,
    FOREIGN KEY (ingredient_id) REFERENCES Ingredient(ingredient_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE RestaurantTable (
    table_id     INT AUTO_INCREMENT PRIMARY KEY,
    table_number INT UNIQUE NOT NULL,
    capacity     INT NOT NULL,
    status       ENUM('available','occupied','reserved') DEFAULT 'available'
) ENGINE=InnoDB;

CREATE TABLE Reservation (
    reservation_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id    INT NOT NULL,
    table_id       INT,
    party_size     INT NOT NULL,
    date_time      DATETIME NOT NULL,
    status         ENUM('pending','confirmed','cancelled','completed') DEFAULT 'pending',
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (table_id)    REFERENCES RestaurantTable(table_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE `Order` (
    order_id    INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    table_id    INT,
    order_type  ENUM('dine-in','delivery') NOT NULL,
    status      ENUM('placed','preparing','ready','served','delivered','cancelled') DEFAULT 'placed',
    is_peak     BOOLEAN DEFAULT FALSE,
    priority    INT DEFAULT 5,
    placed_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (table_id)    REFERENCES RestaurantTable(table_id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE OrderItem (
    order_item_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id      INT NOT NULL,
    item_id       INT NOT NULL,
    quantity      INT NOT NULL DEFAULT 1,
    special_note  VARCHAR(255),
    FOREIGN KEY (order_id) REFERENCES `Order`(order_id)   ON DELETE CASCADE,
    FOREIGN KEY (item_id)  REFERENCES MenuItem(item_id)   ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE Delivery (
    delivery_id INT AUTO_INCREMENT PRIMARY KEY,
    order_id    INT UNIQUE NOT NULL,
    rider_id    INT,
    address     TEXT NOT NULL,
    status      ENUM('assigned','picked_up','delivered') DEFAULT 'assigned',
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES `Order`(order_id) ON DELETE CASCADE,
    FOREIGN KEY (rider_id) REFERENCES Rider(rider_id)   ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE Bill (
    bill_id        INT AUTO_INCREMENT PRIMARY KEY,
    order_id       INT UNIQUE NOT NULL,
    subtotal       DECIMAL(10,2) NOT NULL,
    tax_rate       DECIMAL(5,2) DEFAULT 10.00,
    total          DECIMAL(10,2) NOT NULL,
    payment_status ENUM('pending','paid') DEFAULT 'pending',
    payment_method ENUM('cash','card','online'),
    generated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES `Order`(order_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE Feedback (
    feedback_id  INT AUTO_INCREMENT PRIMARY KEY,
    customer_id  INT NOT NULL,
    order_id     INT,
    rating       INT CHECK (rating BETWEEN 1 AND 5),
    comment      TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (order_id)    REFERENCES `Order`(order_id)     ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE InventoryAlert (
    alert_id         INT AUTO_INCREMENT PRIMARY KEY,
    ingredient_id    INT NOT NULL,
    ingredient_name  VARCHAR(150),
    current_quantity DECIMAL(10,2),
    threshold        DECIMAL(10,2),
    alerted_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ingredient_id) REFERENCES Ingredient(ingredient_id) ON DELETE CASCADE
) ENGINE=InnoDB;


CREATE INDEX idx_customer_email        ON Customer(email);
CREATE INDEX idx_staff_email           ON Staff(email);
CREATE INDEX idx_order_customer        ON `Order`(customer_id);
CREATE INDEX idx_order_status          ON `Order`(status);
CREATE INDEX idx_order_type            ON `Order`(order_type);
CREATE INDEX idx_order_placed_at       ON `Order`(placed_at);
CREATE INDEX idx_order_priority_status ON `Order`(priority ASC, status);
CREATE INDEX idx_reservation_datetime  ON Reservation(date_time);
CREATE INDEX idx_reservation_customer  ON Reservation(customer_id);
CREATE INDEX idx_table_status          ON RestaurantTable(status);
CREATE INDEX idx_menuitem_category     ON MenuItem(category);
CREATE INDEX idx_ingredient_quantity   ON Ingredient(quantity);
CREATE INDEX idx_delivery_order        ON Delivery(order_id);
CREATE INDEX idx_delivery_rider        ON Delivery(rider_id);
CREATE INDEX idx_bill_payment_status   ON Bill(payment_status);
CREATE INDEX idx_feedback_rating       ON Feedback(rating);


CREATE VIEW vw_kitchen_queue AS
SELECT
    o.order_id,
    o.order_type,
    o.priority,
    o.placed_at,
    c.name AS customer_name,
    rt.table_number,
    GROUP_CONCAT(CONCAT(oi.quantity, 'x ', mi.name) SEPARATOR ', ') AS items
FROM `Order` o
JOIN Customer c          ON o.customer_id = c.customer_id
LEFT JOIN RestaurantTable rt ON o.table_id = rt.table_id
JOIN OrderItem oi        ON o.order_id = oi.order_id
JOIN MenuItem mi         ON oi.item_id = mi.item_id
WHERE o.status IN ('placed', 'preparing')
GROUP BY o.order_id, o.order_type, o.priority, o.placed_at, c.name, rt.table_number
ORDER BY o.priority ASC, o.placed_at ASC;

CREATE VIEW vw_low_stock_ingredients AS
SELECT
    ingredient_id,
    name,
    quantity,
    unit,
    low_stock_alert,
    CONCAT(ROUND((quantity / low_stock_alert) * 100), '%') AS stock_percentage
FROM Ingredient
WHERE quantity <= low_stock_alert
ORDER BY (quantity / low_stock_alert) ASC;

CREATE VIEW vw_active_deliveries AS
SELECT
    d.delivery_id,
    o.order_id,
    c.name  AS customer_name,
    c.phone AS customer_phone,
    r.name  AS rider_name,
    r.phone AS rider_phone,
    d.address,
    d.status,
    o.placed_at,
    TIMESTAMPDIFF(MINUTE, d.assigned_at, NOW()) AS minutes_since_assigned
FROM Delivery d
JOIN `Order` o   ON d.order_id = o.order_id
JOIN Customer c  ON o.customer_id = c.customer_id
LEFT JOIN Rider r ON d.rider_id = r.rider_id
WHERE d.status IN ('assigned', 'picked_up')
ORDER BY d.assigned_at ASC;

CREATE VIEW vw_customer_order_history AS
SELECT
    c.customer_id,
    c.name,
    c.email,
    COUNT(o.order_id)       AS total_orders,
    COALESCE(SUM(b.total), 0) AS total_spent,
    AVG(f.rating)           AS avg_rating,
    MAX(o.placed_at)        AS last_order_date
FROM Customer c
LEFT JOIN `Order` o   ON c.customer_id = o.customer_id
LEFT JOIN Bill b      ON o.order_id = b.order_id
LEFT JOIN Feedback f  ON c.customer_id = f.customer_id
GROUP BY c.customer_id, c.name, c.email;

CREATE VIEW vw_daily_revenue AS
SELECT
    DATE(o.placed_at)  AS order_date,
    COUNT(o.order_id)  AS total_orders,
    SUM(CASE WHEN o.order_type = 'dine-in'   THEN 1 ELSE 0 END) AS dine_in_orders,
    SUM(CASE WHEN o.order_type = 'delivery'  THEN 1 ELSE 0 END) AS delivery_orders,
    SUM(b.subtotal)    AS total_subtotal,
    SUM(b.total - b.subtotal) AS total_tax,
    SUM(b.total)       AS total_revenue,
    AVG(b.total)       AS avg_order_value
FROM `Order` o
JOIN Bill b ON o.order_id = b.order_id
WHERE b.payment_status = 'paid'
GROUP BY DATE(o.placed_at)
ORDER BY order_date DESC;

CREATE VIEW vw_table_occupancy AS
SELECT
    rt.table_id,
    rt.table_number,
    rt.capacity,
    rt.status,
    o.order_id,
    c.name AS customer_name,
    o.placed_at AS occupied_since,
    TIMESTAMPDIFF(MINUTE, o.placed_at, NOW()) AS minutes_occupied
FROM RestaurantTable rt
LEFT JOIN `Order` o ON rt.table_id = o.table_id
    AND o.status IN ('placed', 'preparing', 'ready', 'served')
    AND o.order_type = 'dine-in'
LEFT JOIN Customer c ON o.customer_id = c.customer_id
ORDER BY rt.table_number;


DELIMITER //

CREATE TRIGGER trg_generate_bill_after_order_served
AFTER UPDATE ON `Order`
FOR EACH ROW
BEGIN
    DECLARE v_subtotal DECIMAL(10,2);
    IF (NEW.status IN ('served', 'delivered') AND OLD.status != NEW.status) THEN
        IF NOT EXISTS (SELECT 1 FROM Bill WHERE order_id = NEW.order_id) THEN
            SELECT SUM(mi.price * oi.quantity) INTO v_subtotal
            FROM OrderItem oi
            JOIN MenuItem mi ON oi.item_id = mi.item_id
            WHERE oi.order_id = NEW.order_id;
            INSERT INTO Bill (order_id, subtotal, total)
            VALUES (NEW.order_id, v_subtotal, v_subtotal * 1.10);
        END IF;
    END IF;
END//

CREATE TRIGGER trg_deduct_inventory_on_order
AFTER INSERT ON OrderItem
FOR EACH ROW
BEGIN
    UPDATE Ingredient i
    JOIN MenuItemIngredient mii ON i.ingredient_id = mii.ingredient_id
    SET i.quantity = i.quantity - (mii.quantity_used * NEW.quantity)
    WHERE mii.item_id = NEW.item_id;
END//

CREATE TRIGGER trg_prevent_negative_inventory
BEFORE UPDATE ON Ingredient
FOR EACH ROW
BEGIN
    IF NEW.quantity < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Error: Ingredient quantity cannot be negative. Insufficient stock.';
    END IF;
END//

CREATE TRIGGER trg_release_table_on_order_complete
AFTER UPDATE ON `Order`
FOR EACH ROW
BEGIN
    IF (NEW.order_type = 'dine-in'
        AND NEW.status = 'served'
        AND OLD.status != 'served'
        AND NEW.table_id IS NOT NULL) THEN
        UPDATE RestaurantTable
        SET status = 'available'
        WHERE table_id = NEW.table_id;
    END IF;
END//

CREATE TRIGGER trg_free_rider_on_delivery_complete
AFTER UPDATE ON Delivery
FOR EACH ROW
BEGIN
    IF (NEW.status = 'delivered' AND OLD.status != 'delivered') THEN
        UPDATE Rider
        SET is_available = TRUE
        WHERE rider_id = NEW.rider_id;
    END IF;
END//

CREATE TRIGGER trg_log_low_stock_alert
AFTER UPDATE ON Ingredient
FOR EACH ROW
BEGIN
    IF (NEW.quantity <= NEW.low_stock_alert
        AND OLD.quantity > OLD.low_stock_alert) THEN
        INSERT INTO InventoryAlert (ingredient_id, ingredient_name, current_quantity, threshold)
        VALUES (NEW.ingredient_id, NEW.name, NEW.quantity, NEW.low_stock_alert);
    END IF;
END//

DELIMITER ;


-- Customers
INSERT INTO Customer (name, email, phone, password) VALUES
('Ali Khan',    'ali@example.com',    '03001234567', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi'),
('Sara Ahmed',  'sara@example.com',   '03009876543', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi'),
('Hassan Raza', 'hassan@example.com', '03111234567', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi');

-- Staff
INSERT INTO Staff (name, role, email, password) VALUES
('Ahmed Waiter', 'waiter', 'ahmed@dine.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi'),
('Chef Bilal',   'chef',   'bilal@dine.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi'),
('Admin Zainab', 'admin',  'admin@dine.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5jtJ3vQPA6sMi');

-- Riders
INSERT INTO Rider (name, phone) VALUES
('Rider Usman',  '03112233445'),
('Rider Kamran', '03223344556'),
('Rider Fahad',  '03334455667');

INSERT INTO MenuItem (name, description, price, category) VALUES
('Mozzarella Sticks',     'Crispy breaded mozzarella with marinara sauce.',                      5.99,  'Starters'),
('Nachos',                'Tortilla chips with cheese, jalapeños, and salsa.',                   4.99,  'Starters'),
('Stuffed Mushrooms',     'Mushrooms stuffed with garlic, herbs, and cream cheese.',             6.49,  'Starters'),
('Jalapeño Loaded Fries', 'Crispy fries topped with jalapeños, cheese, and creamy sauce.',      7.99,  'Starters'),
('Beef Steak',            'Grilled beef with mashed potatoes or seasonal vegetables.',          12.99,  'Main Course'),
('Chicken Steak',         'Grilled chicken in citrus glaze, served with vegetables.',           14.99,  'Main Course'),
('Signature Pizza',       'Topped with fresh ingredients and melted cheese.',                   10.99,  'Main Course'),
('Alfredo Pasta',         'Creamy Alfredo with Parmesan and grilled chicken.',                  13.49,  'Main Course'),
('Club Sandwich',         'Three-layer sandwich with chicken, bacon, lettuce, and tomato.',      8.99,  'Main Course'),
('Ice Cream',             'Choose from chocolate, vanilla, or mint chocolate chip.',             4.99,  'Desserts'),
('Tiramisu',              'Coffee-soaked biscuits with mascarpone cream layers.',                5.99,  'Desserts'),
('Strawberry Cheesecake', 'Rich cheesecake with a fresh strawberry topping.',                   6.49,  'Desserts'),
('Lemon Tart',            'Tangy lemon filling in a buttery crispy crust.',                      4.49,  'Desserts'),
('Carbonated Drink',      'Choice of sodas and fizzy beverages.',                               2.99,  'Beverages'),
('Iced Latte',            'Creamy iced coffee with a shot of espresso.',                        3.49,  'Beverages'),
('Iced Mocha',            'Chocolatey iced coffee topped with whipped cream.',                  3.49,  'Beverages'),
('Hot Chocolate',         'Warm, rich chocolate drink with whipped cream.',                     2.49,  'Beverages'),
('Cappuccino',            'Espresso with steamed milk and foam.',                               2.99,  'Beverages'),
('Dipping Sauces',        'Various sauces to complement your meal.',                            1.49,  'Extras'),
('Plain Fries',           'Crispy fries served with ketchup and mayo.',                         2.49,  'Extras');


INSERT INTO Ingredient (name, quantity, unit, low_stock_alert) VALUES
('Mozzarella Cheese',  30.0,  'kg',     5.0),   -- id 1
('Tortilla Chips',     20.0,  'kg',     4.0),   -- id 2
('Mushrooms',          15.0,  'kg',     3.0),   -- id 3
('Potatoes',           50.0,  'kg',     8.0),   -- id 4
('Beef',               40.0,  'kg',    10.0),   -- id 5
('Chicken',            50.0,  'kg',    10.0),   -- id 6
('Pizza Dough',        25.0,  'kg',     5.0),   -- id 7
('Pasta',              20.0,  'kg',     4.0),   -- id 8
('Bread',              30.0,  'pieces', 10.0),  -- id 9
('Cream',              20.0,  'litres', 4.0),   -- id 10
('Coffee Beans',       10.0,  'kg',     2.0),   -- id 11
('Milk',               40.0,  'litres', 8.0),   -- id 12
('Strawberries',       15.0,  'kg',     3.0),   -- id 13
('Lemons',             20.0,  'kg',     4.0),   -- id 14
('Soda Syrup',         15.0,  'litres', 3.0),   -- id 15
('Chocolate',          10.0,  'kg',     2.0),   -- id 16
('Jalapeños',          10.0,  'kg',     2.0),   -- id 17
('Marinara Sauce',     10.0,  'litres', 2.0),   -- id 18
('Cheese Blend',       25.0,  'kg',     5.0),   -- id 19
('Vegetables Mix',     30.0,  'kg',     6.0);   -- id 20


INSERT INTO MenuItemIngredient (item_id, ingredient_id, quantity_used) VALUES
-- Mozzarella Sticks (id 1): mozzarella + marinara sauce
(1,  1,  0.15),
(1,  18, 0.05),

-- Nachos (id 2): tortilla chips + cheese blend + jalapeños
(2,  2,  0.15),
(2,  19, 0.05),
(2,  17, 0.03),

-- Stuffed Mushrooms (id 3): mushrooms + cream + cheese blend
(3,  3,  0.20),
(3,  10, 0.05),
(3,  19, 0.05),

-- Jalapeño Loaded Fries (id 4): potatoes + jalapeños + cheese blend
(4,  4,  0.30),
(4,  17, 0.04),
(4,  19, 0.05),

-- Beef Steak (id 5): beef + vegetables mix
(5,  5,  0.35),
(5,  20, 0.10),

-- Chicken Steak (id 6): chicken + vegetables mix
(6,  6,  0.30),
(6,  20, 0.10),

-- Signature Pizza (id 7): pizza dough + cheese blend + vegetables mix
(7,  7,  0.25),
(7,  19, 0.10),
(7,  20, 0.08),

-- Alfredo Pasta (id 8): pasta + cream + chicken + cheese blend
(8,  8,  0.20),
(8,  10, 0.10),
(8,  6,  0.15),
(8,  19, 0.05),

-- Club Sandwich (id 9): bread + chicken + vegetables mix
(9,  9,  2.00),
(9,  6,  0.15),
(9,  20, 0.08),

-- Ice Cream (id 10): cream + milk
(10, 10, 0.15),
(10, 12, 0.10),

-- Tiramisu (id 11): cream + coffee beans + chocolate
(11, 10, 0.15),
(11, 11, 0.02),
(11, 16, 0.03),

-- Strawberry Cheesecake (id 12): cream + strawberries + cheese blend
(12, 10, 0.10),
(12, 13, 0.12),
(12, 19, 0.05),

-- Lemon Tart (id 13): cream + lemons
(13, 10, 0.08),
(13, 14, 0.10),

-- Carbonated Drink (id 14): soda syrup
(14, 15, 0.05),

-- Iced Latte (id 15): coffee beans + milk
(15, 11, 0.02),
(15, 12, 0.20),

-- Iced Mocha (id 16): coffee beans + milk + chocolate
(16, 11, 0.02),
(16, 12, 0.20),
(16, 16, 0.03),

-- Hot Chocolate (id 17): chocolate + milk
(17, 16, 0.05),
(17, 12, 0.25),

-- Cappuccino (id 18): coffee beans + milk
(18, 11, 0.02),
(18, 12, 0.15),

-- Dipping Sauces (id 19): marinara sauce + cheese blend (mixed sauces)
(19, 18, 0.05),
(19, 19, 0.03),

-- Plain Fries (id 20): potatoes
(20, 4,  0.25);


INSERT INTO RestaurantTable (table_number, capacity) VALUES
(1, 2),
(2, 4),
(3, 4),
(4, 6),
(5, 8),
(6, 2),
(7, 4);


SELECT 'Tables created:' AS Info;
SHOW TABLES;

SELECT 'Menu items (should be 20 rows):' AS Info;
SELECT item_id, name, price, category FROM MenuItem ORDER BY item_id;

SELECT 'Ingredients (should be 20 rows):' AS Info;
SELECT ingredient_id, name, quantity, unit FROM Ingredient ORDER BY ingredient_id;

SELECT 'MenuItemIngredient links:' AS Info;
SELECT COUNT(*) AS total_links FROM MenuItemIngredient;

SELECT 'Views created:' AS Info;
SHOW FULL TABLES WHERE Table_Type = 'VIEW';

SELECT 'Triggers created:' AS Info;
SHOW TRIGGERS;
