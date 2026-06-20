#!/usr/bin/env python3
"""Vendor Incident Alpha Signal Generator

Detects when major infrastructure vendors have incidents and maps them to
S&P 500 companies that are likely affected. Generates trade signals that can
be fed into the LeadSignal trading system.

Thesis: When a vendor has a major/critical incident, companies that heavily
depend on that vendor will underperform short-term (1-4 days). This is
event-driven alpha that's detectable before the market fully prices it in.

Signal types:
- AVOID: Don't buy companies dependent on a degraded vendor (filter signal)
- SHORT_BIAS: Consider reducing/avoiding existing positions in affected companies
- RECOVERY: When vendor recovers, affected companies may bounce back (buy signal)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Set
import httpx


class SignalType(str, Enum):
    AVOID = "avoid"
    SHORT_BIAS = "short_bias"
    RECOVERY = "recovery"


class Severity(str, Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    MAINTENANCE = "maintenance"


@dataclass
class VendorIncidentSignal:
    """A trade signal generated from a vendor incident."""
    signal_type: SignalType
    vendor_slug: str
    vendor_name: str
    incident_severity: Severity
    incident_title: str
    incident_started: str
    affected_symbols: List[str]
    affected_companies: List[str]
    confidence: float  # 0-1, how confident we are in the signal
    reasoning: str
    generated_at: str


# ─── Vendor → S&P 500 Company Dependency Map ───────────────────────────────
# This maps infrastructure vendors to S&P 500 companies that are their
# known customers or heavily dependent on their services.
# Sources: public case studies, 10-K risk factors, customer pages.

VENDOR_DEPENDENCY_MAP: Dict[str, Dict] = {
    "cloudflare": {
        "name": "Cloudflare",
        "category": "CDN/Edge",
        "affected_symbols": {
            # E-commerce (CDN-dependent)
            "AMZN": "AWS + Cloudflare for edge",
            "EBAY": "Cloudflare CDN for storefront",
            "ETSY": "Cloudflare for DDoS protection",
            "WMT": "Cloudflare for online storefront",
            "TGT": "Cloudflare for online storefront",
            # SaaS (Cloudflare DNS/proxy)
            "CRM": "Cloudflare for edge security",
            "NOW": "Cloudflare for edge",
            "WDAY": "Cloudflare for CDN",
            "ZM": "Cloudflare for edge routing",
            # Media
            "NFLX": "Cloudflare DNS fallback",
            "DIS": "Cloudflare for Disney+ streaming edge",
            "WBD": "Cloudflare for Max streaming",
        },
    },
    "twilio": {
        "name": "Twilio",
        "category": "Communications API",
        "affected_symbols": {
            # SaaS comms
            "CRM": "Twilio for SMS/voice in Salesforce",
            "ZD": "Twilio for Zendesk messaging",
            "HUBS": "Twilio for HubSpot SMS",
            "MNDY": "Twilio for monday.com notifications",
            "TEAM": "Twilio for Atlassian notifications",
            # Fintech
            "SQ": "Twilio for Cash App notifications",
            "PYPL": "Twilio for PayPal 2FA",
            # Healthcare
            "VEEV": "Twilio for Veeva comms",
            # Rideshare
            "UBER": "Twilio for driver/rider comms",
            "LYFT": "Twilio for driver/rider comms",
        },
    },
    "aws": {
        "name": "Amazon Web Services",
        "category": "Cloud Infrastructure",
        "affected_symbols": {
            "NFLX": "AWS primary cloud",
            "DIS": "AWS for Disney+",
            "ZM": "AWS primary cloud",
            "SNAP": "AWS primary cloud",
            "PINS": "AWS primary cloud",
            "MRVL": "AWS for infrastructure",
            "FTNT": "AWS for FortiCWP",
            "DDOG": "AWS-heavy customers",
            "MELI": "AWS for Mercado Libre",
            "ABNB": "AWS primary cloud",
        },
    },
    "datadog": {
        "name": "Datadog",
        "category": "Monitoring/Observability",
        "affected_symbols": {
            # Monitoring-dependent SaaS
            "CRM": "Datadog for Salesforce infra monitoring",
            "NOW": "Datadog monitoring",
            "WDAY": "Datadog monitoring",
            "SNOW": "Datadog for Snowflake infra",
            "NET": "Datadog for Cloudflare infra",
            "DDOG": "Self-impact",
        },
    },
    "stripe": {
        "name": "Stripe",
        "category": "Payment Processing",
        "affected_symbols": {
            # E-commerce / SaaS payments
            "ABNB": "Stripe for payments",
            "LYFT": "Stripe for payments",
            "DOCU": "Stripe for billing",
            "SHOP": "Stripe for Shopify payments",
            "PLTR": "Stripe for billing",
            "ZM": "Stripe for billing",
            "FSLY": "Stripe for billing",
            "ROKU": "Stripe for payments",
        },
    },
    "okta": {
        "name": "Okta",
        "category": "Identity/Auth",
        "affected_symbols": {
            # Enterprise SaaS using Okta for SSO
            "CRM": "Okta for SSO",
            "NOW": "Okta for SSO",
            "WDAY": "Okta for SSO",
            "ZM": "Okta for SSO",
            "TEAM": "Okta for Atlassian SSO",
            "HUBS": "Okta for HubSpot SSO",
            "MNDY": "Okta for SSO",
            "SNOW": "Okta for SSO",
        },
    },
    "azure": {
        "name": "Microsoft Azure",
        "category": "Cloud Infrastructure",
        "affected_symbols": {
            "MSFT": "Self-impact (Azure = Microsoft)",
            "CRM": "Azure for Salesforce",
            "ORCL": "Azure for Oracle Cloud",
            "SAP": "Azure for SAP",
            "ADBE": "Azure for Adobe Creative Cloud",
            "PLTR": "Azure for Palantir Foundry",
            "U": "Azure for Unity Cloud",
        },
    },
    "github": {
        "name": "GitHub",
        "category": "DevOps/Code",
        "affected_symbols": {
            "MSFT": "Self-impact (GitHub = Microsoft)",
            "CRM": "GitHub for engineering",
            "NOW": "GitHub for engineering",
            "SNOW": "GitHub for engineering",
            "PLTR": "GitHub for engineering",
            "DDOG": "GitHub for engineering",
            "NET": "GitHub for engineering",
        },
    },
    "snowflake": {
        "name": "Snowflake",
        "category": "Data Warehouse",
        "affected_symbols": {
            "CRM": "Snowflake for Salesforce Data Cloud",
            "ABNB": "Snowflake for analytics",
            "DDOG": "Snowflake for data",
            "PLTR": "Snowflake partnership",
            "NET": "Snowflake for analytics",
        },
    },
    "elastic-cloud": {
        "name": "Elastic Cloud",
        "category": "Search/Logging",
        "affected_symbols": {
            "CRM": "Elastic for search infra",
            "UBER": "Elastic for logging",
            "DDOG": "Elastic for log correlation",
            "NET": "Elastic for security analytics",
        },
    },
    "grafana": {
        "name": "Grafana",
        "category": "Monitoring/Visualization",
        "affected_symbols": {
            "CRM": "Grafana for infra dashboards",
            "NOW": "Grafana for monitoring",
            "DDOG": "Grafana complementary",
            "NET": "Grafana for observability",
        },
    },
    "cloudfare-stream": {
        "name": "Cloudflare Stream",
        "category": "Video Delivery",
        "affected_symbols": {
            "NFLX": "Cloudflare Stream for video delivery",
            "DIS": "Cloudflare Stream edge",
            "WBD": "Cloudflare Stream for Max",
            "RBLX": "Cloudflare for video content",
        },
    },
    "flutterwave": {
        "name": "Flutterwave",
        "category": "African Payments",
        "affected_symbols": {
            # Minimal S&P 500 impact (African market)
        },
    },
}


class VendorIncidentSignalGenerator:
    """Generate trade signals from PulseWatch vendor incident data."""

    def __init__(self, api_base: str = "https://api.pulsewatch.us"):
        self.api_base = api_base

    def fetch_open_incidents(self) -> List[Dict]:
        """Fetch open incidents from PulseWatch API."""
        # Use the PulseWatch MCP tool instead of direct API
        # This is called externally; for standalone use, call PulseWatch API directly
        try:
            url = f"{self.api_base}/v1/incidents/open"
            r = httpx.get(url, timeout=30)
            if r.status_code == 200:
                return r.json().get("incidents", [])
        except Exception:
            pass
        return []

    def generate_signals(
        self,
        incidents: List[Dict],
        min_severity: Severity = Severity.MAJOR,
    ) -> List[VendorIncidentSignal]:
        """Generate trade signals from incident data."""
        severity_order = {
            Severity.CRITICAL: 4,
            Severity.MAJOR: 3,
            Severity.MINOR: 2,
            Severity.MAINTENANCE: 1,
        }
        min_sev = severity_order.get(min_severity, 3)

        signals: List[VendorIncidentSignal] = []
        now = datetime.now(timezone.utc).isoformat()

        for incident in incidents:
            slug = incident.get("slug", "")
            sev_str = incident.get("severity", "minor")
            sev = Severity(sev_str) if sev_str in [s.value for s in Severity] else Severity.MINOR

            if severity_order.get(sev, 0) < min_sev:
                continue

            # Check if we have a dependency mapping for this vendor
            vendor_map = VENDOR_DEPENDENCY_MAP.get(slug)
            if not vendor_map:
                # Try partial match (e.g. "cloudflare-stream" matches "cloudflare")
                for key, vmap in VENDOR_DEPENDENCY_MAP.items():
                    if slug.startswith(key) or key in slug:
                        vendor_map = vmap
                        break

            if not vendor_map or not vendor_map.get("affected_symbols"):
                continue

            affected = vendor_map["affected_symbols"]
            symbols = list(affected.keys())
            companies = [f"{sym}: {desc}" for sym, desc in affected.items()]

            # Confidence based on severity and incident recency
            confidence = 0.5
            if sev == Severity.CRITICAL:
                confidence = 0.8
            elif sev == Severity.MAJOR:
                confidence = 0.65

            # Boost confidence if incident is recent (started within 24h)
            started_at = incident.get("startedAt", "")
            if started_at:
                try:
                    start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    age_hours = (datetime.now(timezone.utc) - start_dt).total_seconds() / 3600
                    if age_hours < 6:
                        confidence = min(confidence + 0.15, 0.95)
                    elif age_hours > 48:
                        confidence = max(confidence - 0.2, 0.3)
                except Exception:
                    pass

            signal = VendorIncidentSignal(
                signal_type=SignalType.AVOID,
                vendor_slug=slug,
                vendor_name=vendor_map["name"],
                incident_severity=sev,
                incident_title=incident.get("title", "Unknown"),
                incident_started=started_at,
                affected_symbols=symbols,
                affected_companies=companies,
                confidence=round(confidence, 2),
                reasoning=f"{vendor_map['name']} ({vendor_map['category']}) has a {sev.value} incident: {incident.get('title', '')}. "
                          f"{len(symbols)} S&P 500 companies may be affected. "
                          f"Avoiding new buys in affected symbols until vendor recovers.",
                generated_at=now,
            )
            signals.append(signal)

        return signals

    def signals_to_dict_list(self, signals: List[VendorIncidentSignal]) -> List[Dict]:
        """Convert signals to JSON-serializable dicts."""
        return [asdict(s) for s in signals]


def run_with_pulsewatch_data(incidents: List[Dict]) -> List[Dict]:
    """Entry point for use with PulseWatch MCP data.

    Pass the result from pulsewatch__list_open_incidents directly.
    """
    gen = VendorIncidentSignalGenerator()
    signals = gen.generate_signals(incidents, min_severity=Severity.MAJOR)
    return gen.signals_to_dict_list(signals)


if __name__ == "__main__":
    # Standalone test with mock data
    test_incidents = [
        {
            "slug": "cloudflare",
            "severity": "major",
            "title": "Edge network degradation",
            "startedAt": datetime.now(timezone.utc).isoformat(),
        },
        {
            "slug": "twilio",
            "severity": "critical",
            "title": "API outage affecting messaging",
            "startedAt": datetime.now(timezone.utc).isoformat(),
        },
    ]

    signals = run_with_pulsewatch_data(test_incidents)
    print(json.dumps(signals, indent=2))