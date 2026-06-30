-- PART A: SQL RECONCILIATION QUERIES
-- Dialect: SQLite

-- QUERY 1: MATCHED TRANSACTIONS
-- Loan-system transactions that have a corresponding bank-side transaction,
-- where both sides agree on amount
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
ORDER BY lt.transaction_date DESC;


-- QUERY 2: AMOUNT MISMATCHES
-- Transactions that pair across the two sides but where amounts disagree.
-- Ordered by most material differences first.
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
ORDER BY ABS(CAST(lt.amount AS REAL) - CAST(bt.amount AS REAL)) DESC;


-- QUERY 3: BREAKS (ONE-SIDED TRANSACTIONS)
-- Transactions that exist on one side but not the other.
-- Structured as two UNION branches: LOAN_ONLY and BANK_ONLY.
-- LOAN_ONLY: loan transactions without matching bank transaction
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

-- BANK_ONLY: bank transactions without matching loan transaction
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
WHERE lt.transaction_id IS NULL;


-- QUERY 4: DUPLICATES
-- Definition: duplicate = same end_to_end_id appearing multiple times in the same table.

-- Loan transaction duplicates (by end_to_end_id)
SELECT
    'LOAN_DUPLICATES' as source,
    end_to_end_id,
    COUNT(*) as count,
    GROUP_CONCAT(transaction_id) as transaction_ids
FROM loan_transactions
WHERE end_to_end_id IS NOT NULL
GROUP BY end_to_end_id
HAVING COUNT(*) > 1;

-- Bank transaction duplicates (by end_to_end_id)
SELECT
    'BANK_DUPLICATES' as source,
    end_to_end_id,
    COUNT(*) as count,
    GROUP_CONCAT(bank_transaction_id) as bank_transaction_ids
FROM bank_transactions
GROUP BY end_to_end_id
HAVING COUNT(*) > 1;


-- QUERY 5: PER-ACCOUNT RECONCILIATION SUMMARY
-- For every loan account, produces a single row with reconciliation state.
-- Columns: account_id, customer_id, product_name, status, loan totals,
-- matched totals, transaction counts, and reconciliation_status.
-- Reconciliation states: RECONCILED, LOAN_BREAKS, BANK_BREAKS, BOTH_SIDES_BREAKS
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
ORDER BY reconciliation_status, account_id;
