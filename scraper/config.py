import os
from dataclasses import dataclass
from typing import List


@dataclass
class Geography:
    city: str
    state: str
    state_code: str
    zips: List[str]
    radius_miles: int = 25


OMAHA = Geography(
    city="Omaha",
    state="Nebraska",
    state_code="NE",
    zips=[
        "68102", "68104", "68105", "68106", "68107", "68108", "68110", "68111",
        "68112", "68114", "68116", "68117", "68118", "68122", "68124", "68127",
        "68130", "68131", "68132", "68134", "68135", "68136", "68137", "68138",
        "68142", "68144", "68152", "68154", "68164", "68172", "68181", "68183",
        "68197", "68198",
    ],
    radius_miles=25,
)

# Search keywords for local B2B lead gen and service-provider intelligence
TARGET_INDUSTRIES = [
    "HVAC", "plumbing", "roofing", "electrical", "landscaping",
    "home remodeling", "property management", "real estate",
    "software", "IT services", "cybersecurity", "MSP",
    "healthcare", "dental", "medical practice", "veterinary",
    "logistics", "trucking", "warehouse", "manufacturing",
    "restaurant", "retail", "salon", "fitness", "gym",
]

# Hiring thresholds
HIRING_SPIKE_WINDOW_DAYS = 7
HIRING_SPIKE_MIN_NEW_JOBS = 3

# Review thresholds
REVIEW_CLUSTER_WINDOW_DAYS = 14
REVIEW_CLUSTER_MIN_REVIEWS = 3
REVIEW_CLUSTER_MAX_STARS = 2.0

# Permit thresholds
PERMIT_MIN_PROJECT_VALUE = 50000


def _default_db_path() -> str:
    """Return an absolute SQLite path shared by the backend app and scrapers."""
    cwd = os.getcwd()
    if os.path.basename(cwd) == "backend":
        return os.path.abspath("leadsignal.db")
    if os.path.basename(cwd) == "leadsignal":
        return os.path.abspath(os.path.join("backend", "leadsignal.db"))
    # Fallback: assume the backend dir is next to scraper dir.
    this_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(this_dir, "..", "backend"))
    if os.path.isdir(backend_dir):
        return os.path.join(backend_dir, "leadsignal.db")
    return os.path.abspath("leadsignal.db")


DATABASE_URL = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL") or f"sqlite:///{_default_db_path()}"
# The scraper uses synchronous SQLAlchemy sessions, so async driver URLs
# (e.g., sqlite+aiosqlite or postgresql+asyncpg) must be converted to their sync equivalent.
if DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///")
if DATABASE_URL.startswith("sqlite:///./"):
    DATABASE_URL = f"sqlite:///{_default_db_path()}"
if DATABASE_URL.startswith("postgresql+asyncpg://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
if DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL.split("://", 1)[0]:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2" + DATABASE_URL.removeprefix("postgres")

# PermitStack API
PERMITSTACK_API_KEY = os.getenv("PERMITSTACK_API_KEY", "")
PERMITSTACK_API_BASE = "https://api.permit-stack.com/v1"
PERMITSTACK_MIN_VALUE = int(os.getenv("PERMITSTACK_MIN_VALUE", "1000"))

# Thresholds and constants for the expanded Omaha signal set
DOR_DELINQ_MIN_BALANCE = 500
DOR_DELINQ_COUNTIES = ["28"]  # Douglas County FIPS code in NE

DCGIS_OMaha_BBOX_WGS84 = "-96.05,41.16,-95.85,41.33"

DOUGLAS_BIDS_MIN_VALUE = 1000

CIVICDATA_HISTORICAL_PACKAGE = "blds_permitcore_historical_aa_14757"
CIVICDATA_HISTORICAL_RESOURCE = "efecb9f2-b254-4e34-90ce-4097fbe82322"
CIVICDATA_API_BASE = "https://www.civicdata.com/api/3"

# Apify
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "")
