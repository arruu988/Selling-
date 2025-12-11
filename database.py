import sqlite3
import logging

logger = logging.getLogger(__name__)

def init_database():
    """Database tables create karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  product_data TEXT UNIQUE NOT NULL,
                  category TEXT,
                  price INTEGER DEFAULT 50,
                  sold INTEGER DEFAULT 0,
                  added_date DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (order_id TEXT PRIMARY KEY,
                  user_id INTEGER NOT NULL,
                  username TEXT,
                  product_id INTEGER,
                  product_data TEXT,
                  amount INTEGER,
                  screenshot_id TEXT,
                  status TEXT DEFAULT 'pending',
                  order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                  admin_action_date DATETIME,
                  admin_id INTEGER)''')
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                  total_orders INTEGER DEFAULT 0,
                  total_spent INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()
    logger.info("✅ Database initialized successfully!")

def add_product(product_data, category="General", price=50):
    """New product add karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO products (product_data, category, price) 
                     VALUES (?, ?, ?)''', (product_data, category, price))
        conn.commit()
        return c.lastrowid
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_available_products():
    """Available products return karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT id, product_data, category, price 
                 FROM products WHERE sold = 0 ORDER BY added_date''')
    products = c.fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    """Specific product details"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM products WHERE id = ?''', (product_id,))
    product = c.fetchone()
    conn.close()
    return product

def mark_product_sold(product_id):
    """Product sold mark karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''UPDATE products SET sold = 1 WHERE id = ?''', (product_id,))
    conn.commit()
    conn.close()

def create_order(order_id, user_id, username, product_id, product_data, amount):
    """New order create karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    c.execute('''INSERT INTO orders 
                 (order_id, user_id, username, product_id, product_data, amount) 
                 VALUES (?, ?, ?, ?, ?, ?)''', 
              (order_id, user_id, username, product_id, product_data, amount))
    
    c.execute('''INSERT OR IGNORE INTO users (user_id, username) 
                 VALUES (?, ?)''', (user_id, username))
    
    conn.commit()
    conn.close()

def update_order_screenshot(order_id, screenshot_id):
    """Order mein screenshot update karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''UPDATE orders SET screenshot_id = ?, status = 'waiting_approval' 
                 WHERE order_id = ?''', (screenshot_id, order_id))
    conn.commit()
    conn.close()

def approve_order(order_id, admin_id):
    """Order approve karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    c.execute('''UPDATE orders SET status = 'approved', 
                 admin_action_date = CURRENT_TIMESTAMP, admin_id = ? 
                 WHERE order_id = ?''', (admin_id, order_id))
    
    result = c.execute('''SELECT product_id FROM orders WHERE order_id = ?''', (order_id,)).fetchone()
    if result:
        mark_product_sold(result[0])
    
    order = c.execute('''SELECT user_id, amount FROM orders WHERE order_id = ?''', (order_id,)).fetchone()
    if order:
        user_id, amount = order
        c.execute('''UPDATE users SET total_orders = total_orders + 1, 
                     total_spent = total_spent + ? WHERE user_id = ?''', 
                  (amount, user_id))
    
    conn.commit()
    conn.close()

def reject_order(order_id, admin_id):
    """Order reject karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''UPDATE orders SET status = 'rejected', 
                 admin_action_date = CURRENT_TIMESTAMP, admin_id = ? 
                 WHERE order_id = ?''', (admin_id, order_id))
    conn.commit()
    conn.close()

def get_pending_orders():
    """Pending orders return karta hai"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM orders WHERE status = 'waiting_approval' 
                 ORDER BY order_date''')
    orders = c.fetchall()
    conn.close()
    return orders

def get_order_by_user(user_id):
    """User ka last pending order"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM orders WHERE user_id = ? AND 
                 (status = 'pending' OR status = 'waiting_approval') 
                 ORDER BY order_date DESC LIMIT 1''', (user_id,))
    order = c.fetchone()
    conn.close()
    return order

def get_order_by_id(order_id):
    """Order details by order_id"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM orders WHERE order_id = ?''', (order_id,))
    order = c.fetchone()
    conn.close()
    return order

def get_user_orders(user_id, limit=10):
    """User ke orders"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM orders WHERE user_id = ? 
                 ORDER BY order_date DESC LIMIT ?''', (user_id, limit))
    orders = c.fetchall()
    conn.close()
    return orders

def get_stats():
    """Bot statistics"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    
    stats = {}
    c.execute('''SELECT COUNT(*) FROM products''')
    stats['total_products'] = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM products WHERE sold = 0''')
    stats['available_products'] = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM products WHERE sold = 1''')
    stats['sold_products'] = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM orders''')
    stats['total_orders'] = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM orders WHERE status = 'approved' ''')
    stats['approved_orders'] = c.fetchone()[0]
    
    c.execute('''SELECT COUNT(*) FROM orders WHERE status = 'waiting_approval' ''')
    stats['pending_orders'] = c.fetchone()[0]
    
    c.execute('''SELECT SUM(amount) FROM orders WHERE status = 'approved' ''')
    stats['total_revenue'] = c.fetchone()[0] or 0
    
    c.execute('''SELECT COUNT(*) FROM users''')
    stats['total_users'] = c.fetchone()[0]
    
    conn.close()
    return stats

def get_all_users():
    """All users list"""
    conn = sqlite3.connect('bot_database.db')
    c = conn.cursor()
    c.execute('''SELECT * FROM users ORDER BY join_date DESC''')
    users = c.fetchall()
    conn.close()
    return users