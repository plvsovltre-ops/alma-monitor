# ALMA Human Response Core — controlled pilot release

Status: approved by Yernar Sailybayev as author and legal editor for the private
controlled pilot. The approval is bound to the exact
`kz-alma-human-response-0.1.0` catalog with SHA-256
`ae1c62c8c77e018dbf7cb303a648c48f79ef2cff28ec971c8c61941a73b340b1`.

## Volunteer contract

Every successful result contains the same deterministic structure in Russian
and Kazakh:

1. a short greeting and acknowledgement from the ALMA team;
2. `What we saw`: the reviewed public-interest context, one bilingual Gemini
   fact object, a cautious reviewed assessment, and a practical next step;
3. a draft request: ALMA scope notice, reviewed recipient and channel, concise
   observation, Legal Core provisions, short request, merits/forwarding/appeal
   formula;
4. a final contribution acknowledgement. Prior contributions are counted only
   from delivered private incident cards with the same normalized email.

The model prepares only `facts_ru` and `facts_kz` in one JSON object. It does not
select law, public-interest context, authority, request, action, or contribution
history. A non-JSON object, extra field, prohibited legal reference, authority,
legal conclusion, or unsuitable volunteer phrase quarantines the incident before
email delivery.

## Reviewed sources checked on 2026-08-13

- Land Code of Kazakhstan, protection and rational-use principles:
  <https://adilet.zan.kz/rus/docs/K030000442_>
- Environmental Code of Kazakhstan, prevention and ecosystem principles:
  <https://adilet.zan.kz/rus/docs/K2100000400>
- Administrative Procedural and Process-Related Code of Kazakhstan, the basis
  for the controlled procedural request:
  <https://adilet.zan.kz/rus/docs/K2000000350>

The public-interest profile in this release applies only to the eight reviewed
orchard GeoPackage filenames in the territory catalog. A protected-area,
agricultural-land, water-body, or other profile requires its own exact sources,
bilingual text, tests, catalog hash, and approval before it can be selected.
