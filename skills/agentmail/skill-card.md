## Description: <br>
AgentMail helps agents create and manage dedicated email inboxes, send and receive email programmatically, and handle email workflows with webhooks and real-time events. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[adboio](https://clawhub.ai/user/adboio) <br>

### License/Terms of Use: <br>


## Use Case: <br>
Developers and agent builders use this skill to give agents an email identity, send rich email with attachments, poll inboxes, and connect incoming email to webhook-driven workflows. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Email contents, attachments, webhook payloads, and API keys may contain sensitive information. <br>
Mitigation: Keep AGENTMAIL_API_KEY secure, avoid logging full payloads in shared environments, and redact or summarize email content before forwarding it to other systems. <br>
Risk: Incoming email webhooks can carry untrusted instructions or prompt-injection content. <br>
Mitigation: Restrict webhook endpoints, allowlist trusted senders where practical, and treat email bodies as untrusted input that requires review before agent action. <br>
Risk: Outbound email or attachments may be sent to unintended recipients if agent output is not reviewed. <br>
Mitigation: Verify recipients, subjects, message bodies, and attachments before sending email through the skill. <br>


## Reference(s): <br>
- [AgentMail ClawHub release](https://clawhub.ai/adboio/agentmail) <br>
- [AgentMail API Reference](references/API.md) <br>
- [AgentMail Webhooks Guide](references/WEBHOOKS.md) <br>
- [AgentMail Usage Examples](references/EXAMPLES.md) <br>
- [AgentMail Console](https://console.agentmail.to) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, code, shell commands, configuration, guidance] <br>
**Output Format:** [Markdown guidance with Python, HTTP, shell, and JSON examples] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [May include API calls and local script usage that require AGENTMAIL_API_KEY.] <br>

## Skill Version(s): <br>
1.1.1 (source: server release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
