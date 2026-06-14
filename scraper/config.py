
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

DATABASE_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://leadsignal:leadsignal@localhost:5432/leadsignal")
