# Part B: Pipeline & Architecture Design

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Azure Environment                      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Data Ingestion Layer (Daily @ 05:55 UTC)                  │ │
│  │                                                            │ │
│  │  ┌──────────────────┐  ┌──────────────────┐             │ │
│  │  │ Cloud Data       │  │ Cloud Data       │             │ │
│  │  │ Warehouse        │  │ Warehouse        │             │ │
│  │  │ (on-premise)     │  │ (via VPN/PrivEP) │             │ │
│  │  └──────────┬───────┘  └────────┬─────────┘             │ │
│  │             │                    │                       │ │
│  │             └────────┬───────────┘                       │ │
│  │                      │                                   │ │
│  │             ┌────────▼─────────┐                        │ │
│  │             │  ADLS Gen2       │                        │ │
│  │             │  /raw/loans/     │  (Raw landing zone)    │ │
│  │             │  /raw/bank/      │                        │ │
│  │             └────────┬─────────┘                        │ │
│  └────────────────────┼─────────────────────────────────────┘ │
│                       │                                        │
│  ┌────────────────────▼─────────────────────────────────────┐ │
│  │ Orchestration Layer (ADF)                                │ │
│  │                                                          │ │
│  │  ┌──────────────────────────────────────────────────┐  │ │
│  │  │ Daily Pipeline (Trigger: 06:00 UK / 05:00 UTC)  │  │ │
│  │  │                                                  │  │ │
│  │  │ 1. Determine business_date (yesterday, T-1)    │  │ │
│  │  │ 2. Copy yesterday's CSVs to staging zone       │  │ │
│  │  │ 3. Execute reconciliation engine (Python/PySpark)  │  │ │
│  │  │ 4. Validate output (row count, completeness)  │  │ │
│  │  │ 5. Store results in ADLS + SQL database       │  │ │
│  │  │ 6. Trigger materialized view refresh          │  │ │
│  │  └────────────────┬─────────────────────────────┘  │ │
│  └────────────────┼──────────────────────────────────────┘ │
│                   │                                        │
│  ┌────────────────▼──────────────────────────────────────┐ │
│  │ Storage & Analytics Layer                             │ │
│  │                                                       │ │
│  │  ┌────────────────┐  ┌────────────────────────────┐  │ │
│  │  │ ADLS Gen2      │  │ Azure Synapse Analytics  │  │ │
│  │  │ /output/       │  │ (SQL on-demand or Spark) │  │ │
│  │  │ /archive/      │  │                          │  │ │
│  │  └────────────────┘  │  - Reconciliation facts  │  │ │
│  │                      │  - Matched transactions  │  │ │
│  │                      │  - Breaks & mismatches   │  │ │
│  │                      │  - Per-account summary   │  │ │
│  │                      └────────────┬─────────────┘  │ │
│  └───────────────────────────────────┼────────────────┘ │
│                                      │                  │
│  ┌───────────────────────────────────▼──────────────────┐ │
│  │ BI & Reporting Layer                               │ │
│  │                                                     │ │
│  │  ┌──────────────────────────────────────────────┐  │ │
│  │  │ Power BI / Looker Dashboard                 │  │ │
│  │  │ - Reconciliation status by account          │  │ │
│  │  │ - Break analysis and trends                 │  │ │
│  │  │ - Materiality threshold alerts              │  │ │
│  │  │ (Finance & Operations read access)          │  │ │
│  │  └──────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                           │
└─────────────────────────────────────────────────────────────┘

  Alerting & Notifications (outside Azure)
  ┌────────────────────────────────────────────┐
  │ Action Group / Logic App                   │
  │ ┌────────────────────────────────────────┐ │
  │ │ - Email: Finance team (daily summary)  │ │
  │ │ - Slack: On-call engineer (failures)   │ │
  │ │ - PagerDuty: Materiality alerts (>£1k) │ │
  │ └────────────────────────────────────────┘ │
  └────────────────────────────────────────────┘
```

---

## Detailed Design

### 1. Data Ingestion: Source to Landing

**Question:** How does data get from source into your Azure environment, and where does it land first?

**Answer:**
- **Source:** Cloud data warehouse (on-premise, accessed over private network via ExpressRoute or VPN)
- **Ingestion Method:**
  - Azure Data Factory (Copy Activity)
  - Daily pull at 05:55 UTC (just before pipeline start)
  - Connection: Private Endpoint or VPN-based connection (no internet exposure)
  - Authentication: Service Principal with managed identity (stored in Azure Key Vault)
  
- **Landing Zone (ADLS Gen2):**
  ```
  /reconciliation/
  ├── raw/
  │   ├── loan_transactions/YYYY/MM/DD/
  │   ├── bank_transactions/YYYY/MM/DD/
  │   └── loan_accounts/YYYY/MM/DD/ (reference, pulled daily)
  ├── staging/
  │   ├── loan_transactions_YYYYMMDD_processed
  │   ├── bank_transactions_YYYYMMDD_processed
  │   └── validation_logs/
  └── output/
      ├── matched_transactions/
      ├── breaks/
      ├── summary/
      └── archive/ (partition by month for retention)
  ```

- **Data Format:** CSV → Parquet (post-validation) for efficient querying
- **Retention Policy:**
  - Raw (90 days, cold storage after 30 days)
  - Staging (7 days, auto-delete)
  - Output/Archive (indefinite, immutable)

**Why this approach:**
- Private network eliminates internet exposure
- Daily pulls ensure freshness while avoiding duplicate processing
- Immutable landing zone supports re-processing and audit
- Partitioning by date enables efficient querying of specific periods

---

### 2. Orchestration: Pipeline Scheduling & Date Logic

**Question:** What runs the pipeline, on what schedule, and how does it know which day to process?

**Answer:**
- **Orchestration:** Azure Data Factory
- **Trigger:** Scheduled Trigger (Recurring)
  - Time: 06:00 UK time (UTC+0/+1 depending on DST) = 05:00 UTC standard
  - Frequency: Daily, Monday–Sunday
  - Timezone: Europe/London

- **Date Logic:**
  ```
  Pipeline Parameters:
  @pipeline().TriggerTime              // System variable: when trigger fired
  @adddays(pipeline().TriggerTime, -1) // business_date = yesterday (T-1)
  
  In ADF pipeline:
  1. Set variable: business_date = @formatDateTime(
       @adddays(pipeline().TriggerTime, -1), 'yyyy-MM-dd')
  2. Use business_date in all Copy Activity paths:
       source path: /raw/loan_transactions/${business_date}/*.csv
       output path: /output/summary/${business_date}/
  ```

- **Business Logic:**
  - Processes **previous business day's data**
  - Runs at 06:00 UK time → processes day T-1 data
  - Handles weekends automatically (Friday pipeline processes Friday's data, Monday pipeline processes Monday's data—no skip logic needed)
  - **Note:** If you need to exclude weekends, add a filter condition before pipeline execution

- **Why this approach:**
  - Simple, deterministic date logic (TriggerTime - 1 day)
  - No dependency on external calendars
  - Easy to re-run for a specific date (override parameter)
  - Aligns with typical batch processing (end-of-day snapshots ready next morning)

---

### 3. Re-processing: Fixing and Rolling Back

**Question:** If yesterday's run produced wrong results and you fix the code today, how do you re-process yesterday safely? What happens if you have to re-process 30 days?

**Answer:**

**Single Day Re-processing:**
```
ADF: Manual trigger with parameter override
Pipeline execution settings:
  business_date = 2026-05-15  (hardcoded, instead of TriggerTime-1)
  
  1. Delete outputs from /output/summary/2026-05-15/
  2. Re-ingest from /raw/loan_transactions/2026-05-15/
  3. Re-run reconciliation engine
  4. Publish new results to /output/summary/2026-05-15/
  5. Update Synapse view (refreshes automatically via Stored Procedure)
  
Audit trail:
  - ADF run history records: old run (failure), new run (fix)
  - All outputs immutably stored by date partition
  - No data loss; old results archived with metadata
```

**Bulk Re-processing (e.g., 30 days):**
```
Script: batch_reprocess.py (manual trigger in ADF)
  - Parameter: start_date, end_date
  - Loop: for each date in range:
      1. Delete /output/summary/${date}/ (idempotent via Databricks)
      2. Trigger child ADF pipeline for ${date}
      3. Wait for completion, log results
      4. If failure, stop and alert; if success, continue
  
  Risk mitigation:
    - Keep /raw/ and /staging/ immutable (do not re-delete source)
    - Archive old outputs before re-processing (copy to /archive/old_run_${timestamp}/)
    - Snapshot Synapse fact table before re-processing (table version control)
  
  Rollback strategy (if re-processing introduces new bugs):
    - Synapse: Restore fact table from backup (daily backup job)
    - Finance BI: Revert Power BI dataset refresh to previous run_date
    - ADF: No rollback needed (source data untouched; only output re-derived)
```

**Why this approach:**
- **Safe:** Source data (/raw/) never modified; only outputs re-derived
- **Auditable:** ADF run history and dated outputs create immutable audit trail
- **Parallelizable:** Can re-process multiple days in parallel (via Databricks clusters)
- **Testable:** Fix code in dev environment, validate against test data, then re-process prod with confidence

---

### 4. Output & Finance Consumption

**Question:** Where does the reconciliation output end up, and how does Finance consume it?

**Answer:**

**Output Storage:**
```
ADLS Gen2 + Synapse Analytics
├── /output/matched_transactions/YYYY/MM/DD/matched_txn.parquet
│   Columns: transaction_id, account_id, amount, end_to_end_id, ...
│
├── /output/breaks/YYYY/MM/DD/breaks.parquet
│   Columns: transaction_id, account_id, break_type (LOAN_ONLY/BANK_ONLY), amount, ...
│
├── /output/summary/YYYY/MM/DD/account_summary.parquet
│   Columns: account_id, customer_id, product_name, status,
│   unmatched_loan_txns, unmatched_bank_txns, reconciliation_status, ...
│
└── /output/alerts/YYYY/MM/DD/materiality_alerts.json
    Events: accounts_with_breaks > 10, single_break > £1,000
```

**Synapse Analytics (SQL on-demand or Dedicated Pool):**
```sql
-- Materialized views for Finance consumption
CREATE EXTERNAL TABLE facts.reconciliation_matched
  WITH (location = '/output/matched_transactions/**', ...)
  AS SELECT * FROM reconciliation_matched_parquet;

CREATE EXTERNAL TABLE facts.reconciliation_breaks
  WITH (location = '/output/breaks/**', ...) ...

CREATE EXTERNAL TABLE facts.reconciliation_summary
  WITH (location = '/output/summary/**', ...) ...

-- Aggregation views
CREATE VIEW vw_daily_reconciliation_status AS
  SELECT business_date, COUNT(*) as total_accounts, 
         SUM(CASE WHEN reconciliation_status='RECONCILED' THEN 1 ELSE 0 END) as reconciled_count,
         SUM(CASE WHEN reconciliation_status LIKE '%BREAKS' THEN 1 ELSE 0 END) as break_count
  FROM facts.reconciliation_summary
  GROUP BY business_date;
```

**Finance Consumption — Power BI / Looker:**
- **Dashboard 1: Daily Status**
  - Date picker (select reconciliation_date)
  - Reconciliation status by account (pivot: status vs. product_name)
  - Trend: %reconciled over time
  - Top 10 break accounts (sorted by total_unmatched_amount)

- **Dashboard 2: Break Analysis**
  - Breaks by type (LOAN_ONLY vs. BANK_ONLY)
  - Timeline: when did the break first appear?
  - Materiality: breaks > £1,000
  - Recommended action (based on patterns identified in Part A)

- **Dataset Refresh:** Daily at 07:00 UTC (1 hour after pipeline completes) via Service Principal

**Email Distribution (Logic App):**
```
Trigger: ADF pipeline success
Action: Send email
To: finance-team@company.com
Subject: Reconciliation Report — ${business_date}
Body:
  - Total accounts: X
  - Reconciled: Y (Z%)
  - Breaks: W (accounts)
  - Materiality alerts: [list]
  - Action items: [summary of recommended actions]
  - Link: [Power BI report]
```

---

### 5. Alerting: Failures vs. Data Problems

**Question:** How do you find out when the pipeline fails? How do you find out when the pipeline succeeds but the data has a problem? Are those the same alert or different alerts?

**Answer:**

**Two separate alerting channels (different alert types):**

#### Alert Type 1: Pipeline Failures (Technical)
```
ADF Pipeline Failure → Action Group → On-Call Engineer
Trigger: Pipeline execution fails (Copy Activity, validation step, compute error)
Channel: Slack + PagerDuty
Action: Immediate investigation
Examples:
  - VPN connection timeout to cloud data warehouse
  - Insufficient storage quota in ADLS Gen2
  - Reconciliation engine crashes (Python error)
  - Synapse refresh timeout
```

**Implementation (ADF):**
```
Pipeline: Failure Handler Notification
  Activity: If pipeline fails, execute:
    1. Log error to EventHub
    2. Call Azure Function → send Slack message to #data-eng
    3. Trigger PagerDuty incident (if Severity=HIGH)
    4. Email dpo@company.com with error stack trace
```

#### Alert Type 2: Data Quality / Reconciliation Issues (Business)
```
Reconciliation Output Validation → Action Group → Finance Team
Trigger: Pipeline succeeds, but reconciliation output has anomalies
Channel: Email (daily) + Slack (escalation only)
Action: Manual review and follow-up investigation
Examples:
  - More than 10 breaks detected
  - Any break > £1,000 (materiality threshold)
  - Mismatch count > threshold
  - New duplicates detected
```

**Implementation (Databricks + Logic App):**
```python
# Validation layer: run after reconciliation engine
def validate_reconciliation_output(output_df, business_date):
    alerts = []
    
    break_count = len(output_df[output_df['break_type'].notna()])
    if break_count > 10:
        alerts.append({
            'severity': 'medium',
            'message': f'{break_count} breaks detected on {business_date}'
        })
    
    large_breaks = output_df[output_df['amount'] > 1000]
    if len(large_breaks) > 0:
        alerts.append({
            'severity': 'high',
            'message': f'Materiality threshold exceeded: {len(large_breaks)} breaks > £1,000'
        })
    
    if alerts:
        # Publish to Event Hub → trigger Logic App
        return alerts
    else:
        # Silent pass; no escalation needed
        return []

# Logic App trigger: if alerts exist, send email + conditional Slack ping
```

**Why separate alerts:**
- **Technical failures require immediate eng response** (blocking issue, retry or manual fix)
- **Data quality issues require business review** (non-blocking; can proceed with manual workaround)
- Prevents alert fatigue; Finance is not paged for data anomalies, Eng is not emailed about business metrics

---

### 6. Credentials & Secrets Management

**Question:** How does credentials and secrets flow through the system? How does each component authenticate to the next?

**Answer:**

**Architecture: Managed Identities + Azure Key Vault**

```
┌─────────────────────────────────────────────────────────────┐
│ Azure Key Vault                                             │
│ ├── cloud-dw-connection-string (source system credentials)  │
│ ├── adls-storage-account-key (ADLS access)                  │
│ ├── synapse-connection-string (destination Synapse)         │
│ ├── databricks-api-token (Databricks job execution)         │
│ └── slack-webhook-url (for notifications)                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   ┌────────────────┐   ┌──────────────────┐
   │ Azure Data     │   │ Azure Databricks │
   │ Factory        │   │ (reconciliation  │
   │ (Managed ID)   │   │  engine)         │
   │                │   │ (Managed ID)     │
   └────────────────┘   └──────────────────┘
        │                     │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │ ADLS Gen2           │
        │ (Stored as Parquet) │
        └─────────────────────┘
        
        └────────────┬────────────┐
                     │            │
                ┌────▼───┐   ┌────▼────────┐
                │ Synapse│   │Logic App    │
                │ (SQL   │   │(via webhook)│
                │on-dem) │   │             │
                └────────┘   └─────────────┘
```

**Flow (no secrets in logs):**

1. **ADF → Cloud Data Warehouse:**
   - Managed Identity (ADF system-assigned)
   - Assigned Reader role on cloud DW
   - Uses Azure Key Vault reference for connection string (encrypted at rest)
   - No plaintext credentials in pipeline definition
   ```json
   {
     "type": "LinkedService",
     "name": "CloudDW",
     "properties": {
       "type": "AzureSqlDatabase",
       "typeProperties": {
         "connectionString": "@{linkedService().secretName}",
         "keyVaultSecret": {
           "secretName": "cloud-dw-connection",
           "store": "AzureKeyVault"
         }
       }
     }
   }
   ```

2. **ADF → ADLS Gen2:**
   - Managed Identity (ADF system-assigned)
   - Assigned "Storage Blob Data Contributor" role on ADLS
   - No storage account keys exposed

3. **Databricks → ADLS Gen2:**
   - Cluster configured with managed identity
   - IAM assignment: Databricks Service Principal → ADLS "Storage Blob Data Reader" role
   - At runtime: Databricks obtains token via MSI, authenticates to ADLS

4. **Databricks → Synapse:**
   - Connection string stored in Databricks Secrets API (encrypted)
   - Retrieve at runtime:
     ```python
     connection_string = dbutils.secrets.get(scope="synapse", key="connection-string")
     ```

5. **Logic App → Slack / Email:**
   - Slack webhook URL stored in Key Vault
   - Logic App retrieves secret dynamically
   - Webhook URL never logged or exposed in run history

6. **Audit & Rotation:**
   - All secret accesses logged in Azure Key Vault audit trail
   - Rotation policy: quarterly
   - Pre-rotation validation: test new secret against all systems before deactivating old one

**Why this approach:**
- **Zero secrets in code/config:** All secrets retrieved at runtime from Key Vault
- **Audit trail:** Every secret access logged and monitored
- **Easy rotation:** Update Key Vault secret; all consumers automatically use new value on next execution
- **Least privilege:** Managed identities assigned only the minimum roles needed

---

### 7. Cost Analysis

**Question:** What is the rough monthly cost? Where would cost grow if the organisation added 20 more similar reconciliations?

**Answer:**

**Monthly Cost Estimate (Single Reconciliation):**

| Component | Estimate | Notes |
|-----------|----------|-------|
| **Azure Data Factory** | £50 | 30 Copy Activities + 1 Stored Procedure (DIU cost + runs) |
| **ADLS Gen2 Storage** | £80 | 3 CSV copies/day × 30 days + output (30 GB stored) |
| **Azure Synapse (SQL on-demand)** | £150 | 1 hour/day query execution @ 5 DPU (ad-hoc pricing) |
| **Databricks (reconciliation engine)** | £200 | All-purpose cluster, 8 hours/month (1-node, minimal) |
| **Key Vault** | £5 | 10 secret operations/day × 30 (retrieval operations) |
| **Action Group / Logic App** | £5 | Email + Slack notifications |
| **Network (ExpressRoute)** | £100 | (shared; dedicated ER circuit, amortized) |
| **Monitoring & Logging** | £20 | EventHub ingestion + Log Analytics retention |
| **Data Transfer** | £0 | Private network (no egress charges) |
| **SUBTOTAL** | **~£610** | Per reconciliation, per month |

**Scaling: 20 Similar Reconciliations**

```
Scenario: Adding 20 more reconciliations (same structure, different data)

Single reconciliation cost breakdown:
  - Fixed (ADF, networking, monitoring): £375/month
  - Variable (storage, compute, queries): £235/month

20 reconciliations (marginal cost model):
  - Fixed costs (shared): +£375 (same ADF instance, monitoring)
  - Variable costs (21 total): 235 × 21 = £4,935
  - Optimization: Batch Synapse queries, consolidate Databricks clusters
  
  Revised estimate:
    - ADF: £100 (shared across 21)
    - ADLS: £1,200 (output × 21 reconciliations)
    - Synapse: £1,500 (consolidated queries, shared compute)
    - Databricks: £2,000 (Shared cluster pools, distributed jobs)
    - Other (Vault, networking, monitoring): £500
  
  TOTAL: ~£5,300/month for 21 reconciliations
  Per-reconciliation average: £252 (vs. £610 for single)
  
  Savings from scale: Configuration-driven approach (reusable pipeline) = 50-60% cost reduction
```

**Cost Optimization Strategies:**
1. **Consolidate storage:** All reconciliations → single ADLS hierarchy (partition by reconciliation_type)
2. **Shared Databricks cluster:** One auto-scaling cluster runs all 21 reconciliation engines (via job pools)
3. **Synapse materialization:** Pre-aggregate results into Synapse fact tables (vs. on-demand queries)
4. **Scheduled queries:** Batch Synapse refresh at 08:00 UTC (after all pipelines complete) = parallelized compute

**Budget Monitoring:**
- Azure Cost Management: Alert if monthly spend > £5,500 (for 21 reconciliations)
- ADF audit: Log run count, duration, and DPU usage for chargeback
- Databricks: Enable cluster tagging by reconciliation type for cost allocation

---

### 8. Reusability for Future Reconciliations

**Question:** What part of your design is reusable for future reconciliations, and what part would need to be rewritten?

**Answer:**

**Reusable Components (80% of system):**
```
✓ REUSABLE: ADF pipeline structure
  - Copy Activity pattern (source → ADLS raw landing)
  - Scheduling framework (06:00 UTC daily, date logic, retries)
  - Validation framework (row count checks, schema validation)
  - Orchestration (sequential/parallel task DAG)
  - Alerting framework (Action Groups, Logic Apps)
  
  Effort to reuse: Parameterize the pipeline
    - Replace hardcoded table names with parameters
    - Create pipeline template (ARM template)
    - Specify for new reconciliation: source connection, table names, business_date format
    - ~2 hours setup per new reconciliation

✓ REUSABLE: Storage & partitioning scheme
  - ADLS folder structure: /raw/, /staging/, /output/, /archive/
  - Partition by date (YYYY/MM/DD)
  - Materialized views in Synapse
  - Retention policies (90 days raw, indefinite archive)
  - Apply to all reconciliations (no changes needed)

✓ REUSABLE: Alerting framework
  - Action Group (materiality threshold, failure alerts)
  - Logic App (email + Slack)
  - Only change: recipient email, Slack channel
  - Applies to all reconciliations (copy + parameterize)

✓ REUSABLE: Secrets management
  - Key Vault references for all connections
  - Managed identity pattern
  - No secrets in code
  - Works for any reconciliation (no changes needed)

✓ REUSABLE: Monitoring & logging
  - ADF run history, error logging
  - EventHub pipeline for alerts
  - Log Analytics queries
  - Applies to all (no changes needed)
```

**Custom Development (20% of system):**
```
✗ CUSTOM: Reconciliation engine logic
  - Part C: Configuration-driven approach means:
    - Core engine is reusable (Python/PySpark reconciliation library)
    - Config file is new for each reconciliation
    - Example for this exercise: loan-to-bank reconciliation config
    - Example for new reconciliation: supplier-invoice-to-PO reconciliation
  - Effort: 4-6 hours to write and test new config (not new code)

✗ CUSTOM: Synapse views & aggregations
  - fact tables structure may differ by reconciliation
  - Loan reconciliation: matched_transactions, breaks, per-account_summary
  - Supplier reconciliation: might need per-supplier_summary, invoice_aging, etc.
  - Effort: 2-3 hours to design views (SQL template for common patterns)

✗ CUSTOM: Power BI dashboards
  - Different metrics/dimensions per reconciliation type
  - Loan: breaks by account, product, status
  - Supplier: breaks by supplier, invoice date, amount
  - Effort: 4-8 hours (Power BI template reduces this to 2 hours)
```

**Reusability Summary:**

| Phase | Reusable | Effort for New Reconciliation |
|-------|----------|-------------------------------|
| Ingestion | 95% | 1 hour (update source connection + table names) |
| Orchestration | 100% | 0 hours (ADF template deployed as-is) |
| Reconciliation logic | ~30% (engine core) | 6 hours (write + test config) |
| Storage & archival | 100% | 0 hours |
| Alerting | 100% | 0.5 hour (update recipient list) |
| BI & reporting | 50% (template) | 4 hours (customize dashboard) |
| **TOTAL** | **~80%** | **~11-12 hours** |

**Comparison to bespoke approach:**
- Bespoke (no config-driven engine): 40-60 hours per reconciliation
- Reusable (config-driven): 11-12 hours per new reconciliation
- **Time savings: 73-80% per reconciliation after first one**

**Path to Full Reusability:**
1. **Phase 1 (this exercise):** Build for loan-to-bank reconciliation
2. **Phase 2:** Extract reconciliation engine into reusable library (PyPI package)
3. **Phase 3:** Create config templates for common patterns (2-table join, 3-table, N-table)
4. **Phase 4:** Package ADF + Synapse + BI as reusable ARM template
   - New reconciliation: Update config file, deploy template, run
   - Effort per new reconciliation: 2-3 hours

---

## Summary

| Question | Answer |
|----------|--------|
| Data ingestion | ADLS Gen2 landing zone via ADF (private network, scheduled) |
| Pipeline schedule | ADF daily @ 06:00 UK time, processes day T-1 data |
| Re-processing | Safe via dated partitions; rollback via snapshots |
| Output consumption | Synapse materialized views → Power BI dashboards + email reports |
| Alert strategy | Two channels: technical failures (Eng) vs. data issues (Finance) |
| Secrets management | Azure Key Vault + Managed Identities (zero secrets in code) |
| Monthly cost | ~£610 single reconciliation; ~£5,300 for 21 reconciliations (50-60% savings at scale) |
| Reusability | 80% reusable; new reconciliation = 11-12 hours (vs. 40-60 hours bespoke) |

