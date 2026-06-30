#!/usr/bin/env python3
"""
Configuration-driven Reconciliation Engine
Language: Python (pandas + no heavy dependencies for portability)

This engine takes a config file describing two tables and produces:
  - matched transactions (both sides agree)
  - mismatches (matched but amounts differ)
  - breaks (exist in one system only)
  - duplicates (same key multiple times in same table)
  - account_summary (per-account reconciliation status)

Usage:
  python reconciliation_engine.py --config reconciliation_config.yaml --output-dir ./output
"""

import pandas as pd
import yaml
import argparse
import logging
from typing import Dict, List, Tuple
from datetime import datetime
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReconciliationEngine:
    def __init__(self, config_path: str, output_dir: str = './output'):
        self.config_path = config_path
        self.output_dir = output_dir
        self.config = self._load_config()
        self.left_df = None
        self.right_df = None
        self.reference_df = None
        self.summary = {}

    def _load_config(self) -> Dict:
        """Load YAML config file"""
        logger.info(f"Loading config from {self.config_path}")
        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)
        logger.info(f"Reconciliation: {config['reconciliation']['name']}")
        return config

    def load_data(self) -> None:
        """Load left, right, and optional reference DataFrames"""
        recon_config = self.config['reconciliation']
        sources = self.config['sources']

        # Load left table
        left_source = sources['left']
        logger.info(f"Loading left table: {left_source['name']} from {left_source['path']}")
        self.left_df = pd.read_csv(left_source['path'])
        logger.info(f"  → {len(self.left_df)} rows loaded")

        # Load right table
        right_source = sources['right']
        logger.info(f"Loading right table: {right_source['name']} from {right_source['path']}")
        self.right_df = pd.read_csv(right_source['path'])
        logger.info(f"  → {len(self.right_df)} rows loaded")

        # Load optional reference table
        if 'reference' in sources:
            reference_source = sources['reference']
            logger.info(f"Loading reference table: {reference_source['name']} from {reference_source['path']}")
            self.reference_df = pd.read_csv(reference_source['path'])
            logger.info(f"  → {len(self.reference_df)} rows loaded")

    def _apply_exclusions(self) -> None:
        """Filter out transactions based on exclusion rules"""
        config = self.config['transaction_classification']

        # Apply left exclusions
        if config['left_excludes']:
            logger.info("Applying left table exclusions...")
            for exclusion in config['left_excludes']:
                field = exclusion['field']
                values = exclusion['values']
                reason = exclusion.get('reason', '')

                before = len(self.left_df)
                self.left_df = self.left_df[~self.left_df[field].isin(values)]
                after = len(self.left_df)

                logger.info(f"  Excluded {before - after} rows where {field} in {values} ({reason})")

    def _detect_duplicates(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Detect duplicate join keys in each table"""
        join_config = self.config['join_logic']
        join_keys = [k['left_field'] for k in join_config['keys']]

        logger.info("Detecting duplicates...")

        # Left duplicates
        left_dups = self.left_df[self.left_df.duplicated(subset=join_keys, keep=False)].copy()
        left_dups['source'] = 'LEFT'

        # Right duplicates
        right_dups = self.right_df[self.right_df.duplicated(subset=join_keys, keep=False)].copy()
        right_dups['source'] = 'RIGHT'

        if len(left_dups) > 0:
            logger.info(f"  Found {len(left_dups)} duplicate rows in left table")
        if len(right_dups) > 0:
            logger.info(f"  Found {len(right_dups)} duplicate rows in right table")

        duplicates = pd.concat([left_dups, right_dups], ignore_index=True)
        return left_dups, right_dups, duplicates

    def _perform_join(self) -> pd.DataFrame:
        """Join left and right tables on configured keys"""
        join_config = self.config['join_logic']
        join_keys = join_config['keys']

        logger.info(f"Performing join on {len(join_keys)} key(s)...")

        # Prepare join columns
        left_cols = [k['left_field'] for k in join_keys]
        right_cols = [k['right_field'] for k in join_keys]

        # Outer join to capture all records from both sides
        merged = self.left_df.merge(
            self.right_df,
            left_on=left_cols,
            right_on=right_cols,
            how='outer',
            indicator=True,
            suffixes=('_left', '_right')
        )

        logger.info(f"  Merged result: {len(merged)} rows")
        logger.info(f"    - Both sides: {len(merged[merged['_merge'] == 'both'])} rows")
        logger.info(f"    - Left only: {len(merged[merged['_merge'] == 'left_only'])} rows")
        logger.info(f"    - Right only: {len(merged[merged['_merge'] == 'right_only'])} rows")

        return merged

    def _compare_amounts(self, merged: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Compare amounts between left and right"""
        amount_config = self.config['amount_matching']
        left_amount = amount_config['left_amount_field']
        right_amount = amount_config['right_amount_field']
        tolerance = amount_config['tolerance']

        logger.info(f"Comparing amounts (tolerance: £{tolerance})...")

        # Filter to matched records only
        matched = merged[merged['_merge'] == 'both'].copy()

        if len(matched) == 0:
            logger.warning("No matched records found")
            return matched[matched['_merge'].isna()], pd.DataFrame(), matched

        # Handle merged column naming: if both tables have same column name, pandas adds _x and _y suffixes
        left_amount_col = f"{left_amount}_left" if f"{left_amount}_left" in matched.columns else left_amount
        right_amount_col = f"{right_amount}_right" if f"{right_amount}_right" in matched.columns else right_amount

        # Convert amounts to float
        matched[left_amount_col] = pd.to_numeric(matched[left_amount_col], errors='coerce')
        matched[right_amount_col] = pd.to_numeric(matched[right_amount_col], errors='coerce')

        # Calculate difference
        matched['amount_difference'] = abs(matched[left_amount_col] - matched[right_amount_col])

        # Categorize
        matched['match_status'] = matched['amount_difference'].apply(
            lambda x: 'MATCHED' if x <= tolerance else 'MISMATCH' if pd.notna(x) else 'NULL_AMOUNT'
        )

        # Split results
        exact_matches = matched[matched['match_status'] == 'MATCHED'].copy()
        mismatches = matched[matched['match_status'] == 'MISMATCH'].copy()

        logger.info(f"  Exact matches (within tolerance): {len(exact_matches)}")
        logger.info(f"  Amount mismatches: {len(mismatches)}")

        return exact_matches, mismatches, matched

    def _identify_breaks(self, merged: pd.DataFrame) -> pd.DataFrame:
        """Identify one-sided transactions (breaks)"""
        logger.info("Identifying breaks (one-sided transactions)...")

        # Left-only and right-only
        left_only = merged[merged['_merge'] == 'left_only'].copy()
        left_only['break_type'] = 'LEFT_ONLY'

        right_only = merged[merged['_merge'] == 'right_only'].copy()
        right_only['break_type'] = 'RIGHT_ONLY'

        breaks = pd.concat([left_only, right_only], ignore_index=True)

        logger.info(f"  Left-only breaks: {len(left_only)}")
        logger.info(f"  Right-only breaks: {len(right_only)}")
        logger.info(f"  Total breaks: {len(breaks)}")

        return breaks

    def _create_account_summary(self, exact_matches: pd.DataFrame, breaks: pd.DataFrame,
                                mismatches: pd.DataFrame) -> pd.DataFrame:
        """Create per-account reconciliation summary"""
        logger.info("Creating per-account summary...")

        account_field = self.config['reconciliation_summary'].get('account_reference_field', 'account_id')

        if account_field not in self.left_df.columns:
            logger.warning(f"Account field '{account_field}' not found in left table")
            return pd.DataFrame()

        # Collect all unique accounts
        accounts = set(self.left_df[account_field].dropna().unique())

        summaries = []
        for account in sorted(accounts):
            account_left = self.left_df[self.left_df[account_field] == account]

            # Count matched transactions
            matched_count = len(exact_matches[exact_matches[account_field] == account]) if account_field in exact_matches.columns else 0

            # Count breaks
            breaks_for_account = breaks[breaks[account_field] == account] if account_field in breaks.columns else pd.DataFrame()
            unmatched_left = len(breaks_for_account[breaks_for_account['break_type'] == 'LEFT_ONLY'])
            unmatched_right = len(breaks_for_account[breaks_for_account['break_type'] == 'RIGHT_ONLY'])

            # Determine status
            if unmatched_left == 0 and unmatched_right == 0:
                status = 'RECONCILED'
            elif unmatched_left > 0 and unmatched_right == 0:
                status = 'LEFT_BREAKS'
            elif unmatched_left == 0 and unmatched_right > 0:
                status = 'RIGHT_BREAKS'
            else:
                status = 'BOTH_SIDES_BREAKS'

            # Add metadata from reference if available
            account_metadata = {}
            if self.reference_df is not None and account_field in self.reference_df.columns:
                ref_row = self.reference_df[self.reference_df[account_field] == account]
                if len(ref_row) > 0:
                    account_metadata = ref_row.iloc[0].to_dict()

            summary = {
                account_field: account,
                'total_left_transactions': len(account_left),
                'matched_transactions': matched_count,
                'unmatched_left': unmatched_left,
                'unmatched_right': unmatched_right,
                'reconciliation_status': status,
                **account_metadata
            }
            summaries.append(summary)

        summary_df = pd.DataFrame(summaries)
        logger.info(f"  Summary for {len(summary_df)} accounts")

        return summary_df

    def run(self) -> Dict:
        """Execute full reconciliation"""
        logger.info("=" * 80)
        logger.info("RECONCILIATION ENGINE START")
        logger.info("=" * 80)

        self.load_data()
        self._apply_exclusions()

        # Detect duplicates
        left_dups, right_dups, all_dups = self._detect_duplicates()

        # Join tables
        merged = self._perform_join()

        # Compare amounts
        exact_matches, mismatches, matched_records = self._compare_amounts(merged)

        # Identify breaks
        breaks = self._identify_breaks(merged)

        # Create account summary
        account_summary = self._create_account_summary(exact_matches, breaks, mismatches)

        # Build summary stats
        self.summary = {
            'reconciliation_name': self.config['reconciliation']['name'],
            'timestamp': datetime.now().isoformat(),
            'input_records': {
                'left_total': len(self.left_df),
                'right_total': len(self.right_df)
            },
            'output_records': {
                'exact_matches': len(exact_matches),
                'mismatches': len(mismatches),
                'breaks': len(breaks),
                'duplicates': len(all_dups)
            },
            'accounts_analyzed': len(account_summary) if len(account_summary) > 0 else 0,
            'accounts_reconciled': len(account_summary[account_summary['reconciliation_status'] == 'RECONCILED']) if len(account_summary) > 0 else 0
        }

        logger.info("=" * 80)
        logger.info("RECONCILIATION ENGINE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Input records: {self.summary['input_records']}")
        logger.info(f"Output records: {self.summary['output_records']}")
        logger.info(f"Accounts reconciled: {self.summary['accounts_reconciled']}/{self.summary['accounts_analyzed']}")

        return {
            'exact_matches': exact_matches,
            'mismatches': mismatches,
            'breaks': breaks,
            'duplicates': all_dups,
            'account_summary': account_summary,
            'summary': self.summary
        }

    def save_outputs(self, results: Dict) -> None:
        """Save reconciliation results to CSV files"""
        logger.info(f"Saving outputs to {self.output_dir}...")

        import os
        os.makedirs(self.output_dir, exist_ok=True)

        # Save each output table
        if len(results['exact_matches']) > 0:
            results['exact_matches'].to_csv(f"{self.output_dir}/matched_transactions.csv", index=False)
            logger.info(f"  ✓ matched_transactions.csv ({len(results['exact_matches'])} rows)")

        if len(results['mismatches']) > 0:
            results['mismatches'].to_csv(f"{self.output_dir}/mismatches.csv", index=False)
            logger.info(f"  ✓ mismatches.csv ({len(results['mismatches'])} rows)")

        if len(results['breaks']) > 0:
            results['breaks'].to_csv(f"{self.output_dir}/breaks.csv", index=False)
            logger.info(f"  ✓ breaks.csv ({len(results['breaks'])} rows)")

        if len(results['duplicates']) > 0:
            results['duplicates'].to_csv(f"{self.output_dir}/duplicates.csv", index=False)
            logger.info(f"  ✓ duplicates.csv ({len(results['duplicates'])} rows)")

        if len(results['account_summary']) > 0:
            results['account_summary'].to_csv(f"{self.output_dir}/account_summary.csv", index=False)
            logger.info(f"  ✓ account_summary.csv ({len(results['account_summary'])} rows)")

        # Save summary as JSON
        with open(f"{self.output_dir}/summary.json", 'w') as f:
            json.dump(results['summary'], f, indent=2)
        logger.info(f"  ✓ summary.json")

def main():
    parser = argparse.ArgumentParser(description="Configuration-driven Reconciliation Engine")
    parser.add_argument('--config', required=True, help='Path to reconciliation config YAML file')
    parser.add_argument('--output-dir', default='./output', help='Output directory for results')

    args = parser.parse_args()

    engine = ReconciliationEngine(args.config, args.output_dir)
    results = engine.run()
    engine.save_outputs(results)

    logger.info("=" * 80)
    logger.info("RECONCILIATION COMPLETE")
    logger.info("=" * 80)

if __name__ == '__main__':
    main()
