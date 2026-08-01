import sqlite3
import os

DB_FILE = 'banking.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Create accounts table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_number TEXT UNIQUE NOT NULL,
                holder_name TEXT NOT NULL,
                balance REAL NOT NULL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(account_id) REFERENCES accounts(id)
            )
        ''')
        
        conn.commit()
        print("✓ Database tables created successfully")
        return True
    except sqlite3.Error as e:
        print(f"✗ Error creating tables: {e}")
        return False
    finally:
        conn.close()

def initialize_database():
    if os.path.exists(DB_FILE):
        print(f"Database '{DB_FILE}' already exists")
    else:
        print(f"Creating new database '{DB_FILE}'...")
    
    create_tables()

if __name__ == "__main__":
    initialize_database()