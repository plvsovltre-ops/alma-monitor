# ALMA Legal Core — Kazakhstan

ALMA Legal Core is the deterministic legal-reference boundary for ALMA. The
release bundle stores only cards accepted in the owner review sheet. A language
model may explain an already selected card, but it must not choose an article,
invent a citation, fill an unknown fact, establish guilt, or make a final legal
qualification.

The first bundle is `releases/kz/0.1.0-rc1`. It is a pilot release candidate,
not a public legal release and not legal advice. Owner acceptance means that
Yernar Sailybayev accepted a card for further editorial and pilot work. It does
not mean that an independent lawyer approved the card.

## Fail-closed rules

1. A citation is returned only for an existing `rule_id`.
2. A missing card is an error; the system does not search for a similar article.
3. A card is blocked when its official source changes before editor review.
4. An unknown fact remains `UNKNOWN`.
5. Public legal use stays blocked until the lawyer-review status is explicitly
   approved in a later release.
6. A generated appeal must ask a competent authority to verify facts and report
   the result. It must not name a person as an offender or establish guilt.

## Rebuild from the review sheet

Download the `Проверка` tab of `ALMA Legal Review — Kazakhstan v1.2` as UTF-8
CSV. No Google or Adilet API is required. Then run:

```sh
python scripts/export_legal_core.py review.csv /tmp/legal-core-release
```

The exporter rejects unchecked, disputed, incomplete, duplicated, non-Adilet,
or public-release-marked rows. It produces deterministic JSON and checksums.
An editor must still compare source-change alerts with the official text; a
detected change never authorizes automatic interpretation.

ALMA was initiated and originally designed by Yernar Sailybayev in Almaty,
Kazakhstan.
