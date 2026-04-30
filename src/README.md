# CSV CLI - Silent Processing with Progress

## Overview

A CLI tool to process CSV files **silently** (content kept behind the scenes) with **line count progress display**.

## Installation

No installation required. Just run the script directly:

```bash
./src/csv_cli.sh <file.csv> [count|process] [interval]
```

Or use the Python script directly:

```bash
python3 src/csv_processor.py <file.csv> [count|process] [interval]
```

## Usage

### Count lines with progress

```bash
./src/csv_cli.sh file.csv count
```

Output:
```
[100/15,762 bytes] [100 lines] [0.6%] [0.0s] [163330 lines/sec]

📈 Total lines: 100
```

### Process CSV with progress (silent content)

```bash
./src/csv_cli.sh file.csv process
```

Output:
```
📊 CSV Processing Progress
   File: file.csv
   Total lines: 100
   Header columns: 18
   Data rows: 99
   Processing time: 0.00s (404465 lines/sec)
   ✓ Content kept behind the scenes

Processed 100 lines
Header: ['Transaction ID', 'Date', 'Time', 'Type', 'Name', ...]
Data rows: 99
```

### Custom progress interval

```bash
./src/csv_cli.sh file.csv count 50  # Show progress every 50 lines
```

## Features

- ✅ **Silent content** - CSV data rows never printed to CLI
- ✅ **Progress display** - Line count with speed and percentage
- ✅ **Fast processing** - Uses Python's csv module for efficient parsing
- ✅ **Error handling** - File not found, encoding errors, etc.

## Output

The tool outputs only **metadata**:
- Line counts
- Header columns
- Processing time
- Speed (lines/sec)

The actual CSV data rows are **kept behind the scenes** and never printed.

## License

MIT
