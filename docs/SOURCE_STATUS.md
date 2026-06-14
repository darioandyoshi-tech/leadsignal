# LeadSignal Source Status — June 14, 2026

## Verified Live Sources

| Signal | Source | Status | Automation |
|--------|--------|--------|------------|
| Hiring spikes | Apify `borderline/indeed-scraper` | ✅ Returns real Omaha jobs | `scraper/sources/apify_jobs_reviews.py` |
| Negative review clusters | Apify `compass/Google-Maps-Reviews-Scraper` + Google Places API | ✅ Verified | `scraper/sources/apify_jobs_reviews.py`, `scraper/sources/google_reviews.py` |
| Permits (live current) | PermitStack API | ✅ Live recent Omaha permits (small volume) | `scraper/sources/permitstack_omaha.py` |
| Permits (inspections) | CivicData BLDS inspection history | ✅ 373 signals from 500 records | `scraper/sources/civicdata_inspections.py` |
| Permits (historical) | CivicData CKAN `blds_permitcore_historical_aa_14757` | ✅ 2006-2007 historical backfill | `scraper/sources/civicdata_permits.py` |
| Parcel/property changes | DCGIS `Parcels_public` FeatureServer | ✅ Live real records | `scraper/sources/dcgis_parcels.py` |
| Tax-delinquent property | Nebraska DOR county Excel | ✅ Douglas 2026 Excel parses | `scraper/sources/ne_dor_delinquency.py` |
| Gov bid awards | Douglas County Purchasing Ionwave | ✅ List page parseable; detail page TBD | `scraper/sources/douglas_bids.py` |
| Federal awards in Omaha | USASpending.gov API | ✅ Real awards returned | `scraper/sources/usaspending_omaha.py` |
| Nebraska liquor licenses | NLCC active roster Excel | ✅ 1,580 signals from 6,295 rows | `scraper/sources/nlcc_licenses.py` |
| Nebraska DOL contractors | DOL contractor registration search | ✅ 100 signals from 500 inspected | `scraper/sources/ne_dol_contractors.py` |
| NADC vendor leads | Nebraska campaign-finance bulk ZIP | ✅ 521 signals from 4,500 rows | `scraper/sources/nadc_vendors.py` |
| Public notices | Omaha Daily Record RSS feeds | ✅ 198 signals from 27 feeds | `scraper/sources/odr_feeds.py` |

## Placeholder / Blocked Sources

| Source | Reason |
|--------|--------|
| Accela live current permits | JS-heavy portal; stub with seed data |
| Sarpy County tax-sale PDF | Needs PDF table extraction (PyMuPDF/pdfplumber) |
| Sarpy County SmartGov | Citizenserve portal; needs browser automation |
| Nebraska SOS entity search | reCAPTCHA-gated; paid batch portal available |
| Nebraska UCC | Paid interactive web form |
| Nebraska DHHS licenses | JS-driven search; bulk lists available |
| BBB Omaha | Blocks raw HTTP; use Parse.bot or Apify actor |
| OSHA establishment search | Oracle APEX form; needs Apify/browser automation |
| LandmarkWeb deeds | JS disclaimer + paid docs; use ODR/DGIS instead |
| Google Places reviews | Works but GOOGLE_PLACES_API_KEY not configured in this run |

## Rejected Sources

| Source | Reason |
|--------|--------|
| Indeed public HTML | 403 blocked |
| ZipRecruiter public HTML | 403 blocked |
| CivicData current permit datastores (2016–present, 2018–current) | Empty (0 rows) |
| Douglas County Assessor | 403 |
| Nebraska court records JUSTICE portal | Subscriber-only |
| Nebraska Work Search | Incapsula block |

## Apify Actor Candidates

| Use case | Actor | Notes |
|----------|-------|-------|
| US business licenses | `intelscrape/business-license-scraper` | Paid; new-license signals |
| US building permits | `jungle_synthesizer/building-permits-national-aggregator` | 30+ metros |
| Realtor.com / Zillow foreclosure | `scrapemind/realtor-com-scraper`, `crawlerbros/zillow-foreclosure-scraper` | Distressed property signals |
| OSHA inspections | `fortuitous_pirate/osha-inspection-scraper` | Compliance signals |
| LinkedIn company growth | `harvestapi/linkedin-company` | Hiring/growth signals |
| Website change monitor | `ryanclinton/website-change-monitor` | Watch ODR / source pages |

## ODR Source Mapping

Omaha Daily Record repackages the following official sources:

- **Building / Electrical / Plumbing / Mechanical Permits** → City of Omaha Accela Citizen Access (`aca-prod.accela.com/OMAHA`)
- **Real Estate Leads / Active Property Sales** → DCGIS `Parcels_public` + Nebraska DOR delinquency + Douglas County Register of Deeds LandmarkWeb (subscription)
- **City/County Notice of Bids** → Douglas County Purchasing Ionwave
- **Public Records / Fictitious Business Names / Court Records** → Nebraska SOS (reCAPTCHA), Nebraska courts (subscriber-only), various county sources

## Next Steps

1. Fix Render scraper execution (`greenlet_spawn` async/sync SQLAlchemy conflict).
2. Populate Render SQLite database with signals from live sources.
3. Complete Render cron job setup or run scrapers via admin endpoint.
4. Rotate exposed Apify and PermitStack tokens.
5. Add PyMuPDF / pdfplumber for Sarpy delinquency PDF parsing.
6. Implement Accela live-permit browser automation.
7. Detail-page automation for Douglas County bid awards.
8. Subscribe to Apify business-license actor or Parse.bot BBB API.
9. Create Stripe products/prices once signals are reliable.
