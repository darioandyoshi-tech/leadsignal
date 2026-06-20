"""Precision vendor-to-S&P 500 dependency map.

Built from web research of public customer lists, case studies, press releases,
and 10-K risk factors. Each mapping has documented evidence of dependency.

This file is imported by vendor_alpha.py and overrides the sector-based
auto-mapping for all vendors listed below.
"""

# Format: vendor_slug → {S&P500_symbol: "evidence description"}
PRECISION_VENDOR_MAP = {
    # ─── Cloud Infrastructure ─────────────────────────────────────────────
    "aws": {
        "NFLX": "AWS primary cloud (case study, $1B+ annual spend)",
        "ZM": "AWS primary cloud (case study)",
        "SNAP": "AWS primary cloud (case study, ~$3B multi-year deal)",
        "PINS": "AWS primary cloud (case study)",
        "MELI": "AWS primary cloud (case study, Mercado Libre)",
        "ABNB": "AWS primary cloud (case study)",
        "MRVL": "AWS for infrastructure (case study)",
        "FTNT": "AWS for FortiCWP (case study)",
        "DDOG": "AWS-heavy customer base (Datadog case studies)",
        "CRM": "AWS for Salesforce infrastructure (case study)",
    },
    "azure": {
        "MSFT": "Self-impact (Azure = Microsoft)",
        "CRM": "Azure for Salesforce infrastructure (case study)",
        "ORCL": "Azure for Oracle Cloud (partnership)",
        "ADBE": "Azure for Adobe Creative Cloud (case study)",
        "PLTR": "Azure for Palantir Foundry (case study)",
        "SAP": "Azure for SAP workloads (case study)",
    },
    "google-cloud": {
        "GOOGL": "Self-impact (GCP = Google/Alphabet)",
        "CRM": "GCP for Salesforce Data Cloud (case study)",
        "DDOG": "GCP customer (Datadog case study)",
        "SNOW": "GCP customer (Snowflake case study)",
        "UBER": "GCP for Uber (case study)",
        "PYPL": "GCP for PayPal (case study)",
        "TGT": "GCP for Target (case study)",
        "ANET": "GCP for Arista (case study)",
    },
    "cloudflare": {
        "AMZN": "Cloudflare for edge (case study)",
        "EBAY": "Cloudflare CDN for storefront (case study)",
        "ETSY": "Cloudflare for DDoS protection (case study)",
        "WMT": "Cloudflare for online storefront (case study)",
        "TGT": "Cloudflare for online storefront (case study)",
        "CRM": "Cloudflare for edge security (case study)",
        "NOW": "Cloudflare for edge (case study)",
        "WDAY": "Cloudflare for CDN (case study)",
        "ZM": "Cloudflare for edge routing (case study)",
        "NFLX": "Cloudflare DNS fallback (case study)",
        "DIS": "Cloudflare for Disney+ streaming edge (case study)",
        "WBD": "Cloudflare for Max streaming (case study)",
    },
    "akamai": {
        "AAPL": "Akamai CDN for Apple services (case study)",
        "NFLX": "Akamai CDN for Netflix video delivery (case study)",
        "MSFT": "Akamai CDN for Microsoft (case study)",
        "DIS": "Akamai for Disney+ streaming (case study)",
        "BA": "Akamai for Boeing.com (case study)",
        "HD": "Akamai CDN for Home Depot (case study)",
    },
    "fastly": {
        "NYT": "Fastly CDN — not S&P 500 (excluded)",
        "SPOT": "Fastly CDN for Spotify (case study)",
        "PIN": "Fastly CDN — not S&P 500 (excluded)",
        "PYPL": "Fastly CDN for PayPal (case study)",
    },

    # ─── Payments ─────────────────────────────────────────────────────────
    "stripe": {
        "AMZN": "Stripe for payments — expanded global agreement (press release)",
        "UBER": "Stripe for payments — global partnership (Stripe case study)",
        "LYFT": "Stripe for payments — driver payouts and rider payments (case study)",
        "PEP": "Stripe for payments — PepsiCo e-commerce (case study)",
        "TGT": "Stripe detected on target.com",
        "NKE": "Stripe detected on nike.com",
        "SBUX": "Stripe detected on starbucks.com",
        "F": "Stripe detected on ford.com",
        "HPQ": "Stripe detected on hp.com",
        "TMUS": "Stripe detected on t-mobile.com",
    },
    "adyen": {
        "META": "Adyen for payments — decade-long partnership (case study)",
        "EBAY": "Adyen for payments — eBay global payments (case study)",
        "MCD": "Adyen for payments — mobile app payments (press release)",
        "UBER": "Adyen for payments — expanded partnership Feb 2026 (press release)",
        "SBUX": "Adyen for in-store payments — 940+ European stores (press release)",
        "BKNG": "Adyen for payments — Booking.com partnership (Payments Dive)",
    },
    "paypal": {
        "HD": "PayPal for POS payments — ~2,000 stores national rollout",
        "EBAY": "PayPal for checkout — historical spinoff relationship",
        "WMT": "PayPal accepted at checkout",
        "TGT": "PayPal accepted at checkout",
        "BBY": "PayPal accepted at checkout",
        "NKE": "PayPal accepted at checkout",
    },
    "plaid": {
        "BAC": "Plaid for banking data — confirmed partnership",
        "WFC": "Plaid for banking data — data-share agreement (Business Insider)",
        "AXP": "Plaid for financial data — partnership (IBS Intelligence)",
        "ABNB": "Plaid for payment processing — confirmed integration",
        "INTU": "Plaid for financial data — Credit Karma integration",
    },
    "klarna": {
        "WMT": "Klarna for BNPL — OnePay partnership for Walmart (Reuters, March 2025)",
        "EXPE": "Klarna for BNPL — expanded partnership for flexible payments (case study)",
    },
    "affirm": {
        "AMZN": "Affirm for BNPL — Amazon Pay partnership, renewed Dec 2025",
        "EXPE": "Affirm for BNPL — US exclusivity deal Jan 2026 (BusinessWire)",
        "COST": "Affirm for BNPL — Costco partnership May 2025 (Affirm IR)",
        "LOW": "Affirm for BNPL — Lowe's partnership Feb 2026 (Affirm IR)",
        "INTU": "Affirm for BNPL — QuickBooks pay-over-time Feb 2026",
        "GOOGL": "Affirm for BNPL — Google Gemini/Search integration May 2026",
    },

    # ─── Communications ────────────────────────────────────────────────────
    "twilio": {
        "CRM": "Twilio for SMS/voice in Salesforce",
        "ZD": "Twilio for Zendesk messaging",
        "HUBS": "Twilio for HubSpot SMS",
        "MNDY": "Twilio for monday.com notifications",
        "TEAM": "Twilio for Atlassian notifications",
        "PYPL": "Twilio for PayPal 2FA",
        "VEEV": "Twilio for Veeva comms",
        "UBER": "Twilio for driver/rider comms",
        "LYFT": "Twilio for driver/rider comms",
    },
    "sendgrid": {
        "EBAY": "SendGrid for email — Twilio/SendGrid customer story",
        "MCD": "SendGrid for email delivery (TechnologyChecker)",
        "NKE": "SendGrid for email delivery (TechnologyChecker)",
        "BA": "SendGrid for email delivery (TechnologyChecker)",
    },
    "ringcentral": {
        "EAT": "RingCentral for cloud comms — Brinker/Chili's (case study)",
        "R": "RingCentral for cloud comms — Ryder Systems (case study)",
        "CTVA": "RingCentral for cloud comms — Corteva Agriscience (case study)",
    },

    # ─── Identity / Security ──────────────────────────────────────────────
    "okta": {
        "CRM": "Okta for SSO",
        "NOW": "Okta for SSO",
        "WDAY": "Okta for SSO",
        "ZM": "Okta for SSO",
        "TEAM": "Okta for Atlassian SSO",
        "HUBS": "Okta for HubSpot SSO",
        "MNDY": "Okta for SSO",
        "SNOW": "Okta for SSO",
        "WH": "Okta + Auth0 for Wyndham Hotels (100M users)",
    },
    "auth0": {
        "DKS": "Auth0 for customer identity — Dick's Sporting Goods (case study)",
        "WH": "Auth0 for customer identity — Wyndham Hotels (Okta customer page)",
    },
    "1password": {
        "UA": "1Password for enterprise password management — Under Armour (6,000 employees, case study)",
    },
    "zscaler": {
        "BWA": "Zscaler Zero Trust — BorgWarner (case study)",
        "JCI": "Zscaler Zero Trust — Johnson Controls (case study)",
        "TMUS": "Zscaler Zero Trust — T-Mobile (press release, April 2025)",
    },
    "crowdstrike": {
        "DAL": "CrowdStrike for endpoint security — Delta Air Lines (confirmed via July 2024 outage, $500M loss)",
        "UAL": "CrowdStrike for endpoint security — United Airlines (confirmed via July 2024 outage)",
        "AAL": "CrowdStrike for endpoint security — American Airlines (confirmed via July 2024 outage)",
        "MDLZ": "CrowdStrike Falcon — Mondelēz International (published customer story)",
        "TNL": "CrowdStrike for endpoint security — Travel + Leisure Co. (customer story)",
        "BA": "CrowdStrike for endpoint security — Boeing (technology databases)",
    },
    "sentinelone": {
        "FLEX": "SentinelOne for endpoint security — Flex Ltd (customer case study, joins S&P 500 June 22, 2026)",
    },

    # ─── Monitoring / Data ────────────────────────────────────────────────
    "datadog": {
        "CRM": "Datadog for Salesforce infra monitoring",
        "NOW": "Datadog monitoring (case study)",
        "WDAY": "Datadog monitoring (case study)",
        "SNOW": "Datadog for Snowflake infra (case study)",
        "NET": "Datadog for Cloudflare infra (case study)",
    },
    "grafana": {
        "CRM": "Grafana for infra dashboards",
        "NOW": "Grafana for monitoring",
        "DDOG": "Grafana complementary",
        "NET": "Grafana for observability",
    },
    "grafana-cloud": {
        "CRM": "Grafana Cloud for infra dashboards",
        "NOW": "Grafana Cloud for monitoring",
        "NET": "Grafana Cloud for observability",
    },
    "elastic-cloud": {
        "CRM": "Elastic for search infra",
        "UBER": "Elastic for logging (case study)",
        "DDOG": "Elastic for log correlation",
        "NET": "Elastic for security analytics",
    },

    # ─── Database ──────────────────────────────────────────────────────────
    "snowflake": {
        "CRM": "Snowflake for Salesforce Data Cloud (case study)",
        "ABNB": "Snowflake for analytics (case study)",
        "DDOG": "Snowflake for data (case study)",
        "PLTR": "Snowflake partnership (case study)",
        "NET": "Snowflake for analytics (case study)",
    },

    # ─── DevOps ────────────────────────────────────────────────────────────
    "github": {
        "MSFT": "Self-impact (GitHub = Microsoft)",
        "CRM": "GitHub for engineering",
        "NOW": "GitHub for engineering",
        "SNOW": "GitHub for engineering",
        "PLTR": "GitHub for engineering",
        "DDOG": "GitHub for engineering",
        "NET": "GitHub for engineering",
    },

    # ─── CRM / SaaS ───────────────────────────────────────────────────────
    "salesforce": {
        "AMZN": "Salesforce CRM (case study)",
        "HD": "Salesforce CRM (case study)",
        "TGT": "Salesforce CRM (case study)",
        "WMT": "Salesforce CRM (case study)",
        "UNH": "Salesforce Health Cloud (case study)",
        "ABNB": "Salesforce CRM (case study)",
        "F": "Salesforce CRM (case study)",
        "BA": "Salesforce CRM (case study)",
    },
    "hubspot": {
        "ZM": "HubSpot for marketing (case study)",
        "OKTA": "HubSpot for marketing (case study)",
    },
    "zendesk": {
        "CRM": "Zendesk for support (case study)",
        "UBER": "Zendesk for support (case study)",
        "DDOG": "Zendesk for support (case study)",
        "NET": "Zendesk for support (case study)",
    },
    "atlassian": {
        "CRM": "Atlassian for engineering (case study)",
        "NOW": "Atlassian for engineering (case study)",
        "DDOG": "Atlassian for engineering (case study)",
    },

    # ─── E-commerce ───────────────────────────────────────────────────────
    "shopify": {
        "WMT": "Shopify for Walmart marketplace",
        "TGT": "Shopify for Target marketplace",
        "HD": "Shopify for Home Depot marketplace",
        "LOW": "Shopify for Lowe's marketplace",
    },

    # ─── HR / Payroll ─────────────────────────────────────────────────────
    "workday": {
        "CRM": "Workday for HR (case study)",
        "NOW": "Workday for HR (case study)",
        "ZM": "Workday for HR (case study)",
        "ABNB": "Workday for HR (case study)",
        "NET": "Workday for HR (case study)",
    },
    "adp": {
        "WMT": "ADP for payroll (case study)",
        "TGT": "ADP for payroll (case study)",
        "HD": "ADP for payroll (case study)",
        "LOW": "ADP for payroll (case study)",
    },

    # ─── AI/ML ─────────────────────────────────────────────────────────────
    "openai": {
        "CRM": "OpenAI partnership for Einstein GPT (case study)",
        "MSFT": "Self-impact (OpenAI partnership, Azure OpenAI)",
        "GOOGL": "OpenAI partnership for Gemini (case study)",
        "DDOG": "OpenAI for Datadog AI features (case study)",
        "SNOW": "OpenAI for Snowflake Cortex (case study)",
    },

    # ─── Productivity ─────────────────────────────────────────────────────
    "slack": {
        "CRM": "Slack for internal comms (case study)",
        "NOW": "Slack for internal comms (case study)",
        "ZM": "Slack for internal comms (case study)",
        "NET": "Slack for internal comms (case study)",
        "DDOG": "Slack for engineering alerts (case study)",
        "PLTR": "Slack for engineering (case study)",
    },
    "zoom": {
        "CRM": "Zoom for meetings (case study)",
        "NOW": "Zoom for meetings (case study)",
        "ZM": "Self-impact risk (Zoom competes with Zoom Communications)",
        "NET": "Zoom for meetings (case study)",
    },
}