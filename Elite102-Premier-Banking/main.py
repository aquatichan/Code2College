import sqlite3
from banking_operations import BankingOperations
from database.db_setup import DB_FILE, create_tables

# ANSI color codes for formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def print_separator():
    print(BLUE + "-" * 100 + RESET)

def print_header(title):
    print("\n" + BLUE + "=" * 100 + RESET)
    print(BOLD + CYAN + f"  {title}".center(100) + RESET)
    print(BLUE + "=" * 100 + RESET)

def print_success(message):
    print(GREEN + f"✓ {message}" + RESET)

def print_error(message):
    print(RED + f"✗ {message}" + RESET)

def main_menu():
    print_header("PREMIER BANKING APPLICATION")
    print(CYAN + """
    1. Create New Account
    2. Deposit Money
    3. Withdraw Money
    4. Check Account Balance
    5. List All Accounts
    6. Transaction History
    7. Transfer Between Accounts
    8. Delete Account
    9. Exit
    """ + RESET)
    return input(YELLOW + "Select an option (1-9): " + RESET).strip()

def create_account_menu():
    print_header("Create New Account")

    name = input("Enter account holder name: ").strip()
    if not name:
        print_error("Name cannot be empty")
        return
    try:
        initial_deposit = float(input("Enter initial deposit amount: $"))
        if initial_deposit < 0:
            print_error("Amount cannot be negative")
            return
    except ValueError:
        print_error("Invalid amount. Please enter a number.")
        return
    
    result = BankingOperations.create_account(name, initial_deposit)
    
    if result['success']:
        print_separator()
        print_success("Account created successfully!")
        print(f"Account Number: {CYAN}{result['account_number']}{RESET}")
        print(f"Account Holder: {result['holder_name']}")
        print(f"Initial Balance: {GREEN}${result['balance']:.2f}{RESET}")
        print_separator()
    else:
        print_error(result['error'])

def deposit_menu():
    print_header("Deposit Money")
    
    account_number = input("Enter account number: ").strip()
    
    try:
        amount = float(input("Enter deposit amount: $"))
        if amount <= 0:
            print_error("Amount must be positive")
            return
    except ValueError:
        print_error("Invalid amount. Please enter a number.")
        return
    
    result = BankingOperations.deposit(account_number, amount)
    
    if result['success']:
        print_separator()
        print_success(result['message'])
        print(f"New Balance: {GREEN}${result['new_balance']:.2f}{RESET}")
        print_separator()
    else:
        print_error(result['error'])

def withdraw_menu():
    print_header("Withdraw Money")
    
    account_number = input("Enter account number: ").strip()
    
    try:
        amount = float(input("Enter withdrawal amount: $"))
        if amount <= 0:
            print_error("Amount must be positive")
            return
    except ValueError:
        print_error("Invalid amount. Please enter a number.")
        return
    
    result = BankingOperations.withdraw(account_number, amount)
    
    if result['success']:
        print_separator()
        print_success(result['message'])
        print(f"New Balance: {GREEN}${result['new_balance']:.2f}{RESET}")
        print_separator()
    else:
        print_error(result['error'])

def check_balance_menu():
    print_header("Check Account Balance")
    
    account_number = input("Enter account number: ").strip()
    
    result = BankingOperations.check_balance(account_number)
    
    if result['success']:
        print_separator()
        print(f"Account Number: {CYAN}{result['account_number']}{RESET}")
        print(f"Account Holder: {result['holder_name']}")
        print(f"Current Balance: {GREEN}${result['balance']:.2f}{RESET}")
        print_separator()
    else:
        print_error(result['error'])

def list_accounts_menu():
    print_header("List All Accounts")
    
    result = BankingOperations.list_accounts()
    
    if result['success']:
        accounts = result['accounts']
        
        if not accounts:
            print(YELLOW + "No accounts found." + RESET)
            return
        
        print_separator()
        print(BOLD + f"{'Account #':<20} {'Holder Name':<50} {'Balance':<28}" + RESET) # 20 + 1 + 50 + 1 + 28 = 100
        print_separator()
        
        for acc in accounts:
            bal = "$" + f"{acc['balance']:.2f}"
            print(f"{acc['account_number']:<20} {acc['holder_name']:<50} {GREEN}{bal:<28}{RESET}")
        
        print_separator()
    else:
        print_error(result['error'])

def transaction_history_menu():
    print_header("Account Transaction History")
    
    account_number = input("Enter account number: ").strip()
    
    result = BankingOperations.get_transaction_history(account_number)
    
    if result['success']:
        transactions = result['transactions']
        
        if not transactions:
            print(YELLOW + "No transactions found for this account." + RESET)
            return
        
        print_separator()
        print(BOLD + f"{'Type':<20} {'Amount':<20} {'New Balance':<20} {'Timestamp':<37}" + RESET) # 20 + 1 + 20 + 1 + 20 + 1 + 37 = 100
        print_separator()
        
        for tx in transactions:
            amt = "$" + f"{tx['amount']:.2f}"
            bal = "$" + f"{tx['balance_after']:.2f}"
            print(f"{tx['transaction_type']:<20} {GREEN}{amt:<20}{RESET} {GREEN}{bal:<20}{RESET} {tx['timestamp']:<37}")
        
        print_separator()
    else:
        print_error(result['error'])

def transfer_menu():
    print_header("Transfer Between Accounts")
    
    from_account = input("Enter source account number: ").strip()
    to_account = input("Enter destination account number: ").strip()
    
    try:
        amount = float(input("Enter transfer amount: $"))
        if amount <= 0:
            print_error("Amount must be positive")
            return
    except ValueError:
        print_error("Invalid amount. Please enter a number.")
        return
    
    result = BankingOperations.transfer_between_accounts(from_account, to_account, amount)
    
    if result['success']:
        print_separator()
        print_success(result['message'])
        print_separator()
    else:
        print_error(result['error'])

def delete_account_menu():
    print_header("Delete Account")
    
    account_number = input("Enter account number to delete: ").strip()
    
    result = BankingOperations.check_balance(account_number)
    if not result['success']:
        print_error(result['error'])
        return
    
    print_separator()
    print(f"Account Number: {CYAN}{result['account_number']}{RESET}")
    print(f"Account Holder: {result['holder_name']}")
    print(f"Current Balance: {GREEN}${result['balance']:.2f}{RESET}")
    print_separator()
    
    if result['balance'] != 0:
        print_error(f"Cannot delete account with balance ${result['balance']:.2f}")
        print(YELLOW + "Please withdraw or transfer all funds before deletion." + RESET)
        return
    
    confirm = input("Are you sure you want to delete this account? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print(YELLOW + "Deletion cancelled." + RESET)
        return
    
    result = BankingOperations.delete_account(account_number)
    
    if result['success']:
        print_separator()
        print_success(result['message'])
        print_separator()
    else:
        print_error(result['error'])

def run_app():
    try:
        create_tables()
    except Exception:
        pass

    print_header('''
                 
   \|\||
  -' ||||/
 /$   |||||/
/    |||||||/`-.____________
\-' |||||||||    PREMIER    `-._
 -|||||||||||    BANKING    |` -`.
   ||||||               \   |   `\\
    |||||\  \______...---\_  \    \\
       |  \  \           | \  |    ``-.__--.
       |  |\  \         / / | |       ``---'
     _/  /_/  /      __/ / _| |
    (,__/(,__/      (,__/ (,__/

    ''') # Adapted from https://asciiart.cc/view/12679
    
    while True:
        try:
            choice = main_menu()
            
            if choice == '1':
                create_account_menu()
            elif choice == '2':
                deposit_menu()
            elif choice == '3':
                withdraw_menu()
            elif choice == '4':
                check_balance_menu()
            elif choice == '5':
                list_accounts_menu()
            elif choice == '6':
                transaction_history_menu()
            elif choice == '7':
                transfer_menu()
            elif choice == '8':
                delete_account_menu()
            elif choice == '9':
                print_header("Thank you for using Premier Banking!")
                print(GREEN + "Goodbye!" + RESET + "\n")
                break
            else:
                print_error("Invalid option. Please choose a number from 1-9.")
        
        except KeyboardInterrupt:
            print("\n\n" + YELLOW + "Application interrupted. Goodbye!" + RESET)
            break
        except Exception as e:
            print_error(f"An unexpected error occurred: {str(e)}")

if __name__ == "__main__":
    run_app()