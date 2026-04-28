"""Raw text extraction from PDF files.

Two backends: pdfplumber and PyMuPDF (fitz).
Both return per-page text so you can compare quality.
"""

from pathlib import Path


def extract_text_pdfplumber(pdf_path: str | Path) -> list[str]:
    """Extract text from each page using pdfplumber.

    Returns a list of strings, one per page.
    Preserves spatial layout which helps with table-like statements.
    """
    import pdfplumber

    pdf_path = Path(pdf_path)
    pages: list[str] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(text)

    return pages


def extract_text_pymupdf(pdf_path: str | Path) -> list[str]:
    """Extract text from each page using PyMuPDF (fitz).

    Returns a list of strings, one per page.
    Generally faster than pdfplumber; may handle encoding edge cases differently.
    """
    import fitz  # PyMuPDF

    pdf_path = Path(pdf_path)
    pages: list[str] = []

    doc = fitz.open(pdf_path)
    for page in doc:
        text = page.get_text() or ""
        pages.append(text)
    doc.close()

    return pages


def extract_text(pdf_path: str | Path, backend: str = "pdfplumber") -> list[str]:
    """Extract text using the specified backend.

    Args:
        pdf_path: Path to the PDF file.
        backend: Either "pdfplumber" or "pymupdf".

    Returns:
        List of page texts.
    """
    if backend == "pdfplumber":
        return extract_text_pdfplumber(pdf_path)
    elif backend == "pymupdf":
        return extract_text_pymupdf(pdf_path)
    else:
        raise ValueError(f"Unknown backend: {backend!r}. Use 'pdfplumber' or 'pymupdf'.")
