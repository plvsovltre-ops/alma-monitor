# Citizen science release readiness

This note supports an open release of ALMA Monitor as a reusable citizen science
reference implementation. It does not claim United Nations endorsement.

## Public release boundary

Publish code, deployment instructions, a synthetic GIS project, and a synthetic
incident dataset. Keep the production Mergin Maps project private.

Do not publish volunteer email addresses, phone numbers, exact locations of
vulnerable sites, original photo EXIF data, access credentials, or raw complaint
texts that can identify a person.

## Minimum data protocol

For each published observation, record:

1. A stable observation ID.
2. Observation date and collection method.
3. Generalised location and coordinate reference system.
4. Incident category and controlled vocabulary.
5. Evidence type and consent status.
6. Validation status, validator role, and validation date.
7. Dataset version, licence, and data quality limitations.

Keep the unmodified source record, the validation record, and the published
record as separate data products. This makes the publication traceable.

## AI safeguards

- The AI response is a draft, not a legal decision.
- The output must cite the supplied legal source title and section when possible.
- A trained reviewer must approve a complaint before official submission.
- Store the model name, prompt version, source set version, and processing time.
- Test Russian and Kazakh output with native-language reviewers.

## Open package

Before publication, add:

- a reviewed open-source licence;
- a `CITATION.cff` file;
- `SECURITY.md` and a responsible disclosure contact;
- a privacy notice and data retention schedule;
- an English installation guide and field collection guide;
- a reproducible demonstration with synthetic data;
- automated tests for schema validation and duplicate delivery protection.

## Alignment evidence

Document data quality, provenance, inclusion, privacy protection, and the limits
of citizen-generated observations. These items support use with the United
Nations guidance for citizen data and the Copenhagen Framework on Citizen Data.
