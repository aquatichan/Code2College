from database.db_setup import get_db_connection
import random
import string
from datetime import datetime

class Account:
    
    @staticmethod # Decorator that indicates this method can be called directly using the class name
    def generate_account_number():
        return ''.join(random.choices(string.digits, k=8))
    
    @staticmethod
    def create_account(holder_name, initial_deposit):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            account_number = Account.generate_account_number()
            
            while True:
                cursor.execute('SELECT id FROM accounts WHERE account_number = ?', (account_number,))
                if cursor.fetchone() is None:
                    break
                account_number = Account.generate_account_number()
            
            created_at = datetime.now().isoformat() + 'Z'
            cursor.execute('''
                INSERT INTO accounts (account_number, holder_name, balance, created_at)
                VALUES (?, ?, ?, ?)
            ''', (account_number, holder_name, initial_deposit, created_at))
            
            conn.commit()
            account_id = cursor.lastrowid
            return {
                'success': True,
                'account_id': account_id,
                'account_number': account_number,
                'holder_name': holder_name,
                'balance': initial_deposit
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def get_account(account_number):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM accounts WHERE account_number = ?', (account_number,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'success': True,
                    'id': row['id'],
                    'account_number': row['account_number'],
                    'holder_name': row['holder_name'],
                    'balance': row['balance'],
                    'created_at': row['created_at']
                }
            else:
                return {'success': False, 'error': 'Account not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def list_accounts():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT id, account_number, holder_name, balance FROM accounts')
            rows = cursor.fetchall()
            
            accounts = []
            for row in rows:
                accounts.append({
                    'id': row['id'],
                    'account_number': row['account_number'],
                    'holder_name': row['holder_name'],
                    'balance': row['balance']
                })
            
            return {'success': True, 'accounts': accounts}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def get_account_by_id(account_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
            row = cursor.fetchone()
            
            if row:
                return {
                    'success': True,
                    'id': row['id'],
                    'account_number': row['account_number'],
                    'holder_name': row['holder_name'],
                    'balance': row['balance']
                }
            else:
                return {'success': False, 'error': 'Account not found'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def update_balance(account_id, new_balance):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('UPDATE accounts SET balance = ? WHERE id = ?', (new_balance, account_id))
            conn.commit()
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def delete_account(account_number):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # First get the account to verify it exists
            cursor.execute('SELECT id, balance FROM accounts WHERE account_number = ?', (account_number,))
            row = cursor.fetchone()
            
            if not row:
                return {'success': False, 'error': 'Account not found'}
            
            account_id = row['id']
            
            # Delete associated transactions first (foreign key)
            cursor.execute('DELETE FROM transactions WHERE account_id = ?', (account_id,))
            
            # Delete the account
            cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
            
            conn.commit()
            return {'success': True, 'message': f'Account {account_number} deleted successfully'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
