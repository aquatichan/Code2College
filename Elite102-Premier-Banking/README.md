# 🦁 Premier Banking - 2026 Code2College Elite102 Banking App Project 🦁

A fully functional, text-based CLI banking application built with Python 3.12.1 and SQLite. Supports account management, deposits, withdrawals, transfers, and transaction history tracking.
<img width="716" height="487" alt="Screen Shot 2026-04-23 at 5 35 05 PM" src="https://github.com/user-attachments/assets/d4b13e63-6ffe-4baf-83e9-ecc589a52053" />


## Project Structure

```
Elite102-Premier-Banking/
├── main.py                 # Interactive menu-driven application
├── initialize_db.py        # Database initialization script
├── banking_operations.py   # Core business logic
├── demo.py                 # Automated demonstration
├── tests.py                # Comprehensive test suite (25 tests)
├── requirements.txt        # Project dependencies
│
├── database/
│   ├── __init__.py
│   └── db_setup.py         # Database schema and connections
│
├── models/
│   ├── __init__.py
│   ├── account.py          # Account model and operations
│   └── transaction.py      # Transaction model and operations
│
└── README.md               # You're reading it!
```

### Core Banking Features
- **Create Accounts**: Opens a new bank account with holder name and initial deposit
- **Deposit Money**: Add funds to any account
- **Withdraw Money**: Withdraw funds from any account
- **Check Balance**: View current account balance
- **List Accounts**: View all accounts in the system
- **Delete Accounts**: Delete obselete accounts
- **Transaction History**: View detailed history of all transactions for an account
- **Transfer Funds**: Send money between two accounts (extension feature)

### Database Features
- SQLite database with two main tables: `accounts` and `transactions`
- Automatic transaction logging with ISO 8601 formatted timestamps
- Foreign key relationships for data integrity
- Persistent data storage

### Application Features
- Terminal-based menu interface
- Input validation for all operations
- Error handling with user-friendly messages
- Formatted CLI output with clear visual separators

## Database Schema

### Accounts Table
```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number TEXT UNIQUE NOT NULL,
    holder_name TEXT NOT NULL,
    balance REAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Transactions Table
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    transaction_type TEXT NOT NULL,
    amount REAL NOT NULL,
    balance_after REAL NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(account_id) REFERENCES accounts(id)
);
```

## Testing

This application includes 25 comprehensive unit tests that ensure full functional coverage:

```bash
Test Categories:
- Account Creation (3 tests)
- Deposits (3 tests)
- Withdrawals (4 tests)
- Balance Checks (2 tests)
- Transfers (4 tests)
- Account Listing (2 tests)
- Transaction History (3 tests)
- Delete Accounts (4 tests)

Result: All 25/25 tests passed ✓
```

## Error Handling

This application validates all inputs:
- ✓ Prevents negative amounts
- ✓ Prevents zero amounts for deposits/withdrawals
- ✓ Validates account existence
- ✓ Checks sufficient balance before withdrawal/transfer
- ✓ Validates account holder name is not empty
- ✓ Prevents duplicate account numbers

## Weekly Milestone Tracker

| Week | Goal | Status |
|------|------|--------|
| Week 1 | Environment setup + welcome menu | Complete ✓ |
| Week 2 | Database tables + core functions | Complete ✓ |
| Week 3 | Full menu UI + tests | Complete ✓ |
| Week 4 | Fully functional demo-ready app | Complete ✓ |

## Extension Ideas

Optional features that could be added:
- Wire transfers between accounts (already implemented ✓)
- Transaction history log with timestamps (already implemented ✓)
- Advanced UI with colors and formatted tables (already implemented ✓)
- Interest calculation
- Overdraft protection
- Account suspension/freeze
- Password/PIN authentication
- Admin account management
- Interest compounding
- Recurring transfers
- Budget tracking

## Learning Outcomes

This project demonstrates:
- **Database Design**: SQLite schema with relationships
- **Python Programming**: OOP, command-line I/O, error handling
- **Unit Testing**: Test isolation, setup/teardown, comprehensive coverage
- **Data Persistence**: CRUD operations, transaction management

## Start Steps

### 1. Initialize Blank Database

```bash
python3 initialize_db.py
```

### 2. Run Main App

```bash
python3 main.py
```

### 3. Run Demo

```bash
python3 demo.py
```

### 4. Run Tests

```bash
python3 tests.py
```
