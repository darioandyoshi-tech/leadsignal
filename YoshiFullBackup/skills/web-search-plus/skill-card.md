## Description: <br>
Unified multi-provider web search and URL extraction skill with intelligent auto-routing across Serper, Brave, Tavily, Querit, Linkup, Exa, Firecrawl, Perplexity, You.com, SearXNG, and SerpBase. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[robbyczgw-cla](https://clawhub.ai/user/robbyczgw-cla) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Developers and agent users use this skill to run web search and URL extraction across configured providers without manually choosing a provider for each query. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Search queries and extraction URLs may be sent to configured third-party providers through automatic routing. <br>
Mitigation: Use explicit provider selection for sensitive work, review configured providers before use, and avoid submitting internal or private URLs to extraction providers. <br>
Risk: Raw queries and results are cached locally by default. <br>
Mitigation: Disable caching with --no-cache for sensitive queries or clear the local cache regularly. <br>
Risk: Broad trigger phrases can activate the skill in more situations than expected. <br>
Mitigation: Review and narrow automatic activation triggers when using this skill in shared or sensitive agent workflows. <br>


## Reference(s): <br>
- [Web Search Plus on ClawHub](https://clawhub.ai/robbyczgw-cla/web-search-plus) <br>
- [SerpBase](https://serpbase.dev) <br>
- [Brave Search API](https://brave.com/search/api/) <br>
- [Tavily](https://tavily.com) <br>
- [Querit](https://querit.ai) <br>
- [SearXNG Installation](https://docs.searxng.org/admin/installation.html) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, shell commands, configuration, guidance] <br>
**Output Format:** [Markdown guidance with shell commands and text or JSON-like results from search and extraction scripts] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [Requires python3 and bash; uses one configured search provider key or SearXNG URL for search, and one supported extraction provider for URL extraction.] <br>

## Skill Version(s): <br>
3.1.0 (source: frontmatter, package.json, changelog released 2026-05-25, server evidence) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
