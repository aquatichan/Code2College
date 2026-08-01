from models.account import Account
from models.transaction import Transaction

class BankingOperations:
    
    @staticmethod # Decorator that indicates this method can be called directly using the class name
    def create_account(holder_name, initial_deposit):
        if initial_deposit < 0:
            return {'success': False, 'error': 'Initial deposit cannot be negative'}
        
        if not holder_name.strip():
            return {'success': False, 'error': 'Account holder name cannot be empty'}
        
        result = Account.create_account(holder_name, initial_deposit)
        return result
    
    @staticmethod
    def deposit(account_number, amount):
        if amount <= 0:
            return {'success': False, 'error': 'Deposit amount must be positive'}
        
        account = Account.get_account(account_number)
        if not account['success']:
            return account
        
        account_id = account['id']
        new_balance = account['balance'] + amount
        
        # Update balance
        Account.update_balance(account_id, new_balance)
        
        # Record transaction
        Transaction.record_transaction(account_id, 'DEPOSIT', amount, new_balance)
        
        return {
            'success': True,
            'message': f'Deposited ${amount:.2f}',
            'new_balance': new_balance
        }
    
    @staticmethod
    def withdraw(account_number, amount):
        if amount <= 0:
            return {'success': False, 'error': 'Withdrawal amount must be positive'}
        
        account = Account.get_account(account_number)
        if not account['success']:
            return account
        
        account_id = account['id']
        
        if account['balance'] < amount:
            return {
                'success': False,
                'error': f'Insufficient balance. Available: ${account["balance"]:.2f}'
            }
        
        new_balance = account['balance'] - amount
        
        # Update balance
        Account.update_balance(account_id, new_balance)
        
        # Record transaction
        Transaction.record_transaction(account_id, 'WITHDRAWAL', amount, new_balance)
        
        return {
            'success': True,
            'message': f'Withdrew ${amount:.2f}',
            'new_balance': new_balance
        }
    
    @staticmethod
    def check_balance(account_number):
        account = Account.get_account(account_number)
        return account
    
    @staticmethod
    def list_accounts():
        return Account.list_accounts()
    
    @staticmethod
    def get_transaction_history(account_number):
        account = Account.get_account(account_number)
        if not account['success']:
            return account
        
        account_id = account['id']
        return Transaction.get_account_transactions(account_id)
    
    @staticmethod
    def transfer_between_accounts(from_account_number, to_account_number, amount):
        if amount <= 0:
            return {'success': False, 'error': 'Transfer amount must be positive'}
        
        # Check if both accounts exist
        from_account = Account.get_account(from_account_number)
        if not from_account['success']:
            return {'success': False, 'error': f'From account not found: {from_account_number}'}
        
        to_account = Account.get_account(to_account_number)
        if not to_account['success']:
            return {'success': False, 'error': f'To account not found: {to_account_number}'}
        
        # Check if from_account has sufficient balance
        if from_account['balance'] < amount:
            return {
                'success': False,
                'error': f'Insufficient balance. Available: ${from_account["balance"]:.2f}'
            }
        
        # Perform withdrawal from source
        new_from_balance = from_account['balance'] - amount
        Account.update_balance(from_account['id'], new_from_balance)
        Transaction.record_transaction(from_account['id'], 'TRANSFER_OUT', amount, new_from_balance)
        
        # Perform deposit to destination
        new_to_balance = to_account['balance'] + amount
        Account.update_balance(to_account['id'], new_to_balance)
        Transaction.record_transaction(to_account['id'], 'TRANSFER_IN', amount, new_to_balance)
        
        return {
            'success': True,
            'message': f'Transferred ${amount:.2f} from {from_account_number} to {to_account_number}'
        }
    
    @staticmethod
    def delete_account(account_number):
        account = Account.get_account(account_number)
        if not account['success']:
            return account
        
        if account['balance'] != 0:
            return {
                'success': False,
                'error': f'Cannot delete account with balance ${account["balance"]:.2f}. Withdraw or transfer funds first.'
            }
        
        return Account.delete_account(account_number)
