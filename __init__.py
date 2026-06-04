"""
final_bot_final package

This package contains a fully self‑contained Telegram shop bot.  All
modules live at the top level of the package and use absolute imports
so that the code can be deployed without a package wrapper.  The
SQLite database is used for persistence (``shop.db`` by default) and
no external dependencies beyond ``python‑telegram‑bot`` are required.

Files included:

* ``config.py`` – reads API tokens and other configuration from the
  environment.
* ``database.py`` – SQLite helper functions to manage users,
  products, orders, transactions and inventory.
* ``admin.py`` – high level admin operations such as adding products
  and stock, editing metadata and marking freebies.
* ``utils.py`` – helper functions to build Telegram inline
  keyboards and manage button layouts.
* ``products.py`` – message formatting helpers for product details
  including custom emoji substitution.
* ``payment.py`` – Binance Pay integration helpers.
* ``bot.py`` – main entry point that wires the Telegram handlers
  together into a functioning bot.  Handles user flows, admin
  actions, freebies and broadcast messaging.

To run the bot locally:

```
python3 -m final_bot_final.bot
```

Ensure that the required environment variables (``TOKEN`` at a
minimum) are set before launching.
"""
