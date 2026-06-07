"""
recommender
-----------
Knapsack-based recommender koji bira tasks za vježbu u zadanom vremenskom
budžetu, s diminishing returns na klastere (raznolikost tema).
"""

from recommender.solver import (
    RecommenderConfig,
    Mode,
    recommend,
)

__all__ = ["RecommenderConfig", "Mode", "recommend"]
