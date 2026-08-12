# Competent Authority Routing — controlled proposal

Status: author and legal editor review required. The proposal is not active in
the runtime until its exact SHA-256 is approved by Yernar Sailybayev for the
private controlled pilot.

## Deterministic routing matrix

| Exact `incident_type` | Primary authority | Short purpose of the request |
|---|---|---|
| `waste` | Almaty land-resources department | Check whether the recorded placement is permitted on protected orchard land. |
| `logging` | Almaty Ecology and Environment Department | Check the condition of green spaces and the documents required for cutting, transplanting, or damage. |
| `construction` | Almaty Urban Planning Control Department | Check the recorded works and compliance with requirements protecting green spaces and topsoil. |
| `soil_damage` | Almaty land-resources department | Check the recorded impact on soil and requirements protecting land and fertile topsoil. |
| `water_pollution` | Balkhash-Alakol Basin Inspection | Check the water body, possible source of the recorded material, and whether sampling is needed. |

The route is selected only when both conditions are satisfied:

1. the point intersects a reviewed orchard GeoPackage filename; and
2. `incident_type` exactly matches one of the five reviewed field values.

Gemini, volunteer free text, the photograph, and inferred legal provisions do
not select the authority. An unknown territory or type remains quarantined. The
system presents one primary authority and a fixed request to forward the appeal
if another authority is competent. It does not automatically submit the appeal.

## Official sources checked on 2026-08-13

- Almaty land-resources department: <https://www.gov.kz/memleket/entities/land/press/article/details/235871>
- Almaty Ecology and Environment Department: <https://www.gov.kz/memleket/entities/almaty-eco?lang=ru>
- Almaty Urban Planning Control Department: <https://www.gov.kz/memleket/entities/almaty-ugask?lang=ru>
- Balkhash-Alakol Basin Inspection position: <https://www.gov.kz/memleket/entities/maidd/documents/details/744463>

District akimats and other bodies are not guessed in this release. Adding them
requires a separate deterministic condition, an official competence source, a
short bilingual request, tests, and a newly approved catalog hash.
