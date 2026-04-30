"""Parse extracted PDF text into structured transactions.

Handles:
- Current account statements (date, description, debit/credit columns)
- Credit card statements (transaction tables with amounts)
- Investment/savings statements (balance tables)
- Edge cases: headers, footers, warnings, promotional text
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    """A parsed transaction record."""
    date: str  # Original date string from PDF
    amount: float  # Amount (positive = credit/income, negative = debit/expense)
    description: str  # Transaction description
    category: str  # Mapped category (e.g., groceries, bills, income)
    type: str  # 'withdrawal', 'deposit', 'transfer', 'charge', etc.


class TransactionParser:
    """Parse PDF text into transactions with category mapping."""

    # Category mapping patterns (description → category)
    CATEGORY_PATTERNS = {
        # Groceries
        r'tesco|sainsburys|asda|morrisons|aldi|lidl|co-op|wholefoods|groceries|supermarket': 'groceries',
        # Food & drink
        r'coffee|costa|starbucks|tea|cafe|restaurant|pub|dinner|lunch|meal|takeaway|delivery': 'food_drink',
        # Bills & utilities
        r'council tax|water|electric|gas|energy|ofgem|broadband|internet|phone|ee|o2|virgin|sky|bills': 'bills',
        # Entertainment
        r'spotify|netflix|disney|amazon|prime|kindle|apple|spotify|subscription': 'entertainment',
        # Transport
        r'bus|train|tube|metro|transport|parking|uber|lyft|taxi': 'transport',
        # Health
        r'pharmacy|boots|superdrug|nhs|gym|fitness|health|doctor|dentist': 'health',
        # Shopping
        r'amazon|argos|currys|pc|clothes|primark|debenhams|shopping': 'shopping',
        # Transfers
        r'savings|transfer|overdraft|loan|bank': 'transfers',
        # Bank charges
        r'fee|charge|maintenance|annual|monthly|overdraft': 'bank_charges',
        # Income
        r'salary|income|pension|dividend|interest|bonus|award': 'income',
        # Housing
        r'rent|landlord|housing|mortgage': 'housing',
        # Insurance
        r'insurance|admiral|aviva|axa|insurance': 'insurance',
        # Personal
        r'gift|haircut|barber|salon|personal': 'personal',
        # Pets
        r'pets|petfood|vets|animal': 'pets',
    }

    def __init__(self):
        self.compiled_patterns = {}
        for pattern, category in self.CATEGORY_PATTERNS.items():
            self.compiled_patterns[category] = re.compile(pattern, re.IGNORECASE)

    def _map_category(self, description: str) -> str:
        """Map a description to a category using pattern matching."""
        for category, compiled_pattern in self.compiled_patterns.items():
            if compiled_pattern.search(description):
                return category
        return 'uncategorised'

    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats to ISO format."""
        date_str = date_str.strip()
        formats = [
            '%d/%m/%Y',  # 02/01/2026
            '%d-%m-%Y',  # 02-01-2026
            '%Y-%m-%d',  # 2026-01-02
            '%d %b %Y',  # 02 Jan 2026
            '%d %B %Y',  # 02 January 2026
            '%Y/%m/%d',  # 2026/01/02
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return date_str  # Return as-is if parsing fails

    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float, handling currency symbols and signs."""
        amount_str = amount_str.strip().replace('£', '').replace('€', '').replace('$', '').strip()
        # Remove thousands separators (commas)
        amount_str = amount_str.replace(',', '')
        if amount_str.startswith('-'):
            return float(amount_str)
        return float(amount_str)

    def _extract_transactions_from_table(self, text: str) -> list[Transaction]:
        """Extract transactions from a table-like structure."""
        transactions = []
        
        # Look for transaction tables - common patterns:
        # - "Date" header with amounts on same line
        # - "Details" column with amounts
        # - "Money out" / "Money in" columns
        
        lines = text.split('\n')
        in_table = False
        table_start = -1
        
        for i, line in enumerate(lines):
            # Detect table start (look for date headers or transaction headers)
            if any(keyword in line.lower() for keyword in ['date', 'details', 'money out', 'money in', 'cash balance', 'transaction']):
                in_table = True
                table_start = i
                continue
            
            if not in_table:
                continue
            
            # Parse transaction line
            # Common formats:
            # "02/01/2026 Brought forward £4,003.30"
            # "26/01/2026 £1,000.00 £5,003.30"
            # "14 Apr Payment By Direct Debit £42.45"
            
            # Pattern: date, description, amount (possibly with balance)
            match = re.search(
                r'(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}\s+\w+\s+\d{4})\s+(.+?)\s+([£€$]?\s*[\d,]+\.?\d*)',
                line
            )
            if match:
                date_str, desc, amount_str = match.groups()
                amount = self._parse_amount(amount_str)
                transactions.append(Transaction(
                    date=self._parse_date(date_str),
                    amount=amount,
                    description=desc.strip(),
                    category=self._map_category(desc),
                    type='withdrawal' if amount < 0 else 'deposit'
                ))
        
        return transactions

    def _extract_transactions_from_text(self, text: str) -> list[Transaction]:
        """Extract transactions from unstructured text."""
        # Remove headers, footers, warnings, promotional text
        cleaned = re.sub(
            r'(email|phone|registered|address|ni number|lifetime isa|interest rate|value of|total|after charges|earnings|bonuses|penalties|fees|authorised|regulated|financial conduct authority|registered office|page of)',
            '',
            text,
            flags=re.IGNORECASE
        )
        
        # Look for transaction-like lines
        transactions = []
        lines = cleaned.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Skip if line doesn't look like a transaction
            if not any(x in line for x in ['£', '€', '$', '20', '21', '22', '23', '24', '25', '26', '27', '28', '29', '30', '31']):
                continue
            
            # Try to extract date, description, amount
            # Pattern: date at start, then description, then amount with currency
            match = re.search(
                r'^(\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}\s+\w+\s+\d{4})\s+(.+?)\s+([£€$]?\s*[\d,]+\.?\d*)',
                line
            )
            if match:
                date_str, desc, amount_str = match.groups()
                amount = self._parse_amount(amount_str)
                transactions.append(Transaction(
                    date=self._parse_date(date_str),
                    amount=amount,
                    description=desc.strip(),
                    category=self._map_category(desc),
                    type='withdrawal' if amount < 0 else 'deposit'
                ))
        
        return transactions

    def parse(self, text: str) -> list[Transaction]:
        """Parse extracted text into transactions."""
        # Try table extraction first
        transactions = self._extract_transactions_from_table(text)
        
        # If no transactions found, try text-based extraction
        if not transactions:
            transactions = self._extract_transactions_from_text(text)
        
        return transactions
