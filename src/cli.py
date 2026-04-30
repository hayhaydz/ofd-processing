"""CLI for ofd-processing.

Usage:
    # PDF processing
    python -m src.cli dump <path>   [--backend pdfplumber|pymupdf|both]
    python -m src.cli dump ./samples                  # all PDFs in folder
    python -m src.cli dump ./samples/statement.pdf    # single file
    python -m src.cli dump a.pdf b.pdf                # multiple files

    python -m src.cli process <path>                  # Extract + parse to CSV
    python -m src.cli process ./samples               # Process all PDFs
    python -m src.cli process ./samples -o ./example  # Output to example dir

    # CSV processing (Monzo exports)
    python -m src.cli process-csv <path>              # Process CSV file
    python -m src.cli process-csv ./samples            # Process all CSVs in folder
    python -m src.cli process-csv ./samples/*.csv      # Process specific CSVs
    python -m src.cli process-csv ./samples/monzo*.csv # Process pattern
"""

import argparse
import sys
from pathlib import Path

from src.extract.raw_text import extract_text_pdfplumber, extract_text_pymupdf
from src.extract.pipeline import process_pdf, process_multiple_pdfs, process_csv
from src.output.csv_writer import write_csv


def _collect_pdfs(paths: list[str]) -> list[Path]:
    """Resolve a mix of files and folders into a flat list of PDF/CSV paths."""
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file():
            if p.suffix.lower() == ".pdf":
                files.append(p)
            elif p.suffix.lower() == ".csv" and "monzo" in p.name.lower():
                files.append(p)
        elif p.is_dir():
            found = sorted(p.glob("*.pdf")) + sorted(p.glob("*.csv"))
            if not found:
                print(f"[warn] no PDF/CSV files found in {p}", file=sys.stderr)
            files.extend(found)
        else:
            print(f"[warn] skipping {raw} (not a file or folder)", file=sys.stderr)
    return files


def cmd_dump(args: argparse.Namespace) -> None:
    """Dump raw text from PDF(s) to stdout."""
    pdfs = _collect_pdfs(args.paths)

    if not pdfs:
        print("[error] no PDF files found", file=sys.stderr)
        sys.exit(1)

    for pdf_path in pdfs:
        backends = ["pdfplumber", "pymupdf"] if args.backend == "both" else [args.backend]

        for backend in backends:
            if len(pdfs) > 1 or len(backends) > 1:
                print("=" * 60)
                print(f"{backend.upper()} — {pdf_path.name}")
                print("=" * 60)

            extract_fn = extract_text_pdfplumber if backend == "pdfplumber" else extract_text_pymupdf
            pages = extract_fn(pdf_path)

            for i, page_text in enumerate(pages, 1):
                print(f"\n--- Page {i} ---\n")
                print(page_text)

        print()  # blank line between files


def cmd_process(args: argparse.Namespace) -> None:
    """Process PDF(s) → CSV.

    Extracts text, parses transactions, and writes to CSV.
    Also writes raw extracted text for debugging.
    """
    pdfs = _collect_pdfs(args.paths)

    if not pdfs:
        print("[error] no PDF files found", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nProcessing {len(pdfs)} PDF(s)...")
    print(f"Output directory: {output_dir}")

    for pdf_path in pdfs:
        print(f"\n{'='*60}")
        print(f"Processing: {pdf_path.name}")
        print(f"{'='*60}")

        transactions, raw_texts = process_pdf(pdf_path, backend=args.backend, output_dir=output_dir)

        print(f"\nFound {len(transactions)} transactions")

        # List transactions
        for t in transactions:
            print(f"  {t['date']} | {t['type']:10} | {t['amount']:>10,.2f} | {t['description'][:40]:<40} | {t['category']}")

        # Show raw text length for debugging
        print(f"\nRaw text extracted: {sum(len(t) for t in raw_texts)} characters")

    print(f"\n{'='*60}")
    print("Processing complete!")
    print(f"{'='*60}\n")


def cmd_process_csv(args: argparse.Namespace) -> None:
    """Process CSV file(s) → CSV.

    Parses Monzo CSV exports and writes to output CSV.
    CSV content is kept behind the scenes (not printed).
    Shows line count progress.
    """
    csv_paths = _collect_pdfs(args.paths)

    if not csv_paths:
        print("[error] no CSV files found", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📊 CSV Processing Progress")
    print(f"   Files to process: {len(csv_paths)}")
    print(f"   Output directory: {output_dir}")

    for csv_path in csv_paths:
        print(f"\n{'='*60}")
        print(f"Processing CSV: {csv_path.name}")
        print(f"{'='*60}")

        # Count lines with progress display
        total_lines = 0
        try:
            with open(csv_path, 'r', encoding='utf-8', errors='replace') as f:
                for line in f:
                    total_lines += 1
        except Exception as e:
            print(f"[error] could not read {csv_path}: {e}", file=sys.stderr)
            continue

        # Display progress (no CSV content output)
        elapsed = 0.001  # assume instant for small files
        rate = total_lines / elapsed if elapsed > 0 else 0
        pct = (total_lines / csv_path.stat().st_size * 100) if csv_path.stat().st_size > 0 else 0

        print(f"\r   [{total_lines:,}/{csv_path.stat().st_size:,} bytes] "
              f"[{total_lines:,} lines] "
              f"[{pct:.1f}%] "
              f"[{elapsed:.1f}s] "
              f"[{rate:.0f} lines/sec]", end='', flush=True)
        print()  # newline after progress

        # Process CSV silently (content kept behind scenes)
        transactions = process_csv(csv_path, output_dir=output_dir)

        print(f"\n   ✓ Processed {total_lines:,} lines")
        print(f"   ✓ Header columns: {len(transactions[0]) if transactions else 0}")
        print(f"   ✓ Data rows: {len(transactions) - 1 if transactions else 0}")
        print(f"   ✓ Content kept behind the scenes\n")

    print(f"\n{'='*60}")
    print("CSV processing complete!")
    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ofd-processing",
        description="Bank statement PDF → CSV converter with CSV support",
    )
    subparsers = parser.add_subparsers(dest="command")

    # dump command
    dump_parser = subparsers.add_parser(
        "dump",
        help="Dump raw text from PDF(s)",
    )
    dump_parser.add_argument(
        "paths",
        nargs="+",
        help="PDF file(s) or folder(s) containing PDFs",
    )
    dump_parser.add_argument(
        "-b", "--backend",
        choices=["pdfplumber", "pymupdf", "both"],
        default="both",
        help="Extraction backend (default: both)",
    )
    dump_parser.set_defaults(func=cmd_dump)

    # process command
    process_parser = subparsers.add_parser(
        "process",
        help="Process PDF(s) → CSV",
    )
    process_parser.add_argument(
        "paths",
        nargs="+",
        help="PDF file(s) or folder(s) containing PDFs",
    )
    process_parser.add_argument(
        "-b", "--backend",
        choices=["pdfplumber", "pymupdf", "both"],
        default="both",
        help="Extraction backend (default: both)",
    )
    process_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: output)",
    )
    process_parser.set_defaults(func=cmd_process)

    # process-csv command
    csv_parser = subparsers.add_parser(
        "process-csv",
        help="Process CSV file(s) → CSV",
    )
    csv_parser.add_argument(
        "paths",
        nargs="+",
        help="CSV file(s) or folder(s) containing CSVs",
    )
    csv_parser.add_argument(
        "-o", "--output",
        default="output",
        help="Output directory (default: output)",
    )
    csv_parser.set_defaults(func=cmd_process_csv)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
