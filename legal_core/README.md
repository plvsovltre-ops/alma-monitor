# ALMA Legal Core — Kazakhstan

ALMA Legal Core is the deterministic legal-reference boundary for ALMA. The
release bundle stores only cards accepted in the owner review sheet. A language
model may explain an already selected card, but it must not choose an article,
invent a citation, fill an unknown fact, establish guilt, or make a final legal
qualification.

The first bundle is `releases/kz/0.1.0-rc1`. Yernar Sailybayev approved its
reviewed cards in the disclosed capacity of author and legal editor for a
private controlled pilot. It is not a public legal release, independent legal
review, or legal advice. The separate `review.json` binds that decision to the
exact reviewed `cards.json` and `sources.json` artifacts.

## Fail-closed rules

1. A citation is returned only for an existing `rule_id`.
2. A missing card is an error; the system does not search for a similar article.
3. A card is blocked when its official source changes, is missing, or has an
   unrecognized monitoring status.
4. An unknown fact remains `UNKNOWN`.
5. Controlled-pilot use requires the recorded author/legal-editor approval.
6. Public legal use requires the separate hash-bound author review,
   independent-lawyer review, and final activation under `governance/public/`.
7. A generated appeal must ask a competent authority to verify facts and report
   the result. It must not name a person as an offender or establish guilt.
8. The catalog verifies `SHA256SUMS`, the manifest, the review record, the
   source registry, and every canonical card hash before it returns a citation.
9. This controlled-pilot bundle remains immutable and accepts only the recorded
   review by Yernar Sailybayev. The public governance overlay cannot be
   unlocked by editing this bundle or changing a status string.

## Canonical card hash

`card_hash` is SHA-256 of UTF-8 JSON containing `rule_id`, `provision`,
`safe_summary`, `source_id`, and `official_url`. Keys are sorted, insignificant
whitespace is removed, Unicode is preserved, and `www.adilet.zan.kz` is
normalized to `adilet.zan.kz`. The exporter rejects a row when this hash does
not match the reviewed content.

## Rebuild from the review sheet

Download the `Проверка` tab of `ALMA Legal Review — Kazakhstan v1.2` as UTF-8
CSV. No Google or Adilet API is required. Then run:

```sh
python scripts/export_legal_core.py review.csv /tmp/legal-core-release \
  --release-id kz-0.1.0-rc1 \
  --review-date 2026-08-11 \
  --review-view-version 1.2 \
  --source-spreadsheet-id 1OfPXFwk3RnrJP6H6FVsv_KIRpX-9Gy-ULkWom1ZThaQ \
  --source-review-view "ALMA Legal Review — Kazakhstan v1.2" \
  --expected-card-count 122 \
  --legal-reviewer-name "Yernar Sailybayev" \
  --legal-review-date 2026-08-12
```

The exporter rejects unchecked, disputed, incomplete, duplicated, non-Adilet,
stale-hash, conflicting-source, or public-release-marked rows. It refuses to
overwrite a non-empty release directory and produces deterministic JSON and
checksums.
An editor must still compare source-change alerts with the official text; a
detected change never authorizes automatic interpretation.

## Runtime mapping

`policies/kz/0.1.0-rc1/policy.json` proposes deterministic mappings for the five
exact Mergin Maps field values: `waste`, `logging`, `construction`,
`soil_damage`, and `water_pollution`. Description text, photos, coordinates,
GIS context, and the language model cannot add or replace a `rule_id`.

The separate `approval.json` binds the mapping to the exact policy file and the
exact reviewed `cards.json` and `review.json`. Yernar Sailybayev approved the
exact policy SHA-256
`dff20191ef26409fa23c1c43130961a9987b081b88b35c79605e94441c4c26b6`
on 2026-08-12 as author and legal editor for the private controlled pilot only.
The policy keeps its original proposal marker so that the reviewed artifact
remains byte-for-byte unchanged; the separate approval decision unlocks it.
Changing the policy after approval invalidates its hash and stops processing.

## Public governance overlay

The proposed `kz-alma-public-0.1.0-rc1` overlay is blocked by default. Its
proposal binds the exact card, source, owner-review, runtime-policy, territory,
and human-response artifacts. A second manifest hash binds the exact 32-object
lawyer view produced from those files. This prevents a changed exporter from
hiding a governed object while leaving the underlying artifact hashes intact.

The review view has 18 active cards, five signal mappings (including the
bilingual public-interest and action text), four competent-authority routes
(including their complete GIS territory coverage),
and five bilingual request templates. A complete author review and a separate
complete review by an identified qualified lawyer are both required. The
process is documented in
[`../docs/PUBLIC_RELEASE_GOVERNANCE.md`](../docs/PUBLIC_RELEASE_GOVERNANCE.md).

Gemini receives one shared fact object for Russian and Kazakh drafting. It does
not receive article names or official URLs and may not insert a legal citation.
The application rejects such output and appends reviewed Legal Core cards itself.
Unknown cadastral, ownership, permitting, causation, material, and boundary
facts remain requests for verification.

ALMA was initiated and originally designed by Yernar Sailybayev in Almaty,
Kazakhstan.
