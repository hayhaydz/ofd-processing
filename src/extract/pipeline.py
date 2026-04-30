"""Main processing pipeline.

Orchestrates:
1. Text extraction (pdfplumber or PyMuPDF)
2. CSV parsing (Monzo exports)
3. Transaction parsing
4. CSV output generation
"""

from pathlib import Path
from typing import Optional

from src.extract.raw_text import extract_text_pdfplumber, extract_text_pymupdf
from src.extract.transaction_parser import TransactionParser
from src.extract.csv_parser import CSVParser, parse_csv_file, parse_csv_directory
from src.output.csv_writer import write_csv, write_csv_with_metadata


def process_pdf(
    pdf_path: str | Path,
    backend: str = "both",
    output_dir: Optional[str | Path] = None,
) -> tuple[list[dict], list[str]]:
    """Process a single PDF file.

    Args:
        pdf_path: Path to PDF file.
        backend: "pdfplumber", "pymupdf", or "both".
        output_dir: Directory to write output CSVs.

    Returns:
        Tuple of (list of transaction dicts, list of raw extracted texts).
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract text
    if backend == "both":
        text = _extract_both_backends(pdf_path)
    elif backend == "pdfplumber":
        text = extract_text_pdfplumber(pdf_path)
    elif backend == "pymupdf":
        text = extract_text_pymupdf(pdf_path)
    else:
        raise ValueError(f"Unknown backend: {backend}")

    # Parse transactions
    parser = TransactionParser()
    all_transactions = []

    for page_text in text:
        transactions = parser.parse(page_text)
        all_transactions.extend(transactions)

    # Remove duplicates (same date + description + amount)
    seen = set()
    unique_transactions = []
    for t in all_transactions:
        key = (t.date, t.description.lower(), t.amount)
        if key not in seen:
            seen.add(key)
            unique_transactions.append(t)

    # Write CSV
    if unique_transactions:
        csv_path = output_dir / f"{pdf_path.stem}.csv"
        write_csv(unique_transactions, csv_path, template="full")

        # Also write with metadata header
        meta_csv_path = output_dir / f"{pdf_path.stem}_meta.csv"
        write_csv_with_metadata(unique_transactions, meta_csv_path)

    # Write raw extracted text for debugging
    raw_text_path = output_dir / f"{pdf_path.stem}_raw.txt"
    with open(raw_text_path, "w", encoding="utf-8") as f:
        for text in text:
            f.write(text)
            f.write("\n\n" + "="*60 + "\n\n")

    return [t.__dict__ for t in unique_transactions], text


def process_csv(
    csv_path: str | Path,
    output_dir: Optional[str | Path] = None,
) -> list[dict]:
    """Process a single CSV file (Monzo export).

    Args:
        csv_path: Path to CSV file.
        output_dir: Directory to write output CSV.

    Returns:
        List of transaction dicts.
    """
    csv_path = Path(csv_path)
    output_dir = Path(output_dir) if output_dir else Path.cwd() / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Parsing CSV: {csv_path.name}")

    # Parse CSV using CSVParser
    parser = CSVParser()
    transactions = parser.parse(csv_path)

    print(f"  Found {len(transactions)} transactions")

    # Write CSV
    csv_path_out = output_dir / f"{csv_path.stem}.csv"
    write_csv(transactions, csv_path_out, template="full")

    return [t.__dict__ for t in transactions]


def process_multiple_inputs(
    input_paths: list[str | Path],
    backend: str = "both",
    output_dir: Optional[str | Path] = None,
) -> list[dict]:
    """Process multiple PDF and/or CSV files.

    Args:
        input_paths: List of PDF paths, CSV paths, or directories.
        backend: Extraction backend for PDFs.
        output_dir: Output directory.

    Returns:
        List of all transactions from all inputs.
    """
    all_transactions = []

    for input_path in input_paths:
        input_path = Path(input_path)

        # Check if it's a CSV file
        if input_path.suffix.lower() == ".csv" and "monzo" in input_path.name.lower():
            # CSV file - use CSV parser
            transactions = process_csv(input_path, output_dir)
            all_transactions.extend(transactions)

        # Check if it's a directory with CSV files
        elif input_path.is_dir():
            csv_files = sorted(input_path.glob("MonzoDataExport*.csv"))
            csv_files.extend(sorted(input_path.glob("FlexMonzoDataExport*.csv")))

            if csv_files:
                print(f"Found {len(csv_files)} CSV file(s) in {input_path}")
                for csv_path in csv_files:
                    transactions = process_csv(csv_path, output_dir)
                    all_transactions.extend(transactions)

        # Check if it's a PDF file
        elif input_path.suffix.lower() == ".pdf":
            # PDF file - use PDF parser
            transactions, _ = process_pdf(input_path, backend, output_dir)
            all_transactions.extend(transactions)

        # Check if it's a directory (collect PDFs)
        elif input_path.is_dir():
            pdfs = sorted(input_path.glob("*.pdf"))
            if pdfs:
                print(f"Found {len(pdfs)} PDF(s) in {input_path}")
                for pdf_path in pdfs:
                    transactions, _ = process_pdf(pdf_path, backend, output_dir)
                    all_transactions.extend(transactions)

        else:
            print(f"[warn] Skipping {input_path} (not a recognized file type)")

    return all_transactions


def _extract_both_backends(pdf_path: Path) -> list[str]:
    """Extract text using both backends and merge."""
    text_plumber = extract_text_pdfplumber(pdf_path)
    text_mupdf = extract_text_pymupdf(pdf_path)

    # Merge: prefer plumber, fall back to mupdf
    merged = []
    for i, (plumber_text, mupdf_text) in enumerate(zip(text_plumber, text_mupdf)):
        plumber_cleaned = plumber_text.replace("CropBox missing", "")
        mupdf_cleaned = mupdf_text.replace("CropBox missing", "")
        merged.append(plumber_cleaned or mupdf_cleaned)

    # If lengths differ, extend with remaining pages
    for text in text_plumber[len(merged):]:
        merged.append(text)
    for text in text_mupdf[len(merged):]:
        merged.append(text)

    return merged


def process_multiple_pdfs(
    pdf_paths: list[str | Path],
    backend: str = "both",
    output_dir: Optional[str | Path] = None,
) -> list[dict]:
    """Process multiple PDF files.

    Args:
        pdf_paths: List of PDF paths or directories.
        backend: Extraction backend.
        output_dir: Output directory.

    Returns:
        List of all transactions from all PDFs.
    """
    all_transactions = []

    for pdf_path in pdf_paths:
        pdf_path = Path(pdf_path)
        if pdf_path.is_dir():
            pdfs = list(pdf_path.glob("*.pdf"))
        elif pdf_path.is_file() and pdf_path.suffix.lower() == ".pdf":
            pdfs = [pdf_path]
        else:
            print(f"[warn] Skipping {pdf_path} (not a PDF or directory)")
            continue

        transactions = process_pdf(pdf_path, backend, output_dir)
        all_transactions.extend(transactions)

    return all_transactions
