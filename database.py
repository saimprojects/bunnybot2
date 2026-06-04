import psycopg2
from psycopg2 import extras
import datetime
import json
import config

def get_connection():
    return psycopg2.connect(
        host=config.DB_HOST,
        database=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASS,
        port=config.DB_PORT
    )

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username TEXT,
            joined_date TIMESTAMP,
            wallet_balance REAL DEFAULT 0.0,
            total_orders INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_earnings REAL DEFAULT 0.0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
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
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id BIGINT,
            product_id INTEGER,
            quantity INTEGER,
            total_amount REAL,
            payment_method TEXT,
            status TEXT,
            order_date TIMESTAMP,
            delivery_details TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            type TEXT,
            amount REAL,
            transaction_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS unsold_items (
            id SERIAL PRIMARY KEY,
            product_id INTEGER,
            email TEXT,
            password TEXT,
            item_data TEXT,
            is_sold INTEGER DEFAULT 0,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT,
            amount REAL,
            address TEXT,
            status TEXT DEFAULT 'Pending',
            request_date TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Freebies configuration table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS freebies_config (
            id SERIAL PRIMARY KEY,
            channel_id BIGINT,
            channel_link TEXT,
            is_enabled BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Check if freebies_config has any data, if not insert default
    cursor.execute("SELECT COUNT(*) FROM freebies_config")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO freebies_config (is_enabled) VALUES (FALSE)")

    # Products marked as freebies
    cursor.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_freebie BOOLEAN DEFAULT FALSE")

    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username):
    conn = get_connection()
    cursor = conn.cursor()
    joined_date = datetime.datetime.now()
    cursor.execute(
        'INSERT INTO users (id, username, joined_date) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING',
        (user_id, username, joined_date)
    )
    conn.commit()
    conn.close()

def update_user_wallet(user_id, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s',
        (amount, user_id)
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
    users = cursor.fetchall()
    conn.close()
    return users

def add_product(name, duration, price, stock, rating, description, features, note, emoji_id, is_freebie=False):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        INSERT INTO products 
        (name, duration, price, stock, rating, description, features, note, emoji_id, is_freebie) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (name, duration, price, stock, rating, description, json.dumps(features), note, emoji_id, is_freebie)
    )
    conn.commit()
    conn.close()

def get_all_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products ORDER BY id DESC')
    products = cursor.fetchall()
    conn.close()
    return products

def get_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cursor.fetchone()
    conn.close()
    return product

def update_product_stock(product_id, amount):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = stock + %s WHERE id = %s', (amount, product_id))
    conn.commit()
    conn.close()

def set_product_stock(product_id, new_stock):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET stock = %s WHERE id = %s', (new_stock, product_id))
    conn.commit()
    conn.close()

def set_product_price(product_id, new_price):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET price = %s WHERE id = %s', (new_price, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM unsold_items WHERE product_id = %s', (product_id,))
    cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
    conn.commit()
    conn.close()

def create_order(order_id, user_id, product_id, quantity, total_amount, payment_method, status, delivery_details):
    conn = get_connection()
    cursor = conn.cursor()
    order_date = datetime.datetime.now()
    cursor.execute(
        '''
        INSERT INTO orders 
        (id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, delivery_details) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (order_id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, json.dumps(delivery_details))
    )
    conn.commit()
    conn.close()

def get_order_by_id(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order

def get_user_orders(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders WHERE user_id = %s ORDER BY order_date DESC', (user_id,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_all_orders(limit=20):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM orders ORDER BY order_date DESC LIMIT %s', (limit,))
    orders = cursor.fetchall()
    conn.close()
    return orders

def add_transaction(user_id, tx_type, amount):
    conn = get_connection()
    cursor = conn.cursor()
    transaction_date = datetime.datetime.now()
    cursor.execute(
        'INSERT INTO transactions (user_id, type, amount, transaction_date) VALUES (%s, %s, %s, %s)',
        (user_id, tx_type, amount, transaction_date)
    )
    conn.commit()
    conn.close()

def get_user_transactions(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM transactions WHERE user_id = %s ORDER BY transaction_date DESC', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def add_unsold_item(product_id, item_data, password=None):
    if isinstance(item_data, dict):
        data_dict = item_data
        email_value = data_dict.get("email", "")
        password_value = data_dict.get("password", "")
    else:
        data_dict = {"email": item_data, "password": password or ""}
        email_value = item_data
        password_value = password or ""
        
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO unsold_items (product_id, email, password, item_data) VALUES (%s, %s, %s, %s)',
        (product_id, email_value, password_value, json.dumps(data_dict))
    )
    conn.commit()
    conn.close()

def get_unsold_items(product_id, quantity):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT id, email, password, item_data 
        FROM unsold_items 
        WHERE product_id = %s AND is_sold = 0 
        ORDER BY id ASC 
        LIMIT %s
        ''',
        (product_id, quantity)
    )
    rows = cursor.fetchall()
    conn.close()
    
    items = []
    for row in rows:
        item_id, email, password, item_data = row
        if item_data:
            try:
                data = json.loads(item_data)
            except Exception:
                data = {"email": email, "password": password}
        else:
            data = {"email": email, "password": password}
        
        items.append({"id": item_id, "data": data})
        
    return items

def mark_items_as_sold(product_id, item_ids):
    conn = get_connection()
    cursor = conn.cursor()
    for item_id in item_ids:
        cursor.execute(
            'UPDATE unsold_items SET is_sold = 1 WHERE product_id = %s AND id = %s AND is_sold = 0',
            (product_id, item_id)
        )
    conn.commit()
    conn.close()

def get_unsold_count(product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = %s AND is_sold = 0', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def create_withdrawal_request(user_id, amount, address):
    conn = get_connection()
    cursor = conn.cursor()
    request_date = datetime.datetime.now()
    cursor.execute(
        'INSERT INTO withdrawals (user_id, amount, address, request_date) VALUES (%s, %s, %s, %s)',
        (user_id, amount, address, request_date)
    )
    conn.commit()
    conn.close()

def get_withdrawal(withdrawal_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE id = %s', (withdrawal_id,))
    withdrawal = cursor.fetchone()
    conn.close()
    return withdrawal

def get_pending_withdrawals():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE status = \'Pending\' ORDER BY request_date DESC')
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals

def update_withdrawal_status(withdrawal_id, status):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE withdrawals SET status = %s WHERE id = %s', (status, withdrawal_id))
    conn.commit()
    conn.close()

# Freebies functions
def get_freebies_config():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM freebies_config LIMIT 1')
    config_data = cursor.fetchone()
    conn.close()
    return config_data

def update_freebies_config(channel_id, channel_link, is_enabled):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE freebies_config SET channel_id = %s, channel_link = %s, is_enabled = %s WHERE id = 1',
        (channel_id, channel_link, is_enabled)
    )
    conn.commit()
    conn.close()

def get_freebie_products():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM products WHERE is_freebie = TRUE ORDER BY id DESC')
    products = cursor.fetchall()
    conn.close()
    return products

def toggle_product_freebie(product_id, is_freebie):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE products SET is_freebie = %s WHERE id = %s', (is_freebie, product_id))
    conn.commit()
    conn.close()

def has_user_received_freebie(user_id, product_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT COUNT(*) FROM orders WHERE user_id = %s AND product_id = %s AND payment_method = \'Freebie\'',
        (user_id, product_id)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0
