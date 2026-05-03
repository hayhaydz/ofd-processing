#!/usr/bin/env python3
"""
Lean Monzo CSV Converter
Reads Monzo CSV exports and outputs transactions in personal finance app format.
Includes CLI reporting and log generation.
"""

import csv
import re
import os
from datetime import datetime
from collections import Counter

# Master ruleset organized by Account Type -> Direction -> Monzo Method
TRANSACTION_RULES = {
    'asset': {
        'out': {  
            'faster payment': 'withdrawal',
            'direct debit / bacs dd': 'withdrawal',
            'standing order': 'withdrawal',
            'monzo-to-monzo': 'transfer_out',
            'pot transfer': 'transfer_out',
            'cash withdrawal / atm': 'withdrawal',
            'card payment': 'charge',
            'fee / charge': 'charge',
        },
        'in': {   
            'faster payment': 'transfer_in',
            'bacs payment': 'deposit',
            'standing order': 'deposit',
            'monzo-to-monzo': 'transfer_in',
            'pot transfer': 'transfer_in',
            'top up': 'transfer_in',
            'cash deposit': 'deposit',
            'cheque': 'deposit',
            'interest': 'interest',
            'card payment': 'value_change',
            'refund': 'value_change',
            'reversal / chargeback': 'value_change',
        }
    },
    'liability': {
        'out': {  
            'flex (purchase)': 'charge',
            'flex (fee)': 'charge',
            'flex (interest)': 'interest_charge',
        },
        'in': {   
            'flex (repayment)': 'payment',
        }
    }
}

# Category mapping
CATEGORY_MAP = {
    'general': 'general',
    'eating out': 'eating_out',
    'expenses': 'expenses',
    'transport': 'transport',
    'cash': 'cash',
    'bills': 'bills',
    'entertainment': 'entertainment',
    'shopping': 'shopping',
    'holidays': 'holidays',
    'groceries': 'groceries',
    'personal care': 'shopping',
    'gifts': 'shopping',
    'family': 'general',
    'charity': 'general',
    'finances': 'bills',
    'education': 'general',
}

class ProcessingStats:
    """Tracks running statistics during the CSV conversion."""
    def __init__(self):
        self.files_processed = 0
        self.records_kept = 0
        self.records_skipped = 0
        self.total_in = 0.0
        self.total_out = 0.0
        self.type_counts = Counter()
        self.category_counts = Counter()

def format_date(date_str: str) -> str:
    """Convert DD/MM/YYYY to YYYY-MM-DD."""
    parts = date_str.split('/')
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    return date_str

def format_description(name: str, description: str, notes: str) -> str:
    """Format description, preserving whitespace and quoting if needed."""
    text = description if description and description != 'Flex' else notes if notes else ''
    if not description and notes and notes.strip() and not notes.strip().startswith('🔒'):
        text += ' | ' + notes.strip()
    return text[:500]

def map_type(row: dict, is_asset: bool) -> str:
    """Map Monzo Type to app type based on amount direction first."""
    try:
        amount = float(row.get('Amount', 0))
    except (ValueError, TypeError):
        amount = 0.0

    direction = 'in' if amount > 0 else 'out'
    account_context = 'asset' if is_asset else 'liability'
    
    raw_type = row.get('Type', '').lower().strip()
    clean_type = re.sub(r'\s*\((in|out)\)', '', raw_type)
    
    mapped_type = TRANSACTION_RULES[account_context][direction].get(clean_type)
    
    if mapped_type:
        return mapped_type
        
    if account_context == 'asset':
        return 'deposit' if direction == 'in' else 'withdrawal'
    else:
        return 'payment' if direction == 'in' else 'charge'

def map_category(category: str) -> str:
    """Map Monzo Category to app category."""
    if not category:
        return ''
    return CATEGORY_MAP.get(category.lower().strip(), '')

def process_row(row: dict, is_asset: bool, stats: ProcessingStats) -> dict:
    """Process a single row and update running stats."""
    # Track skips for declined or zero-amount
    if 'decline' in row.get('Type', '').lower():
        stats.records_skipped += 1
        return None
    
    try:
        amount = float(row.get('Amount', 0))
        if abs(amount) < 0.01:
            stats.records_skipped += 1
            return None
    except (ValueError, TypeError):
        stats.records_skipped += 1
        return None
    
    # Process valid record
    record_type = map_type(row, is_asset)
    category = map_category(row.get('Category', ''))
    
    # Update Stats
    stats.records_kept += 1
    if amount > 0:
        stats.total_in += amount
    else:
        stats.total_out += amount
        
    stats.type_counts[record_type] += 1
    if category:
        stats.category_counts[category] += 1

    return {
        'date': format_date(row.get('Date', '')),
        'type': record_type,
        'amount': amount,
        'description': format_description(
            row.get('Name', ''),
            row.get('Description', ''),
            row.get('Notes and #tags', '')
        ),
        'category': category,
    }

def generate_report(stats: ProcessingStats) -> str:
    """Generates a formatted text summary of the processing run."""
    lines = []
    lines.append("==================================================")
    lines.append("           MONZO CSV CONVERSION SUMMARY           ")
    lines.append("==================================================")
    lines.append(f"Run Date:          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Files Processed:   {stats.files_processed}")
    lines.append(f"Records Kept:      {stats.records_kept}")
    lines.append(f"Records Skipped:   {stats.records_skipped} (declines/zero-amounts)")
    lines.append("--------------------------------------------------")
    lines.append("💰 FINANCIAL TOTALS")
    lines.append(f"Total Money In:   +£{stats.total_in:,.2f}")
    lines.append(f"Total Money Out:   £{stats.total_out:,.2f}")
    lines.append(f"Net Change:        £{(stats.total_in + stats.total_out):,.2f}")
    lines.append("--------------------------------------------------")
    lines.append("📊 TRANSACTION TYPES (TOP 5)")
    for t_type, count in stats.type_counts.most_common(5):
        lines.append(f"  - {t_type:<18} {count} txns")
    lines.append("--------------------------------------------------")
    lines.append("🛒 TOP CATEGORIES")
    for cat, count in stats.category_counts.most_common(5):
        lines.append(f"  - {cat:<18} {count} txns")
    lines.append("==================================================")
    
    return "\n".join(lines)

def main():
    samples_dir = './samples'
    output_dir = './output'
    logs_dir = './logs'
    
    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    
    stats = ProcessingStats()
    
    files_to_process = [f for f in sorted(os.listdir(samples_dir)) 
                        if f.startswith(('current_MonzoDataExport_', 'flex_MonzoDataExport_'))]
    
    if not files_to_process:
        print(f"No valid Monzo CSV files found in {samples_dir}.")
        return

    for filename in files_to_process:
        filepath = os.path.join(samples_dir, filename)
        is_asset = filename.startswith('current_MonzoDataExport_')
        
        base_name = filename.replace('current_MonzoDataExport_', '').replace('flex_MonzoDataExport_', '')
        if base_name.endswith('.csv'):
            base_name = base_name[:-4]
            
        output_filename = f"{base_name}_transactions.csv"
        output_path = os.path.join(output_dir, output_filename)
        
        records = []
        stats.files_processed += 1
        
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                record = process_row(row, is_asset, stats)
                if record:
                    records.append(record)
        
        records.sort(key=lambda r: r['date'])
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'type', 'amount', 'description', 'category'])
            for record in records:
                writer.writerow([
                    record['date'], record['type'], record['amount'],
                    record['description'], record['category']
                ])

    # Generate and handle the report
    report = generate_report(stats)
    
    # Print to CLI
    print(report)
    
    # Save to Log file
    log_filename = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_filepath = os.path.join(logs_dir, log_filename)
    with open(log_filepath, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\n📝 Log saved to: {log_filepath}")

if __name__ == '__main__':
    main()