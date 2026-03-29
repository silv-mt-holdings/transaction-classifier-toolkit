"""
Revenue Classifier

Classifies bank transactions by revenue type and detects RBF payments.

Data source: lending_intelligence.db (SQLite) → local JSON fallback
"""

import re
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import date

_HERE = Path(__file__).parent

# SQLite DB search paths
_SQLITE_SEARCH = [
    _HERE.parent.parent / "lending-intelligence-db" / "data" / "lending_intelligence.db",
    _HERE.parent / "data" / "lending_intelligence.db",
]


def _get_sqlite_conn() -> Optional[sqlite3.Connection]:
    for path in _SQLITE_SEARCH:
        if path.exists():
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row
            return conn
    return None


def _load_lenders_from_sqlite(conn: sqlite3.Connection) -> dict:
    """Load lender data from SQLite into the canonical dict format."""
    cur = conn.execute(
        "SELECT ml.name, mla.alias "
        "FROM mca_lenders ml "
        "JOIN mca_lender_aliases mla ON ml.id = mla.lender_id "
        "ORDER BY ml.name"
    )
    lenders = defaultdict(list)
    for row in cur.fetchall():
        lenders[row["name"]].append(row["alias"])
    return dict(lenders) if lenders else {}


def _load_patterns_from_sqlite(conn: sqlite3.Connection) -> dict:
    """Load revenue patterns from SQLite into the canonical dict format."""
    rows = conn.execute(
        "SELECT category, pattern, sub_type FROM revenue_patterns"
    ).fetchall()
    if not rows:
        return {}

    result = {
        "true_revenue_patterns": [],
        "non_true_revenue_patterns": [],
        "treasury_true_patterns": [],
        "treasury_false_positive_patterns": [],
        "zelle_venmo_patterns": [],
        "wire_patterns": {},
    }
    for r in rows:
        cat = r["category"]
        if cat == "true_revenue":
            result["true_revenue_patterns"].append(r["pattern"])
        elif cat == "non_true_revenue":
            result["non_true_revenue_patterns"].append(r["pattern"])
        elif cat == "treasury_true":
            result["treasury_true_patterns"].append(r["pattern"])
        elif cat == "treasury_false_positive":
            result["treasury_false_positive_patterns"].append(r["pattern"])
        elif cat == "zelle_venmo":
            result["zelle_venmo_patterns"].append(r["pattern"])
        elif cat == "wire":
            result["wire_patterns"][r["pattern"]] = r["sub_type"] or "unknown"
    return result


# Revenue and Wire type enums
class RevenueType(Enum):
    """Classification of transaction revenue type"""
    TRUE_REVENUE = "true_revenue"
    NON_TRUE_REVENUE = "non_true_revenue"
    OUTLIER = "outlier"
    RBF_PAYMENT = "rbf_payment"
    NEEDS_REVIEW = "needs_review"


class WireType(Enum):
    """Classification of wire transfer types"""
    WIRE_TRANSFER = "wire_transfer"
    FED_WIRE = "fed_wire"
    CHIPS_CREDIT = "chips_credit"
    BOOK_TRANSFER = "book_transfer"
    FOREIGN_REMITTANCE = "foreign_remittance"
    UNKNOWN = "unknown"


class TransactionType(Enum):
    """Type of bank transaction"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    WIRE = "wire"
    ACH = "ach"
    CHECK = "check"
    CARD = "card"
    FEE = "fee"


@dataclass
class Transaction:
    """Base transaction (compatible with parser toolkit)"""
    date: date
    description: str
    amount: float
    transaction_type: TransactionType = TransactionType.ACH
    raw_text: str = ""


@dataclass
class ClassifiedTransaction(Transaction):
    """Transaction with classification metadata"""
    revenue_type: RevenueType = RevenueType.NEEDS_REVIEW
    mca_match: Optional[str] = None
    wire_type: Optional[WireType] = None
    flags: List[str] = field(default_factory=list)


class RevenueClassifier:
    """
    Classifies transactions by revenue type and RBF detection.
    """

    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize classifier with pattern data.

        Args:
            data_dir: Optional path to data directory. Defaults to ./data
        """
        if data_dir is None:
            data_dir = Path(__file__).parent.parent / 'data'

        self.data_dir = Path(data_dir)
        self._load_patterns()

    def _load_patterns(self):
        """Load classification patterns — SQLite first, JSON fallback."""
        lenders = None
        patterns = None

        # Try SQLite first
        conn = _get_sqlite_conn()
        if conn:
            try:
                lenders = _load_lenders_from_sqlite(conn)
                patterns = _load_patterns_from_sqlite(conn)
                conn.close()
            except Exception:
                conn.close()
                lenders = None
                patterns = None

        # JSON fallback for lenders
        if not lenders:
            with open(self.data_dir / 'rbf_lender_list.json', 'r') as f:
                rbf_data = json.load(f)
                lenders = rbf_data['lenders']

        # JSON fallback for patterns
        if not patterns:
            with open(self.data_dir / 'revenue_patterns.json', 'r') as f:
                patterns = json.load(f)

        # Store lenders and build reverse lookup
        self.rbf_names = lenders
        self.aka_to_rbf = {}
        for rbf_name, aka_list in self.rbf_names.items():
            for aka in aka_list:
                self.aka_to_rbf[aka.upper()] = rbf_name

        # Compile regex patterns
        self.true_revenue_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns['true_revenue_patterns']
        ]
        self.non_true_revenue_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns['non_true_revenue_patterns']
        ]
        self.treasury_true_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns['treasury_true_patterns']
        ]
        self.treasury_false_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns['treasury_false_positive_patterns']
        ]
        self.p2p_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in patterns['zelle_venmo_patterns']
        ]

        # Wire type patterns
        self.wire_patterns = {}
        for pattern, wire_type in patterns['wire_patterns'].items():
            self.wire_patterns[pattern] = WireType(wire_type)

    def classify(self, transaction: Transaction) -> ClassifiedTransaction:
        """
        Classify a single transaction.

        Args:
            transaction: Transaction to classify

        Returns:
            ClassifiedTransaction with classification metadata
        """
        # Convert to ClassifiedTransaction
        classified = ClassifiedTransaction(
            date=transaction.date,
            description=transaction.description,
            amount=transaction.amount,
            transaction_type=transaction.transaction_type,
            raw_text=transaction.raw_text
        )

        desc = transaction.description.upper()

        # Only classify deposits
        if transaction.amount <= 0:
            classified.revenue_type = RevenueType.NON_TRUE_REVENUE
            return classified

        # Check for RBF payment (withdrawal side)
        rbf_match = self._lookup_rbf(desc)
        if rbf_match:
            classified.mca_match = rbf_match
            # Don't classify as revenue if it's an RBF payment
            return classified

        # Check wire type
        wire_type = self._classify_wire(desc)
        if wire_type:
            classified.wire_type = wire_type
            if wire_type == WireType.FOREIGN_REMITTANCE:
                classified.revenue_type = RevenueType.NON_TRUE_REVENUE
                classified.flags.append("FOREIGN_WIRE_NOT_REVENUE")
                return classified

        # Check for P2P (flag for review)
        if self._is_p2p(desc):
            classified.revenue_type = RevenueType.NEEDS_REVIEW
            classified.flags.append("P2P_REVIEW_REQUIRED")
            return classified

        # Check treasury payments
        if self._is_treasury_true(desc):
            classified.revenue_type = RevenueType.TRUE_REVENUE
            classified.flags.append("TREASURY_PAYMENT")
            return classified

        if self._is_treasury_false(desc):
            classified.revenue_type = RevenueType.NON_TRUE_REVENUE
            classified.flags.append("TREASURY_FALSE_POSITIVE")
            return classified

        # Check non-true revenue first (exclusions)
        if self._is_non_true_revenue(desc):
            classified.revenue_type = RevenueType.NON_TRUE_REVENUE
            return classified

        # Check true revenue
        if self._is_true_revenue(desc):
            classified.revenue_type = RevenueType.TRUE_REVENUE
            return classified

        # Default: needs review
        classified.revenue_type = RevenueType.NEEDS_REVIEW
        return classified

    def classify_all(self, transactions: List[Transaction]) -> List[ClassifiedTransaction]:
        """
        Classify a list of transactions.

        Args:
            transactions: List of transactions to classify

        Returns:
            List of classified transactions
        """
        return [self.classify(txn) for txn in transactions]

    def _lookup_rbf(self, description: str) -> Optional[str]:
        """Look up RBF company from description"""
        desc_upper = description.upper()
        for aka_name, rbf_name in self.aka_to_rbf.items():
            if aka_name in desc_upper:
                return rbf_name
        return None

    def _classify_wire(self, description: str) -> Optional[WireType]:
        """Classify wire transfer type"""
        for pattern, wire_type in self.wire_patterns.items():
            if re.search(pattern, description, re.IGNORECASE):
                return wire_type
        return None

    def _is_p2p(self, description: str) -> bool:
        """Check if P2P payment (Zelle, Venmo, etc.)"""
        return any(p.search(description) for p in self.p2p_patterns)

    def _is_treasury_true(self, description: str) -> bool:
        """Check if valid treasury payment"""
        return any(p.search(description) for p in self.treasury_true_patterns)

    def _is_treasury_false(self, description: str) -> bool:
        """Check if treasury false positive"""
        return any(p.search(description) for p in self.treasury_false_patterns)

    def _is_true_revenue(self, description: str) -> bool:
        """Check if true revenue"""
        return any(p.search(description) for p in self.true_revenue_patterns)

    def _is_non_true_revenue(self, description: str) -> bool:
        """Check if non-true revenue"""
        return any(p.search(description) for p in self.non_true_revenue_patterns)
