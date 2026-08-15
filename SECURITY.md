# Security policy

## Supported version

Security fixes are applied to the latest published release. Release candidates
and older versions may be changed or withdrawn without a compatibility promise.

## Private reporting

Do not place credentials, volunteer identities, precise unpublished locations,
field photographs, or exploitable details in a public issue. Report a suspected
vulnerability privately to `monitor@alma.eco` with:

- the affected version and component;
- a minimal reproduction that contains no real field data;
- the potential impact;
- a safe way to contact the reporter.

Do not access, alter, or download data that you are not authorised to use. The
maintainer will acknowledge a usable report and coordinate disclosure after the
risk has been contained.

## Operational boundary

Secrets belong in Google Secret Manager, field projects stay in Mergin Maps,
and the public repository contains neither real observations nor production
credentials. A suspected secret exposure requires rotation; deleting it from a
later commit is not sufficient.
