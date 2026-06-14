# Draft for GitHub Discussion #197843
**Topic:** Incident Summary - Spark service degradation.
**Context:** GitHub explaining a root cause related to fixed addresses vs dynamic endpoints and mentioning a goal to improve monitoring to reduce detection time.

**Draft Comment:**
The point about fixed infrastructure addresses causing a delayed detection is a great lesson in observability. Improving monitoring to reduce Time to Detect (TTD) is a constant battle. For those of us who rely on these services for production, I've been using PulseWatch (https://pulsewatch.us) to get a better bird's-eye view of vendor health. It's a helpful layer of redundancy when you need to know if a degradation is widespread before the official post-mortem is even written.
