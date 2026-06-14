# LeadSignal Source Status — June 14, 2026

## Verified Live Sources (ready to wire)

| Signal | Source | Status | Automation |
|--------|--------|--------|------------|
| Hiring spikes | Apify `borderline/indeed-scraper` | ✅ Returns real Omaha jobs | `scraper/sources/apify_jobs_reviews.py` |
| Negative review clusters | Apify `compass/Google-Maps-Reviews-Scraper` + Google Places API | ✅ Verified input schema / direct API works | `scraper/sources/apify_jobs_reviews.py`, `scraper/sources/google_reviews.py` |
| Permits (historical) | CivicData CKAN `blds_permitcore_historical_aa_14757` | ✅ ~60,859 rows live | `scraper/sources/civicdata_permits.py` |
| Permits (live current) | City of Omaha Accela portal | ⚠️ JS-heavy, needs browser automation | `scraper/sources/accela_omaha.py` (stub with seed fallback) |
| Parcel/property changes | DCGIS `Parcels_public` FeatureServer | ✅ Live, real records | `scraper/sources/dcgis_parcels.py` |
| Tax-delinquent property | Nebraska DOR county Excel | ✅ Douglas 2026 Excel parses | `scraper/sources/ne_dor_delinquency.py` |
| Tax-delinquent property (Sarpy) | Sarpy County tax-sale PDF | ✅ PDF downloads + parses | New module needed |
| Gov bid awards | Douglas County Purchasing Ionwave | ✅ List page parseable; detail page needs automation | `scraper/sources/douglas_bids.py` |
| Federal awards in Omaha | USASpending.gov API | ✅ Real awards returned (Raytheon $197M, Metgreen $116M, etc.) | New module needed |
| Nebraska liquor licenses | NLCC active roster Excel | ✅ 956K Excel with licensee, trade name, address, city, county | New module needed |
| Nebraska campaign finance / vendor leads | NADC bulk ZIP | ✅ 22.5 MB weekly ZIP with committees, expenditures, contributions | New module needed |
| Nebraska professional licenses | DHHS license search | ✅ Form-based search live; paid bulk lists also available | New module needed |
| Sarpy County tax sale information | CivicPlus page | ✅ Live; delinquent PDF follows redirects | New module needed |

## Rejected / Blocked Sources

| Source | Reason |
|--------|--------|
| Indeed public HTML | 403 blocked |
| ZipRecruiter public HTML | 403 blocked |
| CivicData current permit datastores (2016–present, 2018–current) | Empty (0 rows) |
| Nebraska SOS entity search | reCAPTCHA-gated |
| Nebraska Work Search (neworks.nebraska.gov) | Incapsula block |
| Douglas County Assessor | 403 |
| Nebraska court records JUSTICE portal | Unreachable |
| Omaha crime open data portal | Unreachable |
| Restaurant/food inspections (DCHD) | Only static PDF + interactive map; no structured live feed |
| ArcGIS `FoodServiceData` | Louisville, KY — not Omaha |
| Omaha Public Works bids page | Initial HTML contains no bid list; likely loaded dynamically via JS — needs browser automation |

## Apify Actor Candidates

| Use case | Actor | Notes |
|----------|-------|-------|
| US building permits (multi-city) | `jungle_synthesizer/building-permits-national-aggregator` | 30+ metros; may include Omaha |
| US building permits | `lentic_clockss/us-building-permits-scraper` | 8 cities + NJ |
| Realtor.com property data | `scrapemind/realtor-com-scraper` | For active listings/foreclosures |
| Court records | `martc03/court-records-mcp`, `parseforge/harris-county-court-records-scraper` | Mostly TX/other counties |
| Foreclosures/distressed property | `dominvo/distressed-property-ai-scraper`, `crawlerbros/zillow-foreclosure-scraper` | Real-estate signals |
| Government contracts | Need to search Apify Store for `sam.gov`, `usaspending`, or Ionwave-specific actors |
| LinkedIn company growth | `harvestapi/linkedin-company` | Hiring/growth signals |
| OSHA inspections | `fortuitous_pirate/osha-inspection-scraper` | Safety/compliance signals |
| Public tenders | `lofomachines/public-tenders-scraper` | Gov bid expansion |
| Website change monitor | `ryanclinton/website-change-monitor` | Monitor ODR / source pages for changes |

## ODR Source Mapping

Omaha Daily Record repackages the following official sources:

- **Building / Electrical / Plumbing / Mechanical Permits** → City of Omaha Accela Citizen Access (`aca-prod.accela.com/OMAHA`)
- **Real Estate Leads / Active Property Sales** → DCGIS `Parcels_public` + Nebraska DOR delinquency + Douglas County Register of Deeds LandmarkWeb (subscription)
- **City/County Notice of Bids** → Douglas County Purchasing Ionwave
- **Public Records / Fictitious Business Names / Court Records** → Nebraska SOS (reCAPTCHA), Nebraska courts (unreachable), various county sources

## Next Steps

1. Fix imports in `dcgis_parcels.py` and `ne_dor_delinquency.py` (currently using fragile inline `__import__`).
2. Test the three new scraper modules end-to-end locally or on Render.
3. Add new scraper modules for Sarpy delinquency, NLCC licenses, NADC campaign finance, USASpending awards.
4. Add a scheduled job (cron) to run `scraper/run_all.py` daily/hourly.
5. Implement Accela live-permit browser automation (Playwright/Apify).
6. Detail-page automation for Douglas County bid awards to capture vendor + amount.
7. Disable Vercel deployment protection.
8. Verify Render backend deployment.
9. Rotate exposed Apify token.
10. Create Stripe products/prices once signals are flowing reliably.
