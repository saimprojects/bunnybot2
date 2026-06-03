"""
PostgreSQL-backed database helper module for the Telegram bot.

This module replaces the earlier SQLite implementation.  All state is
stored in a PostgreSQL database defined by the ``DATABASE_URL``
environment variable.  Connections are created on demand via
``get_connection()``.  Each function is responsible for opening a
connection, executing its query with parameterised placeholders, and
closing the connection.  Table creation occurs in ``init_db()`` the
first time the module is imported.

JSON data (e.g. credential dictionaries) are stored as plain text
using ``json.dumps()`` and parsed with ``json.loads()``.  If you
prefer to store JSON using the native PostgreSQL ``JSONB`` type you
may modify the DDL accordingly, but text storage keeps dependencies
minimal.

To use this module with your bot:

  1. Ensure ``psycopg2`` (or ``psycopg2-binary``) is installed in
     your environment.
  2. Set the ``DATABASE_URL`` environment variable to a valid
     PostgreSQL connection string, for example:
        ``postgresql://user:password@hostname:5432/dbname``
  3. Deploy a PostgreSQL instance on your hosting provider and
     configure backups to avoid data loss.

The schema is largely compatible with the previous SQLite version but
uses ``SERIAL`` columns for auto-incrementing keys and ``TIMESTAMP``
types for dates.  If you already have a populated SQLite database and
wish to migrate it to PostgreSQL you will need to export your data
manually (e.g. using ``sqlite3`` and ``COPY`` into Postgres).
"""

import os
import json
import datetime
import psycopg2
import psycopg2.extras

# Connection URL for PostgreSQL.  A sensible default is provided for
# development but MUST be overridden in production.  The URL format
# should follow ``postgresql://user:password@host:port/database``.
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/shopdb")


def get_connection():
    """Return a new database connection.

    ``psycopg2`` will parse the connection URL provided via
    ``DATABASE_URL``.  Caller is responsible for closing the
    connection.
    """
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    """Create all required tables if they don't already exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Users table stores basic account information and wallet
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGINT PRIMARY KEY,
            username TEXT,
            joined_date TIMESTAMP,
            wallet_balance NUMERIC DEFAULT 0,
            total_orders INTEGER DEFAULT 0,
            referrals INTEGER DEFAULT 0,
            referral_earnings NUMERIC DEFAULT 0
        )
        """
    )

    # Products table describes products available for purchase
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name TEXT,
            duration TEXT,
            price NUMERIC,
            stock INTEGER,
            rating NUMERIC,
            description TEXT,
            features TEXT,
            note TEXT,
            emoji_id TEXT
        )
        """
    )

    # Orders table records purchases.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            product_id INTEGER REFERENCES products(id),
            quantity INTEGER,
            total_amount NUMERIC,
            payment_method TEXT,
            status TEXT,
            order_date TIMESTAMP,
            delivery_details TEXT
        )
        """
    )

    # Transactions table keeps a ledger of wallet changes
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            type TEXT,
            amount NUMERIC,
            transaction_date TIMESTAMP
        )
        """
    )

    # unsold_items holds stock items that have not yet been sold.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS unsold_items (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            email TEXT,
            password TEXT,
            item_data TEXT,
            is_sold BOOLEAN DEFAULT FALSE
        )
        """
    )

    # Withdrawals table stores user withdrawal requests.
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id BIGINT REFERENCES users(id),
            amount NUMERIC,
            address TEXT,
            status TEXT DEFAULT 'Pending',
            request_date TIMESTAMP
        )
        """
    )

    # Add optional columns for freebies.  If they already exist,
    # PostgreSQL will ignore the IF NOT EXISTS clause.  ``is_free``
    # indicates that a product is available for free and
    # ``free_channel`` stores the channel username (without '@') that
    # the user must join to claim it.  You can modify ``free_channel``
    # to store a channel ID instead if preferred.
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS is_free BOOLEAN DEFAULT FALSE")
    cur.execute("ALTER TABLE products ADD COLUMN IF NOT EXISTS free_channel TEXT")

    conn.commit()
    cur.close()
    conn.close()


def get_user(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user


def create_user(user_id, username):
    conn = get_connection()
    cur = conn.cursor()
    joined_date = datetime.datetime.now()
    cur.execute(
        'INSERT INTO users (id, username, joined_date) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING',
        (user_id, username, joined_date)
    )
    conn.commit()
    cur.close()
    conn.close()


def update_user_wallet(user_id, amount):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE users SET wallet_balance = wallet_balance + %s WHERE id = %s', (amount, user_id))
    conn.commit()
    cur.close()
    conn.close()


def get_all_users():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users ORDER BY joined_date DESC')
    users = cur.fetchall()
    cur.close()
    conn.close()
    return users


def get_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    return product


def get_all_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM products ORDER BY id DESC')
    products = cur.fetchall()
    cur.close()
    conn.close()
    return products


def add_product(name, duration, price, stock, rating, description, features, note, emoji_id=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        INSERT INTO products
        (name, duration, price, stock, rating, description, features, note, emoji_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
    cur.close()
    conn.close()


def update_product_stock(product_id, quantity_change):
    """Increment or decrement stock by ``quantity_change`` for a product."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE products SET stock = stock + %s WHERE id = %s', (quantity_change, product_id))
    conn.commit()
    cur.close()
    conn.close()


def set_product_stock(product_id, new_stock):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE products SET stock = %s WHERE id = %s', (new_stock, product_id))
    conn.commit()
    cur.close()
    conn.close()


def set_product_price(product_id, new_price):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE products SET price = %s WHERE id = %s', (new_price, product_id))
    conn.commit()
    cur.close()
    conn.close()


def delete_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM unsold_items WHERE product_id = %s', (product_id,))
    cur.execute('DELETE FROM products WHERE id = %s', (product_id,))
    conn.commit()
    cur.close()
    conn.close()


def create_order(order_id, user_id, product_id, quantity, total_amount, payment_method, status, delivery_details):
    conn = get_connection()
    cur = conn.cursor()
    order_date = datetime.datetime.now()
    cur.execute(
        '''
        INSERT INTO orders
        (id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, delivery_details)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''',
        (order_id, user_id, product_id, quantity, total_amount, payment_method, status, order_date, json.dumps(delivery_details))
    )
    conn.commit()
    cur.close()
    conn.close()


def get_order_by_id(order_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM orders WHERE id = %s', (order_id,))
    order = cur.fetchone()
    cur.close()
    conn.close()
    return order


def get_user_orders(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM orders WHERE user_id = %s ORDER BY order_date DESC', (user_id,))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return orders


def get_all_orders(limit=20):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM orders ORDER BY order_date DESC LIMIT %s', (limit,))
    orders = cur.fetchall()
    cur.close()
    conn.close()
    return orders


def add_transaction(user_id, tx_type, amount):
    conn = get_connection()
    cur = conn.cursor()
    transaction_date = datetime.datetime.now()
    cur.execute(
        'INSERT INTO transactions (user_id, type, amount, transaction_date) VALUES (%s, %s, %s, %s)',
        (user_id, tx_type, amount, transaction_date)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_user_transactions(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM transactions WHERE user_id = %s ORDER BY transaction_date DESC', (user_id,))
    transactions = cur.fetchall()
    cur.close()
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        'INSERT INTO unsold_items (product_id, email, password, item_data) VALUES (%s, %s, %s, %s)',
        (product_id, email_value, password_value, json.dumps(data_dict))
    )
    conn.commit()
    cur.close()
    conn.close()


def get_unsold_items(product_id, quantity):
    """Return up to ``quantity`` unsold items for the given product.  Each
    returned item is a dict with ``id`` and ``data`` fields.  The
    ``data`` field contains the decoded credential dictionary."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        '''
        SELECT id, email, password, item_data
        FROM unsold_items
        WHERE product_id = %s AND is_sold = FALSE
        ORDER BY id ASC
        LIMIT %s
        ''',
        (product_id, quantity)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    items = []
    for row in rows:
        item_id = row["id"]
        email = row.get("email")
        password = row.get("password")
        item_data_json = row.get("item_data")
        if item_data_json:
            try:
                data = json.loads(item_data_json)
            except Exception:
                data = {"email": email, "password": password}
        else:
            data = {"email": email, "password": password}
        items.append({"id": item_id, "data": data})
    return items


def mark_items_as_sold(product_id, item_ids):
    conn = get_connection()
    cur = conn.cursor()
    for item_id in item_ids:
        cur.execute(
            'UPDATE unsold_items SET is_sold = TRUE WHERE product_id = %s AND id = %s AND is_sold = FALSE',
            (product_id, item_id)
        )
    conn.commit()
    cur.close()
    conn.close()


def get_unsold_count(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = %s AND is_sold = FALSE', (product_id,))
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count


def get_sold_count(product_id):
    """Return the number of items sold for the given product.  This counts
    unsold_items rows with ``is_sold = TRUE``."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM unsold_items WHERE product_id = %s AND is_sold = TRUE', (product_id,))
    count = cur.fetchone()[0]
    cur.close()
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT item_data FROM unsold_items WHERE id = %s', (item_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
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
    email_value = data_dict.get('email', '')
    password_value = data_dict.get('password', '')
    cur.execute(
        'UPDATE unsold_items SET email = %s, password = %s, item_data = %s WHERE id = %s',
        (email_value, password_value, json.dumps(data_dict), item_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def create_withdrawal_request(user_id, amount, address):
    conn = get_connection()
    cur = conn.cursor()
    request_date = datetime.datetime.now()
    cur.execute(
        'INSERT INTO withdrawals (user_id, amount, address, request_date) VALUES (%s, %s, %s, %s)',
        (user_id, amount, address, request_date)
    )
    conn.commit()
    cur.close()
    conn.close()


def get_withdrawal(withdrawal_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM withdrawals WHERE id = %s', (withdrawal_id,))
    withdrawal = cur.fetchone()
    cur.close()
    conn.close()
    return withdrawal


def get_pending_withdrawals():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM withdrawals WHERE status = 'Pending' ORDER BY request_date DESC")
    withdrawals = cur.fetchall()
    cur.close()
    conn.close()
    return withdrawals


def update_withdrawal_status(withdrawal_id, status):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('UPDATE withdrawals SET status = %s WHERE id = %s', (status, withdrawal_id))
    conn.commit()
    cur.close()
    conn.close()


def set_product_free(product_id, channel_username):
    """Mark a product as free and associate it with the given channel.

    ``channel_username`` should be provided without the leading '@'.  This
    function sets ``is_free`` to TRUE and stores the channel for later
    membership verification.  Returns True if updated, False if the
    product does not exist.
    """
    conn = get_connection()
    cur = conn.cursor()
    # Ensure the product exists
    cur.execute('SELECT id FROM products WHERE id = %s', (product_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return False
    cur.execute(
        'UPDATE products SET is_free = TRUE, free_channel = %s WHERE id = %s',
        (channel_username, product_id)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def unset_product_free(product_id):
    """Remove the free status from a product.

    Sets ``is_free`` to FALSE and clears the ``free_channel``.  Returns
    True if the product existed.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute('SELECT id FROM products WHERE id = %s', (product_id,))
    if not cur.fetchone():
        cur.close()
        conn.close()
        return False
    cur.execute(
        'UPDATE products SET is_free = FALSE, free_channel = NULL WHERE id = %s',
        (product_id,)
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


# Initialise the database when the module is imported.
try:
    init_db()
except Exception:
    # Avoid crashing the bot on module import if the database is
    # temporarily unavailable.  Connection errors will surface when
    # functions are called and should be logged at that point.  You
    # may choose to log here if you have a logger available.
    pass