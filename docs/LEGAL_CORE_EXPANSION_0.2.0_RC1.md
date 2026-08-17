# ALMA Legal Core: OOPT and water-protection expansion 0.2.0-rc1

Status: **legal review reported complete; strict runtime activation remains
blocked pending official boundary provenance**.

Proposal SHA-256:
`f0df0ce5f24dacec3a6629f0b9e1c69e9bc59ac0c107062f7b991bbb7a9fc816`.

This package extends the reviewable ALMA Legal Core for two spatial contexts:

- the Iley-Alatau State National Nature Park;
- water-protection strips in and near Almaty.

It does not activate the boundary-dependent rules as if either GIS layer were
an official boundary. A separate controlled field mode uses both layers only
as open-source screening context and remains bound to Legal Core cards already
admitted to the active release.

The owner reported on 17 August 2026 that the independent lawyer agreed with
all 42 hash-bound review objects. The public repository keeps the reviewer
identity confidential. This completes the legal-review stage but does not
replace missing official spatial acts.

## What the reviewer approves

The compact table contains 42 hash-bound objects:

- 23 legal cards;
- 1 explicit supersession of an obsolete Article 48 card;
- 2 territory-context profiles;
- 10 deterministic `context × incident type` mappings;
- 2 authority routes;
- 2 short request-template families;
- 2 spatial-source records.

For each row the reviewer selects exactly one result:

- `Согласен = TRUE`, `Не согласен = FALSE`; or
- `Согласен = FALSE`, `Не согласен = TRUE` and a short comment.

Any missing, changed, duplicated or disagreed row blocks approval. The official
source column is placed immediately before the norm or decision.

## Important legal correction

The earlier card `kz-oopt-48-1-5-8-other-harm` does not match the verified
current structure of Article 48. It was not part of the 18 active legal cards in
the public runtime. This proposal records it as superseded and blocks it from
future mappings. Current Article 48 provisions are split into narrower cards.

## Why strict spatial qualification remains blocked

The files themselves were inspected and fingerprinted, but their embedded
metadata does not establish an official spatial provenance:

- `Национальный_Природный_Парк.gpkg` contains 28 geometries and cadastral
  identifiers, but does not preserve a sufficient official source or the
  functional-zoning map;
- `Водоохранные_полосы.gpkg` contains 33 geometries, but preserves technical
  local GeoJSON names instead of the decision and official publication URL.

The user subsequently documented that the polygons were manually exported one
by one from the public ALAG geo-information map. That provenance is sufficient
for controlled open-source screening and is recorded in
`config/spatial_sources.json`. It is not sufficient to call the polygons an
official national-park boundary, functional-zoning map, or approved
water-protection boundary. Strict activation still requires a second,
hash-bound step after the following fields are confirmed for each layer:

1. issuing public authority;
2. title, number and date of the approving act or project;
3. official publication URL;
4. official dataset URL or documented extraction method;
5. coordinate reference system and effective date;
6. file SHA-256;
7. for the national park, the official functional-zoning source.

## Deterministic selection

Gemini does not select article numbers. A policy mapping is selected only by:

`reviewed context_profile_id + exact reviewed incident_type`

Unknown circumstances remain unknown. The output asks the competent authority
to verify facts and report the result; it does not establish a violation,
offender or guilt.

## Official sources checked on 17 August 2026

- [Law on Specially Protected Natural Areas](https://adilet.zan.kz/rus/docs/Z060000175_)
- [Water Code of the Republic of Kazakhstan](https://adilet.zan.kz/rus/docs/K2500000178)
- [Forestry and Wildlife Committee](https://www.gov.kz/memleket/entities/forest)
- [Official Iley-Alatau National Park context](https://www.gov.kz/memleket/entities/ecogeo/press/news/details/1252960?lang=ru)
- [Official publication identifying the park administration](https://www.gov.kz/memleket/entities/almaty-eco/press/article/details/208767)

ALMA was initiated and originally designed by Yernar Sailybayev in Almaty,
Kazakhstan.
