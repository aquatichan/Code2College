from banking_operations import BankingOperations

# ANSI color codes for formatting
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def line(char="-"):
    return char * 100

def header(title):
    print("\n" + BLUE + line("=") + RESET)
    print(BOLD + CYAN + title.center(100) + RESET)
    print(BLUE + line("=") + RESET)

def success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def fmt_balance(amount):
    return "$" + f"{amount:.2f}"

def demo():
    header("BANKING APPLICATION DEMO")

    # 1. Create Accounts
    header("1. Creating Bank Accounts")

    result1 = BankingOperations.create_account("Alice Johnson", 5000)
    if result1['success']:
        alice = result1['account_number']
        success(f"Created account for {result1['holder_name']}")
        print(f"  {'Account:':<12}{alice}")
        print(f"  {'Balance:':<12}{GREEN}{fmt_balance(result1['balance'])}{RESET}")

    result2 = BankingOperations.create_account("Bob Smith", 3000)
    if result2['success']:
        bob = result2['account_number']
        success(f"Created account for {result2['holder_name']}")
        print(f"  {'Account:':<12}{bob}")
        print(f"  {'Balance:':<12}{GREEN}{fmt_balance(result2['balance'])}{RESET}")

    result3 = BankingOperations.create_account("Charlie Brown", 2500)
    if result3['success']:
        charlie = result3['account_number']
        success(f"Created account for {result3['holder_name']}")
        print(f"  {'Account:':<12}{charlie}")
        print(f"  {'Balance:':<12}{GREEN}{fmt_balance(result3['balance'])}{RESET}")

    # 2. List Accounts
    header("2. List All Accounts")

    result = BankingOperations.list_accounts()
    if result['success']:
        print(YELLOW + line() + RESET)
        print(BOLD + f"  {'Account #':<32} {'Holder':<32} {'Balance':<32}" + RESET) # 2 + 32 + 1 + 32 + 1 + 32 = 100
        print(YELLOW + line() + RESET)
        for acc in result['accounts']:
            print(f"  {acc['account_number']:<32} {acc['holder_name']:<32} {GREEN}{fmt_balance(acc['balance']):<32}{RESET}") # 2 + 32 + 1 + 32 + 1 + 32 = 100
        print(YELLOW + line() + RESET)

    # 3. Deposits
    header("3. Deposit Operations")

    print(YELLOW + line() + RESET)
    print(BOLD + f"  {'Account Holder':<24} {'Operation':<24} {'Amount':<24} {'New Balance':<23}" + RESET) # 2 + 24 + 1 + 24 + 1 + 24 + 1 + 23 = 100
    print(YELLOW + line() + RESET)
    for acct, name, amt in [(alice, "Alice", 1000), (bob, "Bob", 500)]:
        result = BankingOperations.deposit(acct, amt)
        if result['success']:
            print(f"  {name:<24} {'Deposit':<24} {GREEN}{fmt_balance(amt):<24} {fmt_balance(result['new_balance']):<23}{RESET}")  # 2 + 24 + 1 + 24 + 1 + 24 + 1 + 23 = 100
    print(YELLOW + line() + RESET)

    # 4. Withdrawals
    header("4. Withdrawal Operations")

    print(YELLOW + line() + RESET)
    print(BOLD + f"  {'Account Holder':<24} {'Operation':<24} {'Amount':<24} {'New Balance':<23}" + RESET)
    print(YELLOW + line() + RESET)
    for acct, name, amt in [(charlie, "Charlie", 500), (alice, "Alice", 800)]:
        result = BankingOperations.withdraw(acct, amt)
        if result['success']:
            print(f"  {name:<24} {'Withdrawal':<24} {GREEN}{fmt_balance(amt):<24} {fmt_balance(result['new_balance']):<23}{RESET}")
    print(YELLOW + line() + RESET)

    # 5. Balances
    header("5. Check Account Balances")

    print(YELLOW + line() + RESET)
    print(BOLD + f"  {'Account Holder':<49} {'Balance':<48}" + RESET) # 2 + 49 + 1 + 48 = 100
    print(YELLOW + line() + RESET)
    for name, acct in [("Alice", alice), ("Bob", bob), ("Charlie", charlie)]:
        result = BankingOperations.check_balance(acct)
        if result['success']:
            print(f"  {name:<49} {GREEN}{fmt_balance(result['balance']):<48}{RESET}") # 2 + 49 + 1 + 48 = 100
    print(YELLOW + line() + RESET)

    # 6. Transfers
    header("6. Transfers")

    print(YELLOW + line() + RESET)
    print(BOLD + f"  {'From':<32} {'To':<32} {'Amount':<32}" + RESET)
    print(YELLOW + line() + RESET)
    transfers = [
        (alice, bob,     "Alice",   "Bob",     500),
        (bob,   charlie, "Bob",     "Charlie", 300),
    ]
    for frm, to, frm_name, to_name, amt in transfers:
        result = BankingOperations.transfer_between_accounts(frm, to, amt)
        if result['success']:
            print(f"  {frm_name:<32} {to_name:<32} {GREEN}{fmt_balance(amt):<32}{RESET}")
    print(YELLOW + line() + RESET)

    # 7. Updated Balances
    header("7. Updated Balances")

    print(YELLOW + line() + RESET)
    print(BOLD + f"  {'Account Holder':<49} {'Balance':<48}" + RESET)
    print(YELLOW + line() + RESET)
    for name, acct in [("Alice", alice), ("Bob", bob), ("Charlie", charlie)]:
        result = BankingOperations.check_balance(acct)
        if result['success']:
            print(f"  {name:<49} {GREEN}{fmt_balance(result['balance']):<48}{RESET}")
    print(YELLOW + line() + RESET)

    # 8. Transaction History
    header("8. Alice Transaction History")

    result = BankingOperations.get_transaction_history(alice)
    if result['success'] and result['transactions']:
        print(YELLOW + line() + RESET)
        print(BOLD + f"  {'Type':<32} {'Amount':<32} {'Balance After':<32}" + RESET)
        print(YELLOW + line() + RESET)
        for tx in result['transactions']:
            print(
                f"  {tx['transaction_type']:<32} "
                f"{GREEN}{fmt_balance(tx['amount']):<32} "
                f"{fmt_balance(tx['balance_after']):<32}{RESET}"
            )
        print(YELLOW + line() + RESET)

    # 9. Final State
    header("9. Final Account Status")

    result = BankingOperations.list_accounts()
    if result['success']:
        print(YELLOW + line() + RESET)
        print(BOLD + f"  {'Account #':<32} {'Holder':<32} {'Balance':<32}" + RESET)
        print(YELLOW + line() + RESET)
        for acc in result['accounts']:
            print(f"  {acc['account_number']:<32} {acc['holder_name']:<32} {GREEN}{fmt_balance(acc['balance']):<32}{RESET}")
        print(YELLOW + line() + RESET)

    # 10. Delete Account Setup
    header("10. Delete Account - Init")

    result = BankingOperations.check_balance(charlie)
    if result['success']:
        charlie_balance = result['balance']
        if charlie_balance > 0:
            print(f"  {'Current Balance:':<20} {GREEN}{fmt_balance(charlie_balance)}{RESET}")
            result = BankingOperations.withdraw(charlie, charlie_balance)
            if result['success']:
                success(f"Withdrew {fmt_balance(charlie_balance)}")
                print(f"  {'New Balance:':<20} {GREEN}{fmt_balance(result['new_balance'])}{RESET}")

    # 11. Delete `Charlie Brown` Dummy Account
    header("11. Delete Account")

    result = BankingOperations.delete_account(charlie)
    if result['success']:
        success(result['message'])
    else:
        error(result['error'])

    # 12. Final State After Deletion
    header("12. Final State After Deletion")

    result = BankingOperations.list_accounts()
    if result['success']:
        print(YELLOW + line() + RESET)
        print(BOLD + f"  {'Account #':<32} {'Holder':<32} {'Balance':<32}" + RESET)
        print(YELLOW + line() + RESET)
        for acc in result['accounts']:
            print(f"  {acc['account_number']:<32} {acc['holder_name']:<32} {GREEN}{fmt_balance(acc['balance']):<32}{RESET}")
        print(YELLOW + line() + RESET)


    header("DEMO COMPLETED")

    print("\nFeatures Demonstrated:")
    print(GREEN + " ✓ Account creation" + RESET)
    print(GREEN + " ✓ Deposits & withdrawals" + RESET)
    print(GREEN + " ✓ Balance checking" + RESET)
    print(GREEN + " ✓ Transfers" + RESET)
    print(GREEN + " ✓ Transaction history" + RESET)
    print(GREEN + " ✓ Account deletion" + RESET)

if __name__ == "__main__":
    demo()