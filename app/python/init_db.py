"""
Database initialization script.
Run this script to create the database tables.
"""

from database import Database

if __name__ == "__main__":
    print("Initializing TradeIQ database...")
    db = Database()
    db.init_db()
    print("✓ Database initialized successfully!")
    print("✓ Tables created: channels, training_data, trade_signals, trade_executions")




