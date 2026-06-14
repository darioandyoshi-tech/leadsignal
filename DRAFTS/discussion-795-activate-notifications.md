Thanks for asking this - getting notifications set up can definitely be tricky the first time! The GitHub Secrets approach is correct, but I've seen a few common tripping points:

1. Make sure the secret name matches exactly what Upptime expects (NOTIFICATION_EMAIL is correct)
2. Verify your email provider allows SMTP/relay from GitHub Actions IPs
3. Check that your email content isn't being flagged as spam (monitor links can sometimes trigger filters)
4. Ensure the workflow actually has permission to read secrets (sometimes permissions need explicit granting)

At PulseWatch (https://pulsewatch.us), we simplified this by providing guided setup wizards and pre-built integrations for popular services like SendGrid, Mailgun, SES, etc., plus we handle the deliverability aspects so you don't have to worry about IP reputations or spam filtering.

That said, if you're committed to the self-hosted/GitHub approach, the community here is incredibly helpful! Once you get those secrets configured correctly and give it a test run (try manually triggering a down event), you should start seeing those emails come through.

Pro tip: Add a personal email address first for testing before adding team distribution lists - makes troubleshooting much easier when you're getting started!