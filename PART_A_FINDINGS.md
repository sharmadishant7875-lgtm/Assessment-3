# Part A: SQL Reconciliation — Findings Summary

## Executive Summary

**Headline for Finance Leadership:**
Month-end reconciliation break identified: 15 unmatched transactions totaling £22,496.12 require investigation and reprocessing. Additionally, 4 amount discrepancies (£0.50–£0.75 each) detected between systems.

---

## Data Overview

| Component | Row Count |
|-----------|-----------|
| loan_accounts | 25 |
| loan_transactions | 82 |
| bank_transactions | 74 |

---

## Reconciliation Results

### Overall Status
- **Accounts fully reconciled:** 14 out of 25 (56%)
- **Accounts with breaks:** 11 out of 25 (44%)

### Transaction Matching
| Category | Count |
|----------|-------|
| Transactions matched (amounts agree) | 67 |
| Transactions with amount mismatches | 4 |
| One-sided breaks (unmatched transactions) | 15 |

---

## Key Issues Identified

### 1. BREAKS: Unmatched Transactions (15 total)

#### Loan-only breaks (12 transactions)
These loan transactions have no corresponding bank payment:
- **Most common type:** INTEREST_ACCRUAL (10 out of 12)
  - Interest accruals on 31/05/2026 from accounts: L1004, L1006, L1009, L1010, L1011, L1012, L1013, L1016, L1019, L1020, L1022
  - Total value: £12,289.28
  - **Root cause (likely):** Interest accruals are accounting journal entries in the loan system, NOT cash movements. They should not be matched to bank transactions; they require separate handling in the reconciliation process.

- **One repayment break:**
  - LTX5049 (L1016, £2,035.08) — no bank match despite having end_to_end_id
  - Date: 25/05/2026
  - **Root cause (likely):** Bank payment processing delay; may post in subsequent month.

#### Bank-only breaks (3 transactions)
These bank payments have no corresponding loan transaction:
- BK80071, BK80072, BK80073
- Total value: £6,707.52
- **Root cause (likely):** Manual receipts with placeholder end-to-end IDs (E2E00099000, E2E00099001, E2E00099002)
  - Narrative: "Manual receipt - unallocated"
  - These indicate unallocated cash not yet matched to specific loans
  - Require manual investigation for account allocation

### 2. AMOUNT MISMATCHES (4 transactions)

All mismatches are small fractional differences (£0.50–£0.75):
- LTX5025 / BK80023: £1,428.25 vs £1,427.50 (£0.75)
- LTX5057 / BK80048: £2,866.28 vs £2,865.53 (£0.75)
- LTX5058 / BK80049: £2,628.54 vs £2,627.79 (£0.75)
- LTX5065 / BK80055: £1,902.10 vs £1,901.60 (£0.50)

**Root cause (likely):** Rounding differences or FX conversion discrepancies. The pattern (three at exactly £0.75) suggests a systematic issue in amount calculation, possibly:
- Fee deduction in one system only
- FX conversion precision mismatch
- Rounding applied at different stages

### 3. DUPLICATES (1 identified)

**E2E00005002** appears twice in bank_transactions:
- BK80002 (2026-03-25 16:21:00, £802.55)
- BK80074 (2026-03-25 16:23:00, £802.55)

**Root cause:** Duplicate bank ingestion — same payment processed twice, 2 minutes apart.

**Impact:** This artificially inflates the bank-side transaction count but the loan-side correctly has only one LTX5002.

---

## Root Cause Analysis

| Issue | Type | Likely Cause | Remediation |
|-------|------|--------------|-------------|
| Interest accruals unmatched (12 txns) | Data design | Interest accruals are journal entries, not cash | Exclude from future reconciliation or create separate interest accrual matcher |
| Manual receipts unmatched (3 txns) | Operational | Unallocated cash not yet assigned to loans | Manual review; allocate to correct loan accounts |
| Duplicate bank transaction | Data quality | Double ingestion into bank_transactions feed | Implement deduplication in bank ingestion pipeline; review ETL logs for 25/03/2026 |
| Fractional amount mismatches (4 txns) | System precision | Rounding or FX handling difference | Analyze calculation logic in both systems; consider tolerance band in future reconciliation |
| One missing repayment (LTX5049, £2,035) | Timing | Processing lag in bank system | Implement lookback window; re-reconcile in subsequent month |

---

## Accounts Affected by Breaks

11 accounts have reconciliation breaks:
- **L1004, L1006, L1009, L1010, L1011, L1012, L1013, L1016, L1019, L1020, L1022**
- All except L1016 have only LOAN_BREAKS (unmatched interest accruals)
- L1016 has 2 LOAN_BREAKS: one interest accrual, one repayment

---

## Recommendations

### Immediate Actions (this month-end)
1. Investigate duplicate BK80002/BK80074 in bank feed; remove from statement
2. Manually review manual receipts (BK80071, BK80072, BK80073) and allocate to correct loan accounts
3. Verify LTX5049 status with bank; may clear in June

### Process Improvements (for future reconciliation)
1. **Interest accruals:** Separate reconciliation path — do not match to bank cash
2. **Tolerance band:** Accept mismatches ≤£1 automatically; flag larger discrepancies
3. **Deduplication:** Implement row-level deduplication in bank ingestion pipeline (unique on bank_transaction_id)
4. **Manual receipts:** Require allocation/classification before importing to avoid unallocated cash breakages
5. **Lookback window:** Implement 2-3 day lookback for late-clearing items before declaring breaks
6. **FX handling:** Document and standardize rounding rules across both systems

---

## Conclusion

The reconciliation identified material data quality and process issues totaling £22,496.12. The majority (55%) relate to interest accruals, which are a design issue (accounting vs. cash). The remaining breaks are operational (manual allocation) or technical (duplicate/rounding). Once these patterns are addressed, the reconciliation process can be automated with high confidence.
