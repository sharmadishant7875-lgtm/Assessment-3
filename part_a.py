#!/usr/bin/env python3
"""
Part A: SQL Reconciliation
Dialect: SQLite
"""

import sqlite3
import pandas as pd
from datetime import datetime

# Create database and load data
db_path = 'reconciliation.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Drop tables if they exist (for fresh runs)
cursor.execute('DROP TABLE IF EXISTS loan_accounts')
cursor.execute('DROP TABLE IF EXISTS loan_transactions')
cursor.execute('DROP TABLE IF EXISTS bank_transactions')

# Load CSVs
loan_accounts_df = pd.read_csv('loan_accounts.csv')
loan_transactions_df = pd.read_csv('loan_transactions.csv')
bank_transactions_df = pd.read_csv('bank_transactions.csv')

# Create tables
loan_accounts_df.to_sql('loan_accounts', conn, index=False, if_exists='replace')
loan_transactions_df.to_sql('loan_transactions', conn, index=False, if_exists='replace')
bank_transactions_df.to_sql('bank_transactions', conn, index=False, if_exists='replace')

print("=" * 80)
print("PART A: SQL RECONCILIATION")
print("Dialect: SQLite")
print("=" * 80)
print()

# A1: Row counts
print("A1. DATA LOAD - ROW COUNTS")
print("-" * 80)
print(f"loan_accounts:      {len(loan_accounts_df)} rows")
print(f"loan_transactions:  {len(loan_transactions_df)} rows")
print(f"bank_transactions:  {len(bank_transactions_df)} rows")
print()

# QUERY 1: Matched transactions
print("QUERY 1: MATCHED TRANSACTIONS")
print("-" * 80)
query1 = """
SELECT
    lt.transaction_id,
    lt.account_id,
    lt.transaction_type,
    lt.amount as loan_amount,
    bt.bank_transaction_id,
    bt.amount as bank_amount,
    lt.end_to_end_id,
    lt.transaction_date,
    bt.transaction_time
FROM loan_transactions lt
INNER JOIN bank_transactions bt ON lt.end_to_end_id = bt.end_to_end_id
WHERE CAST(lt.amount AS REAL) = CAST(bt.amount AS REAL)
ORDER BY lt.transaction_date DESC
"""
result1 = pd.read_sql_query(query1, conn)
print(f"Found {len(result1)} matched transactions")
print(result1.to_string())
print()

# QUERY 2: Amount mismatches
print("QUERY 2: AMOUNT MISMATCHES")
print("-" * 80)
query2 = """
SELECT
    lt.transaction_id,
    lt.account_id,
    lt.amount as loan_amount,
    bt.bank_transaction_id,
    bt.amount as bank_amount,
    ABS(CAST(lt.amount AS REAL) - CAST(bt.amount AS REAL)) as difference,
    lt.end_to_end_id,
    lt.transaction_date
FROM loan_transactions lt
INNER JOIN bank_transactions bt ON lt.end_to_end_id = bt.end_to_end_id
WHERE CAST(lt.amount AS REAL) != CAST(bt.amount AS REAL)
ORDER BY ABS(CAST(lt.amount AS REAL) - CAST(bt.amount AS REAL)) DESC
"""
result2 = pd.read_sql_query(query2, conn)
print(f"Found {len(result2)} amount mismatches")
if len(result2) > 0:
    print(result2.to_string())
else:
    print("No amount mismatches found")
print()

# QUERY 3: Breaks (one-sided transactions)
print("QUERY 3: BREAKS (ONE-SIDED TRANSACTIONS)")
print("-" * 80)
query3 = """
-- Loan transactions without matching bank transaction
SELECT
    lt.transaction_id,
    lt.account_id,
    'LOAN_ONLY' as break_type,
    CAST(lt.amount AS REAL) as amount,
    lt.transaction_type,
    lt.end_to_end_id,
    lt.transaction_date,
    NULL as bank_transaction_id
FROM loan_transactions lt
LEFT JOIN bank_transactions bt ON lt.end_to_end_id = bt.end_to_end_id
WHERE bt.bank_transaction_id IS NULL

UNION ALL

-- Bank transactions without matching loan transaction
SELECT
    NULL as transaction_id,
    CASE WHEN lt.account_id IS NULL THEN SUBSTR(bt.narrative, -5) ELSE lt.account_id END as account_id,
    'BANK_ONLY' as break_type,
    CAST(bt.amount AS REAL) as amount,
    NULL as transaction_type,
    bt.end_to_end_id,
    DATE(bt.transaction_time) as transaction_date,
    bt.bank_transaction_id
FROM bank_transactions bt
LEFT JOIN loan_transactions lt ON bt.end_to_end_id = lt.end_to_end_id
WHERE lt.transaction_id IS NULL
"""
result3 = pd.read_sql_query(query3, conn)
result3 = result3.sort_values(['break_type', 'amount'], ascending=[True, False])
print(f"Found {len(result3)} breaks")
print(result3.to_string())
print()

# QUERY 4: Duplicates
print("QUERY 4: DUPLICATES")
print("-" * 80)
print("Definition: Duplicate = same end_to_end_id appearing multiple times in same table")
print()

query4a = """
SELECT
    'LOAN_DUPLICATES' as source,
    end_to_end_id,
    COUNT(*) as count,
    GROUP_CONCAT(transaction_id) as transaction_ids
FROM loan_transactions
WHERE end_to_end_id IS NOT NULL
GROUP BY end_to_end_id
HAVING COUNT(*) > 1
"""
result4a = pd.read_sql_query(query4a, conn)
print("Loan transaction duplicates (by end_to_end_id):")
if len(result4a) > 0:
    print(result4a.to_string())
else:
    print("None found")
print()

query4b = """
SELECT
    'BANK_DUPLICATES' as source,
    end_to_end_id,
    COUNT(*) as count,
    GROUP_CONCAT(bank_transaction_id) as bank_transaction_ids
FROM bank_transactions
GROUP BY end_to_end_id
HAVING COUNT(*) > 1
"""
result4b = pd.read_sql_query(query4b, conn)
print("Bank transaction duplicates (by end_to_end_id):")
if len(result4b) > 0:
    print(result4b.to_string())
else:
    print("None found")
print()

# QUERY 5: Per-account reconciliation summary
print("QUERY 5: PER-ACCOUNT RECONCILIATION SUMMARY")
print("-" * 80)
query5 = """
WITH account_summary AS (
    SELECT
        la.account_id,
        la.customer_id,
        la.product_name,
        la.status,
        COALESCE(SUM(CASE WHEN lt.transaction_id IS NOT NULL THEN CAST(lt.amount AS REAL) ELSE 0 END), 0) as total_loan_amount,
        COALESCE(SUM(CASE WHEN bt.bank_transaction_id IS NOT NULL AND lt.transaction_id IS NOT NULL THEN CAST(bt.amount AS REAL) ELSE 0 END), 0) as total_matched_amount,
        COUNT(DISTINCT CASE WHEN lt.transaction_id IS NOT NULL THEN lt.transaction_id END) as loan_transaction_count,
        COUNT(DISTINCT CASE WHEN bt.bank_transaction_id IS NOT NULL AND lt.transaction_id IS NOT NULL THEN bt.bank_transaction_id END) as matched_transaction_count,
        COUNT(DISTINCT CASE WHEN lt.transaction_id IS NOT NULL AND bt.bank_transaction_id IS NULL THEN lt.transaction_id END) as unmatched_loan_transactions,
        COUNT(DISTINCT CASE WHEN bt.bank_transaction_id IS NOT NULL AND lt.transaction_id IS NULL THEN bt.bank_transaction_id END) as unmatched_bank_transactions
    FROM loan_accounts la
    LEFT JOIN loan_transactions lt ON la.account_id = lt.account_id
    LEFT JOIN bank_transactions bt ON lt.end_to_end_id = bt.end_to_end_id
    GROUP BY la.account_id, la.customer_id, la.product_name, la.status
)
SELECT
    account_id,
    customer_id,
    product_name,
    status,
    total_loan_amount,
    total_matched_amount,
    loan_transaction_count,
    matched_transaction_count,
    unmatched_loan_transactions,
    unmatched_bank_transactions,
    CASE
        WHEN unmatched_loan_transactions = 0 AND unmatched_bank_transactions = 0 THEN 'RECONCILED'
        WHEN unmatched_loan_transactions > 0 AND unmatched_bank_transactions = 0 THEN 'LOAN_BREAKS'
        WHEN unmatched_loan_transactions = 0 AND unmatched_bank_transactions > 0 THEN 'BANK_BREAKS'
        ELSE 'BOTH_SIDES_BREAKS'
    END as reconciliation_status
FROM account_summary
ORDER BY reconciliation_status, account_id
"""
result5 = pd.read_sql_query(query5, conn)
print(result5.to_string())
print()

# Summary statistics
print("=" * 80)
print("FINDINGS SUMMARY")
print("=" * 80)
print()
reconciled = len(result5[result5['reconciliation_status'] == 'RECONCILED'])
with_breaks = len(result5[result5['reconciliation_status'] != 'RECONCILED'])
total_breaks = len(result3)
total_matched = len(result1)
total_mismatches = len(result2)

print(f"Total loan accounts: {len(result5)}")
print(f"Accounts fully reconciled: {reconciled}")
print(f"Accounts with breaks: {with_breaks}")
print()
print(f"Transactions matched (amounts agree): {total_matched}")
print(f"Transactions with amount mismatches: {total_mismatches}")
print(f"One-sided breaks (exist in one system only): {total_breaks}")
print()

if total_breaks > 0:
    print("BREAK ANALYSIS:")
    loan_only = len(result3[result3['break_type'] == 'LOAN_ONLY'])
    bank_only = len(result3[result3['break_type'] == 'BANK_ONLY'])
    print(f"  - Loan-only (no bank counterpart): {loan_only}")
    print(f"  - Bank-only (no loan counterpart): {bank_only}")
    if len(result3) > 0:
        total_value = result3['amount'].sum()
        print(f"  - Total value of breaks: £{total_value:,.2f}")
print()

print("KEY FINDINGS:")
print("-" * 80)
if total_mismatches == 0 and total_breaks == 0:
    print("✓ PERFECT RECONCILIATION: No breaks, no mismatches detected.")
else:
    if total_breaks > 0:
        print(f"⚠ {total_breaks} unmatched transactions found")
        print(f"  Most common break type: {result3['break_type'].value_counts().index[0]}")
    if total_mismatches > 0:
        print(f"⚠ {total_mismatches} amount mismatches detected")
        if len(result2) > 0:
            largest_mismatch = result2['difference'].max()
            print(f"  Largest mismatch: £{largest_mismatch:,.2f}")
print()

print("HEADLINE FOR FINANCE LEADERSHIP:")
print("-" * 80)
if total_breaks == 0 and total_mismatches == 0:
    print("Month-end reconciliation complete: loan book and bank payments reconcile perfectly.")
else:
    if total_breaks > 0:
        print(f"Month-end reconciliation break identified: {total_breaks} unmatched transactions")
        if len(result3) > 0:
            total_break_value = result3['amount'].sum()
            print(f"totaling £{total_break_value:,.2f} require investigation and reprocessing.")
    if total_mismatches > 0:
        print(f"Additionally, {total_mismatches} amount discrepancies detected between systems.")

conn.close()
