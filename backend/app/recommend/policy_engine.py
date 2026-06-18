"""Policy engine that turns scored LeadSignal opportunities into actions.

Inspired by the recommender class in the multivariate stock forecasting project,
but adapted for B2B local-market signals rather than stock trades.
"""

from dataclasses import dataclass
from typing import Optional, List

from app.scoring.result import ScreeningResult


@dataclass
class Recommendation:
    action: str  # contact, watch, alert, ignore
    confidence: float  # 0..1
    reasoning: str
    urgency: str  # low, medium, high
    playbook: Optional[str] = None


class SignalPolicyEngine:
    """Convert screening results into concrete business recommendations."""

    def __init__(self, contact_threshold: float = 0.75, watch_threshold: float = 0.55):
        self.contact_threshold = contact_threshold
        self.watch_threshold = watch_threshold

    def recommend(self, result: ScreeningResult) -> Recommendation:
        score = result.score
        dims = result.dimension_scores
        passed = set(result.passed_dimensions)

        # High-score + forecast momentum + severity = contact now
        if score >= self.contact_threshold:
            reasons = ["Composite score above contact threshold"]
            if "forecast" in passed and dims.get("forecast", 0.5) > 0.6:
                reasons.append("forecast trend is positive")
            if "velocity" in passed and dims.get("velocity", 0) >= 0.8:
                reasons.append("signal velocity is high")
            if "proximity" in passed and dims.get("proximity", 0) >= 0.6:
                reasons.append("clustering of nearby activity")
            if "severity" in passed and dims.get("severity", 0) >= 0.8:
                reasons.append("high severity")

            return Recommendation(
                action="contact",
                confidence=min(1.0, score + 0.1),
                reasoning="; ".join(reasons),
                urgency="high",
                playbook=self._playbook(result.signal_type, "contact"),
            )

        # Medium score or rising momentum = watch closely
        if score >= self.watch_threshold:
            reasons = ["Composite score indicates emerging opportunity"]
            if "freshness" in passed and dims.get("freshness", 0) >= 0.8:
                reasons.append("very recent signal")
            if "diversity" in passed and dims.get("diversity", 0) >= 0.7:
                reasons.append("multiple signal types on same company/area")

            return Recommendation(
                action="watch",
                confidence=score,
                reasoning="; ".join(reasons),
                urgency="medium",
                playbook=self._playbook(result.signal_type, "watch"),
            )

        return Recommendation(
            action="ignore",
            confidence=1.0 - score,
            reasoning="Score too low to warrant action",
            urgency="low",
            playbook=None,
        )

    @staticmethod
    def _playbook(signal_type: str, action: str) -> Optional[str]:
        playbooks = {
            "hiring_spike": {
                "contact": "Reach out with staffing/IT onboarding packages.",
                "watch": "Monitor for continued hiring acceleration.",
            },
            "negative_review_cluster": {
                "contact": "Pitch reputation management + review response service.",
                "watch": "Track sentiment trend before outreach.",
            },
            "permit_filing": {
                "contact": "Offer contractors, inspectors, or material suppliers.",
                "watch": "Wait for permit approval or additional filings.",
            },
            "gov_contract_award": {
                "contact": "Pitch compliance, cybersecurity, or capacity scaling.",
                "watch": "Track follow-on contract opportunities.",
            },
            "business_license": {
                "contact": "Welcome new business with starter IT/payment package.",
                "watch": "Wait for business to open or hire.",
            },
            "tax_delinquency": {
                "contact": "Offer accounting/cash-flow advisory (sensitive tone).",
                "watch": "Confirm public record before outreach.",
            },
            "ucc_filing": {
                "contact": "Pitch working-capital or equipment financing.",
                "watch": "Monitor for follow-on filings.",
            },
            "parcel_change": {
                "contact": "Offer title, insurance, or improvement services.",
                "watch": "Wait for sale or development activity.",
            },
            "new_business_registration": {
                "contact": "Welcome kit: website, POS, bookkeeping.",
                "watch": "Track for hiring or location opening.",
            },
            "land_bank_property": {
                "contact": "Pitch development, demolition, or renovation services.",
                "watch": "Wait for zoning or sale updates.",
            },
        }
        return playbooks.get(signal_type, {}).get(action)
