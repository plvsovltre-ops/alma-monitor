# --- ALMA 8.9: SYNC FIX & SMART COLUMN SEARCH ---
print("🚀 SYSTEM STARTUP...", flush=True)

import warnings
warnings.filterwarnings("ignore")

import os
import glob
import sys
import json
import math
import logging
import smtplib
import shutil
import time
import pandas as pd
import geopandas as gpd
from datetime import datetime, timezone
import PIL.Image

# ИСПОЛЬЗУЕМ НОВУЮ БИБЛИОТЕКУ (Google GenAI SDK)
from google import genai
from google.genai import types
import google.auth
from google.cloud import storage
from google.api_core.exceptions import NotFound, PreconditionFailed

# Гугл Таблицы
import gspread

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from mergin import MerginClient, ClientError # Добавили импорт ошибки

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
LOG = logging.getLogger("alma_monitor")
LOG.info("Libraries loaded")

# --- НАСТРОЙКИ ---
MERGIN_PROJECT = "ALMA_exmachina/alma_bot"
PROJECT_PATH = "./project"
ARCHIVE_PATH = "./ALMA_ARCHIVE"
GOOGLE_SHEET_NAME = "ALMA_Registry"
GOOGLE_SHEET_HEADERS = [
    "Дата",
    "ID Дела",
    "Кадастр",
    "Тип нарушения",
    "Координаты",
    "Ответ AI (RU)",
    "Ответ AI (KZ)",
    "Путь к фото",
]

INCIDENTS_FILE = "Инцидент.gpkg"
PHOTOS_FILE = "photos.gpkg"
LAWS_FOLDER = "laws"
GARDEN_KEYWORDS = ["сады", "orchards", "защищенные", "проверке", "возвращенный"]
MAX_LAW_CHARS = 200000 

DEFAULT_MODEL_CANDIDATES = ("gemini-3.6-flash", "gemini-2.5-flash")
STATE_OBJECT = "state/last-scanned-version.json"
LOCK_OBJECT = "locks/alma-monitor.lock"
LOCK_TTL_SECONDS = 30 * 60
STATE_SCHEMA_VERSION = 2


def model_candidates():
    configured = os.environ.get("GEMINI_MODEL", "").strip()
    candidates = [configured] if configured else []
    candidates.extend(DEFAULT_MODEL_CANDIDATES)
    return list(dict.fromkeys(candidates))

FILE_MAPPING = {
    "00_guidelines.txt": "Руководство и Стратегия ALMA",
    "01_land_code.txt": "Земельный кодекс РК",
    "02_eco_code.txt": "Экологический кодекс РК",
    "03_water_code.txt": "Водный кодекс РК",
    "04_adm_code.txt": "КоАП РК",
    "05_crime_code.txt": "Уголовный кодекс РК",
    "06_law_architecture.txt": "Закон об архитектуре",
    "07_almaty_rules.txt": "ПЗЗ и Генплан Алматы",
    "08_biodiversity.txt": "Биоразнообразие",
    "10_presidential_acts.txt": "Акты Президента",
    "11_paris_agreement.txt": "Парижское соглашение",
    "12_biodiversity_convention.txt": "Конвенция о биоразнообразии",
    "13_aarhus_convention.txt": "Орхусская конвенция",
    "14_land_inspection.txt": "Полномочия Земельной инспекции"
}

os.makedirs(ARCHIVE_PATH, exist_ok=True)
os.makedirs(os.path.join(ARCHIVE_PATH, "PHOTOS"), exist_ok=True)

def get_env(name, required=True):
    val = os.environ.get(name)
    if not val:
        message = f"Required environment variable is not set: {name}"
        if required:
            raise RuntimeError(message)
        LOG.warning(message)
    return val


def get_project_version(mc):
    try:
        version = mc.project_info(MERGIN_PROJECT).get("version")
    except Exception as e:
        raise RuntimeError(
            f"Could not read Mergin Maps project version for {MERGIN_PROJECT}"
        ) from e

    if not version:
        raise RuntimeError("Mergin Maps did not return a project version")
    return str(version)


def get_state_bucket():
    bucket_name = get_env("STATE_BUCKET")
    return storage.Client().bucket(bucket_name)


def read_last_scanned_version(bucket):
    try:
        state = json.loads(bucket.blob(STATE_OBJECT).download_as_text())
    except NotFound:
        return None
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        raise RuntimeError("The ALMA Monitor state object is invalid") from e

    if state.get("schema_version") != STATE_SCHEMA_VERSION:
        LOG.info("Watcher state schema changed; a full scan is required")
        return None

    version = state.get("version")
    return str(version) if version else None


def write_last_scanned_version(bucket, version):
    payload = {
        "schema_version": STATE_SCHEMA_VERSION,
        "version": version,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }
    bucket.blob(STATE_OBJECT).upload_from_string(
        json.dumps(payload, ensure_ascii=True),
        content_type="application/json",
    )
    LOG.info("Recorded scanned Mergin Maps version: %s", version)


def _delete_stale_lock(bucket):
    blob = bucket.blob(LOCK_OBJECT)
    try:
        blob.reload()
    except NotFound:
        return True

    if not blob.time_created:
        return False

    age = datetime.now(timezone.utc) - blob.time_created
    if age.total_seconds() < LOCK_TTL_SECONDS:
        return False

    try:
        blob.delete(if_generation_match=blob.generation)
        LOG.warning(
            "Removed stale watcher lock after %s seconds",
            int(age.total_seconds()),
        )
        return True
    except (NotFound, PreconditionFailed):
        return False


def acquire_watcher_lock(bucket, version):
    for attempt in range(2):
        blob = bucket.blob(LOCK_OBJECT)
        payload = {
            "version": version,
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            blob.upload_from_string(
                json.dumps(payload, ensure_ascii=True),
                content_type="application/json",
                if_generation_match=0,
            )
            blob.reload()
            LOG.info("Acquired watcher lock")
            return blob, blob.generation
        except PreconditionFailed:
            if attempt == 0 and _delete_stale_lock(bucket):
                continue
            return None

    return None


def release_watcher_lock(lock):
    if not lock:
        return

    blob, generation = lock
    try:
        blob.delete(if_generation_match=generation)
        LOG.info("Released watcher lock")
    except NotFound:
        LOG.warning("Watcher lock was already removed")
    except PreconditionFailed:
        LOG.warning("Watcher lock changed before it could be released")


def normalize_sheet_value(value):
    if value is None:
        return ""

    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass

    if isinstance(value, float) and not math.isfinite(value):
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def require_incident_id(value):
    uid = str(normalize_sheet_value(value)).strip()
    if not uid:
        raise ValueError("Incident ID is required")
    return uid


def open_registry_sheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds, _ = google.auth.default(scopes=scope)
    client_gs = gspread.authorize(creds)
    sheet = client_gs.open(GOOGLE_SHEET_NAME).sheet1

    if not sheet.get_all_values():
        sheet.append_row(GOOGLE_SHEET_HEADERS)
    return sheet


def append_registry_row(sheet, data_row, existing_ids=None):
    safe_row = [normalize_sheet_value(value) for value in data_row]
    uid = require_incident_id(safe_row[1] if len(safe_row) > 1 else None)

    if existing_ids is None:
        existing_ids = {str(value).strip() for value in sheet.col_values(2)[1:]}
    if uid and uid in existing_ids:
        LOG.info("Incident is already present in Google Sheets: %s", uid)
        return False

    sheet.append_row(safe_row)
    if uid:
        existing_ids.add(uid)
    return True


def log_to_google_sheet(data_row):
    try:
        sheet = open_registry_sheet()
        append_registry_row(sheet, data_row)
        LOG.info("Incident written to Google Sheets")
        return True
    except Exception as e:
        # The GeoPackage and Mergin Maps are the system of record. The registry is
        # a secondary log, so a registry failure must not cause duplicate emails.
        LOG.exception("Google Sheets registry update failed: %s", e)
        return False


def get_coordinates(row, source_crs):
    try:
        if source_crs != "EPSG:4326":
            geometry = (
                gpd.GeoDataFrame([row], crs=source_crs)
                .to_crs("EPSG:4326")
                .iloc[0]
                .geometry
            )
        else:
            geometry = row.geometry
        return f"{geometry.y:.6f}, {geometry.x:.6f}"
    except Exception:
        LOG.warning("Could not read incident coordinates", exc_info=True)
        return ""


def reconcile_google_sheet(incidents):
    try:
        sheet = open_registry_sheet()
        existing_ids = {str(value).strip() for value in sheet.col_values(2)[1:]}
        processed = incidents[incidents["is_sent"] == 1]
        restored = 0

        for _, row in processed.iterrows():
            uid = normalize_sheet_value(row.get("unique-id"))
            uid = str(uid).strip()
            if not uid or uid in existing_ids:
                continue

            data_row = [
                row.get("processed_at"),
                uid,
                row.get("cadastre_id"),
                row.get("incident_type"),
                get_coordinates(row, incidents.crs),
                row.get("ai_complaint"),
                row.get("ai_complaint_kz"),
                "",
            ]
            if append_registry_row(sheet, data_row, existing_ids):
                restored += 1

        if restored:
            LOG.info("Restored missing Google Sheets rows: %s", restored)
        return True
    except Exception as e:
        LOG.exception("Google Sheets registry reconciliation failed: %s", e)
        return False

def load_knowledge_base():
    full_text = ""
    files = sorted(glob.glob(os.path.join(LAWS_FOLDER, "*.txt")))
    if not files: return "База законов пуста."
    total_chars = 0
    print(f"📚 Читаю законы...", flush=True)
    for f_path in files:
        if total_chars >= MAX_LAW_CHARS: break
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                content = f.read()
                filename_raw = os.path.basename(f_path)
                doc_title = FILE_MAPPING.get(filename_raw, filename_raw)
                if "00_" not in filename_raw and len(content) > 30000:
                    content = content[:30000] + "\n...[СОКР]..."
                
                full_text += f"\n\nИСТОЧНИК: {doc_title}\n" + content
                total_chars += len(content)
        except: pass
    return full_text

def get_legal_prompt(lang, inc_type, desc, cad_id, coords, legal_db):
    if lang == "RU":
        lang_instruction = "ЯЗЫК ОТВЕТА: РУССКИЙ."
        glossary = ""
        subject_hint = "ЗАЯВЛЕНИЕ"
        phrase_cadastral = f"На участке с кадастровым номером {cad_id}"
        phrase_photo = "На предоставленном фотоснимке зафиксировано"
    else:
        lang_instruction = "ЯЗЫК ОТВЕТА: КАЗАХСКИЙ (Қазақ тілі)."
        glossary = """
        ТЕРМИНОЛОГИЯ (ГЛОССАРИЙ) ОБЯЗАТЕЛЬНА К ИСПОЛЬЗОВАНИЮ:
        1. "Земельная инспекция (ДУЗР)" -> "Жер ресурстарын басқару департаменті (Жер инспекциясы)".
        2. "Нецелевое использование" -> "Мақсатсыз пайдалану".
        3. "Признаки нарушения" -> "Бұзушылық белгілері".
        4. "Водоохранная полоса" -> "Су қорғау белдеуі".
        5. "Крутизна склона" -> "Бөктердің тікдігі".
        """
        subject_hint = "ӨТІНІШ (ЗАЯВЛЕНИЕ)"
        phrase_cadastral = f"Кадастрлық нөмірі {cad_id} учаскесінде"
        phrase_photo = "Ұсынылған фотосуретте тіркелген"

    return f"""
    РОЛЬ: Ты Юрист-эколог движения ALMA. Твоя библия — файл "00_guidelines.txt".
    ЗАДАЧА: Проанализировать данные и составить текст обращения, строго следуя СЦЕНАРИЯМ реагирования.
    
    ВВОДНЫЕ ДАННЫЕ:
    - Нарушение: {inc_type}
    - Описание: {desc}
    - ID участка: {cad_id}
    - Координаты: {coords}
    
    БАЗА ЗНАНИЙ (ЗАКОНЫ И РУКОВОДСТВО):
    {legal_db}

    ================================================================
    СТРОГАЯ ИНСТРУКЦИЯ:
    1. {lang_instruction}
    2. КЛАССИФИКАЦИЯ: Сначала определи тип угрозы согласно "00_guidelines.txt":
       - СЦЕНАРИЙ А (Критическая угроза): Сады, склоны, срезка гор, стройка. -> Требуй проверку ДУЗР, ссылайся на Президента и Экокодекс.
       - СЦЕНАРИЙ Б (Локальное): Мусор, шум, листья. -> Жалоба в Акимат/Полицию.
    3. ФОРМАТ ТЕКСТА: Только обычный текст. ЗАПРЕЩЕНО использовать Markdown (никаких звездочек **, решеток #).
    4. ЛОКАЦИЯ: При указании места используй фразу: "{phrase_cadastral}" по координатам {coords}.
    5. ФОТО: Начни анализ с фразы: "{phrase_photo}..." и опиши визуальные факты.
    
    {glossary}
    ================================================================
    СТРУКТУРА ОТВЕТА:
    1. АНАЛИЗ СИТУАЦИИ (Описание фото + Квалификация по Сценарию А или Б).
    2. ПРОЕКТ {subject_hint} (Текст для госоргана, соответствующий выбранному сценарию).
    """

def send_email_with_attachments(to_email, subject, body, attachment_paths):
    sender = get_env('GMAIL_USER')
    password = get_env('GMAIL_APP_PASS')

    msg = MIMEMultipart()
    msg['From'] = sender
    recipients = [sender]
    if to_email and str(to_email).strip().lower() != "nan":
        recipients.append(str(to_email).strip())
    msg['To'] = ", ".join(recipients)
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    for f_path in attachment_paths:
        if f_path and os.path.exists(f_path):
            try:
                with open(f_path, 'rb') as f:
                    img_data = f.read()
                    image = MIMEImage(img_data, name=os.path.basename(f_path))
                    msg.attach(image)
            except: pass

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as s:
            s.login(sender, password)
            s.send_message(msg)
        LOG.info("Email sent: %s", subject)
    except Exception as e:
        raise RuntimeError(f"Email delivery failed for {subject}") from e

def sync_project_safely(mc, project_path):
    """Пытается отправить изменения. Если версия устарела, обновляет и пробует снова."""
    try:
        mc.push_project(project_path)
    except ClientError as e:
        if "There is a new version" in str(e):
            LOG.warning("Mergin Maps project changed. Pulling and retrying push.")
            try:
                mc.pull_project(project_path) # Скачиваем изменения (v93)
                mc.push_project(project_path) # Отправляем наши изменения поверх
                LOG.info("Mergin Maps synchronization restored")
            except Exception as e2:
                raise RuntimeError("Mergin Maps synchronization recovery failed") from e2
        else:
            raise RuntimeError("Mergin Maps push failed") from e

def process_project(mc):
    if os.path.exists(PROJECT_PATH): shutil.rmtree(PROJECT_PATH)
    try:
        mc.download_project(MERGIN_PROJECT, PROJECT_PATH)
    except Exception as e:
        raise RuntimeError(f"Could not download Mergin Maps project {MERGIN_PROJECT}") from e

    try:
        incidents = gpd.read_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE))
        photos_gdf = gpd.read_file(os.path.join(PROJECT_PATH, PHOTOS_FILE))
    except Exception as e:
        raise RuntimeError("Could not read Mergin Maps GeoPackage files") from e

    if 'is_sent' not in incidents.columns: incidents['is_sent'] = 0
    incidents['is_sent'] = incidents['is_sent'].fillna(0).astype(int)
    registry_ok = reconcile_google_sheet(incidents)
    new_recs = incidents[incidents['is_sent'] == 0]
    
    if new_recs.empty: 
        LOG.info("No new incidents")
        return registry_ok

    # Do not spend Gemini quota on scheduled checks that have no new work.
    api_key = get_env('GEMINI_API_KEY')
    client = genai.Client(api_key=api_key)

    LOG.info("Checking Gemini model availability")
    active_model_name = None
    for m in model_candidates():
        try:
            client.models.generate_content(model=m, contents="Ping")
            LOG.info("Gemini model is available: %s", m)
            active_model_name = m
            break
        except Exception as e:
            LOG.warning("Gemini model is unavailable: %s (%s)", m, e)

    if not active_model_name:
        raise RuntimeError("No configured Gemini model is available")

    legal_knowledge = load_knowledge_base()

    garden_files = []
    for f in glob.glob(f"{PROJECT_PATH}/*.gpkg"):
        if os.path.basename(f) not in [INCIDENTS_FILE, PHOTOS_FILE]:
            if any(k in os.path.basename(f).lower() for k in GARDEN_KEYWORDS):
                garden_files.append(f)

    LOG.info("New incidents: %s", len(new_recs))

    for idx, row in new_recs.iterrows():
        uid = require_incident_id(row.get('unique-id'))
        LOG.info("Processing incident: %s", uid)
        
        # --- ФОТО ---
        attachments = []
        incident_photo_dir = os.path.join(ARCHIVE_PATH, "PHOTOS", f"{datetime.now().strftime('%Y-%m-%d')}_{uid}")
        os.makedirs(incident_photo_dir, exist_ok=True)

        rel_photos = photos_gdf[photos_gdf['external_pk'] == uid]
        if not rel_photos.empty:
            for _, p_row in rel_photos.iterrows():
                original = p_row.get('photo')
                if original:
                    possible_paths = [os.path.join(PROJECT_PATH, original), os.path.join(PROJECT_PATH, os.path.basename(original))]
                    src = next((p for p in possible_paths if os.path.exists(p)), None)
                    if src:
                        dst = os.path.join(incident_photo_dir, os.path.basename(src))
                        shutil.copy2(src, dst)
                        attachments.append(dst)

        # --- КООРДИНАТЫ ---
        if incidents.crs != "EPSG:4326":
            p_geo = gpd.GeoDataFrame([row], crs=incidents.crs).to_crs("EPSG:4326").iloc[0].geometry
        else: p_geo = row.geometry
        coords_str = get_coordinates(row, incidents.crs)
        
        # --- ОПРЕДЕЛЕНИЕ КАДАСТРОВОГО НОМЕРА ---
        cad_id = None
        
        # 1. Сначала проверяем поле 'layers' в самом инциденте
        if 'layers' in row:
            val = row.get('layers')
            if val and str(val).strip():
                cad_id = str(val)
        
        # 2. Если не найдено, ищем гео-пересечение с файлами садов
        if not cad_id:
            for g_file in garden_files:
                try:
                    temp_gdf = gpd.read_file(g_file).to_crs("EPSG:4326")
                    matches = temp_gdf[temp_gdf.contains(p_geo)]
                    
                    if not matches.empty:
                        match_row = matches.iloc[0]
                        # УМНЫЙ ПОИСК КОЛОНКИ: ищем что-то похожее на 'layer'
                        found_col = None
                        for col in match_row.index:
                            if 'layer' in col.lower() or 'kadastr' in col.lower() or 'name' in col.lower():
                                found_col = col
                                break
                        
                        if found_col:
                             cad_id = str(match_row[found_col])
                             LOG.info("Cadastre found in %s for incident %s", os.path.basename(g_file), uid)
                        else:
                            cad_id = os.path.splitext(os.path.basename(g_file))[0]
                            LOG.warning("Cadastre field not found in %s", os.path.basename(g_file))
                        break
                except Exception as e: pass
        
        if not cad_id:
            cad_id = "Не указан"

        # --- ГЕНЕРАЦИЯ ---
        responses = {"RU": "", "KZ": ""}

        for lang in ["RU", "KZ"]:
            LOG.info("Generating %s response for incident %s", lang, uid)
            prompt = get_legal_prompt(lang, row.get('incident_type'), row.get('description'), cad_id, coords_str, legal_knowledge)
            
            contents_list = [prompt]
            for img_path in attachments:
                try:
                    img = PIL.Image.open(img_path)
                    contents_list.append(img)
                except: pass

            try:
                resp = client.models.generate_content(
                    model=active_model_name,
                    contents=contents_list,
                    config=types.GenerateContentConfig(temperature=0.0)
                )
                
                clean_text = resp.text.replace("**", "").replace("##", "").replace("--- ДОКУМЕНТ:", "")
                responses[lang] = clean_text
            except Exception as e:
                raise RuntimeError(f"Could not process {lang} response for incident {uid}") from e

        # One bilingual email prevents a partially delivered case if the second
        # language generation or delivery fails.
        email_subject = f"ALMA: {cad_id}"
        email_body = f"РУССКИЙ\n\n{responses['RU']}\n\n{'=' * 72}\n\nҚАЗАҚША\n\n{responses['KZ']}"
        send_email_with_attachments(
            row.get('volunteer_email'), email_subject, email_body, attachments
        )
        time.sleep(2)

        # The primary result is first written back to the source GeoPackage and
        # synchronised to Mergin Maps. This preserves successful work if a later
        # incident fails and causes Cloud Run to retry the job.
        incidents.at[idx, 'cadastre_id'] = cad_id
        incidents.at[idx, 'ai_complaint'] = responses["RU"]
        incidents.at[idx, 'ai_complaint_kz'] = responses["KZ"]
        incidents.at[idx, 'processed_at'] = datetime.now(timezone.utc).isoformat()
        incidents.at[idx, 'is_sent'] = 1

        incidents.to_file(os.path.join(PROJECT_PATH, INCIDENTS_FILE), driver="GPKG")
        sync_project_safely(mc, PROJECT_PATH)

        # --- GOOGLE SHEETS ---
        sheet_row = [
            datetime.now().strftime("%Y-%m-%d %H:%M"),
            uid, 
            cad_id, 
            row.get('incident_type'), 
            coords_str,
            responses["RU"], 
            responses["KZ"], 
            os.path.abspath(incident_photo_dir)
        ]
        registry_ok = log_to_google_sheet(sheet_row) and registry_ok

    LOG.info("ALMA Monitor completed successfully")
    return registry_ok


def main():
    LOG.info("Starting ALMA Monitor watcher")

    try:
        mc = MerginClient("https://app.merginmaps.com", login=get_env('MERGIN_USER'), password=get_env('MERGIN_PASS'))
        LOG.info("Mergin Maps client configured")
    except Exception as e:
        raise RuntimeError("Mergin Maps client configuration failed") from e

    bucket = get_state_bucket()
    current_version = get_project_version(mc)
    last_scanned_version = read_last_scanned_version(bucket)

    if current_version == last_scanned_version:
        LOG.info("Mergin Maps version unchanged: %s", current_version)
        return

    LOG.info(
        "Mergin Maps version changed: %s -> %s",
        last_scanned_version or "not scanned",
        current_version,
    )
    lock = acquire_watcher_lock(bucket, current_version)
    if not lock:
        LOG.info("Another watcher execution is active; this execution will stop")
        return

    try:
        # A second check closes the race between the fast version check and the
        # atomic lock acquisition.
        current_version = get_project_version(mc)
        last_scanned_version = read_last_scanned_version(bucket)
        if current_version == last_scanned_version:
            LOG.info("Mergin Maps version was already scanned: %s", current_version)
            return

        registry_ok = process_project(mc)
        if not registry_ok:
            raise RuntimeError("Google Sheets registry synchronization is incomplete")

        # Record the version that this execution selected for scanning. The
        # worker can create a newer version when it writes results. Keeping the
        # selected version forces one safe follow-up scan, which also catches an
        # incident that was synchronised while this execution was running.
        write_last_scanned_version(bucket, current_version)
    finally:
        release_watcher_lock(lock)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        LOG.exception("ALMA Monitor failed")
        sys.exit(1)
