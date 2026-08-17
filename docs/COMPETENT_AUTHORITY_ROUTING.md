# Competent Authority Routing — controlled field release

Status: approved by Yernar Sailybayev as author and legal editor for controlled
field use and active in the runtime. The approval is bound to exact
SHA-256 `717f1487ed05813d803419d7dea38acfc8499e33bdbbd888b5a5a45ce0485d35`.

The active catalog is `kz-almaty-field-routes-0.4.0`. It preserves the orchard
routes and adds controlled open-source screening routes to the national-park
administration and the basin inspection. The exact `context_profile_id` selects
the volunteer explanation and screening legal mapping deterministically. The
new layers are not classified as official legal boundaries.

## Deterministic routing matrix

| Exact `incident_type` | Primary authority | Short purpose of the request |
|---|---|---|
| `waste` | Almaty land-resources department | Check whether the recorded placement is permitted on protected orchard land. |
| `logging` | Almaty Ecology and Environment Department | Check the condition of green spaces and the documents required for cutting, transplanting, or damage. |
| `construction` | Almaty Urban Planning Control Department | Check the recorded works and compliance with requirements protecting green spaces and topsoil. |
| `soil_damage` | Almaty land-resources department | Check the recorded impact on soil and requirements protecting land and fertile topsoil. |
| `water_pollution` | Balkhash-Alakol Basin Inspection | Check the water body, possible source of the recorded material, and whether sampling is needed. |

For the two versioned screening contexts, all five exact signal types use a
single conservative primary route:

| Exact context | Primary authority | Purpose |
|---|---|---|
| `ile_alatau_open_source_screening` | Administration of the Iley-Alatau State National Nature Park | Verify the official boundary, functional zone, applicable regime, facts, and documents. |
| `water_open_source_screening` | Balkhash-Alakol Basin Inspection | Verify the approved water-protection boundary, applicable regime, facts, approvals, and protective measures. |

The route is selected only when both conditions are satisfied:

1. the point intersects an exact reviewed GeoPackage filename; and
2. `incident_type` exactly matches one of the five reviewed field values.

For an ALAG-derived layer the runtime also verifies the source-registry ID,
local file SHA-256, allowed screening-only use, and next-review date. Such an
intersection does not establish an official protected-area or water-protection
boundary.

Gemini, volunteer free text, the photograph, and inferred legal provisions do
not select the authority. An unknown territory or type remains quarantined. The
system presents one primary authority and a fixed request to forward the appeal
if another authority is competent. It does not automatically submit the appeal.

## Official sources checked on 2026-08-13

- Almaty land-resources department: <https://www.gov.kz/memleket/entities/land/press/article/details/235871>
- Almaty Ecology and Environment Department: <https://www.gov.kz/memleket/entities/almaty-eco?lang=ru>
- Almaty Urban Planning Control Department: <https://www.gov.kz/memleket/entities/almaty-ugask?lang=ru>
- Balkhash-Alakol Basin Inspection position: <https://www.gov.kz/memleket/entities/maidd/documents/details/744463>
- Forestry and Wildlife Committee: <https://www.gov.kz/memleket/entities/forest>
- Official publication identifying the Iley-Alatau park administration:
  <https://www.gov.kz/memleket/entities/almaty-eco/press/article/details/208767>

District akimats and other bodies are not guessed in this release. Adding them
requires a separate deterministic condition, an official competence source, a
short bilingual request, tests, and a newly approved catalog hash.
