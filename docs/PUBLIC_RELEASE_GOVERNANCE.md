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
   jurisdiction, and review date. The lawyer declares no conflict of interest
   and consents to public attribution of the name and qualification. A work
   email is used only for identity verification and is not published.
6. All 32 rows must contain `Согласен = TRUE` and `Не согласен = FALSE`. A
   disagreement starts a new revision cycle. An approved row must not be
   silently changed.
7. The final tab is exported as CSV. The review record stores the source Sheet
   URL and the CSV SHA-256. The Google Sheets revision history must show that
   the lawyer's account entered the decision.

This is a controlled electronic attestation for ALMA release governance. It is
not described as a qualified electronic signature.

## Two legal decisions

Yernar Sailybayev makes the first decision as author and legal editor:

```sh
python scripts/record_public_review.py author-review.csv \
  governance/public/kz/0.1.0-rc1/author_review.json \
  --role author \
  --reviewer-name "Yernar Sailybayev" \
  --reviewed-on YYYY-MM-DD \
  --review-source-url "https://docs.google.com/spreadsheets/d/..."
```

A different lawyer personally makes the second decision:

```sh
python scripts/record_public_review.py independent-review.csv \
  governance/public/kz/0.1.0-rc1/independent_review.json \
  --role independent \
  --reviewer-name "Full name" \
  --qualification "Qualification and jurisdiction" \
  --reviewed-on YYYY-MM-DD \
  --review-source-url "https://docs.google.com/spreadsheets/d/..." \
  --declare-no-conflict \
  --consent-public-attribution
```

The no-conflict flag means that the lawyer declares no conflict. The second
lawyer's name, qualification, and approval are public. Yernar Sailybayev, a
developer, or a model must not enter these decisions on the lawyer's behalf.

The lawyer does not need a GitHub account. If the lawyer has one, the lawyer may
also approve the pull request. That optional GitHub review does not replace the
32-row legal review and is not a legal-release gate. The required evidence is
the lawyer's personal work in Google Sheets, the completed attestation, the
revision history, the Sheet URL, and the final CSV SHA-256.

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
