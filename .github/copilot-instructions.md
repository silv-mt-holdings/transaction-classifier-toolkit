# Transaction Classifier Toolkit - AI Coding Guidelines

## Project Overview

**transaction-classifier-toolkit** is a pure functional library for classifying bank transactions by type and revenue quality.

**Core Purpose**: Classify transactions as TRUE_REVENUE, TRANSFER, LOAN, P2P, MCA_PAYMENT, etc. using pattern matching.

**Architecture Pattern**: **Functional Core** (Pure Functions, No I/O)

---

## Functional Core Principles

### ✅ What This Toolkit SHOULD Do
- Accept transaction data as input
- Apply pattern matching (regex, keyword detection)
- Return classification results (enum values, flags)
- Provide deterministic classification logic

### ❌ What This Toolkit MUST NOT Do
- File I/O operations
- Database connections
- HTTP requests
- Logging to external systems
- State mutations

---

## Architecture

```
transaction-classifier-toolkit/
├── classifier/
│   ├── revenue_classifier.py   # Main classification logic
│   └── patterns.py              # Classification patterns
├── models/
│   └── classification.py        # TransactionType enum, ClassificationResult
├── data/
│   ├── revenue_patterns.json    # True revenue patterns
│   ├── mca_lender_list.json     # MCA lender names
│   └── p2p_patterns.json        # P2P payment patterns
└── tests/
    └── test_classifier.py
```

---

## Core Classification Types

```python
class TransactionType(Enum):
    TRUE_REVENUE = "TRUE_REVENUE"         # Genuine business income
    TRANSFER = "TRANSFER"                  # Internal transfers
    LOAN = "LOAN"                          # Loan proceeds
    P2P = "P2P"                            # Zelle, Venmo, CashApp
    MCA_PAYMENT = "MCA_PAYMENT"            # MCA/RBF payback
    NON_REVENUE = "NON_REVENUE"            # Other non-revenue
    UNKNOWN = "UNKNOWN"                    # Cannot classify
```

---

## Key Functional Patterns

### Pattern-Based Classification

```python
def classify_transaction(
    description: str,
    amount: Decimal,
    transaction_type: str = "DEBIT"
) -> ClassificationResult:
    """
    Classify a single transaction.

    Args:
        description: Transaction description text
        amount: Transaction amount
        transaction_type: "DEBIT" or "CREDIT"

    Returns:
        ClassificationResult with type and confidence
    """
    # Priority order matters!
    if is_mca_payment(description):
        return ClassificationResult(
            type=TransactionType.MCA_PAYMENT,
            confidence=0.95,
            flags=[]
        )

    if is_p2p_payment(description):
        return ClassificationResult(
            type=TransactionType.TRUE_REVENUE,
            confidence=0.80,
            flags=["P2P_REVIEW_REQUIRED"]
        )

    if is_true_revenue(description):
        return ClassificationResult(
            type=TransactionType.TRUE_REVENUE,
            confidence=0.90,
            flags=[]
        )

    return ClassificationResult(
        type=TransactionType.UNKNOWN,
        confidence=0.50,
        flags=["MANUAL_REVIEW"]
    )
```

---

## Configuration Data

```json
// data/revenue_patterns.json
{
  "true_revenue_patterns": [
    "SQUARE.*PAYMENT",
    "STRIPE.*TRANSFER",
    "PAYPAL.*SALES",
    "SHOPIFY.*PAYOUT"
  ],
  "non_revenue_patterns": [
    "TRANSFER.*TO SAVINGS",
    "LOAN.*PROCEEDS",
    "WIRE.*TRANSFER OUT"
  ]
}
```

**Pattern**: Load patterns once at module init, reuse for all classifications.

---

## Testing

```python
def test_classify_square_payment():
    result = classify_transaction(
        description="SQUARE PAYMENT #12345",
        amount=Decimal("450.00"),
        transaction_type="CREDIT"
    )
    assert result.type == TransactionType.TRUE_REVENUE
    assert result.confidence >= 0.80

def test_classify_zelle_flagged():
    result = classify_transaction(
        description="ZELLE PAYMENT FROM JOHN DOE",
        amount=Decimal("200.00"),
        transaction_type="CREDIT"
    )
    assert result.type == TransactionType.TRUE_REVENUE
    assert "P2P_REVIEW_REQUIRED" in result.flags
```

---

## Integration with Risk-Model-01

```python
# Risk-Model-01/api.py
from classifier.revenue_classifier import RevenueClassifier

classifier = RevenueClassifier()
classified_txns = classifier.classify_all(transactions)
```

---

## Version

**v1.0** - Functional Core Extraction (January 2026)

**Author**: IntensiveCapFi / Silv MT Holdings
