# Email delivery

ALMA Monitor uses `monitor@alma.eco` as the visible `From` and `Reply-To`
address. The production transport is SMTP2GO over authenticated STARTTLS.

## Delivery boundary

SMTP acceptance means that SMTP2GO accepted responsibility for the message. It
does not prove that the destination mailbox displayed it. ALMA therefore stores
new messages as `mail_submitted`, together with the provider name, UTC time,
`Message-ID`, and accepted-recipient count. It does not label provider
acceptance as final delivery.

The result email contains the bilingual dossier only. Field photographs stay
in the private Mergin Maps project. This reduces unnecessary copies of evidence,
message size, forwarding failures, and exposure of location metadata.

## Domain authentication

The operator must add `alma.eco` under **Sending → Verified Senders → Sender
domains** in SMTP2GO and publish the exact three CNAME records supplied for that
account. The domain must show as verified before public field use. SMTP2GO uses
those account-specific records for aligned return-path and DKIM authentication;
do not invent selector names or add a second SPF TXT record.

Inbound forwarding for `monitor@alma.eco` is currently handled separately. A
domain may have only one SPF policy, so any provider-required SPF mechanisms
must be combined into one TXT record. DNS and provider activity must be checked
after changes propagate.

Start DMARC in monitoring mode only after SMTP2GO sender-domain verification is
green. Move to enforcement only after reviewing reports and confirming that all
legitimate ALMA senders align.

## Operational check

For each release, send a synthetic text-only observation to a controlled test
address. Confirm all four stages:

1. Cloud Run records `Email accepted by SMTP2GO` and a `Message-ID`.
2. SMTP2GO Activity reports the same message as delivered or gives a specific
   bounce reason.
3. The destination mailbox receives the message.
4. Cloud Storage records `mail_submitted` and Google Sheets contains one row.

If stage 1 succeeds but stage 2 or 3 fails, do not automatically resend. Inspect
SMTP2GO Activity and domain authentication first; otherwise a delayed original
can create duplicate volunteer messages.
