# ofd-processing

Local, offline bank statement PDF → CSV converter.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

 ```bash
   # Activate (do this each time you open a new terminal)
   source .venv/bin/activate

   # Now you can just use python (not python3)
   python -m src.cli dump samples/

   # When you're done
   deactivate
 ```

## Usage

```bash
python -m src.cli dump <pdf>                # both backends
python -m src.cli dump <pdf> -b pdfplumber  # pdfplumber only
python -m src.cli dump <pdf> -b pymupdf     # PyMuPDF only
```

 ```bash
   python -m src.cli dump samples/                    # all PDFs in folder
   python -m src.cli dump samples/statement.pdf       # single file
   python -m src.cli dump a.pdf b.pdf                 # multiple files
   python -m src.cli dump samples/ -b pdfplumber      # one backend only
 ```

## Status

Text extraction foundation only. See [`.docs/_refile/ROADMAP.md`](.docs/_refile/ROADMAP.md) for the full plan.
