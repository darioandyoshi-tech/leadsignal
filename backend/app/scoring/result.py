from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from uuid import UUID


@dataclass
class Recommendation:
    action: str
    confidence: float
    reasoning: str
    urgency: str
    playbook: Optional[str] = None


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
    recommendation: Optional[Recommendation] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
