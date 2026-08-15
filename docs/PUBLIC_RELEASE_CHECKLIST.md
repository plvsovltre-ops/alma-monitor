# Public release checklist

The release owner records every item in the release pull request.

- [x] `AUTHORS`, `NOTICE`, `CITATION.cff`, `LICENSE`, `LICENSE-CONTENT.md`,
  and `TRADEMARKS.md` are present, author-approved, and bound to exact SHA-256
  values in `authorship_licensing_approval.json`.
- [ ] `SECURITY.md`, `PRIVACY.md`, and `DATA_RETENTION.md` match the actual
  deployment; retention and deletion are enforced, not merely promised.
- [ ] The release contains no credentials, real observations, field photos,
  volunteer identities, or unpublished precise locations.
- [ ] All automated tests pass from a clean checkout.
- [ ] The 32-object author review is approved and bound to its CSV SHA-256.
- [ ] The 32-object independent-lawyer review is approved by a different
  privately identified qualified person, with no-conflict declaration and
  confidential-attestation consent.
- [ ] The independent review is attributable to the lawyer's Google account,
  includes the completed attestation, and is bound to the exact exported CSV
  and private-attestation SHA-256 values. The public repository contains no
  identifying lawyer data or restricted Sheet URL. A GitHub account is optional.
- [ ] The final public decision binds both review-record hashes.
- [ ] Every spatial layer has recorded provenance, version/date, permitted use,
  and an official source where one exists; a community-derived layer is not
  described as official.
- [ ] A synthetic end-to-end incident confirms GIS matching, deterministic
  legal selection, routing, email, private state, and registry output.
- [ ] Unmatched, malformed, and tampered inputs fail closed without a Gemini
  legal guess.
- [ ] The release has a semantic version, Git tag, changelog, immutable image
  digest, and SHA-256 checksum list.
- [ ] Public documentation makes no claim of government or United Nations
  endorsement.
- [ ] The production setting remains `controlled_pilot` until every preceding
  gate is complete.

An unchecked item blocks the public release. A waiver must be an explicit,
dated, public risk decision by the release owner; legal-review and personal-data
gates cannot be waived through this checklist.
