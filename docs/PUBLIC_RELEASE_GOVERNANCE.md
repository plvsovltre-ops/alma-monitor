# ALMA public release: controlled approval

English | [Русский](PUBLIC_RELEASE_GOVERNANCE.ru.md)

The public Legal Core mode cannot be enabled with one setting. It applies only
to an exact set of files and only after two separate legal decisions.

## Authorship and licensing

On 14 August 2026, Yernar Sailybayev approved the exact `AUTHORS`, `NOTICE`,
`CITATION.cff`, `LICENSE`, `LICENSE-CONTENT.md`, and `TRADEMARKS.md` files for
this proposal. The decision and the SHA-256 of each document are recorded in
`governance/public/kz/0.1.0-rc1/authorship_licensing_approval.json`.

The decision approves Apache-2.0 for software and CC BY 4.0 for original prose,
diagrams, and educational materials. It does not relicense legislation or
government data. It does not transfer exclusive rights or transfer the project
to an organisation. A change to any of the six documents breaks the automated
integrity check and requires a new author decision.

This authorship and licensing decision does not replace the separate review of
the 32 legal objects by the author and an independent lawyer.

## Review scope

The first proposal, `kz-alma-public-0.1.0-rc1`, contains 32 compact objects:

| Object type | Count | What the lawyer reviews |
| --- | ---: | --- |
| Legal card | 18 | official source, provision, and cautious summary |
| Signal mapping | 5 | which approved cards apply to each field signal |
| Authority route | 4 | authority name, competence source, forwarding rule, and all GIS territories that use the route |
| Request template | 5 | short request text for each signal type |

The model does not select articles. Free text, a photograph, and coordinates
cannot add a legal provision. An unknown circumstance remains unknown.

## Google Sheets review

1. The release owner creates the review CSV:

   ```sh
   python scripts/prepare_public_review.py public-review.csv
   ```

2. The owner imports the CSV into Google Sheets. The order of the first fields
   must not change: `Тип объекта`, `ID`, `Официальный источник`, `Норма или
   решение`, `Текст проверки`, and `SHA-256 объекта`.
3. Each lawyer receives a separate protected tab or a separate copy. The
   governed fields and SHA-256 values are protected from editing.
4. The lawyer signs in with a Google account under the lawyer's control. The
   lawyer edits only `Согласен`, `Не согласен`, `Комментарий`, and the
   `Подтверждение` tab.
5. On `Подтверждение`, the lawyer records the full name, qualification,
   jurisdiction, and review date in the restricted Sheet. The lawyer declares
   no conflict of interest and records the publication preference. This initial
   governance version always keeps the identity confidential; an old or general
   attribution checkbox cannot override a later specific refusal. A work email
   and the full identity record are used only for confidential verification.
6. All 32 rows must contain `Согласен = TRUE` and `Не согласен = FALSE`. A
   disagreement starts a new revision cycle. An approved row must not be
   silently changed.
7. The final tab is exported as CSV. The public review record stores the CSV
   SHA-256, a non-identifying reviewer reference, and the hash of the private
   attestation. It must not store the lawyer's name, email, qualification text,
   Sheet URL, or identifying revision metadata. The release owner retains that
   evidence outside the public repository with restricted access.

This is a controlled electronic attestation for ALMA release governance. It is
not described as a qualified electronic signature.

If the lawyer refuses publication of their name, the restricted
`Подтверждение` tab records this statement:

> I personally reviewed all 32 objects in proposal
> `kz-alma-public-0.1.0-rc1`. I do not consent to publication of my name,
> email, qualification text, restricted Sheet URL, or other identifying data.
> I consent to confidential verification and retention by the release owner
> outside the public repository solely for release-integrity verification and
> dispute resolution. My approval does not establish facts, final legal
> qualification, or guilt in any individual observation.

The public record contains only the `32/32` result, date, jurisdiction,
non-identifying role, and hashes.

## Two legal decisions

Yernar Sailybayev makes the first decision as author and legal editor:

```sh
python scripts/record_public_review.py author-review.csv \
  governance/public/kz/0.1.0-rc1/author_review.json \
  --role author \
  --reviewer-name "Yernar Sailybayev" \
  --reviewed-on YYYY-MM-DD \
  --review-source-type ALMA_PROJECT_CONVERSATION
```

A different lawyer personally makes the second decision:

```sh
python scripts/record_public_review.py independent-review.csv \
  governance/public/kz/0.1.0-rc1/independent_review.json \
  --role independent \
  --reviewer-reference independent-legal-reviewer-kz-001 \
  --reviewed-on YYYY-MM-DD \
  --review-source-type RESTRICTED_GOOGLE_SHEET \
  --jurisdiction KZ \
  --identity-verified \
  --independence-verified \
  --qualification-verified \
  --declare-no-conflict \
  --consent-confidential-attestation \
  --confidential-attestation-sha256 SHA256
```

The no-conflict flag means that the lawyer declares no conflict. The public
record shows only a non-identifying role, jurisdiction, verification flags,
object count, and hashes. The lawyer's identity, email, qualification text,
restricted Sheet URL, and identifying revision metadata remain confidential.
Yernar Sailybayev, a developer, or a model must not enter the lawyer's legal
decision on the lawyer's behalf.

The lawyer does not need a GitHub account. If the lawyer has one, the lawyer may
also approve the pull request. That optional GitHub review does not replace the
32-row legal review and is not a legal-release gate. The required private
evidence is the lawyer's personal work in Google Sheets, the completed
attestation, the revision history, the Sheet URL, identity and qualification
verification, and the final CSV SHA-256. Only non-identifying hashes and
results enter the public repository.

The `main` branch still requires a pull request, successful Actions checks, and
merge by the release owner. A GitHub technical reviewer, if appointed, reviews
the code and process integrity. That reviewer does not make the independent
lawyer's legal decision.

## Final activation

After both legal decisions, the release owner creates the final record:

```sh
python scripts/activate_public_release.py \
  governance/public/kz/0.1.0-rc1/decision.json \
  --approved-on YYYY-MM-DD
```

A new pull request then verifies every hash and negative test. Only after that
decision is merged and a new image is released may the operator set:

```text
ALMA_RELEASE_MODE=public_legal_release
```

Until then, the deployment uses `controlled_pilot`. A premature public setting
stops the Cloud Run Job before Gemini is called and before a legal draft is
created.

## When a new review is required

A new review cycle is required if any governed item changes:

- a legal card or official source;
- one of the five signal mappings;
- a competent-authority route or request text;
- a territory catalog entry, land purpose, or spatial source.

A new GeoPackage for a new geography usually needs no algorithm change when it
uses the supported format. It still changes the territory catalog, its SHA-256,
and the scope of use. The release therefore needs an intersection test and a
new legal review of the route. A different layer format, multiple target layers
in one file, a different geometry type, or a distance tolerance requires a
separate code change and tests.

The lawyer sees the filenames, purpose, and all territories that use each
authority route. Each public layer must also record its provenance, version or
date, and permitted use. A community-derived layer must not be called official.
The lawyer must mark a disagreement or the record must state its community
origin.

## Limits of the approval

The approval does not establish a violation or a person's guilt. It does not
make ALMA a legal-advice service. It does not permit automatic submission of a
citizen request. A draft asks the competent authority to verify the facts,
determine which rules apply, and report the result.
