"""CLI for ofd-processing.

Usage:
    python -m src.cli dump <path>   [--backend pdfplumber|pymupdf|both]
    python -m src.cli dump ./samples                  # all PDFs in folder
    python -m src.cli dump ./samples/statement.pdf    # single file
    python -m src.cli dump a.pdf b.pdf                # multiple files
"""

import argparse
import sys
from pathlib import Path

from src.extract.raw_text import extract_text_pdfplumber, extract_text_pymupdf


def _collect_pdfs(paths: list[str]) -> list[Path]:
    """Resolve a mix of files and folders into a flat list of PDF paths."""
    pdfs: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)
        elif p.is_dir():
            found = sorted(p.glob("*.pdf"))
            if not found:
                print(f"[warn] no PDFs found in {p}", file=sys.stderr)
            pdfs.extend(found)
        else:
            print(f"[warn] skipping {raw} (not a PDF or folder)", file=sys.stderr)
    return pdfs


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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ofd-processing",
        description="Bank statement PDF → CSV converter",
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

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
