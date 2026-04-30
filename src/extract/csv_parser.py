"""Parse raw CSV files from Monzo data exports.

Supports both standard Monzo CSV exports:
- `MonzoDataExport*.csv` - Standard export with detailed transaction info
- `FlexMonzoDataExport*.csv` - Flex budget export with budget allocation tracking

Output format matches `example/transactions-full.csv`:
    date,type,amount,description,category
"""

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.extract.transaction_parser import Transaction


@dataclass
class CSVTransaction:
    """Transaction parsed from CSV."""
    transaction_id: str
    date: str
    time: str
    type: str
    name: str
    amount: float
    currency: str
    local_amount: float
    local_currency: str
    notes: str
    address: str
    receipt: str
    description: str
    category_split: str
    money_out: float
    money_in: float


class CSVParser:
    """Parse Monzo CSV exports into transactions."""

    # Column index mapping for Monzo CSV exports
    # Header: Transaction ID,Date,Time,Type,Name,Emoji,Category,Amount,Currency,Local amount,
    #         Local currency,Notes and #tags,Address,Receipt,Description,Category split,
    #         Money Out,Money In
    COLUMNS = {
        "transaction_id": 0,
        "date": 1,
        "time": 2,
        "type": 3,
        "name": 4,
        "emoji": 5,
        "category": 6,
        "amount": 7,
        "currency": 8,
        "local_amount": 9,
        "local_currency": 10,
        "notes": 11,
        "address": 12,
        "receipt": 13,
        "description": 14,
        "category_split": 15,
        "money_out": 16,
        "money_in": 17,
    }

    # Type mapping: Monzo export types → output type
    TYPE_MAPPING = {
        "Faster payment": "deposit",
        "Flex": "withdrawal",
        "Transfers": "transfer",
        "Direct debit": "charge",
        "Standing order": "charge",
        "Direct credit": "deposit",
        "Payout": "deposit",
        "Credit card payment": "charge",
        "Savings interest": "interest",
        "Overdraft interest": "interest_charge",
        "Monthly fee": "charge",
        "Monthly interest": "interest",
        "Loan repayment": "charge",
        "Loan interest": "interest_charge",
        "Mortgage repayment": "charge",
        "Mortgage interest": "interest_charge",
        "Direct credit": "deposit",
        "Bounced payment": "charge",
    }

    # Category mapping from Name/Notes to output category
    CATEGORY_MAPPINGS = {
        # Groceries
        "Tesco": "groceries",
        "Sainsbury's": "groceries",
        "Asda": "groceries",
        "Morrisons": "groceries",
        "Aldi": "groceries",
        "Lidl": "groceries",
        "Co-op": "groceries",
        "Wholefoods": "groceries",
        "Waitrose": "groceries",
        # Food & drink
        "Costa": "eating_out",
        "Starbucks": "eating_out",
        "Coffee": "eating_out",
        "Subway": "eating_out",
        "McDonald's": "eating_out",
        "KFC": "eating_out",
        "Pret": "eating_out",
        "Whittard": "eating_out",
        # Transport
        "Shell": "transport",
        "BP": "transport",
        "Tesco Express": "transport",
        "Co-op Petrol": "transport",
        "Uber": "transport",
        "Bolt": "transport",
        # Bills & utilities
        "British Gas": "bills",
        "EDF Energy": "bills",
        "Oxfordshire Water": "bills",
        "EE": "bills",
        "O2": "bills",
        "Vodafone": "bills",
        "Sky": "bills",
        "Netflix": "entertainment",
        "Spotify": "entertainment",
        # Shopping
        "Amazon": "shopping",
        "Argos": "shopping",
        "Currys": "shopping",
        "Primark": "shopping",
        # Entertainment
        "Cineworld": "entertainment",
        "Odeon": "entertainment",
        "Boxing": "entertainment",
        # Gifts
        "Waterstones": "gifts",
        "Book Depository": "gifts",
        "Charity Shop": "gifts",
    }

    def _is_income_transaction(self, type_str: str, notes: str) -> bool:
        """Determine if a transaction is income (allowance, salary, etc.)."""
        type_lower = type_str.lower() if type_str else ""
        notes_lower = notes.lower() if notes else ""
        
        # Income indicators in notes
        income_notes = ["allowance", "salary", "income", "pension", "bonus", "award"]
        if any(x in notes_lower for x in income_notes):
            return True
        
        return False

    def __init__(self):
        self.parser = csv.DictReader

    def _parse_date(self, date_str: str) -> str:
        """Parse Monzo date format (DD/MM/YYYY) to ISO format."""
        date_str = date_str.strip()
        if not date_str:
            return ""
        try:
            dt = datetime.strptime(date_str, "%d/%m/%Y")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            # Try alternative formats
            for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%Y-%m-%d")
                except ValueError:
                    continue
            return date_str

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float, handling currency symbols and signs."""
        amount_str = amount_str.strip().replace("£", "").replace("€", "").replace("$", "").strip()
        amount_str = amount_str.replace(",", "")
        try:
            return float(amount_str)
        except ValueError:
            return 0.0

    def _map_type(self, type_str: str) -> str:
        """Map Monzo export type to output type."""
        if not type_str:
            return "general"
        return self.TYPE_MAPPING.get(type_str, "general")

    def _map_category(self, name: str, notes: str, category: str) -> str:
        """Map transaction name/notes/category to output category."""
        name_lower = name.lower() if name else ""
        notes_lower = notes.lower() if notes else ""
        category_lower = category.lower() if category else ""

        # Check name first (most reliable)
        for merchant, cat in self.CATEGORY_MAPPINGS.items():
            if merchant.lower() in name_lower:
                return cat

        # Check notes for common patterns
        if any(x in notes_lower for x in ["allowance", "salary", "income", "pension", "bonus", "award"]):
            return "income"
        if any(x in notes_lower for x in ["fee", "charge", "maintenance", "annual"]):
            return "expenses"
        if any(x in notes_lower for x in ["transfer", "overdraft", "loan", "bank"]):
            return "transfers"

        # Check category field
        if category_lower == "groceries":
            return "groceries"
        if category_lower == "income":
            return "income"
        if category_lower == "expenses":
            return "expenses"

        return "general"

    def _map_to_target_type(self, type_str: str) -> str:
        """Map CSV type to target output type for transactions-full.csv format.

        The target format expects types like: deposit, withdrawal, interest, etc.
        We map CSV types to these standard categories.
        """
        type_lower = type_str.lower() if type_str else ""

        # Income types
        income_types = ["income", "allowance", "salary", "pension", "bonus", "award"]
        if any(x in type_lower for x in income_types):
            return "deposit"

        # Expense types
        expense_types = ["groceries", "food", "restaurants", "eating", "shopping", "bills"]
        if any(x in type_lower for x in expense_types):
            return "withdrawal"

        # Transfer types
        transfer_types = ["transfer", "flex", "payout", "direct credit", "direct debit"]
        if any(x in type_lower for x in transfer_types):
            if "debit" in type_lower or "out" in type_lower or "fee" in type_lower:
                return "withdrawal"
            return "transfer"

        # Interest types
        interest_types = ["interest", "savings interest", "overdraft interest"]
        if any(x in type_lower for x in interest_types):
            return "interest"

        # Charge types (fees, charges)
        charge_types = ["fee", "charge", "maintenance", "annual", "monthly", "overdraft"]
        if any(x in type_lower for x in charge_types):
            return "withdrawal"

        # Default to general
        return "general"

    def _map_category(self, name: str, notes: str, category: str) -> str:
        """Map transaction name/notes/category to output category."""
        name_lower = name.lower() if name else ""
        notes_lower = notes.lower() if notes else ""
        category_lower = category.lower() if category else ""

        # First, check if this is an income transaction
        if self._is_income_transaction(category, notes):
            return "income"

        # Check name first (most reliable)
        for merchant, cat in self.CATEGORY_MAPPINGS.items():
            if merchant.lower() in name_lower:
                return cat

        # Check notes for common patterns
        if any(x in notes_lower for x in ["allowance", "salary", "income", "pension", "bonus", "award"]):
            return "income"
        if any(x in notes_lower for x in ["fee", "charge", "maintenance", "annual"]):
            return "expenses"
        if any(x in notes_lower for x in ["transfer", "overdraft", "loan", "bank"]):
            return "transfers"

        # Check category field
        if category_lower == "groceries":
            return "groceries"
        if category_lower == "income":
            return "income"
        if category_lower == "expenses":
            return "expenses"

        return "general"

    def parse(self, csv_path: str | Path) -> list[Transaction]:
        """Parse a Monzo CSV export into transactions.

        Args:
            csv_path: Path to CSV file.

        Returns:
            List of Transaction objects.
        """
        csv_path = Path(csv_path)
        transactions = []

        # Read CSV
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = self.parser(f)
            rows = list(reader)

        for row in rows:
            try:
                # Parse fields - handle both DictReader (header with spaces) and column indices
                # The CSV header has spaces, so DictReader returns keys with spaces
                # But we also support column indices for robustness
                try:
                    transaction_id = row.get("Transaction ID", "")
                    date_str = row.get("Date", "")
                    time_str = row.get("Time", "")
                    type_str = row.get("Type", "")
                    name = row.get("Name", "")
                    category = row.get("Category", "")
                    amount_str = row.get("Amount", "")
                    currency = row.get("Currency", "")
                    local_amount_str = row.get("Local amount", "")
                    local_currency = row.get("Local currency", "")
                    notes = row.get("Notes and #tags", "")
                    address = row.get("Address", "")
                    receipt = row.get("Receipt", "")
                    description = row.get("Description", "")
                    category_split = row.get("Category split", "")
                    money_out_str = row.get("Money Out", "")
                    money_in_str = row.get("Money In", "")
                except Exception as e:
                    # Fallback to column indices if DictReader fails
                    try:
                        transaction_id = row[self.COLUMNS["transaction_id"]]
                        date_str = row[self.COLUMNS["date"]]
                        time_str = row[self.COLUMNS["time"]]
                        type_str = row[self.COLUMNS["type"]]
                        name = row[self.COLUMNS["name"]]
                        category = row[self.COLUMNS["category"]]
                        amount_str = row[self.COLUMNS["amount"]]
                        currency = row[self.COLUMNS["currency"]]
                        local_amount_str = row[self.COLUMNS["local_amount"]]
                        local_currency = row[self.COLUMNS["local_currency"]]
                        notes = row[self.COLUMNS["notes"]]
                        address = row[self.COLUMNS["address"]]
                        receipt = row[self.COLUMNS["receipt"]]
                        description = row[self.COLUMNS["description"]]
                        category_split = row[self.COLUMNS["category_split"]]
                        money_out_str = row[self.COLUMNS["money_out"]]
                        money_in_str = row[self.COLUMNS["money_in"]]
                    except:
                        # Skip this row if we can't parse it
                        continue

                # Parse amounts
                amount = self._parse_amount(amount_str)
                local_amount = self._parse_amount(local_amount_str)
                money_out = self._parse_amount(money_out_str)
                money_in = self._parse_amount(money_in_str)

                # Parse date
                date_iso = self._parse_date(date_str)

                # Determine type
                type_out = self._map_to_target_type(type_str)

                # Determine category
                category_out = self._map_category(name, notes, category)

                # Create transaction
                t = Transaction(
                    date=date_iso,
                    amount=amount,
                    description=description or name or category_split or "",
                    category=category_out,
                    type=type_out,
                )
                transactions.append(t)

            except Exception as e:
                # Log error but continue processing other rows
                print(f"[warn] Skipping row: {e}")
                continue

        return transactions


def parse_csv_file(csv_path: str | Path) -> list[Transaction]:
    """Convenience function to parse a CSV file."""
    parser = CSVParser()
    return parser.parse(csv_path)


def parse_csv_directory(directory: str | Path) -> list[Transaction]:
    """Parse all Monzo CSV exports in a directory."""
    directory = Path(directory)
    all_transactions = []

    # Find CSV files
    csv_files = sorted(directory.glob("MonzoDataExport*.csv"))
    csv_files.extend(sorted(directory.glob("FlexMonzoDataExport*.csv")))

    if not csv_files:
        print(f"[warn] No Monzo CSV files found in {directory}")
        return []

    print(f"Found {len(csv_files)} Monzo CSV file(s)")

    for csv_path in csv_files:
        print(f"  Parsing: {csv_path.name}")
        transactions = parse_csv_file(csv_path)
        all_transactions.extend(transactions)

        print(f"    Found {len(transactions)} transactions")

    return all_transactions
