# transaction-classifier-toolkit

Transaction classification toolkit - Identifies revenue types, MCA payments, wire types, and deposit categories.

## Features

- **True Revenue Classification**: Distinguishes true revenue from non-true revenue (refunds, owner draws, etc.)
- **MCA Lender Detection**: Identifies payments to 50+ known MCA lenders
- **P2P Payment Flagging**: Detects Zelle, Venmo, Cash App, PayPal for manual review
- **Wire Transfer Classification**: Categorizes wire types (Fed Wire, CHIPS, Book Transfer, Foreign Remittance)
- **Treasury Payment Validation**: Validates IRS/tax payments vs false positives
- **Deposit Type Categorization**: ACH, wire, cash, card processing deposits

## Installation

```bash
# Basic installation
pip install git+https://github.com/silv-mt-holdings/transaction-classifier-toolkit.git

# For development
git clone https://github.com/silv-mt-holdings/transaction-classifier-toolkit.git
cd transaction-classifier-toolkit
pip install -e ".[dev]"
```

## Quick Start

```python
from classifier.revenue_classifier import RevenueClassifier
from parser.statement_parser import BankStatementParser

# Parse statement first
parser = BankStatementParser()
statement = parser.parse(pdf_bytes, filename="statement.pdf")

# Classify transactions
classifier = RevenueClassifier()
classified = classifier.classify_all(statement.transactions)

# Access classification results
for txn in classified:
    print(f"{txn.date} | {txn.description}")
    print(f"  Revenue Type: {txn.revenue_type.value}")
    print(f"  MCA Match: {txn.mca_match}")
    print(f"  Flags: {txn.flags}")
```

## Classification Logic

### True Revenue Detection

Classifies deposits as **TRUE_REVENUE** if they match:
- Card processing patterns (Stripe, Square, Clover, PayPal, etc.)
- POS system patterns
- Payment processor deposits
- Customer payment patterns

Excludes:
- Refunds, chargebacks
- Owner/personal transfers
- Loan proceeds
- Tax refunds

### MCA Lender Detection

Detects payments to **50+ MCA lenders** including:
- Rapid Advance
- OnDeck
- Kabbage
- BlueVine
- Fundbox
- And 45+ more...

Uses AKA name matching to handle variations like:
- "RAPID ADVANCE" → Rapid Advance
- "ONDECK CAP" → OnDeck
- "STRIPE CAPITAL" → Stripe Capital

### P2P Payment Flagging

Flags for manual review:
- Zelle transfers
- Venmo transactions
- Cash App deposits
- PayPal P2P (non-business)

### Wire Transfer Classification

Categorizes wires by prefix:
- **ORIG:** → Wire Transfer (Fed Wire)
- **B/O:** → CHIPS Credit / Book Transfer
- **Foreign** → Foreign Remittance (NOT true revenue)

### Treasury Payments

Validates IRS/tax payments:
- ✅ True: IRS refunds, EITC, child tax credits
- ❌ False: Generic "treasury" in description

## Data Models

### ClassifiedTransaction

```python
@dataclass
class ClassifiedTransaction(Transaction):
    revenue_type: RevenueType  # TRUE_REVENUE, NON_TRUE_REVENUE, etc.
    mca_match: Optional[str]   # MCA lender name if detected
    wire_type: Optional[WireType]  # Wire classification
    flags: List[str]           # Warning flags
```

### RevenueType Enum

```python
class RevenueType(Enum):
    TRUE_REVENUE = "true_revenue"
    NON_TRUE_REVENUE = "non_true_revenue"
    OUTLIER = "outlier"
    MCA_PAYMENT = "mca_payment"
    NEEDS_REVIEW = "needs_review"
```

### WireType Enum

```python
class WireType(Enum):
    WIRE_TRANSFER = "wire_transfer"      # ORIG: prefix
    FED_WIRE = "fed_wire"                # ORIG: prefix
    CHIPS_CREDIT = "chips_credit"        # B/O: prefix
    BOOK_TRANSFER = "book_transfer"      # B/O: prefix
    FOREIGN_REMITTANCE = "foreign_remittance"  # NOT True Revenue
    UNKNOWN = "unknown"
```

## Configuration Files

### `data/mca_lender_list.json`

```json
{
  "lenders": {
    "Rapid Advance": ["RAPID ADVANCE", "RAPID ADV", "RAPIDADVANCE"],
    "OnDeck": ["ONDECK", "ONDECK CAP", "ON DECK CAPITAL"],
    ...
  }
}
```

### `data/revenue_patterns.json`

```json
{
  "true_revenue_patterns": [
    "stripe.*deposit",
    "square.*sales",
    "clover.*payment",
    ...
  ],
  "non_true_revenue_patterns": [
    "refund",
    "chargeback",
    "owner.*transfer",
    ...
  ],
  ...
}
```

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=classifier tests/
```

## Dependencies

- **bankstatement-parser-toolkit** - Provides Transaction model

## License

MIT License - Copyright (c) 2026 Silv MT Holdings

## Related Projects

- [bankstatement-parser-toolkit](https://github.com/silv-mt-holdings/bankstatement-parser-toolkit) - Parse bank statements
- [cashflow-analytics-toolkit](https://github.com/silv-mt-holdings/cashflow-analytics-toolkit) - Analyze cash flow from classified transactions
- [Risk-Model-01](https://github.com/silv-mt-holdings/Risk-Model-01) - MCA underwriting platform

## Contributing

Contributions welcome! Please open an issue or submit a pull request.
