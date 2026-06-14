# GitHub Engagement Protocol

## Purpose
Automatically engage with developers discussing vendor outages, monitoring challenges, and SRE pain points on GitHub.

## Authentication
- **Account**: `darioandyoshi-tech` (already authenticated via `gh auth login`)
- **Token scopes**: `gist`, `read:org`, `repo`, `workflow`
- **Status**: ✅ Active

## Usage

### Comment on Existing Issue/Discussion
```bash
./scripts/github-engage.sh owner/repo 123 "Your helpful comment here..."
```

### Create New Issue (for announcements/discussions)
```bash
./scripts/github-engage.sh owner/repo --create "Title" "Body text..."
```

## Target Repos for PulseWatch

### High-Priority (Monitoring/Observability)
- `prometheus/prometheus`
- `grafana/grafana`
- `DataDog/dd-agent`
- `kubernetes/kubernetes`
- `helm/helm`
- `terraform-providers/terraform-provider-aws`

### Medium-Priority (DevOps/SRE Tools)
- `ansible/ansible`
- `puppetlabs/puppet`
- `chef/chef`
- `spinnaker/spinnaker`
- `argoproj/argo`

### Engagement Rules (Anti-Spammy)
1. **Only engage when**:
   - Someone is actively complaining about vendor outages
   - Someone asks "how do you monitor X?"
   - A discussion about status pages/monitoring tools is happening
   
2. **Tone**:
   - Helpful, not salesy
   - Share experience, don't pitch
   - Mention PulseWatch as one option among many

3. **Frequency**:
   - Max 3-5 engagements per day
   - No duplicate comments across repos
   - Always add value first

## Example Engagement

**Scenario**: Issue in `prometheus/prometheus` asking about monitoring third-party APIs.

**Comment**:
> "We had this same problem with Stripe/AWS/Slack outages catching us off guard. Status pages were always 15-20 min behind.
> 
> We started using PulseWatch for external vendor monitoring — it checks 1,500+ services every 60 seconds and usually catches issues before they hit Twitter. Not a replacement for Prometheus, but it fills the 'third-party blind spot' nicely.
> 
> Worth a look if you're tired of finding out from Slack."

---
*Created: 2026-06-08*
*Status: Ready for autonomous engagement*
