#!/usr/bin/env python3
"""Auto-map PulseWatch vendors to S&P 500 affected stocks by category+sector.

Generates a comprehensive vendor→stock dependency map for the vendor alpha
signal generator. Uses category-based sector affinity + keyword matching.
"""

import json
from typing import Dict, List, Set

# ─── S&P 500 by sector (abbreviated, top companies) ───────────────────────
SP500_BY_SECTOR = {
    "IT": ["AAPL", "MSFT", "NVDA", "AVGO", "ADBE", "CRM", "ORCL", "NOW", "INTC", "AMD",
           "CSCO", "TXN", "QCOM", "IBM", "AMAT", "KLAC", "SNPS", "CDNS", "ANET", "APH",
           "ADI", "MCHP", "MRVL", "FTNT", "PANW", "NET", "CRWD", "DDOG", "SNOW", "PLTR",
           "ZM", "MDB", "TEAM", "HUBS", "MNDY", "DDOG", "WDC", "STX", "KEYS", "IT",
           "FICO", "GPN", "CTSH", "GLW", "JNPR", "NTAP", "SWKS"],
    "COMM": ["GOOGL", "GOOG", "META", "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
             "CHTR", "WBD", "SIRI", "EA", "TTWO", "TKO", "ROKU", "CZH"],
    "CONDISC": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "BKNG", "ABNB",
                "UBER", "LYFT", "EBAY", "ETSY", "DPZ", "YUM", "MELI", "TGT", "WBD",
                "RIVN", "GM", "F", "CZR", "WYNN", "MAR", "HLT", "DPZ", "LULU",
                "ULTA", "WHR", "POOL", "LEN", "DRI", "CMG", "SHAK", "JD", "BABA",
                "PDD", "APTV", "KMX", "ORLY", "AZO", "ROST", "DG", "DLTR"],
    "FIN": ["JPM", "BAC", "WFC", "GS", "MS", "PYPL", "XYZ", "AXP", "V", "MA",
            "SCHW", "BLK", "BX", "C", "COF", "USB", "PNC", "TFC", "AIG", "CB",
            "MMC", "ALL", "MET", "PRU", "AON", "BRO", "MCK", "CI", "UNH",
            "HIG", "L", "MCO", "RJF", "TROW", "NDAQ", "CME", "ICE", "SPGI",
            "FIS", "FICO", "GPN", "CFG", "RF", "KEY", "HBAN", "FITB", "ZION"],
    "HEALTH": ["UNH", "LLY", "JNJ", "ABBV", "MRK", "PFE", "TMO", "ABT", "DHR",
               "VRTX", "BMY", "AMGN", "GILD", "REGN", "BIIB", "MDT", "ISRG",
               "DXCM", "ZBH", "SYK", "BSX", "ALGN", "IDXX", "ILMN", "WAT",
               "A", "IQV", "VEEV", "CERN", "HOLX", "TECH", "RMD", "STE", "WST",
               "MOH", "HCA", "THC", "DGX", "LH", "FON"],
    "STAPLES": ["WMT", "PG", "COST", "KO", "PEP", "MDLZ", "CL", "KMB", "GIS",
                "K", "HSY", "STZ", "DEO", "BTI", "PM", "MO", "SYY", "CAG",
                "MJN", "CHD", "CLX", "CPB", "HRL", "TAP", "TSN", "ADM",
                "BG", "FLO", "SJM", "MNST", "CCEP"],
    "ENERGY": ["XOM", "CVX", "COP", "SLB", "EOG", "PSX", "MPC", "VLO", "HAL",
               "BKR", "OXY", "APA", "HES", "DVN", "FANG", "CTRA", "MUR",
               "RRC", "EQT", "AR", "CNQ", "SU", "WMB", "KMI", "OKE", "ET",
               "TRGP", "ONEOK", "DTN", "NOV", "CAM", "PDCE", "CHK"],
    "INDUST": ["GE", "CAT", "HON", "UPS", "UNP", "BA", "RTX", "LMT", "DE",
               "PCAR", "FAST", "ODFL", "JCI", "EMR", "ETN", "ROK", "DOV",
               "ITW", "MMM", "WM", "RSG", "FEEX", "GWW", "LEN", "DHI",
               "LHX", "GD", "NOC", "TXT", "HEI", "HII", "TDG", "CR", "CMI",
               "PWR", "ACM", "J", "ALLE", "AOS", "PNR", "ROP", "SWK"],
    "MATERIALS": ["LIN", "APD", "SHW", "ECL", "NEM", "FCX", "NUE", "DOW",
                  "DD", "PPG", "LYB", "IFF", "CE", "ALB", "MOS", "FMC",
                  "CF", "VMC", "MLM", "PKG", "IP", "WRK", "BALL", "CCK",
                  "AVY", "BERY", "SEE", "GEO", "RS"],
    "UTILITIES": ["NEE", "SO", "DUK", "AEP", "EXC", "SRE", "XEL", "WEC",
                  "ED", "DTE", "AEE", "PEG", "FE", "EIX", "SJI", "ATO",
                  "CNP", "CMS", "D", "ETR", "ES", "NRG", "PNW", "PPL",
                  "AIV", "WTRG", "AWK", "AWR", "CWT", "WTR"],
    "REALEST": ["PLD", "AMT", "EQIX", "SPG", "PSA", "O", "DLR", "WELL",
                "VICI", "AVB", "EQR", "INVH", "MAA", "CPT", "ARE", "BXP",
                "KIM", "REG", "ESS", "FRT", "PEAK", "HR", "EXR", "CSGP",
                "CBRE", "JLL"],
}

# ─── Vendor category → affected sector affinity ───────────────────────────
# Higher weight = stronger dependency
CATEGORY_SECTOR_AFFINITY = {
    "cloud":        {"IT": 0.9, "COMM": 0.7, "CONDISC": 0.6, "FIN": 0.5, "HEALTH": 0.4, "STAPLES": 0.3, "INDUST": 0.3, "REALEST": 0.2, "UTILITIES": 0.2},
    "cdn_edge":     {"IT": 0.7, "COMM": 0.8, "CONDISC": 0.8, "FIN": 0.4, "HEALTH": 0.2, "STAPLES": 0.5, "INDUST": 0.2, "REALEST": 0.1, "ENERGY": 0.1, "MATERIALS": 0.1},
    "payments":     {"FIN": 0.9, "CONDISC": 0.7, "IT": 0.5, "STAPLES": 0.6, "COMM": 0.3, "HEALTH": 0.2},
    "comms":        {"IT": 0.8, "COMM": 0.7, "HEALTH": 0.4, "FIN": 0.5, "CONDISC": 0.4},
    "identity":     {"IT": 0.9, "FIN": 0.8, "HEALTH": 0.6, "COMM": 0.5, "CONDISC": 0.3},
    "monitoring":   {"IT": 0.8, "FIN": 0.4, "HEALTH": 0.3, "COMM": 0.3, "INDUST": 0.2},
    "database":     {"IT": 0.9, "FIN": 0.6, "HEALTH": 0.5, "COMM": 0.4, "CONDISC": 0.3},
    "devops":       {"IT": 0.9, "FIN": 0.4, "COMM": 0.3, "INDUST": 0.2},
    "ai_ml":        {"IT": 0.7, "COMM": 0.6, "HEALTH": 0.5, "FIN": 0.4, "CONDISC": 0.3, "STAPLES": 0.2, "INDUST": 0.2},
    "security":     {"IT": 0.9, "FIN": 0.7, "HEALTH": 0.5, "COMM": 0.4, "INDUST": 0.3, "ENERGY": 0.3},
    "crm_saas":     {"IT": 0.8, "FIN": 0.5, "HEALTH": 0.4, "CONDISC": 0.3, "INDUST": 0.3, "STAPLES": 0.3},
    "ecommerce":    {"CONDISC": 0.9, "STAPLES": 0.7, "IT": 0.3, "FIN": 0.3},
    "hosting":      {"IT": 0.7, "COMM": 0.5, "CONDISC": 0.4, "FIN": 0.2, "HEALTH": 0.2},
    "analytics":    {"IT": 0.7, "COMM": 0.6, "CONDISC": 0.5, "FIN": 0.4, "HEALTH": 0.3, "STAPLES": 0.3},
    "email":        {"IT": 0.6, "COMM": 0.5, "CONDISC": 0.6, "STAPLES": 0.4, "FIN": 0.3},
    "hr_payroll":   {"INDUST": 0.6, "HEALTH": 0.5, "IT": 0.4, "FIN": 0.4, "CONDISC": 0.3, "STAPLES": 0.3},
    "productivity": {"IT": 0.7, "FIN": 0.4, "HEALTH": 0.3, "CONDISC": 0.3, "INDUST": 0.3, "COMM": 0.3, "STAPLES": 0.2},
}

# ─── High-impact vendor keywords (critical infrastructure) ────────────────
HIGH_IMPACT_KEYWORDS = {
    "aws": 0.9, "azure": 0.9, "google-cloud": 0.85, "cloudflare": 0.85,
    "akamai": 0.7, "fastly": 0.7, "stripe": 0.85, "adyen": 0.7,
    "twilio": 0.8, "sendgrid": 0.6, "okta": 0.8, "auth0": 0.7,
    "datadog": 0.6, "snowflake": 0.7, "mongodb": 0.5, "redis": 0.5,
    "github": 0.6, "gitlab": 0.5, "docker": 0.4, "kubernetes": 0.4,
    "openai": 0.5, "anthropic": 0.4, "sentry": 0.4, "new-relic": 0.5,
    "grafana": 0.4, "elastic": 0.5, "splunk": 0.5, "crowdstrike": 0.7,
    "zscaler": 0.7, "1password": 0.3, "vercel": 0.5, "netlify": 0.4,
    "supabase": 0.4, "planet-scale": 0.4, "neon": 0.3, "fly": 0.3,
    "paypal": 0.6, "square": 0.5, "block": 0.5, "plaid": 0.6,
    "hubspot": 0.4, "salesforce": 0.6, "zendesk": 0.4, "atlassian": 0.5,
    "jira": 0.4, "notion": 0.3, "slack": 0.5, "zoom": 0.4,
    "shopify": 0.6, "wix": 0.3, "bigcommerce": 0.3,
    "amplitude": 0.3, "segment": 0.4, "braze": 0.3, "mailchimp": 0.3,
    "klaviyo": 0.3, "adp": 0.4, "workday": 0.5, "gusto": 0.3,
    "digitalocean": 0.5, "linode": 0.3, "vultr": 0.3, "rackspace": 0.4,
    "heroku": 0.3, "oracle-cloud": 0.5, "alibaba-cloud": 0.4,
    "ringcentral": 0.4, "vonage": 0.4, "sinch": 0.4, "bandwidth": 0.4,
    "plivo": 0.3, "messagebird": 0.3, "8x8": 0.3,
}

# Vendor categorization keywords (same as earlier script)
CATEGORY_KEYWORDS = {
    "cloud": ["aws", "azure", "gcp", "google-cloud", "oracle-cloud", "digitalocean", "linode", "vultr",
              "rackspace", "heroku", "fly", "render", "vercel", "netlify", "yandex-cloud",
              "alibaba-cloud", "ibm-cloud", "scaleway", "hetzner", "contabo", "kamatera"],
    "cdn_edge": ["cloudflare", "akamai", "fastly", "imperva", "sucuri", "bunnycdn", "keycdn", "stackpath",
                 "bentcdn", "cdnsun", "cdn77"],
    "payments": ["stripe", "adyen", "paypal", "square", "block", "checkout", "razorpay", "flutterwave",
                 "dlocal", "salt-edge", "transak", "affirm", "afterpay", "klarna", "plaid", "tink",
                 "mollie", "braintree", "wise", "bill-com", "shippo", "alipay", "apple-pay",
                 "google-pay", "shop-pay", "amazon-pay", "m-pesa", "paychex", "bolt-checkout",
                 "openpayd", "nium", "airwallex", "currencycloud"],
    "comms": ["twilio", "sendgrid", "vonage", "sinch", "plivo", "bandwidth", "messagebird",
              "ringcentral", "8x8", "dialpad", "agora", "100ms", "vapi", "bland", "retell",
              "mailgun", "postmark", "resend", "postal", "postal-server", "sparkpost"],
    "identity": ["okta", "auth0", "onelogin", "jumpcloud", "fusionauth", "stytch", "magic-link",
                 "clerk", "frontegg", "perimeter81", "zscaler", "tailscale", "cloudflare-zero-trust",
                 "ping", "authentik", "keycloak", "casdoor", "supabase-auth", "descope",
                 "workos", "logto", "corbado", "moq", "fief", "ory", " Hanko"],
    "monitoring": ["datadog", "grafana", "grafana-cloud", "grafana-k6", "prometheus", "new-relic",
                   "sentry", "rollbar", "bugsnag", "sumologic", "splunk", "elastic-cloud",
                   "elastic-security", "logtail", "betterstack", "checkly", "pingdom",
                   "statuspage", "uptimerobot", "freshping", "insping", "monitoro", "downnotifier",
                   "hetrix", "upmonito", "pagely", "cronitor", "healthchecks", "cron-job",
                   "site24x7", "stackstate", "obico", "robusta", "incident-io", "squadcast",
                   "alertdeck", "dispatch", "firehydrant", "rootly", "incident"],
    "database": ["snowflake", "mongodb", "redis", "postgres", "supabase", "planet-scale", "fauna",
                 "cockroach", "neon", "xata", "upstash", "convex", "hasura", "prisma", "zilliz",
                 "meilisearch", "typesense", "algolia", "elastic", "opensearch", "weaviate",
                 "pinecone", "milvus", "qdrant", "dragonfly", "tigris", "ferret", "kestra",
                 "redpanda", "confluent", "kafka", "debezium", "estuary", "airbyte", "fivetran",
                 "estuary-flow", "sling"],
    "devops": ["github", "gitlab", "circleci", "travis-ci", "buildkite", "jenkins",
               "codefresh", "docker", "kubernetes", "render", "railway", "fly-io",
               "porter", "northflank", "release", "shipa", "koyeb", "zeabur", "coolify"],
    "ai_ml": ["openai", "anthropic", "ai21", "cohere", "huggingface", "replicate", "together",
              "perplexity", "stability", "elevenlabs", "deepgram", "assemblyai", "runway",
              "vapi", "retell", "bland", "carter", "wellfound", "pika", "suno",
              "luma", "kuaishou", "minimax", "mistral", "groq", "fireworks", "anyscale",
              "modal", "baseten", "lepton", "vertex", "sagemaker", "bedrock",
              "weights-biases", "comet", "databricks", "anyscale", "determined"],
    "security": ["cloudflare", "crowdstrike", "sentinelone", "qualys", "rapid7", "tenable",
                 "tenable-io", "sophos", "f5", "fortinet", "zscaler", "okta", "1password",
                 "dashlane", "bitwarden", "lastpass", "keeper", "nordvpn", "expressvpn",
                 "surfshark", "cyberghost", "private-internet", "mullvad", "tailscale",
                 "wireguard", "perimeter81", "cloudflare-zero-trust", "twingate",
                 "strongdm", "teleport", "boundary", "teleport"],
    "crm_saas": ["salesforce", "hubspot", "zendesk", "intercom", "freshdesk", "zoho",
                 "monday", "asana", "atlassian", "jira", "linear", "notion", "airtable",
                 "smartsheet", "clickup", "wrike", "aha", "productboard", "shortcut",
                 "clubhouse", "trello", "basecamp", "teamwork", "proofhub", "nifty",
                 "doodle", "calendly", "acuity", "hubspot-crm", "pipedrive", "freshsales",
                 "close", "keap", "agile", "insightly"],
    "ecommerce": ["shopify", "bigcommerce", "woocommerce", "wix", "wix-commerce", "vtex",
                  "magento", "salesforce-commerce", "amazon-seller", "etsy", "ebay",
                  "alibaba", "rakuten", "shopline", "squarespace", "weebly", "webflow",
                  "ecwid", "3dcart", "volusion", "shopify-plus", "shift4shop"],
    "hosting": ["godaddy", "namecheap", "bluehost", "wp-engine", "kinsta", "flywheel",
                "acquia", "hostgator", "dreamhost", "siteground", "inmotion", "a2hosting",
                "greengeeks", "hostinger", "tsohost", "crazy-domains", "hover", "porkbun",
                "dnsimple", "name.com", "dynadot"],
    "analytics": ["amplitude", "mixpanel", "segment", "google-analytics", "hotjar", "fullstory",
                  "logrocket", "heap", "matomo", "posthog", "plausible", "fathom", "pirsch",
                  "umami", "counter", "gauges", "statcounter", "chartbeat", "goatcounter",
                  "kissmetrics", "kameleoon", "optimizely", "vwo", "ab-tasty", "convert"],
    "email": ["sendgrid", "mailgun", "postmark", "mailerlite", "braze", "customer-io",
              "iterable", "klaviyo", "mailchimp", "constant-contact", "campaign-monitor",
              "aweber", "getresponse", "activecampaign", "convertkit", "beehiiv",
              "substack", "ghost", "buttondown", "moosend", "omnisend", "sailthru",
              "sparkpost", "postal", "resend", "loops", "customer-io", "knak"],
    "hr_payroll": ["adp", "paychex", "gusto", "bamboohr", "workday", "rippling", "deel",
                   "remote", "oyster-hr", "icims", "greenhouse", "lever", "15five",
                   "lattice", "culture-amp", "peakon", "qualtrics", "glint", "survey",
                   "achievers", "kazoo", "workhuman", "bonusly", "workleap", "udemy",
                   "coursera", "pluralsight", "a-cloud-guru"],
    "productivity": ["slack", "zoom", "google-workspace", "microsoft-365", "dropbox", "box",
                     "notion", "airtable", "smartsheet", "asana", "clickup", "trello",
                     "basecamp", "confluence", "jira", "linear", "teamwork", "proofhub",
                     "coda", "quip", "airtable", "figma", "miro", "lucid", " mural",
                     "conceptboard", "webex", "gotomeeting", "bluejeans", "highfive"],
}


def categorize_vendor(slug: str) -> List[str]:
    """Categorize a vendor slug based on keyword matching."""
    cats = []
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in slug or slug.startswith(kw) or slug == kw:
                if cat not in cats:
                    cats.append(cat)
                break
    # Fallback pattern matching
    if not cats:
        if any(w in slug for w in ["pay", "billing", "invoice", "subscript", "checkout"]):
            cats.append("payments")
        elif any(w in slug for w in ["auth", "login", "sso", "identity", "password"]):
            cats.append("identity")
        elif any(w in slug for w in ["cdn", "edge", "dns"]):
            cats.append("cdn_edge")
        elif any(w in slug for w in ["monitor", "alert", "status", "uptime", "health", "ping"]):
            cats.append("monitoring")
        elif any(w in slug for w in ["ai", "ml", "llm", "gpt", "model", "neural"]):
            cats.append("ai_ml")
        elif any(w in slug for w in ["chat", "message", "sms", "voice", "call", "video"]):
            cats.append("comms")
        elif any(w in slug for w in ["security", "firewall", "vpn", "threat"]):
            cats.append("security")
        elif any(w in slug for w in ["data", "warehouse", "lake", "etl", "pipeline"]):
            cats.append("database")
        elif any(w in slug for w in ["crm", "ticket", "support", "helpdesk"]):
            cats.append("crm_saas")
        elif any(w in slug for w in ["shop", "store", "commerce", "cart"]):
            cats.append("ecommerce")
        elif any(w in slug for w in ["email", "mail", "newsletter"]):
            cats.append("email")
        elif any(w in slug for w in ["analytics", "tracking", "metrics"]):
            cats.append("analytics")
        elif any(w in slug for w in ["hr", "payroll", "recruit", "hire", "onboard"]):
            cats.append("hr_payroll")
    return cats if cats else ["uncategorized"]


def get_impact_score(slug: str, categories: List[str]) -> float:
    """Score vendor impact: 0-1, higher = more likely to move stocks."""
    # Check high-impact keywords
    for kw, score in HIGH_IMPACT_KEYWORDS.items():
        if kw in slug or slug.startswith(kw):
            return score
    # Category-based default
    high_impact_cats = {"cloud", "cdn_edge", "payments", "comms", "identity", "security"}
    if any(c in high_impact_cats for c in categories):
        return 0.5
    return 0.3


def generate_vendor_map(slugs: List[str]) -> Dict:
    """Generate complete vendor → S&P 500 mapping."""
    vendor_map = {}

    for slug in slugs:
        cats = categorize_vendor(slug)
        impact = get_impact_score(slug, cats)

        # Skip uncategorized + low impact
        if cats == ["uncategorized"] and impact < 0.3:
            continue

        # Get affected symbols by sector affinity
        affected = {}
        for cat in cats:
            if cat == "uncategorized":
                continue
            affinity = CATEGORY_SECTOR_AFFINITY.get(cat, {})
            for sector, weight in affinity.items():
                sector_stocks = SP500_BY_SECTOR.get(sector, [])
                # Only include stocks with meaningful weight
                if weight * impact >= 0.2:
                    for sym in sector_stocks:
                        if sym not in affected:
                            affected[sym] = f"{cat} dependency ({sector} sector, weight={weight:.0%})"

        if affected:
            vendor_map[slug] = {
                "categories": cats,
                "impact_score": round(impact, 2),
                "affected_symbols": affected,
            }

    return vendor_map


if __name__ == "__main__":
    import sys
    vendor_file = sys.argv[1] if len(sys.argv) > 1 else "/tmp/pulsewatch_vendors.json"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "/tmp/vendor_sp500_map.json"

    with open(vendor_file) as f:
        slugs = json.load(f)

    print(f"Processing {len(slugs)} vendor slugs...")

    vendor_map = generate_vendor_map(slugs)

    # Stats
    total_vendors = len(slugs)
    mapped_vendors = len(vendor_map)
    total_mappings = sum(len(v["affected_symbols"]) for v in vendor_map.values())
    high_impact = sum(1 for v in vendor_map.values() if v["impact_score"] >= 0.6)
    medium_impact = sum(1 for v in vendor_map.values() if 0.4 <= v["impact_score"] < 0.6)
    low_impact = sum(1 for v in vendor_map.values() if v["impact_score"] < 0.4)

    print(f"\nResults:")
    print(f"  Total vendors: {total_vendors}")
    print(f"  Mapped vendors (with S&P 500 impact): {mapped_vendors}")
    print(f"  High impact (≥0.6): {high_impact}")
    print(f"  Medium impact (0.4-0.6): {medium_impact}")
    print(f"  Low impact (<0.4): {low_impact}")
    print(f"  Total vendor→stock mappings: {total_mappings}")
    print(f"  Avg symbols per vendor: {total_mappings / mapped_vendors:.1f}")

    # Top 20 by affected symbol count
    top20 = sorted(vendor_map.items(), key=lambda x: len(x[1]["affected_symbols"]), reverse=True)[:20]
    print(f"\nTop 20 vendors by affected symbol count:")
    for slug, info in top20:
        print(f"  {slug:<25s} impact={info['impact_score']:.2f} cats={info['categories']} affected={len(info['affected_symbols'])}")

    # Save
    with open(output_file, "w") as f:
        json.dump(vendor_map, f, indent=2)
    print(f"\nSaved to {output_file}")