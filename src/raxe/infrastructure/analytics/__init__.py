"""
Analytics infrastructure for RAXE CE.

Provides analytics calculation, aggregation, and streak tracking.
"""

from .aggregator import DataAggregator
from .engine import AnalyticsEngine
from .repository import SQLiteAnalyticsRepository
from .streaks import Achievement, StreakTracker

__all__ = [
    "Achievement",
    "AnalyticsEngine",
    "DataAggregator",
    "SQLiteAnalyticsRepository",
    "StreakTracker",
]
