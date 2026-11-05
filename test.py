import os
import json
import time
import re
import hashlib
import requests

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# =========================================================
# CONFIGURACIÓN
# =========================================================

usernames = [
    "frankgamora",
    "omarcs88",
    "wesliph",
    "alex.facchi",
    "angel11ump",
    "victorleon4",
    "alexjimenezdrums",
    "sooyaaa__",
]

mediapuller_url = "https://mediapuller.com/es/instagram-story-viewer"

telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"
MAX_HISTORY = 500
MAX_ATTEMPTS = 3

CANARIAS = ZoneInfo("Atlantic/Canary")


# =========================================================
# SESIÓN CON REINTENTOS
# =========================================================

session = requests.Session()

retry_config = Retry(
    total=3,
    connect=3,
    read=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST"]),
    respect_retry_after_header=True,
)

adapter = HTTPAdapter(max_retries=retry_config)

session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    )
})


# =========================================================
# HISTORIAL
# =========================================================

if os.path.exists(STATE_FILE):

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if not isinstance(state, dict):
        raise ValueError("state.json no contiene un historial válido.")

else:
    state = {}


# Compatibilidad con el historial antiguo
if "sent" in state and "frankgamora" not in state:
    state["frankgamora"] = state.pop("sent")


def save_state():

    temporary_file = STATE_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    os.replace(temporary_file, STATE_FILE)


# =========================================================
# CONVERTIR ANTIGÜEDAD EN FECHA Y HORA
# =========================================================

def get_publication_time(text):

    if not text:
        return None

    text = text.lower()

    units = {
        "segundo": 1,
        "minuto": 60,
        "hora": 3600,
        "día": 86400,
        "dia": 86400,
        "semana": 604800,
        "mes": 2592000,
        "año": 31536000,
        "ano": 31536000,
    }

    matches = re.findall(
        r"(\d+)\s*(segundos?|minutos?|horas?|días?|dias?|semanas?|meses?|años?|anos?)",
        text
    )

    if not matches:
        return None

    total_seconds = 0

    for number, unit in matches:

        unit = unit.rstrip("s")

        for key, seconds in units.items():

            if unit == key:
                total_seconds += int(number) * seconds
                break

    if total_seconds == 0:
        return None

    publication = (
        datetime.now(CANARIAS)
        - timedelta(seconds=total_seconds)
    )

    return publication.strftime("%H:%M · %d/%m/%Y")


# =========================================================
# CONSULTAR MEDIAPULLER
# =========================================================

def get_account_html(username):

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        try:

            print(
                f"CONSULTA MEDIAPULLER: "
                f"intento {attempt}/{MAX_ATTEMPTS}"
            )

            response = session.get(
                mediapuller_url,
                timeout=(15, 40)
            )

            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            token = soup.find(
                "input",
                {"name": "__RequestVerificationToken"}
            )

            if not token or not token.get("value"):
                raise ValueError("No se encontró el token de seguridad.")

            data = {
                "Url": username,
                "__RequestVerificationToken": token.get("value")
            }

            response = session.post(
                mediapuller_url,
                data=data,
                timeout=(15, 60)
            )

            response.raise_for_status()

            if not response.text.strip():
                raise ValueError("Respuesta vacía de MediaPuller.")

            return response.text

        except Exception as error:

            last_error = error

            print(f"ERROR CONSULTANDO @{username}: {error}")

            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 3)

    raise RuntimeError(
        f"No se pudo consultar @{username}: {last_error}"
    )


# =========================================================
# EXTRAER STORIES Y SUS FECHAS
# =========================================================

def extract_stories(soup):

    stories = []

    # Cada tarjeta contiene su propio archivo y su publicación
    cards = soup.select(".thumbnail.storyViewerItem")

    print("TARJETAS DE STORIES ENCONTRADAS:", len(cards))

    for card in cards:

        media = card.select_one(".storyViewerMedia")

        published_element = card.select_one(
            ".storyViewerPublishedDate"
        )

        published_text = (
            published_element.get_text(" ", strip=True)
            if published_element else None
        )

        publication_time = get_publication_time(
            published_text
        )

        if media:

            media_tag = media.name.lower()

            if media_tag == "video":

                source = media.find("source", src=True)

                if source:
                    media_url = source.get("src")
                else:
                    media_url = media.get("src")

                media_type = "video"

            else:

                download_link = card.select_one(
                    ".storyViewerMediaOpen[href]"
                )

                if download_link:
                    media_url = download_link.get("href")
                else:
                    media_url = media.get("src")

                media_type = "photo"

        else:

            source = card.find("source", src=True)

            download_link = card.select_one(
                ".storyViewerMediaOpen[href]"
            )

            if source:
                media_url = source.get("src")
                media_type = "video"

            elif download_link:
                media_url = download_link.get("href")

                media_type = (
                    "video"
                    if ".mp4" in media_url.lower()
                    else "photo"
                )

            else:
                continue

        if not media_url:
            continue

        if ".mp4" in media_url.lower():
            media_type = "video"

        stories.append({
            "url": media_url,
            "type": media_type,
            "publication": publication_time,
            "published_text": published_text
        })

    # Compatibilidad si MediaPuller cambia su estructura
    if not cards:

        print(
            "AVISO: No se encontraron tarjetas individuales. "
            "Se utiliza el detector anterior."
        )

        for source in soup.find_all("source", src=True):

            url = source.get("src")

            if url and ".mp4" in url.lower():

                stories.append({
                    "url": url,
                    "type": "video",
                    "publication": None,
                    "published_text": None
                })

        for link in soup.find_all("a", href=True):

            url = link.get("href")

            if (
                url
                and "scontent-" in url
                and "/v/t51." in url
            ):

                stories.append({
                    "url": url,
                    "type": "photo",
                    "publication": None,
                    "published_text": None
                })

    # Evitar repetir enlaces dentro de la misma consulta
    unique_stories = []
    seen = set()

    for story in stories:

        if story["url"] not in seen:
            seen.add(story["url"])
            unique_stories.append(story)

    return unique_stories


# =========================================================
# DESCARGAR MEDIA CON REINTENTOS
# =========================================================

def download_media(url):

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        try:

            response = session.get(
                url,
                timeout=(15, 90)
            )

            response.raise_for_status()

            if not response.content:
                raise ValueError("Archivo vacío.")

            return response.content

        except Exception as error:

            last_error = error

            print(
                f"ERROR DESCARGANDO MEDIA "
                f"({attempt}/{MAX_ATTEMPTS}): {error}"
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"No se pudo descargar el archivo: {last_error}"
    )


# =========================================================
# ENVIAR A TELEGRAM
# =========================================================

def send_to_telegram(media_data, username, media_type, publication):

    if media_type == "video":

        method = "sendVideo"

        files = {
            "video": (
                "story.mp4",
                media_data,
                "video/mp4"
            )
        }

        title = "🎥 Nueva Story"

    else:

        method = "sendPhoto"

        files = {
            "photo": (
                "story.jpg",
                media_data,
                "image/jpeg"
            )
        }

        title = "📸 Nueva Story"

    if publication:

        date_line = f"🕒 {publication} (Canarias)"

    else:

        date_line = "🕒 Hora de publicación no disponible"

    caption = (
        f"{title}\n\n"
        f"#{username}\n\n"
        f"{date_line}"
    )

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{telegram_token}/{method}"
    )

    data = {
        "chat_id": telegram_chat_id,
        "caption": caption
    }

    response = requests.post(
        telegram_url,
        data=data,
        files=files,
        timeout=120
    )

    print(
        f"TELEGRAM {media_type.upper()} STATUS: "
        f"{response.status_code}"
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram rechazó el envío: {result}")


# =========================================================
# PROCESAR CUENTA
# =========================================================

def process_account(username):

    global total_new

    print("")
    print("=" * 55)
    print(f"COMPROBANDO @{username}")
    print("=" * 55)

    sent_stories = state.get(username, [])

    if not isinstance(sent_stories, list):
        sent_stories = []

    html = get_account_html(username)

    soup = BeautifulSoup(html, "html.parser")

    stories = extract_stories(soup)

    print("TOTAL DE STORIES DETECTADAS:", len(stories))

    account_new = 0

    for story in stories:

        try:

            print("")
            print("TIPO:", story["type"])
            print("PUBLICACIÓN:", story["published_text"])

            print("DESCARGANDO MEDIA...")

            media_data = download_media(story["url"])

            story_id = hashlib.sha256(
                media_data
            ).hexdigest()

            if story_id in sent_stories:

                print("Story ya enviada. Se ignora.")
                continue

            print(f"NUEVA STORY DE @{username}")

            send_to_telegram(
                media_data,
                username,
                story["type"],
                story["publication"]
            )

            sent_stories.append(story_id)

            state[username] = sent_stories[-MAX_HISTORY:]
            sent_stories = state[username]

            save_state()

            total_new += 1
            account_new += 1

            print("STORY ENVIADA Y GUARDADA.")

        except Exception as error:

            print(
                f"ERROR PROCESANDO STORY DE "
                f"@{username}: {error}"
            )

            continue

    state[username] = sent_stories[-MAX_HISTORY:]
    save_state()

    print(
        f"RESULTADO @{username}: "
        f"{account_new} nuevas Stories enviadas."
    )


# =========================================================
# EJECUCIÓN GENERAL
# =========================================================

total_new = 0
failed_accounts = []

print("")
print("=" * 55)
print("INICIANDO MONITOR DE INSTAGRAM")
print("=" * 55)

for username in usernames:

    try:

        process_account(username)

    except Exception as error:

        failed_accounts.append(username)

        print(f"FALLO EN @{username}: {error}")
        print("Se continúa con la siguiente cuenta.")


# =========================================================
# RESUMEN
# =========================================================

print("")
print("=" * 55)
print("RESUMEN FINAL")
print("=" * 55)

print("TOTAL DE STORIES NUEVAS ENVIADAS:", total_new)

if failed_accounts:

    print("CUENTAS CON ERRORES:")

    for username in failed_accounts:
        print("-", username)

else:

    print("TODAS LAS CUENTAS SE HAN PROCESADO CORRECTAMENTE.")

print("=" * 55)
