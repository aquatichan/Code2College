import unittest
import os
import sys
import sqlite3

TEST_DB_FILE = 'test_banking.db'

import database.db_setup
database.db_setup.DB_FILE = TEST_DB_FILE

from models.account import Account
from models.transaction import Transaction
from banking_operations import BankingOperations

# ANSI color codes for formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

class TestBankingApp(unittest.TestCase):
    
    def setUp(self):
        # Remove old test database if it exists
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
        
        # Create new test database
        database.db_setup.DB_FILE = TEST_DB_FILE
        from database.db_setup import create_tables
        create_tables()
    
    def tearDown(self):
        # Remove test database
        if os.path.exists(TEST_DB_FILE):
            os.remove(TEST_DB_FILE)
    
    # Account Creation Tests
    def test_create_account_success(self):
        result = BankingOperations.create_account("John Doe", 1000)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['holder_name'], "John Doe")
        self.assertEqual(result['balance'], 1000)
        self.assertIn('account_number', result)
        self.assertIn('account_id', result)
    
    def test_create_account_negative_balance(self):
        result = BankingOperations.create_account("Jailbroken", -500)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_create_account_empty_name(self):
        result = BankingOperations.create_account("", 1000)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    # Deposit Tests
    def test_deposit_success(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        result = BankingOperations.deposit(account_number, 50)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['new_balance'], 150)
        self.assertIn('deposited', result['message'].lower())
    
    def test_deposit_multiple(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        BankingOperations.deposit(account_number, 50)
        result = BankingOperations.deposit(account_number, 25)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['new_balance'], 175)

    def test_deposit_invalid_account(self):
        result = BankingOperations.deposit("0000000000", 50)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    # Withdrawal Tests
    def test_withdraw_success(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        result = BankingOperations.withdraw(account_number, 30)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['new_balance'], 70)
        self.assertIn('withdrew', result['message'].lower())
    
    def test_withdraw_insufficient_balance(self):
        acc = BankingOperations.create_account("Test User", 50)
        account_number = acc['account_number']
        
        result = BankingOperations.withdraw(account_number, 100)
        
        self.assertFalse(result['success'])
        self.assertIn('insufficient', result['error'].lower())
    
    def test_withdraw_zero_amount(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        result = BankingOperations.withdraw(account_number, 0)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_withdraw_negative_amount(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        result = BankingOperations.withdraw(account_number, -50)
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    # Balance Check Tests
    def test_check_balance_success(self):
        acc = BankingOperations.create_account("Test User", 500)
        account_number = acc['account_number']
        
        result = BankingOperations.check_balance(account_number)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['balance'], 500)
        self.assertEqual(result['holder_name'], "Test User")
    
    def test_check_balance_invalid_account(self):
        result = BankingOperations.check_balance("0000000000")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    # Transfer Tests
    def test_transfer_success(self):
        acc1 = BankingOperations.create_account("User 1", 500)
        acc2 = BankingOperations.create_account("User 2", 100)
        
        result = BankingOperations.transfer_between_accounts(
            acc1['account_number'],
            acc2['account_number'],
            100
        )
        
        self.assertTrue(result['success'])
        
        balance1 = BankingOperations.check_balance(acc1['account_number'])
        balance2 = BankingOperations.check_balance(acc2['account_number'])
        
        self.assertEqual(balance1['balance'], 400)
        self.assertEqual(balance2['balance'], 200)
    
    def test_transfer_insufficient_balance(self):
        acc1 = BankingOperations.create_account("User 1", 50)
        acc2 = BankingOperations.create_account("User 2", 100)
        
        result = BankingOperations.transfer_between_accounts(
            acc1['account_number'],
            acc2['account_number'],
            100
        )
        
        self.assertFalse(result['success'])
        self.assertIn('insufficient', result['error'].lower())
    
    def test_transfer_invalid_from_account(self):
        acc2 = BankingOperations.create_account("User 2", 100)
        
        result = BankingOperations.transfer_between_accounts(
            "0000000000",
            acc2['account_number'],
            50
        )
        
        self.assertFalse(result['success'])
    
    def test_transfer_invalid_to_account(self):
        acc1 = BankingOperations.create_account("User 1", 500)
        
        result = BankingOperations.transfer_between_accounts(
            acc1['account_number'],
            "9999999999",
            50
        )
        
        self.assertFalse(result['success'])
    
    # List Accounts Tests
    def test_list_accounts_empty(self):
        result = BankingOperations.list_accounts()
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['accounts']), 0)
    
    def test_list_accounts_multiple(self):
        BankingOperations.create_account("User 1", 100)
        BankingOperations.create_account("User 2", 200)
        BankingOperations.create_account("User 3", 300)
        
        result = BankingOperations.list_accounts()
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['accounts']), 3)
    
    # Transaction History Tests
    def test_transaction_history_empty(self):
        acc = BankingOperations.create_account("Test User", 100)
        
        result = BankingOperations.get_transaction_history(acc['account_number'])
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['transactions']), 0)
    
    def test_transaction_history_with_operations(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        # Perform operations
        BankingOperations.deposit(account_number, 50)
        BankingOperations.withdraw(account_number, 30)
        
        result = BankingOperations.get_transaction_history(account_number)
        
        self.assertTrue(result['success'])
        self.assertEqual(len(result['transactions']), 2)
        # Check that both transaction types exist
        transaction_types = {tx['transaction_type'] for tx in result['transactions']}
        self.assertIn('DEPOSIT', transaction_types)
        self.assertIn('WITHDRAWAL', transaction_types)
    
    def test_transaction_history_invalid_account(self):
        result = BankingOperations.get_transaction_history("0000000000")
        
        self.assertFalse(result['success'])
    
    # Delete Account Tests
    def test_delete_account_success(self):
        acc = BankingOperations.create_account("Test User", 0)
        account_number = acc['account_number']
        
        result = BankingOperations.delete_account(account_number)
        
        self.assertTrue(result['success'])
        self.assertIn('deleted', result['message'].lower())
        
        # Verify account no longer exists
        check = BankingOperations.check_balance(account_number)
        self.assertFalse(check['success'])
    
    def test_delete_account_nonzero_balance(self):
        acc = BankingOperations.create_account("Test User", 500)
        account_number = acc['account_number']
        
        result = BankingOperations.delete_account(account_number)
        
        self.assertFalse(result['success'])
        self.assertIn('balance', result['error'].lower())
        
        # Verify account still exists
        check = BankingOperations.check_balance(account_number)
        self.assertTrue(check['success'])
    
    def test_delete_invalid_account(self):
        result = BankingOperations.delete_account("0000000000")
        
        self.assertFalse(result['success'])
        self.assertIn('error', result)
    
    def test_delete_clears_transactions(self):
        acc = BankingOperations.create_account("Test User", 100)
        account_number = acc['account_number']
        
        BankingOperations.deposit(account_number, 50)
        BankingOperations.withdraw(account_number, 150)
        
        history = BankingOperations.get_transaction_history(account_number)
        self.assertTrue(history['success'])
        self.assertEqual(len(history['transactions']), 2)
        
        result = BankingOperations.delete_account(account_number)
        self.assertTrue(result['success'])
        check = BankingOperations.check_balance(account_number)
        self.assertFalse(check['success'])

def run_tests():
    suite = unittest.TestLoader().loadTestsFromTestCase(TestBankingApp)
    
    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print formatted summary
    print("\n" + BLUE + "=" * 50 + RESET)
    print(BOLD + CYAN + "TEST SUMMARY".center(50) + RESET)
    print(BLUE + "=" * 50 + RESET)
    print(f"{GREEN}Tests run: {result.testsRun}{RESET}")
    print(f"{GREEN}Successes: {result.testsRun - len(result.failures) - len(result.errors)}{RESET}")
    print(f"{RED}Failures: {len(result.failures)}{RESET}")
    print(f"{RED}Errors: {len(result.errors)}{RESET}")
    print(BLUE + "=" * 50 + RESET + "\n")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    import sys
    success = run_tests()
    sys.exit(0 if success else 1)
