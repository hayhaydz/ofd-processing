#!/usr/bin/env python3
"""
CSV Processor - Process CSV files silently with line count progress display.

Usage:
    python csv_processor.py <file.csv> [--count-only] [--progress-interval N]

Features:
- Reads CSV content behind the scenes (no output to CLI)
- Displays line count progress
- Returns processed data to stdout only when needed
"""

import csv
import sys
import time
from pathlib import Path
from typing import Optional, Iterator, List, Dict, Any


def read_csv_silently(filepath: str) -> Iterator[List[str]]:
    """
    Read CSV file silently (no output to stdout).
    Returns an iterator over rows.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f)
        for row in reader:
            yield row


def process_csv_silently(
    filepath: str,
    progress_interval: int = 100,
    show_header: bool = True
) -> Dict[str, Any]:
    """
    Process CSV file silently with progress display.
    
    Args:
        filepath: Path to CSV file
        progress_interval: Show progress every N lines
        show_header: Show file header info
    
    Returns:
        Dictionary with:
            - total_lines: Total lines in file
            - header: First row (header)
            - data_rows: List of data rows
            - processed: True
    """
    start_time = time.time()
    
    # Read file silently
    rows = list(read_csv_silently(filepath))
    
    total_lines = len(rows)
    header = rows[0] if rows else []
    data_rows = rows[1:] if len(rows) > 1 else []
    
    # Calculate progress
    elapsed = time.time() - start_time
    rate = total_lines / elapsed if elapsed > 0 else 0
    
    # Display progress (no CSV content output)
    if show_header:
        print(f"\n📊 CSV Processing Progress")
        print(f"   File: {filepath}")
        print(f"   Total lines: {total_lines:,}")
        print(f"   Header columns: {len(header)}")
        print(f"   Data rows: {len(data_rows):,}")
        print(f"   Processing time: {elapsed:.2f}s ({rate:.0f} lines/sec)")
        print(f"   ✓ Content kept behind the scenes\n")
    
    return {
        'total_lines': total_lines,
        'header': header,
        'data_rows': data_rows,
        'processed': True
    }


def count_lines_progress(filepath: str, interval: int = 100) -> int:
    """
    Count lines in CSV with progress display.
    
    Args:
        filepath: Path to CSV file
        interval: Show progress every N lines
    
    Returns:
        Total line count
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filepath}")
    
    total = 0
    last_report = 0
    start_time = time.time()
    
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            total += 1
            
            # Show progress at intervals
            if total - last_report >= interval:
                elapsed = time.time() - start_time
                rate = total / elapsed if elapsed > 0 else 0
                pct = (total / path.stat().st_size * 100) if path.stat().st_size > 0 else 0
                
                print(f"\r   [{total:,}/{path.stat().st_size:,} bytes] "
                      f"[{total:,} lines] "
                      f"[{pct:.1f}%] "
                      f"[{elapsed:.1f}s] "
                      f"[{rate:.0f} lines/sec]", end='', flush=True)
                last_report = total
    
    print()  # Newline after progress
    return total


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    filepath = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'process'
    interval = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    
    try:
        if mode == 'count':
            # Just count lines with progress, no content output
            total = count_lines_progress(filepath, interval)
            print(f"\n📈 Total lines: {total:,}")
            sys.exit(0)
        
        elif mode == 'process':
            # Process CSV silently with progress
            result = process_csv_silently(filepath, interval)
            # Output only metadata, not CSV content
            print(f"Processed {result['total_lines']:,} lines")
            print(f"Header: {result['header']}")
            print(f"Data rows: {len(result['data_rows']):,}")
            sys.exit(0)
        
        else:
            print(f"Unknown mode: {mode}")
            print("Use: count <file> or process <file>")
            sys.exit(1)
    
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error processing CSV: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
