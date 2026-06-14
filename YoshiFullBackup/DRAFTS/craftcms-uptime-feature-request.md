# Craft CMS Cloud Discussion #57 - Uptime Monitoring Feature Request

**URL:** https://github.com/craftcms/cloud/discussions/57  
**Topic:** Request for built-in uptime monitoring in Craft CMS Cloud  
**Activity:** Single comment (feature request), no responses yet  
**Why relevant:** Customer asking for monitoring — could use existing solution while waiting for native feature

---

## Draft Comment

```
+1 on this! Uptime monitoring should be table stakes for hosting platforms.

While you're building this out, one option that might help in the meantime:

We built **PulseWatch** (https://pulsewatch.us) specifically for monitoring external dependencies and customer-facing URLs. A few things that might be useful for Craft CMS Cloud customers:

**Quick setup:**
- Add your site URL, get alerts in <2 minutes
- No agents to install — just HTTP checks from multiple regions
- Free tier covers most small-to-medium sites

**What's helpful for hosting:**
- Catch outages before customers report them
- Multi-region checks distinguish "site down" from "regional network issue"
- Public status pages you can share with clients

**Integration ideas:**
- Webhook notifications into your existing alerting
- Custom headers for authenticated endpoints
- Certificate expiry monitoring (TLS is a common failure point)

We'd be happy to offer Craft CMS Cloud customers a discount if you want to bundle this while native monitoring is in development. Sometimes the fastest path to happy customers is integrating existing tools rather than building from scratch.

Either way, hope to see this feature land soon. Monitoring gaps are how small incidents become big ones. 🫡
```

---

## Notes

- Supportive of the feature request
- Position as interim solution, not replacement
- Offer partnership angle (discount for their customers)
- Specific, actionable suggestions (webhooks, cert monitoring)
- Respectful of their roadmap while offering immediate value
