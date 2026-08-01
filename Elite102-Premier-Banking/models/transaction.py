from database.db_setup import get_db_connection
from datetime import datetime

class Transaction:
    
    @staticmethod # Decorator that indicates this method can be called directly using the class name
    def record_transaction(account_id, transaction_type, amount, balance_after):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            timestamp = datetime.now().isoformat() + 'Z'
            cursor.execute('''
                INSERT INTO transactions (account_id, transaction_type, amount, balance_after, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (account_id, transaction_type, amount, balance_after, timestamp))
            
            conn.commit()
            return {'success': True, 'transaction_id': cursor.lastrowid}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    @staticmethod
    def get_account_transactions(account_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM transactions 
                WHERE account_id = ? 
                ORDER BY timestamp DESC
            ''', (account_id,))
            rows = cursor.fetchall()
            
            transactions = []
            for row in rows:
                transactions.append({
                    'id': row['id'],
                    'transaction_type': row['transaction_type'],
                    'amount': row['amount'],
                    'balance_after': row['balance_after'],
                    'timestamp': row['timestamp']
                })
            
            return {'success': True, 'transactions': transactions}
        except Exception as e:
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
