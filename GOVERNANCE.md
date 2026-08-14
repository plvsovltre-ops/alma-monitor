# ALMA governance

ALMA was initiated and originally designed by **Yernar Sailybayev in Almaty,
Kazakhstan**. Yernar Sailybayev is the founding maintainer and release owner of
the initial implementation. Contributors are credited separately.

## Decision model

Ordinary software changes use a pull request, automated tests, and maintainer
review. Changes affecting legal references, deterministic rule mappings,
competent-authority routes, request templates, public-interest statements, or
reviewed spatial coverage also require the controlled review described in
`docs/PUBLIC_RELEASE_GOVERNANCE.md`.

No contributor, model, automation, donor, or partner may:

- select an article from free text or model output;
- turn an unknown circumstance into an asserted fact;
- name a person as an offender or establish guilt;
- interpret a changed official source automatically;
- submit a citizen's request without a separate approved process and the
  user's confirmation;
- approve a legal review on behalf of another person.

## Public legal release

A public legal release needs three hash-bound records:

1. approval by Yernar Sailybayev as author and legal editor;
2. approval by a different, identified and qualified lawyer who declares no
   conflict of interest and consents to public attribution;
3. final activation by the release owner.

Any changed governed artifact invalidates the proposal hash and blocks the
public mode. A disagreement creates a new proposal; it is not overwritten.

The independent lawyer completes a protected Google Sheets review from an
account under the lawyer's control. The Sheet revision history, attestation,
source URL, and exported CSV SHA-256 are the primary approval evidence. A
GitHub account and GitHub PR approval are optional for the lawyer. They do not
replace the complete 32-object legal review.

## Geography

A new polygon GeoPackage with the already supported layer contract normally
requires no algorithm change. It still requires a new catalog entry, official
source and purpose metadata, routing decision, exact checksum, tests, and a new
review proposal. New geometry types, multiple relevant layers in one file,
distance tolerances, or a different schema require a code change and tests.

## Releases and attribution

Public releases are tagged, include a changelog and checksums, and preserve
`AUTHORS`, `NOTICE`, `CITATION.cff`, the applicable licenses, and this governance
file. Use of the code or content does not transfer the ALMA name and does not
imply endorsement by ALMA, a government, a donor, or a United Nations entity.

Material governance changes are discussed in a public issue or pull request.
Security and personal-data matters use the private route in `SECURITY.md`.
