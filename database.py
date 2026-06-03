import sqlite3
import datetime
import json



DATABASE_NAME = 'shop.db'


def init_db():
    """Create all required tables if they don't already exist."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Users table stores basic account information and wallet
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

    # Products table describes products available for purchase
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

    # Orders table records purchases.  ``delivery_details`` is stored
    # as JSON so that arbitrary credential structures can be saved.
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

    # Transactions table keeps a ledger of wallet changes
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

    # unsold_items holds stock items that have not yet been sold.
    # ``item_data`` stores JSON containing the credential fields.  ``is_sold``
    # flags whether the item has been delivered.
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

    # Withdrawals table stores user withdrawal requests.
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

    # Backwards‑compatible schema updates
    cursor.execute("PRAGMA table_info(unsold_items)")
    columns = [row[1] for row in cursor.fetchall()]
    if "item_data" not in columns:
        cursor.execute("ALTER TABLE unsold_items ADD COLUMN item_data TEXT")
    if "is_sold" not in columns:
        cursor.execute("ALTER TABLE unsold_items ADD COLUMN is_sold INTEGER DEFAULT 0")

    cursor.execute("PRAGMA table_info(products)")
    product_columns = [row[1] for row in cursor.fetchall()]
    if "emoji_id" not in product_columns:
        cursor.execute("ALTER TABLE products ADD COLUMN emoji_id TEXT")

    conn.commit()
    conn.close()


def get_user(user_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(user_id, username):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    joined_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO users (id, username, joined_date) VALUES (?, ?, ?)',
        (user_id, username, joined_date)
    )
    conn.commit()
    conn.close()


def update_user_wallet(user_id, amount):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE users SET wallet_balance = wallet_balance + ? WHERE id = ?',
        (amount, user_id)
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users ORDER BY joined_date DESC')
    users = cursor.fetchall()
    conn.close()
    return users


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


def update_product_stock(product_id, quantity_change):
    """Increment or decrement stock by ``quantity_change`` for a product."""
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
    transactions = cursor.fetchall()
    conn.close()
    return transactions


def add_unsold_item(product_id, item_data, password=None):
    """Add a new unsold item for a product.  ``item_data`` may be a dict
    of credential fields or a raw email string.  The JSON-encoded
    representation of the credentials is stored in ``item_data`` column
    while e.g. email and password are duplicated in their own columns
    for quick access."""
    if isinstance(item_data, dict):
        data_dict = item_data
        email_value = data_dict.get("email", "")
        password_value = data_dict.get("password", "")
    else:
        data_dict = {"email": item_data, "password": password or ""}
        email_value = item_data
        password_value = password or ""

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO unsold_items (product_id, email, password, item_data) VALUES (?, ?, ?, ?)',
        (product_id, email_value, password_value, json.dumps(data_dict))
    )
    conn.commit()
    conn.close()


def get_unsold_items(product_id, quantity):
    """Return up to ``quantity`` unsold items for the given product.  Each
    returned item is a dict with ``id`` and ``data`` fields.  The
    ``data`` field contains the decoded credential dictionary."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        '''
        SELECT id, email, password, item_data
        FROM unsold_items
        WHERE product_id = ? AND is_sold = 0
        ORDER BY id ASC
        LIMIT ?
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
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    for item_id in item_ids:
        cursor.execute(
            'UPDATE unsold_items SET is_sold = 1 WHERE product_id = ? AND id = ? AND is_sold = 0',
            (product_id, item_id)
        )
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
    """Return the number of items sold for the given product.  This counts
    unsold_items rows with ``is_sold = 1``."""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = ? AND is_sold = 1', (product_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def update_unsold_item_data(item_id, updates):
    """Update the credential fields for an unsold item.  ``updates`` should
    be a mapping of field names to new values (e.g. {'email': 'new',
    'password': 'secret'}).  The function updates the JSON
    ``item_data`` column as well as the top‑level email/password
    columns.

    Returns True if the item existed and was updated, otherwise
    False.
    """
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT item_data FROM unsold_items WHERE id = ?', (item_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False
    item_data_json = row[0] or '{}'
    try:
        data_dict = json.loads(item_data_json) if item_data_json else {}
    except Exception:
        data_dict = {}
    # Update fields
    for key, value in updates.items():
        data_dict[key] = value
    # Ensure email/password in separate columns reflect updated values
    email_value = data_dict.get('email', '')
    password_value = data_dict.get('password', '')
    cursor.execute(
        'UPDATE unsold_items SET email = ?, password = ?, item_data = ? WHERE id = ?',
        (email_value, password_value, json.dumps(data_dict), item_id)
    )
    conn.commit()
    conn.close()
    return True


def create_withdrawal_request(user_id, amount, address):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    request_date = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        'INSERT INTO withdrawals (user_id, amount, address, request_date) VALUES (?, ?, ?, ?)',
        (user_id, amount, address, request_date)
    )
    conn.commit()
    conn.close()


def get_withdrawal(withdrawal_id):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE id = ?', (withdrawal_id,))
    withdrawal = cursor.fetchone()
    conn.close()
    return withdrawal


def get_pending_withdrawals():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM withdrawals WHERE status = "Pending" ORDER BY request_date DESC')
    withdrawals = cursor.fetchall()
    conn.close()
    return withdrawals


def update_withdrawal_status(withdrawal_id, status):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('UPDATE withdrawals SET status = ? WHERE id = ?', (status, withdrawal_id))
    conn.commit()
    conn.close()


init_db()