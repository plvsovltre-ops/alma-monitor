# Release history

## 1.5.2

- Keeps verified field photographs in private Mergin Maps storage instead of
  duplicating them as email attachments.
- Adds `Date` and traceable `Message-ID` headers and fails closed on explicit
  SMTP recipient refusal.
- Records SMTP2GO acceptance as `mail_submitted` rather than claiming final
  mailbox delivery.

## 1.5.1

- Replaces the unstable whole-file runtime check for reviewed GeoPackages with
  a deterministic feature-content digest covering geometry and attributes.
- Accepts byte-level SQLite repackaging by Mergin Maps while continuing to
  block any reviewed feature-content change.

## 1.4.0-rc1 — Public Release Governance (unreleased)

- Adds a 32-object public legal review view covering 18 active legal cards, five
  deterministic policy mappings, four authority routes, and five request
  templates.
- Requires separate author/legal-editor and independent-lawyer approvals bound
  to exact SHA-256 hashes.
- Keeps public legal mode blocked by default and exposes it only through the
  explicit `ALMA_RELEASE_MODE=public_legal_release` setting after approval.
- Adds authorship, licensing, citation, governance, security, privacy,
  retention, and name-use documents for public review.

## 1.3.1

- Added deterministic correction notices for spatial, evidence, and input
  review states.

## 1.3.0

- Added the reviewed human volunteer response structure.

## 1.2.0

- Integrated the private controlled-pilot Legal Core and authority routing.

Earlier development history remains available in Git commits and merged pull
requests.
