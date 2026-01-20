"""
transaction-classifier-toolkit

Transaction classification for revenue type and MCA detection.
"""

from classifier.revenue_classifier import (
    RevenueClassifier,
    RevenueType,
    WireType,
    ClassifiedTransaction
)

__version__ = "1.0.0"
__all__ = ["RevenueClassifier", "RevenueType", "WireType", "ClassifiedTransaction"]
