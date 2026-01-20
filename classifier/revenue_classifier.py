"""
Revenue Classifier

Classifies bank transactions by revenue type and detects MCA payments.
"""

import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
from datetime import date


# Revenue and Wire type enums
class RevenueType(Enum):
    """Classification of transaction revenue type"""
    TRUE_REVENUE = "true_revenue"
    NON_TRUE_REVENUE = "non_true_revenue"
    OUTLIER = "outlier"
    MCA_PAYMENT = "mca_payment"
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
    Classifies transactions by revenue type and MCA detection.
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
        """Load classification patterns from JSON files"""
        # Load MCA lenders
        with open(self.data_dir / 'mca_lender_list.json', 'r') as f:
            mca_data = json.load(f)
            self.mca_names = mca_data['lenders']

        # Build reverse lookup
        self.aka_to_mca = {}
        for mca_name, aka_list in self.mca_names.items():
            for aka in aka_list:
                self.aka_to_mca[aka.upper()] = mca_name

        # Load revenue patterns
        with open(self.data_dir / 'revenue_patterns.json', 'r') as f:
            patterns = json.load(f)

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

        # Check for MCA payment (withdrawal side)
        mca_match = self._lookup_mca(desc)
        if mca_match:
            classified.mca_match = mca_match
            # Don't classify as revenue if it's an MCA payment
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

    def _lookup_mca(self, description: str) -> Optional[str]:
        """Look up MCA company from description"""
        desc_upper = description.upper()
        for aka_name, mca_name in self.aka_to_mca.items():
            if aka_name in desc_upper:
                return mca_name
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
