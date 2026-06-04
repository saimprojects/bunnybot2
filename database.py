"""
SQLite‑backed database helper for the Telegram shop bot.

The functions defined here provide basic CRUD operations for
users, products, orders, transactions and stock items.  The schema
is created on first import via ``init_db``.  Products can be
optionally marked as free and associated with a channel.  Each
operation opens its own connection to ensure that locks are short
lived and the database file can remain portable.
"""

import sqlite3
import datetime
import json
import os
import config

# Name of the SQLite database file.  Use the environment variable
# ``SHOP_DB_PATH`` to override the default location.  A relative
# filename will create the database in the working directory.
DATABASE_NAME = config.SHOP_DB_PATH


def init_db():
    """Create all tables if they do not exist.

    This function is idempotent and can be called repeatedly.  It
    ensures that the database schema is up to date, adding columns
    such as ``emoji_id``, ``is_free`` and ``free_channel`` if
    necessary.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Create users
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            joined_date TEXT,
            wallet_balance REAL DEFAULT 0.0,
            total_orders INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0.0
        )
        '''
    )

    # Products table
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            duration TEXT,
            price REAL,
            stock INTEGER,
            rating REAL,
            description TEXT,
            features TEXT,
            note TEXT,
            emoji_id TEXT
        )
        '''
    )

    # Orders table: store delivery_details as JSON string
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            total_amount REAL,
            payment_method TEXT,
            status TEXT,
            order_date TEXT,
            delivery_details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        '''
    )

    # Transactions table
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            type TEXT,
            amount REAL,
            transaction_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        '''
    )

    # Inventory (unsold items)
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS unsold_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            email TEXT,
            password TEXT,
            item_data TEXT,
            is_sold INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
        '''
    )

    # Withdrawals table
    cursor.execute(
        '''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            address TEXT,
            status TEXT DEFAULT 'Pending',
            request_date TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        '''
    )

    # Schema migrations: check for missing columns
    cursor.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cursor.fetchall()]
    if "emoji_id" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN emoji_id TEXT")
    if "is_free" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN is_free INTEGER DEFAULT 0")
    if "free_channel" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN free_channel TEXT")

    conn.commit()
    conn.close()


def create_user(user_id, username):
    """Create a user record if it does not exist."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    joined_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT OR IGNORE INTO users (id, username, joined_date) VALUES (?, ?, ?)',
        (user_id, username, joined_date)
    )
    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def get_all_users():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
    users = cursor.fetchall()
    conn.close()
    return users


def update_user_wallet(user_id, amount):
    """Adjust a user's wallet balance by ``amount``."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET wallet_balance = wallet_balance + ? WHERE id = ?',
        (amount, user_id)
    )
    conn.commit()
    conn.close()


def increment_user_referrals(user_id, count=1):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET referrals = referrals + ? WHERE id = ?',
        (count, user_id)
    )
    conn.commit()
    conn.close()


def increment_user_orders(user_id, count=1):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET total_orders = total_orders + ? WHERE id = ?',
        (count, user_id)
    )
    conn.commit()
    conn.close()


def add_product(name, duration, price, stock, rating, description, features, note, emoji_id=""):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO products
        (name, duration, price, stock, rating, description, features, note, emoji_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (
            name,
            duration,
            price,
            stock,
            rating,
            description,
            json.dumps(features),
            note,
            str(emoji_id) if emoji_id else ""
        )
    )
    conn.commit()
    conn.close()


def get_product(product_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product


def get_all_products():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products ORDER BY id DESC')
    products = cursor.fetchall()
    conn.close()
    return products


def update_product_stock(product_id, quantity_change):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE products SET stock = stock + ? WHERE id = ?',
        (quantity_change, product_id)
    )
    conn.commit()
    conn.close()


def set_product_stock(product_id, new_stock):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = ? WHERE id = ?', (new_stock, product_id))
    conn.commit()
    conn.close()


def set_product_price(product_id, new_price):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET price = ? WHERE id = ?', (new_price, product_id))
    conn.commit()
    conn.close()


def update_product_field(product_id, field_name, new_value):
    allowed = {"name", "duration", "description", "note", "emoji_id"}
    if field_name not in allowed:
        raise ValueError(f"Invalid field '{field_name}'. Allowed: {', '.join(sorted(allowed))}.")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    query = f'UPDATE products SET {field_name} = ? WHERE id = ?'
    cursor.execute(query, (new_value, product_id))
    conn.commit()
    conn.close()


def delete_product(product_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM unsold_items WHERE product_id = ?', (product_id,))
    cursor.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()


def create_order(order_id, user_id, product_id, quantity, total_amount, payment_method, status, delivery_details):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    order_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        '''
        INSERT INTO orders
        (id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, delivery_details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''',
        (order_id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, json.dumps(delivery_details))
    )
    conn.commit()
    conn.close()


def get_order_by_id(order_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = ?', (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order


def get_user_orders(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY order_date DESC', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def get_all_orders(limit=20):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders ORDER BY order_date DESC LIMIT ?', (limit,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def get_all_orders_admin(limit=50):
    """Return up to ``limit`` orders for admin review."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders ORDER BY order_date DESC LIMIT ?', (limit,))
    orders = cursor.fetchall()
    conn.close()
    return orders


def add_transaction(user_id, tx_type, amount):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    transaction_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO transactions (user_id, type, amount, transaction_date) VALUES (?, ?, ?, ?)',
        (user_id, tx_type, amount, transaction_date)
    )
    conn.commit()
    conn.close()


def get_user_transactions(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM transactions WHERE user_id = ? ORDER BY transaction_date DESC', (user_id,))
    txs = cursor.fetchall()
    conn.close()
    return txs


def add_unsold_item(product_id, item_data, password=None):
    """Add a new unsold item for a product.  ``item_data`` may be a dict or a string."""
    if not item_data:
        raise ValueError("Empty item_data")
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    if isinstance(item_data, dict):
        email = item_data.get('email')
        pwd = item_data.get('password', password)
        cursor.execute(
            'INSERT INTO unsold_items (product_id, email, password, item_data) VALUES (?, ?, ?, ?)',
            (product_id, email, pwd, json.dumps(item_data))
        )
    else:
        # treat as plain credential (email:password or token)
        cursor.execute(
            'INSERT INTO unsold_items (product_id, item_data) VALUES (?, ?)',
            (product_id, str(item_data))
        )
    conn.commit()
    conn.close()


def get_unsold_items(product_id, limit=1):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM unsold_items WHERE product_id = ? AND is_sold = 0 LIMIT ?',
        (product_id, limit)
    )
    items = cursor.fetchall()
    conn.close()
    return items


def mark_item_sold(item_id, user_id=None):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE unsold_items SET is_sold = 1 WHERE id = ?', (item_id,))
    conn.commit()
    conn.close()


def get_unsold_count(product_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = ? AND is_sold = 0', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_sold_count(product_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = ? AND is_sold = 1', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def update_unsold_item_data(item_id, updates: dict):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT item_data FROM unsold_items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    item_json = row[0]
    data = {}
    try:
        data = json.loads(item_json) if item_json else {}
    except Exception:
        data = {}
    # merge updates
    data.update(updates)
    email = data.get('email')
    password = data.get('password')
    cursor.execute(
        'UPDATE unsold_items SET item_data = ?, email = ?, password = ? WHERE id = ?',
        (json.dumps(data), email, password, item_id)
    )
    conn.commit()
    conn.close()
    return True


def create_withdrawal_request(user_id, amount, address):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    req_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO withdrawals (user_id, amount, address, request_date) VALUES (?, ?, ?, ?)',
        (user_id, amount, address, req_date)
    )
    conn.commit()
    conn.close()


def get_pending_withdrawals():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE status = "Pending"')
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals


def get_withdrawal(withdrawal_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE id = ?', (withdrawal_id,))
    w = cursor.fetchone()
    conn.close()
    return w


def update_withdrawal_status(withdrawal_id, new_status):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (new_status, withdrawal_id))
    conn.commit()
    conn.close()


def set_product_free(product_id, channel: str):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET is_free = 1, free_channel = ? WHERE id = ?', (channel, product_id))
    conn.commit()
    conn.close()


def unset_product_free(product_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET is_free = 0, free_channel = NULL WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()
