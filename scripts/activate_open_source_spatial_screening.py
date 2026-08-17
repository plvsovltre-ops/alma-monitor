#!/usr/bin/env python3
"""Build the reviewed open-source screening catalogs for field operation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OWNER = {"name": "Yernar Sailybayev", "capacity": "AUTHOR_AND_LEGAL_EDITOR"}
REVIEWED_ON = "2026-08-17"
INCIDENT_TYPES = ("waste", "logging", "construction", "soil_damage", "water_pollution")


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_family(subject_ru: str, subject_kz: str, request_ru: str, request_kz: str) -> dict:
    return {
        incident_type: {
            "subject_ru": subject_ru,
            "subject_kz": subject_kz,
            "request_ru": request_ru,
            "request_kz": request_kz,
        }
        for incident_type in INCIDENT_TYPES
    }


def build_territories() -> None:
    base_path = ROOT / "config" / "territory_catalog.json"
    field_dir = ROOT / "config" / "field" / "0.2.0-rc1"
    path = field_dir / "territory_catalog.json"
    catalog = read(base_path)
    catalog["schema_version"] = "1.1"
    catalog["catalog_id"] = "kz-almaty-field-routes-0.4.0"
    catalog["routes"]["ile_alatau_national_park_administration"] = {
        "display_name_ru": "Администрация Иле-Алатауского национального парка",
        "display_name_kz": "Іле-Алатауы ұлттық паркінің әкімшілігі",
        "official_name_ru": "Республиканское государственное учреждение «Иле-Алатауский государственный национальный природный парк» Комитета лесного хозяйства и животного мира Министерства экологии и природных ресурсов Республики Казахстан",
        "official_name_kz": "Қазақстан Республикасы Экология және табиғи ресурстар министрлігі Орман шаруашылығы және жануарлар дүниесі комитетінің «Іле-Алатауы мемлекеттік ұлттық табиғи паркі» республикалық мемлекеттік мекемесі",
        "official_source_url": "https://www.gov.kz/memleket/entities/almaty-eco/press/article/details/208767",
        "competence_source_url": "https://www.gov.kz/memleket/entities/forest",
        "verified_on": REVIEWED_ON,
        "forwarding_ru": "Если отдельный вопрос относится к компетенции другого государственного органа, прошу направить обращение по компетенции.",
        "forwarding_kz": "Егер жекелеген мәселе басқа мемлекеттік органның құзыретіне жатса, өтінішті құзыреті бойынша жолдауды сұраймын."
    }
    catalog["request_template_families"] = {
        "ile_alatau_open_source_screening": request_family(
            "Проверка наблюдения в возможном контексте национального парка",
            "Ұлттық парк ықтимал контексіндегі бақылауды тексеру",
            "Прошу сопоставить координаты с утвержденными границами и функциональным зонированием Иле-Алатауского национального парка, проверить изложенные факты и необходимые документы, принять меры при наличии оснований и сообщить результат.",
            "Координаттарды Іле-Алатауы ұлттық паркінің бекітілген шекараларымен және функционалдық аймақтарымен салыстырып, баяндалған фактілер мен қажетті құжаттарды тексеруді, негіздер болған кезде шаралар қабылдап, нәтижесін хабарлауды сұраймын.",
        ),
        "water_open_source_screening": request_family(
            "Проверка наблюдения в возможном водоохранном контексте",
            "Ықтимал су қорғау контексіндегі бақылауды тексеру",
            "Прошу сопоставить координаты с утвержденными границами водоохранной зоны и полосы, проверить изложенные факты, необходимые согласования и защитные меры, принять меры при наличии оснований и сообщить результат.",
            "Координаттарды су қорғау аймағы мен белдеуінің бекітілген шекараларымен салыстырып, баяндалған фактілерді, қажетті келісімдер мен қорғау шараларын тексеруді, негіздер болған кезде шаралар қабылдап, нәтижесін хабарлауды сұраймын.",
        ),
    }
    new_territories = [
        {
            "territory_id": "ile-alatau-open-source-cadastral-screening-2026",
            "source_file": "Национальный_Природный_Парк.gpkg",
            "public_name_ru": "территория, отмеченная открытым источником как возможный контекст Иле-Алатауского национального парка",
            "public_name_kz": "ашық дереккөзде Іле-Алатауы ұлттық паркінің ықтимал контексі ретінде белгіленген аумақ",
            "purpose_ru": "предварительная проверка природоохранного контекста с последующим подтверждением границ и режима компетентным органом",
            "purpose_kz": "шекаралар мен режимді құзыретті орган кейіннен растайтын табиғат қорғау контексін алдын ала тексеру",
            "context_profile_id": "ile_alatau_open_source_screening",
            "route_ids_by_incident_type": {
                value: "ile_alatau_national_park_administration" for value in INCIDENT_TYPES
            },
            "request_template_family_id": "ile_alatau_open_source_screening",
            "spatial_source_id": "alag-ile-alatau-cadastral-polygons-2026-08-17",
            "spatial_use": "OPEN_SOURCE_SCREENING_CONTEXT_ONLY",
            "reference_fields": ["кадастр", "layer"],
            "priority": 5,
        },
        {
            "territory_id": "almaty-water-open-source-screening-2026",
            "source_file": "Водоохранные_полосы.gpkg",
            "public_name_ru": "территория, отмеченная открытым источником как возможный водоохранный контекст",
            "public_name_kz": "ашық дереккөзде ықтимал су қорғау контексі ретінде белгіленген аумақ",
            "purpose_ru": "предварительная проверка близости к водоохранной зоне или полосе с подтверждением официальных границ бассейновой инспекцией",
            "purpose_kz": "ресми шекараларды бассейндік инспекция растайтын су қорғау аймағына немесе белдеуіне жақындықты алдын ала тексеру",
            "context_profile_id": "water_open_source_screening",
            "route_ids_by_incident_type": {
                value: "balkhash_alakol_water_inspection" for value in INCIDENT_TYPES
            },
            "request_template_family_id": "water_open_source_screening",
            "spatial_source_id": "alag-water-context-polygons-2026-08-17",
            "spatial_use": "OPEN_SOURCE_SCREENING_CONTEXT_ONLY",
            "reference_fields": ["layer"],
            "priority": 4,
        },
    ]
    catalog["territories"] = [
        value
        for value in catalog["territories"]
        if value["source_file"] not in {item["source_file"] for item in new_territories}
    ] + new_territories
    digest = dump(path, catalog)
    approval = {
        "schema_version": "1.1",
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": digest,
        "approval_scope": "CONTROLLED_FIELD_SCREENING_ONLY",
        "decision": "CONTROLLED_PILOT_APPROVED",
        "reviewer": OWNER,
        "reviewed_on": REVIEWED_ON,
        "spatial_registry_id": "kz-alma-open-spatial-sources-0.1.0",
        "statement": "The owner approved the routes and open-source spatial screening labels. The two added layers do not establish official OOPT, functional-zone, or water-protection boundaries."
    }
    dump(field_dir / "territory_catalog.approval.json", approval)


def build_responses() -> None:
    base_path = ROOT / "config" / "response_catalog.json"
    field_dir = ROOT / "config" / "field" / "0.2.0-rc1"
    path = field_dir / "response_catalog.json"
    catalog = read(base_path)
    catalog["schema_version"] = "1.1"
    catalog["catalog_id"] = "kz-alma-human-response-0.2.0"
    catalog["context_profiles"]["ile_alatau_open_source_screening"] = {
        "why_ru": "Этот участок попал в открытый кадастровый слой, который ALMA использует как предварительный сигнал возможного контекста Иле-Алатауского национального парка. Национальный парк сохраняет горные ландшафты, леса, воду и биоразнообразие. Точную границу и функциональную зону должен подтвердить компетентный орган — это нормальная часть проверки, а не недостаток наблюдения волонтера.",
        "why_kz": "Бұл учаске ALMA Іле-Алатауы ұлттық паркінің ықтимал контексінің алдын ала сигналы ретінде пайдаланатын ашық кадастрлық қабатқа түсті. Ұлттық парк тау ландшафттарын, ормандарды, суды және биоалуантүрлілікті сақтайды. Нақты шекара мен функционалдық аймақты құзыретті орган растауға тиіс — бұл еріктінің бақылауындағы кемшілік емес, тексерудің қалыпты бөлігі.",
        "principles": [
            {
                "principle_id": "kz-oopt-purpose-and-regime-screening",
                "text_ru": "Закон об ООПТ требует учитывать целевое назначение территории и установленный режим; ALMA не определяет функциональную зону по фотографии или названию слоя.",
                "text_kz": "ЕҚТА туралы заң аумақтың нысаналы мақсаты мен белгіленген режимін ескеруді талап етеді; ALMA функционалдық аймақты фотосурет немесе қабат атауы бойынша анықтамайды.",
                "official_url": "https://adilet.zan.kz/rus/docs/Z060000175_",
                "verified_on": REVIEWED_ON,
            }
        ],
    }
    catalog["context_profiles"]["water_open_source_screening"] = {
        "why_ru": "Этот участок попал в открытый слой возможного водоохранного контекста. Водоохранные зоны и полосы нужны, чтобы предотвращать загрязнение, засорение и истощение воды и сохранять связанные экосистемы. ALMA просит бассейновую инспекцию подтвердить официальную границу: волонтеру не нужно быть геодезистом, чтобы правильно подать сигнал.",
        "why_kz": "Бұл учаске ықтимал су қорғау контексінің ашық қабатына түсті. Су қорғау аймақтары мен белдеулері судың ластануын, қоқыстануын және сарқылуын болдырмау, сондай-ақ байланысты экожүйелерді сақтау үшін қажет. ALMA бассейндік инспекциядан ресми шекараны растауды сұрайды: дұрыс сигнал беру үшін еріктіге геодезист болудың қажеті жоқ.",
        "principles": [
            {
                "principle_id": "kz-water-protection-boundary-screening",
                "text_ru": "Границы водоохранных зон и полос определяются утвержденной документацией и координатами; открытый пользовательский слой служит только поводом запросить их официальную проверку.",
                "text_kz": "Су қорғау аймақтары мен белдеулерінің шекаралары бекітілген құжаттама және координаттар бойынша айқындалады; ашық пайдаланушылық қабат оларды ресми тексеруді сұрауға ғана негіз болады.",
                "official_url": "https://adilet.zan.kz/rus/docs/K2500000178",
                "verified_on": REVIEWED_ON,
            }
        ],
    }
    incident_ru = {
        "waste": "размещенных предметов или материалов",
        "logging": "удаления или повреждения растительности",
        "construction": "строительных или земляных работ",
        "soil_damage": "изменения почвы или рельефа",
        "water_pollution": "изменения состояния воды или размещения веществ рядом с ней",
    }
    incident_kz = {
        "waste": "орналастырылған заттар немесе материалдар",
        "logging": "өсімдіктердің жойылуы немесе зақымдануы",
        "construction": "құрылыс немесе жер жұмыстары",
        "soil_damage": "топырақтың немесе жер бедерінің өзгеруі",
        "water_pollution": "судың жай-күйінің өзгеруі немесе оның жанында заттардың орналасуы",
    }
    catalog["actions_by_context"] = {}
    for context_id, context_ru, context_kz in (
        (
            "ile_alatau_open_source_screening",
            "возможного природоохранного контекста",
            "ықтимал табиғат қорғау контексінде",
        ),
        (
            "water_open_source_screening",
            "возможного водоохранного контекста",
            "ықтимал су қорғау контексінде",
        ),
    ):
        catalog["actions_by_context"][context_id] = {}
        for incident_type in INCIDENT_TYPES:
            catalog["actions_by_context"][context_id][incident_type] = {
                "assessment_ru": f"Наблюдаемые признаки {incident_ru[incident_type]} внутри {context_ru} — достаточный повод для официальной проверки границы, режима, документов и фактических обстоятельств. Наблюдение не устанавливает нарушение, виновность или ответственное лицо.",
                "assessment_kz": f"{context_kz} {incident_kz[incident_type]} байқалуы шекараны, режимді, құжаттарды және нақты мән-жайларды ресми тексеруге жеткілікті негіз болып табылады. Бақылау құқық бұзушылықты, кінәні немесе жауапты тұлғаны анықтамайды.",
                "next_ru": "Рекомендуем направить подготовленный проект через eOtinish и сохранить номер обращения. Ответ органа поможет уточнить официальный территориальный режим. Если ситуация меняется, повторное безопасное наблюдение покажет динамику.",
                "next_kz": "Дайындалған жобаны eOtinish арқылы жіберіп, өтініш нөмірін сақтауды ұсынамыз. Органның жауабы ресми аумақтық режимді нақтылауға көмектеседі. Жағдай өзгерсе, қауіпсіз қайталама бақылау динамиканы көрсетеді.",
            }
    digest = dump(path, catalog)
    approval = {
        "schema_version": "1.1",
        "catalog_id": catalog["catalog_id"],
        "catalog_sha256": digest,
        "approval_scope": "CONTROLLED_FIELD_SCREENING_ONLY",
        "decision": "CONTROLLED_PILOT_APPROVED",
        "reviewer": OWNER,
        "reviewed_on": REVIEWED_ON,
        "statement": "The owner approved the human-facing screening context. The text preserves uncertainty and asks the competent authority to verify official boundaries and legal regime."
    }
    dump(field_dir / "response_catalog.approval.json", approval)


def build_policy() -> None:
    old_dir = ROOT / "legal_core" / "policies" / "kz" / "0.1.0-rc1"
    policy = read(old_dir / "policy.json")
    policy["schema_version"] = "1.1"
    policy["policy_id"] = "kz-alma-field-screening-0.1.0"
    policy["selection_basis"] = "Exact reviewed context_profile_id plus exact normalized incident_type. Open ALAG polygons are screening context only; the model never selects rule IDs or declares an official boundary."
    policy["context_mappings"] = {
        "ile_alatau_open_source_screening": {
            "waste": {"label_ru": "Материалы в возможном природоохранном контексте", "rule_ids": ["kz-oopt-23-3-purpose", "kz-oopt-45-4-6-tourism-protection", "kz-forest-113-selected-breaches"], "unknowns_ru": ["официальная граница территории и применимая функциональная зона", "статус предметов как отходов или временных материалов", "допустимость размещения и ответственное лицо"]},
            "logging": {"label_ru": "Растительность в возможном природоохранном контексте", "rule_ids": ["kz-oopt-23-3-purpose", "kz-koap-381-1-3-oopt-repeat", "kz-forest-113-selected-breaches"], "unknowns_ru": ["официальная граница территории и функциональная зона", "вид и состояние растительности", "документы, действие, ущерб и ответственное лицо"]},
            "construction": {"label_ru": "Работы в возможном природоохранном контексте", "rule_ids": ["kz-oopt-23-3-purpose", "kz-oopt-45-4-6-tourism-protection", "kz-forest-113-selected-breaches"], "unknowns_ru": ["официальная граница и функциональная зона", "назначение работ, проект и разрешительные документы", "влияние на природные комплексы"]},
            "soil_damage": {"label_ru": "Изменение почвы в возможном природоохранном контексте", "rule_ids": ["kz-oopt-23-3-purpose", "kz-oopt-45-4-6-tourism-protection"], "unknowns_ru": ["официальная граница и функциональная зона", "характер и объем воздействия", "документы и последствия для природного комплекса"]},
            "water_pollution": {"label_ru": "Вода в возможном природоохранном контексте", "rule_ids": ["kz-oopt-23-3-purpose", "kz-water-75-1-protection-directions", "kz-water-86-1-2-surface-waste", "kz-forest-113-selected-breaches"], "unknowns_ru": ["официальная граница и специальный режим территории", "водный объект, вещество и факт попадания в воду", "источник воздействия, пробы и ответственное лицо"]},
        },
        "water_open_source_screening": {
            "waste": {"label_ru": "Материалы в возможном водоохранном контексте", "rule_ids": ["kz-water-85-1-protection-zones-purpose", "kz-water-85-2-protection-zone-spatial-data", "kz-water-86-2-protective-strip", "kz-water-86-3-4-dumps"], "unknowns_ru": ["утвержденная граница водоохранной зоны или полосы", "статус предметов как отходов", "допустимость размещения и применимое исключение"]},
            "logging": {"label_ru": "Растительность в возможном водоохранном контексте", "rule_ids": ["kz-water-85-1-protection-zones-purpose", "kz-water-85-2-protection-zone-spatial-data", "kz-water-86-2-protective-strip"], "unknowns_ru": ["утвержденная граница полосы", "характер растительности и работ", "допустимость деятельности и документы"]},
            "construction": {"label_ru": "Работы в возможном водоохранном контексте", "rule_ids": ["kz-water-85-2-protection-zone-spatial-data", "kz-water-86-1-6-works-no-approval", "kz-water-86-2-protective-strip", "kz-water-86-3-1-no-protection-devices", "kz-water-86-4-protection-systems"], "unknowns_ru": ["утвержденная граница полосы", "вид работ и согласование инспекции", "применимое исключение и защитные системы"]},
            "soil_damage": {"label_ru": "Почва в возможном водоохранном контексте", "rule_ids": ["kz-water-85-1-protection-zones-purpose", "kz-water-85-2-protection-zone-spatial-data", "kz-water-86-2-protective-strip"], "unknowns_ru": ["утвержденная граница полосы", "характер земляных работ и согласования", "влияние на сток и устойчивость берега"]},
            "water_pollution": {"label_ru": "Вода в возможном водоохранном контексте", "rule_ids": ["kz-water-75-1-protection-directions", "kz-water-85-1-protection-zones-purpose", "kz-water-85-2-protection-zone-spatial-data", "kz-water-86-1-2-surface-waste"], "unknowns_ru": ["утвержденная граница водоохранного режима", "водный объект, вещество и факт попадания в воду", "источник воздействия, пробы и ответственное лицо"]},
        },
    }
    policy_dir = ROOT / "legal_core" / "policies" / "kz" / "0.1.1-screening"
    digest = dump(policy_dir / "policy.json", policy)
    old_approval = read(old_dir / "approval.json")
    approval = {
        "schema_version": "1.1",
        "policy_id": policy["policy_id"],
        "decision": "CONTROLLED_PILOT_APPROVED",
        "required_reviewer": OWNER,
        "reviewer": OWNER,
        "reviewed_on": REVIEWED_ON,
        "policy_sha256": digest,
        "legal_release_artifacts": old_approval["legal_release_artifacts"],
        "approval_scope": "CONTROLLED_FIELD_SCREENING_ONLY",
        "independent_lawyer_review_status": "INDEPENDENT_LAWYER_REVIEW_REPORTED_CONFIDENTIAL",
        "public_release_status": "PUBLIC_LEGAL_RELEASE_BLOCKED",
        "expansion_proposal_sha256": "f0df0ce5f24dacec3a6629f0b9e1c69e9bc59ac0c107062f7b991bbb7a9fc816",
        "statement": "The owner approved a conservative field-screening policy after reporting completion of the expansion legal review. It uses only cards already admitted to the active Legal Core and does not activate the expansion's boundary-dependent rules."
    }
    dump(policy_dir / "approval.json", approval)


def main() -> None:
    build_territories()
    build_responses()
    build_policy()


if __name__ == "__main__":
    main()
