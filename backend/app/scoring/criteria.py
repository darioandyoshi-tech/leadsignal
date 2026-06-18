from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict
from enum import Enum


class ScoringDimension(str, Enum):
    SEVERITY = "severity"
    VELOCITY = "velocity"          # how fast this signal type is growing
    PROXIMITY = "proximity"        # geographic density of nearby signals
    FRESHNESS = "freshness"        # recency of detected_at
    DIVERSITY = "diversity"        # breadth of signal types for a company
    FORECAST = "forecast"          # TimesFM trend direction
    MANUAL = "manual"              # admin/boost rules


@dataclass
class ScreeningCriteria:
    dimension: ScoringDimension
    weight: float = 1.0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    transform: Optional[Callable[[Any], float]] = None
    params: Dict[str, Any] = None

    def __post_init__(self):
        if self.params is None:
            self.params = {}
