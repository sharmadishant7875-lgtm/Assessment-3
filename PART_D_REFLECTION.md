# Part D: Reflection

## Trade-offs Made

### 1. Interest Accrual Handling (Part A & C)
**Trade-off:** Exclude interest accruals from reconciliation vs. Include and manage separately

**Decision:** Exclude upfront (Part C implementation)

**Rationale:**
- Interest accruals are journal entries (accounting), not cash movements (bank)
- By design, they have no bank counterpart
- Reconciling them creates noise (false breaks)
- Include them in separate interest accrual matching process (future enhancement)

**Alternative rejected:** Include all transactions, mark interest accruals as "expected breaks"
- Would inflate break count; confusing for Finance
- Mixes two fundamentally different transaction types
- Harder to automate

**Cost:** Requires separate interest accrual reconciliation later
**Benefit:** Clean reconciliation logic; accurate business metrics

---

### 2. Amount Tolerance Band (Part C)
**Trade-off:** Strict matching (tolerance=0.00) vs. Loose tolerance (tolerance=1.00)

**Decision:** Tolerance=1.0 (loose)

**Rationale:**
- Observed 4 mismatches of £0.50–£0.75 in Part A
- Likely causes: rounding, FX conversion, fee deduction
- Setting tolerance=0 would flag these as issues (noisy)
- Setting tolerance=1.0 absorbs these without hiding real problems (e.g., £100+ breaks are still caught)

**Alternative rejected:** Tolerance=0.01 (strict at pence level)
- Would flag fractional differences unnecessarily
- Forces unnecessary investigation of rounding issues
- Not typical for financial reconciliation (which allows small variances)

**Cost:** Misses some precision issues
**Benefit:** Reduces false positives; cleaner daily output

---

### 3. Architecture: Dedicated Reconciliation Engine vs. Stored Procedures (Part B)
**Trade-off:** Python Databricks jobs vs. SQL stored procedures in Synapse

**Decision:** Python Databricks jobs

**Rationale:**
- Configuration-driven engine (reusable for 20+ reconciliations)
- Dynamic schema handling (CSV columns may vary)
- Better logging/alerting integration
- Easier to test and debug
- Faster prototyping (Part C shows working implementation in 1 hour)

**Alternative rejected:** T-SQL stored procedures in Synapse
- Replicating logic across 20 stored procs = maintenance nightmare
- Harder to make dynamic/configurable
- Less suitable for config-driven approach

**Cost:** Extra Python dependency; Databricks licensing
**Benefit:** 80% code reuse across all reconciliations; faster to add new ones

---

### 4. Storage Strategy: ADLS Parquet vs. Synapse Native Tables (Part B)
**Trade-off:** Store as Parquet files vs. Native Synapse tables

**Decision:** ADLS Parquet (immutable landing zone)

**Rationale:**
- Immutable history; snapshots for rollback/audit
- Works with both Synapse and Databricks
- Partition by date enables easy re-processing
- Cheaper than native table storage
- Supports both batch and streaming future use

**Alternative rejected:** Dedicated Synapse tables only
- Harder to maintain immutable audit trail
- Tighter coupling to Synapse (less portable)
- Harder to re-process historical dates

**Cost:** Extra ADLS storage; need external tables in Synapse
**Benefit:** Auditability; flexibility; future-proof

---

### 5. Alerting: One vs. Two Alert Types (Part B)
**Trade-off:** Single alert for all issues vs. Separate technical/business alerts

**Decision:** Two separate channels

**Rationale:**
- Technical failures (pipeline crash) need immediate eng response (Slack + PagerDuty)
- Business issues (data anomalies) need Finance review (Email, next morning)
- Different urgency; different expertise
- Prevents alert fatigue (Eng not paged for business metrics)

**Alternative rejected:** Single alert for everything
- Would page Eng for every data anomaly (noisy)
- Would delay business alerts to next business day (if email only)
- No distinction between actionable technical failures and informational data issues

**Cost:** Extra Logic App complexity
**Benefit:** Right alert to right team at right time

---

## If I Had Two More Days

### Highest-Value Next Steps

1. **Multi-table Reconciliation Engine (6-8 hours)**
   - Current: 2-table joins only
   - Extension: Support 3+ table joins (e.g., PO → Invoice → Payment)
   - Impact: Covers 80% of future reconciliation use cases

2. **Dynamic Threshold Rules (4-6 hours)**
   - Current: Hardcoded materiality (>£1,000)
   - Extension: Configurable thresholds per account, product, date range
   - Example: threshold for new products = stricter; mature products = looser
   - Impact: Reduces false alerts; improves BI insights

3. **Automated Root Cause Analysis (8-10 hours)**
   - Current: Flags breaks; requires manual investigation
   - Extension: Pattern matching to suggest likely causes
   - Example: "3 interest accruals + 1 bank-only = likely unallocated receipt"
   - Impact: Speeds up Finance team's investigation

4. **Reprocessing Orchestration (4 hours)**
   - Current: Manual date parameter override
   - Extension: ADF pipeline for bulk reprocessing (start_date, end_date range)
   - Impact: Enables week-long catch-up after code fix with one click

5. **BI Dashboard Enhancements (4-6 hours)**
   - Current: Basic reconciliation status
   - Extension: Trend analysis (break rates over time), account-level heat maps, anomaly detection
   - Impact: Finance can monitor reconciliation health proactively

**Why in that order:**
- Multi-table: addresses known upcoming requirement (GL-to-subledger)
- Dynamic thresholds: biggest bang for buck in reducing alert noise
- Root cause analysis: unlocks self-service investigation for Finance
- Reprocessing: reduces operational burden on Eng
- BI dashboards: visibility / early warning

---

## Alternative Approaches Considered & Rejected

### Alternative 1: Code-Heavy Approach (Per-Reconciliation Code Files)
**Concept:** Write custom Python/T-SQL for each reconciliation

**Why rejected:**
- Would need 20-30 separate code files (one per reconciliation)
- Bug fix in logic requires changes across all files
- High maintenance burden
- New hire learns config approach, then has to debug 20 custom implementations
- Scaling: 40+ hours to add 20 reconciliations vs. 12 hours with config-driven

**Lesson:** Configuration-driven is right choice for multi-tenant pattern

---

### Alternative 2: Machine Learning for Anomaly Detection (Instead of Rules)
**Concept:** Train model on past reconciliation data; flag anomalies

**Why rejected:**
- Overkill for this problem; rules work well
- Requires historical training data (not available at month 1)
- Black box makes it hard to explain decisions to Finance
- False positive rate likely higher than rules-based approach
- Maintenance: model retraining, feature drift

**Lesson:** Start simple; rules-based is better for audit-sensitive domain

---

### Alternative 3: Real-Time Streaming Reconciliation (Instead of Daily Batch)
**Concept:** Reconcile transactions as they arrive in bank system (minute-level)

**Why rejected:**
- Loan system may not feed real-time (still batch-based)
- Breaks resolved with time lag (repayments clear slowly)
- Finance doesn't need real-time; daily morning report is standard practice
- Complexity: would need Kafka + event processing (3-4x cost)
- Business value: minimal (daily is sufficient)

**Lesson:** Match batch frequency to business process, not infrastructure capabilities

---

### Alternative 4: Synapse Dedicated SQL Pool (Instead of On-Demand)
**Concept:** Pre-allocated compute for consistent query performance

**Why rejected:**
- For this workload, SQL on-demand cheaper ($5-10/day vs. $50-100/day)
- On-demand spins up for query, shuts down after (pay-per-use)
- Queries are short and predictable (not long-running)
- Dedicated pool justified only with 24/7 query load

**Lesson:** Cost optimization matters; pick compute model to match workload

---

## Assumptions Made

1. **Data Quality Assumptions:**
   - end_to_end_id is the universal key linking loan and bank systems
   - Loan system is source of truth (breaks here = loan system issue)
   - Bank system is verification (breaks here = timing or unallocated issue)

2. **Operational Assumptions:**
   - Source systems produce data by 05:00 UTC (before ADF pipeline starts at 05:55)
   - One day lag acceptable (T-1 data available next morning)
   - Manual receipt allocation can be done within 24 hours
   - On-call engineer available 06:00–18:00 UK time for alerts

3. **Financial Assumptions:**
   - Materiality threshold = £1,000 (configurable per organization)
   - Reconciliation break tolerance = £1.00 (rounding acceptable)
   - Interest accruals intentionally unmatched (separate accounting process)

4. **Technical Assumptions:**
   - Azure stack available (ADF, ADLS, Synapse, Databricks)
   - Private network connectivity to source systems (no internet exposure)
   - Python 3.8+ runtime available (Databricks, ADF, or standalone)
   - YAML config files version-controlled (Git or Azure Repos)

---

## Known Limitations & What I'd Fix First

### Limitation 1: No Multi-Column Join Support
**Current:** Single end_to_end_id join key only
**Gap:** Some reconciliations need composite key (account_id + transaction_date)
**Fix priority:** High (affects 5+ future reconciliations)
**Effort:** 2-3 hours (already designed in config schema)

### Limitation 2: Hardcoded Materiality Threshold
**Current:** Manual edit of Part B alerting rules
**Gap:** Cannot change threshold without code change
**Fix priority:** Medium (annual review sufficient)
**Effort:** 1-2 hours (add to config schema)

### Limitation 3: No Automated Deduplication
**Current:** Engine detects duplicates; Eng must manually investigate
**Gap:** Unallocated receipts (BK80071, etc.) still require manual allocation
**Fix priority:** Medium (Finance can handle; not blocking)
**Effort:** 4-6 hours (add deduplication rules to config)

### Limitation 4: No Trend Analysis
**Current:** Daily point-in-time view only
**Gap:** Cannot see if breaks increasing/decreasing over time
**Fix priority:** Low (Finance can add to Power BI manually)
**Effort:** 3-4 hours (add historical aggregation to Synapse)

### Limitation 5: No Account-Level Drill-Down
**Current:** Account summary shows status but not transaction-level detail
**Gap:** Finance must query raw data to understand cause of break
**Fix priority:** Medium (impacts investigation time)
**Effort:** 2-3 hours (add drill-down views to Synapse)

---

## Why I Approached It This Way

### Part A: SQL First
- Understand the data before designing solutions
- Identify patterns (interest accruals, duplicates, unallocated receipts)
- Inform downstream design decisions (exclusions, tolerance)

### Part B: Architecture Before Code
- Design for scale (20+ reconciliations) before implementing one
- Define reusable patterns (ADF template, alerting framework, secrets management)
- Prevent rework later

### Part C: Configuration-Driven Engine
- Build for extensibility, not just this one problem
- Prove the pattern works with actual implementation + test
- Enable non-technical teams (Finance) to add reconciliations later

### Part D: Reflection Last
- Document trade-offs and decisions for future team
- Explain what's reusable vs. custom
- Provide roadmap for the next engineer

---

## Conclusion

The solution balances three goals:
1. **Correctness:** Accurate reconciliation with proper handling of edge cases
2. **Scalability:** Design supports 20+ reconciliations with 80% code reuse
3. **Maintainability:** Clear documentation, configuration-driven logic, audit trails

Trade-offs favor maintainability over completeness (e.g., excluding interest accruals, loose tolerance). This reflects the reality of 4-hour assessment: better to ship a clean, understandable solution than a feature-complete one that's hard to explain.

The highest-value next steps (multi-table joins, dynamic thresholds) are clear, enabling continuity when this work is handed off.
