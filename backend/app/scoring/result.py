from dataclasses import dataclass, field
from typing import Dict, List, Any
from uuid import UUID


@dataclass
class ScreeningResult:
    signal_id: UUID
    symbol_or_company: str
    signal_type: str
    headline: str
    score: float
    rank: int = 0
    passed_dimensions: List[str] = field(default_factory=list)
    failed_dimensions: List[str] = field(default_factory=list)
    dimension_scores: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
