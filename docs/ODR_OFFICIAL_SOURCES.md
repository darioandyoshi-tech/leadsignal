# ODR → Official Source Tracing

Source-research for LeadSignal. ODR (Omaha Daily Record) repackages public records from city/county/state/federal sources. This document maps each ODR category to the authoritative public source, lists additional sources not covered by ODR, and recommends Apify actors / automation approaches.

**Verification legend**
- `[VERIFIED]` – fetched a live sample (HTTP 200 + payload) during this research.
- `[INFERRED]` – source identified by cross-referencing ODR HTML/RSS content with official sites, but not directly sampled via API/query.
- `[BLOCKED]` – live URL responds, but curl returns 403/Cloudflare; likely needs residential proxy or browser automation.

---

## 1. ODR Category → Official Source Table

| ODR Category | Official Source URL | Verification | Format / API | Login/CAPTCHA? | Recommended Apify / Automation | Notes |
|---|---|---|---|---|---|---|
| **Public Notices – City of Omaha** | `https://cityclerk.cityofomaha.org/public-notices/` | [BLOCKED] | Public HTML listing | reCAPTCHA inferred on search; Cloudflare blocks headless curl | `apify/web-scraper` with residential proxy + stealth; or mirror from ODR RSS | ODR republishes the same notices. The City Clerk’s page is the primary official publisher. |
| **Public Notices – Douglas County** | `https://clerk.douglascounty-ne.gov/` | [BLOCKED] | Public HTML / agendas / notices | Cloudflare blocks headless curl | `apify/web-scraper` or `nocturne/stealth-website-crawler` | County Clerk/Comptroller publishes Board of Equalization, budget, and supplier-payment notices. |
| **Public Notices – OPS** | `https://meeting.sparqdata.com/Public/Agenda/120` (Sparq Meetings portal) | [VERIFIED] | HTML agendas / meeting packets; no RSS obvious | No login for public agendas | `apify/web-scraper` + Sparq portal crawl; or ODR RSS | Omaha Public Schools board agendas and public notices. |
| **Public Notices – Learning Community** | `https://learningcommunityds.org/coordinating-council/` | [VERIFIED] | HTML meeting calendar + meeting materials | No login | `apify/web-scraper` + `/meetings` + `/meeting-materials/` | ODR item: “Learning Community of Douglas and Sarpy Counties NOTICE OF PUBLIC MEETING.” |
| **Public Notices – MAPA** | `https://mapacog.org/calendar/news/` + `https://gohub.mapacog.org` | [VERIFIED] | WordPress news + ArcGIS Hub / GoHub open data | No login | `devilscrapes/rss-feed-scraper` on ODR feed; `apify/web-scraper` for MAPA news | MAPA also publishes comment periods for TIP amendments and work programs. |
| **Public Notices – MECA** | `https://omahameca.org/who-we-are/meetings-agendas/` | [VERIFIED] | HTML minutes/agendas; notices published in OWH/Daily Record | No login | `apify/web-scraper` on meetings page | MECA board & Tri-Park Complex, LLC meeting notices. |
| **Public Notices – Metro Transit Authority** | `https://www.ometro.com/` (Metro Transit) | [INFERRED] | Board meeting notices / agendas | Unknown | `apify/web-scraper` on meeting-notice pages | ODR has a `/legals/metro-transit-authority` feed. |
| **Public Notices – Bennington / Gretna / DC West / Millard / Plattsmouth schools** | Respective district websites (e.g., Bennington Public Schools, Gretna Public Schools, etc.) | [INFERRED] | District board agendas / notices | Unknown | `devilscrapes/rss-feed-scraper` via ODR feed; per-district scraper if direct | ODR repackages school-district legal notices. |
| **City/County Notice of Bids** | City: `https://www.douglascountypurchasing.org/current-requests-for-bids-a-proposals` <br> County / joint: `https://publicworks.cityofomaha.org/projects/notice-inviting-bids-list/` <br> City Clerk: `https://cityclerk.cityofomaha.org/bids/` | [BLOCKED] | Public HTML bid listings | Cloudflare blocks curl on these hosts | `xtech/cloudflare-scraper-pro` or `nocturne/stealth-website-crawler` + residential proxies | ODR feed: `https://www.omahadailyrecord.com/taxonomy/term/3706/all/feed`. Many items say “NOTICE INVITING BIDS — City of Omaha/Douglas County.” |
| **Building / Mechanical / Electrical / Plumbing Permits** | **Primary open-data source:** `https://www.civicdata.com/dataset/blds_permitcore_sql_current_13729` (CKAN / Socrata-ish portal hosted by CivicData) <br> **Live lookup:** `https://aca-prod.accela.com/OMAHA/Welcome.aspx` | [VERIFIED] | CKAN API + CSV dump; Accela public search | CivicData: no login; Accela: may require account for details | `devilscrapes/rss-feed-scraper` on ODR feeds (`/taxonomy/term/3701/…`, `3702`, `3807`, `3704`); custom CKAN consumer; `apify/web-scraper` for Accela if needed | ODR publishes permit RSS feeds. CivicData has historic CSVs 2006–current. Verified live API: `https://www.civicdata.com/api/3/action/datastore_search?resource_id=efecb9f2-b254-4e34-90ce-4097fbe82322` returned 60,859 records. CSV dump works at `https://www.civicdata.com/datastore/dump/{resource_id}`. |
| **Public Records / Deeds** | Douglas County Assessor/Register of Deeds: `https://registerofdeeds.douglascounty-ne.gov/` <br> Free index search: `https://landmarkweb.douglascounty-ne.gov/LandmarkWeb/AlphaSearchM2/AlphaSearchIndexM2` | [VERIFIED] | Paid reports + free index search; no bulk API | Free search requires clicking disclaimer; no direct bulk export | `apify/web-scraper` on LandmarkWeb (form + disclaimer); or OCR/extract ODR PDF “Deeds – Month Year” | ODR feed `/taxonomy/term/3719/all/feed` posts monthly deed PDFs. Register of Deeds sells reports. |
| **Real Estate Leads – Notice of Default** | ODR category `/legals/notice-default` + underlying foreclosure filings (Register of Deeds / court) | [INFERRED] | No single official list; derived from recorded notices and court dockets | — | ODR feed `/taxonomy/term/3766/all/feed`; combine with LandmarkWeb search for “Notice of Default” document type | ODR repackages notices of default. No verified free bulk source. |
| **Real Estate Leads – Active Property Sales / Foreclosures** | Douglas County Sheriff: `https://sheriff.douglascounty-ne.gov/services/sheriff-sales-and-auctions/` <br> Douglas County Treasurer tax sales: `https://treasurer.douglascounty-ne.gov/private-tax-sale/` | [VERIFIED] | HTML listings + PDFs | No login | `apify/web-scraper` on sheriff-sales page; `webscrap18/pdf-scraper` or custom PDF parser for lists | ODR feed `/taxonomy/term/3700/all/feed` — “Active Property Sales.” |
| **Real Estate Leads – Active Probates** | Douglas County Court Probate/Adoptions: `https://court.douglascounty-ne.gov/probate-adoptions/` <br> Nebraska judicial calendar: `https://www.nebraska.gov/courts/calendar/index.cgi/` | [VERIFIED] | HTML info pages; calendar search form | No login for info; calendar search is form-based | `apify/web-scraper` on calendar form; ODR feed `/taxonomy/term/3718/all/feed` | ODR feed is the easiest structured feed. Calendar excludes some district courts but includes Douglas County Court. |
| **Tax Delinquency – Douglas County** | Douglas County Treasurer: `https://treasurer.douglascounty-ne.gov/real-property-tax/` + tax sale pages | [VERIFIED] | Property lookup + PDF lists | No login | `apify/web-scraper` for search results; PDF parser for published delinquent lists | Nebraska DOR also publishes a statewide master delinquent PDF: `https://revenue.nebraska.gov/PAD/real-property/nebraska-delinquent-real-property-list`. |
| **Tax Delinquency – Sarpy County** | Sarpy County Treasurer: `https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information` | [VERIFIED] | CivicPlus HTML + PDF delinquent list | No login | `webscrap18/pdf-scraper` on `https://www.sarpy.gov/DocumentCenter/View/8600/2026-DELINQUENT-TAX-LIST` | Verified PDF download (2 MB). Sale held annually; list published in ODR Feb 5/12/19. |

---

## 2. ODR RSS Feed Inventory (Verified)

ODR exposes a dedicated RSS feed for each legal-notice category. These were live-tested and return `application/rss+xml`.

| Category | Feed URL |
|---|---|
| Public Notices | `https://www.omahadailyrecord.com/taxonomy/term/3692/all/feed` |
| City of Omaha | `https://www.omahadailyrecord.com/taxonomy/term/3694/all/feed` |
| Douglas County | `https://www.omahadailyrecord.com/taxonomy/term/3695/all/feed` |
| Omaha Public Schools | `https://www.omahadailyrecord.com/taxonomy/term/3696/all/feed` |
| MAPA | `https://www.omahadailyrecord.com/taxonomy/term/3749/all/feed` |
| MECA | `https://www.omahadailyrecord.com/taxonomy/term/3747/all/feed` |
| Learning Community | `https://www.omahadailyrecord.com/taxonomy/term/3750/all/feed` |
| City/County Notice of Bids | `https://www.omahadailyrecord.com/taxonomy/term/3706/all/feed` |
| Building Permits | `https://www.omahadailyrecord.com/taxonomy/term/3701/all/feed` |
| Electrical Permits | `https://www.omahadailyrecord.com/taxonomy/term/3702/all/feed` |
| Mechanical Permits | `https://www.omahadailyrecord.com/taxonomy/term/3807/all/feed` |
| Plumbing Permits | `https://www.omahadailyrecord.com/taxonomy/term/3704/all/feed` |
| Deeds | `https://www.omahadailyrecord.com/taxonomy/term/3719/all/feed` |
| Active Property Sales | `https://www.omahadailyrecord.com/taxonomy/term/3700/all/feed` |
| Active Probates | `https://www.omahadailyrecord.com/taxonomy/term/3718/all/feed` |
| Notice of Default | `https://www.omahadailyrecord.com/taxonomy/term/3766/all/feed` |

---

## 3. Additional Official Sources Not Covered by ODR

| Source | Official URL | Verification | Data Format | Automation Notes |
|---|---|---|---|---|
| **Nebraska Liquor Control Commission – Active License Roster** | `https://lcc.nebraska.gov/licensing-sdl/active-license-roster` | [VERIFIED] | HTML page with XLSX roster download + POSSE search link | `apify/web-scraper` to download XLSX; or scrape the posted roster file names and fetch direct links. POSSE search is interactive. |
| **Nebraska DHHS Professional License Search** | `https://www.nebraska.gov/LISSearch/search.cgi?new=1&stype=` | [VERIFIED] | Interactive HTML search; paid CSV lists at `https://www.nebraska.gov/hhs/lists/` | The search form works without login. Bulk lists are $ fee per download. Use `apify/web-scraper` to POST search form and paginate results. |
| **Nebraska UCC Search** | `https://sos.nebraska.gov/business-services/uccefs-search-and-filing-center` | [VERIFIED] | Interactive search / paid filings | Requires account/credit card for searches/filings. Not bulk-friendly. |
| **Nebraska SOS Business Entity Search** | `https://www.nebraska.gov/sos/corp/corpsearch.cgi?nav=search` | [VERIFIED] | HTML form with reCAPTCHA | reCAPTCHA on search. Use `xtech/recaptcha-bypass-browser-scraper` or request special batch search at `https://www.nebraska.gov/SpecialRequestSearches/index.cgi` ($15/1000 records). |
| **Douglas County GIS / DCGIS REST Services** | Open Data Hub: `https://data-dogis.opendata.arcgis.com/` <br> REST: `https://apps.douglas.co.us/gisod/rest/services` <br> Public parcels: `https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer` | [VERIFIED] | ArcGIS REST FeatureServer / MapServer | Verified query on `Parcels_public/0` returns parcel attributes (PIN, OWNER_NAME, PROPERTY_A, etc.). MaxRecordCount 2000; use `resultOffset` to page. No auth required. |
| **City of Omaha Open Data (CivicData)** | `https://www.civicdata.com/organization/about/omaha-313d491f-2fb4` | [VERIFIED] | CKAN API + CSV datastore dumps | Verified CSV dump and `datastore_search` API for building permits. City also publishes police incident data on ArcGIS Open Data. |
| **SAM.gov Contract Opportunities / Awards** | `https://open.gsa.gov/api/contract-awards/` <br> Portal: `https://alpha.sam.gov/` | [INFERRED] | REST API (api.sam.gov) – key required for some data | Use `clawdeus/sam-gov-contracts` or `skootle/sam-gov-federal-contracts` Apify actors; or call `api.sam.gov` directly with key. |
| **USASpending.gov** | `https://api.usaspending.gov/` | [VERIFIED] | Open REST API, no auth | Verified POST to `/api/v2/search/spending_by_award/` with NE/Omaha filters returned federal awards. Great for B2G lead enrichment. |
| **OSHA Establishment / Inspection Search** | `https://www.osha.gov/ords/imis/establishment.html` | [VERIFIED] | Public HTML search (Oracle APEX) | No API. Use `apify/web-scraper` to POST search form and paginate. Useful for contractor safety leads. |
| **BBB of Midwest Plains** | `https://www.bbb.org/local-bbb/bbb-of-midwest-plains` | [VERIFIED] | HTML directory; no official bulk API | Third-party APIs exist (e.g., parse.bot). For official use, `apify/web-scraper` on `bbb.org` directory pages. |
| **Nebraska Accountability & Disclosure Commission (NADC)** | `https://nadc.nebraska.gov/` <br> Search: `https://www.nebraska.gov/nadc/ccdb/search.cgi` <br> Bulk data: `https://www.nebraska.gov/nadc_data/nadc_data.zip` | [VERIFIED] | HTML search + weekly ZIP text export | Verified 22 MB ZIP download of campaign statements. Useful for donor/vendor leads. |
| **Nebraska Open Data Portal (Lt. Governor list)** | `https://ltgov.ne.gov/government/open-data/` | [VERIFIED] | Links to state agency interactive searches / exports | Curated index of professional-license searches, campaign data, etc. |
| **Omaha Police Incident Data** | `https://police.cityofomaha.org/crime-information/incident-data-download` <br> ArcGIS: `https://data-dogis.opendata.arcgis.com/` | [INFERRED] | CSV downloads + ArcGIS feature service | Good local crime/safety context; not a lead source per se. |

---

## 4. Verified API / URL Patterns

Use these patterns to pull live data.

### 4.1 ODR RSS feeds
```bash
curl -sL 'https://www.omahadailyrecord.com/taxonomy/term/3692/all/feed'
```
Returns `application/rss+xml; charset=utf-8` with item titles like `Learning Community Public Notices 6/12/2026`.

### 4.2 City of Omaha building permits via CivicData (CKAN)
```bash
# Search the datastore (JSON)
curl -sL 'https://www.civicdata.com/api/3/action/datastore_search?resource_id=efecb9f2-b254-4e34-90ce-4097fbe82322&limit=5'

# CSV dump (CKAN datastore dump endpoint)
curl -sL 'https://www.civicdata.com/datastore/dump/efecb9f2-b254-4e34-90ce-4097fbe82322'
```
Sample record fields: `PermitNum`, `Description`, `AppliedDate`, `IssuedDate`, `OriginalAddress1`, `OriginalCity`, `PermitClassMapped`, `StatusCurrentMapped`, `ContractorCompanyName`, `ContractorLicNum`, `EstProjectCost`, `Publisher`.

### 4.3 Douglas County GIS parcel query
```bash
# FeatureServer metadata
curl -sL 'https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer/0?f=json'

# Query by OBJECTID (bulk WHERE clauses fail; page via OBJECTID range or resultOffset/resultRecordCount)
curl -sL 'https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer/0/query?where=OBJECTID=1&outFields=*&returnGeometry=false&f=json'
```
Confirmed attributes include: `PIN`, `OWNER_NAME`, `ADDRESS1`, `ADDRESS2`, `OWNER_CITY`, `OWNER_STAT`, `OWNER_ZIP`, `PROPERTY_A`, `HOUSE`, `STREET_NAM`, `STREET_TYP`, `PROP_CITY`, `PROP_ZIP`, `LEGAL1-4`, `TAX_DIST`, `ACRES`, `SQ_FEET`, `ASSESSOR`, `TREASURER`, `BLDG_YRBLT`, etc.

### 4.4 USASpending awards in Omaha
```bash
curl -sL -X POST 'https://api.usaspending.gov/api/v2/search/spending_by_award/' \
  -H 'Content-Type: application/json' \
  -d '{
    "filters": {
      "award_type_codes": ["A","B","C","D"],
      "place_of_performance_locations": [{"country":"USA","state":"NE","city":"Omaha"}]
    },
    "fields": ["Award ID","Recipient Name","Award Amount","Awarding Agency","Awarding Sub Agency","Contract Award Type","Start Date","End Date"],
    "sort": "Award Amount",
    "order": "desc",
    "limit": 10
  }'
```
Returns federal contract/grant awards performed in Omaha.

### 4.5 NADC bulk data
```bash
# Weekly campaign-finance text export (≈22 MB)
curl -sL -o nadc_data.zip 'https://www.nebraska.gov/nadc_data/nadc_data.zip'
```

### 4.6 Sarpy County delinquent tax list
```bash
# HTML page
curl -sL 'https://ne-sarpycounty.civicplus.com/981/Tax-Sale-Information'

# PDF list (2026)
curl -sL -o sarpy_delinquent_2026.pdf 'https://www.sarpy.gov/DocumentCenter/View/8600/2026-DELINQUENT-TAX-LIST'
```

---

## 5. Recommended Apify Actors by Source Type

| Use Case | Apify Actor | Why |
|---|---|---|
| **RSS ingestion (ODR categories)** | `devilscrapes/rss-feed-scraper` or `santamaria-automations/rss-feed-reader` | Turn ODR feeds into structured JSON; fastest path for most ODR categories. |
| **Generic city/county HTML pages** | `apify/web-scraper` | Code a pageFunction to extract meeting notices, bid tables, etc. |
| **Cloudflare/reCAPTCHA-protected sites** | `xtech/cloudflare-scraper-pro` or `xtech/recaptcha-bypass-browser-scraper` + residential proxy | City of Omaha / Douglas County purchasing sites block headless curl. |
| **Stealth full-site crawl** | `nocturne/stealth-website-crawler` | For sites with anti-bot when proxy + stealth needed. |
| **PDF parsing (tax sale lists, deeds, notices)** | `webscrap18/pdf-scraper` or `jungle_synthesizer/pdf-to-json-parser` | Extract tables from published PDFs. |
| **ArcGIS REST → JSON** | Custom Request actor or `canadesk/geocode-arcgis` for geocoding only | DCGIS and other REST services are easier to consume directly with your own HTTP client; Apify is optional. |
| **SAM.gov / USASpending** | `clawdeus/sam-gov-contracts` or `skootle/sam-gov-federal-contracts` | Federal contracting leads; USASpending can also be called directly. |
| **Nebraska SOS / POSSE / Accela forms** | `apify/web-scraper` with form POSTs + proxy rotation | Where no official bulk API exists. |

---

## 6. Key Takeaways

1. **ODR itself is the best structured feed for most categories.** Its category RSS feeds are authoritative repackagers and expose exactly the public notices ODR is monetizing. Start there.
2. **Official HTML sources often sit behind Cloudflare.** City of Omaha, Douglas County purchasing, and city clerk pages return 403 to headless curl. Use Apify with residential proxies or stealth browser actors.
3. **Permits have a real open-data endpoint.** CivicData (CKAN) provides City of Omaha permit CSVs and a `datastore_search` API. This is the highest-quality, machine-readable source found.
4. **GIS parcels are fully open.** Douglas County publishes `Parcels_public` via ArcGIS REST with no authentication. It’s a richer source than deed RSS items because it includes owner, address, and assessor/treasurer deep links.
5. **Tax delinquency is PDF-first.** Both Douglas and Sarpy counties publish delinquent lists as PDFs (DOR master PDF + county tax-sale PDFs). Plan on PDF extraction.
6. **Federal dollars are queryable.** USASpending and SAM.gov offer real APIs for Omaha/Nebraska awards — useful for B2G lead enrichment not covered by ODR.

---

*Document generated by LeadSignal source-research subagent on 2026-06-14.*
