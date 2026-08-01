from database.db_setup import initialize_database, DB_FILE
import os

if __name__ == "__main__":
    print("=" * 50)
    print("Premier Banking App - Database Initialization")
    print("=" * 50)

    # Remove old database if exists (for fresh start)
    if os.path.exists(DB_FILE):
        response = input(f"\n'{DB_FILE}' already exists. Replace it? (y/n): ")
        if response.lower() == 'y':
            os.remove(DB_FILE)
            print(f"Removed old database '{DB_FILE}'")
        else:
            print("Using existing database.")
    
    print(f"\nInitializing database '{DB_FILE}'...")
    initialize_database()
    print("\n✓ Database initialization complete!")
    print("=" * 50)
