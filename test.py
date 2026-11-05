import os
import json
import hashlib
import time
import requests

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
# CARGAR Y GUARDAR HISTORIAL
# =========================================================

if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        state = json.load(f)

    if not isinstance(state, dict):
        raise ValueError("El archivo state.json no contiene un historial válido.")

else:
    state = {}


# Compatibilidad con el historial antiguo
if "sent" in state and "frankgamora" not in state:
    state["frankgamora"] = state.pop("sent")


def save_state():
    """Guarda el historial de forma segura e inmediata."""

    temporary_file = STATE_FILE + ".tmp"

    with open(temporary_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

    os.replace(temporary_file, STATE_FILE)


# =========================================================
# OBTENER STORIES DE MEDIAPULLER
# =========================================================

def get_account_html(username):

    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):

        try:
            print(
                f"CONSULTA MEDIAPULLER: "
                f"intento {attempt}/{MAX_ATTEMPTS}"
            )

            # Abrir la página y obtener el token
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

            # Consultar el perfil
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
                raise ValueError("MediaPuller devolvió una respuesta vacía.")

            return response.text

        except Exception as error:

            last_error = error

            print(
                f"ERROR CONSULTANDO @{username}: {error}"
            )

            if attempt < MAX_ATTEMPTS:
                wait_time = attempt * 3
                print(f"Esperando {wait_time} segundos...")
                time.sleep(wait_time)

    raise RuntimeError(
        f"No se pudo consultar @{username}: {last_error}"
    )


# =========================================================
# DETECTAR VÍDEOS
# =========================================================

def find_videos(soup):

    video_urls = set()

    # Sources habituales
    for source in soup.find_all("source", src=True):

        src = source.get("src")

        if src and ".mp4" in src.lower():
            video_urls.add(src)

    # Vídeos con src directo
    for video in soup.find_all("video", src=True):

        src = video.get("src")

        if src and ".mp4" in src.lower():
            video_urls.add(src)

    return list(video_urls)


# =========================================================
# DETECTAR IMÁGENES
# =========================================================

def find_images(soup):

    image_urls = set()

    def valid_instagram_image(url):

        if not url:
            return False

        return (
            "scontent-" in url
            and "/v/t51." in url
        )

    # Enlaces directos a imágenes
    for link in soup.find_all("a", href=True):

        href = link.get("href")

        if valid_instagram_image(href):
            image_urls.add(href)

    # Imágenes incluidas directamente en la página
    for img in soup.find_all("img"):

        # Evitar imágenes que estén dentro de un vídeo
        if img.find_parent("video"):
            continue

        src = img.get("src")

        if valid_instagram_image(src):
            image_urls.add(src)

        # También revisar srcset
        srcset = img.get("srcset", "")

        for item in srcset.split(","):

            candidate = item.strip().split(" ")[0]

            if valid_instagram_image(candidate):
                image_urls.add(candidate)

    return list(image_urls)


# =========================================================
# DESCARGAR CONTENIDO CON REINTENTOS
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
                raise ValueError("El archivo descargado está vacío.")

            return response.content

        except Exception as error:

            last_error = error

            print(
                f"ERROR DESCARGANDO MEDIA "
                f"(intento {attempt}/{MAX_ATTEMPTS}): {error}"
            )

            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt * 2)

    raise RuntimeError(
        f"No se pudo descargar el contenido: {last_error}"
    )


# =========================================================
# ENVIAR A TELEGRAM
# =========================================================

def send_to_telegram(media_data, username, media_type):

    if media_type == "video":

        telegram_method = "sendVideo"

        files = {
            "video": (
                "story.mp4",
                media_data,
                "video/mp4"
            )
        }

        caption = f"🎥 Nueva Story de @{username}"

    else:

        telegram_method = "sendPhoto"

        files = {
            "photo": (
                "story.jpg",
                media_data,
                "image/jpeg"
            )
        }

        caption = f"📸 Nueva Story de @{username}"

    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{telegram_token}/{telegram_method}"
    )

    data = {
        "chat_id": telegram_chat_id,
        "caption": caption
    }

    # No repetir automáticamente los envíos a Telegram:
    # si hay un timeout, no podemos saber con certeza
    # si Telegram recibió ya el archivo.
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
        raise RuntimeError(
            f"Telegram rechazó el envío: {result}"
        )


# =========================================================
# PROCESAR STORIES DE UNA CUENTA
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

    # Consultar MediaPuller
    html = get_account_html(username)

    soup = BeautifulSoup(html, "html.parser")

    # Detectar contenido
    video_urls = find_videos(soup)
    image_urls = find_images(soup)

    print("VÍDEOS ENCONTRADOS:", len(video_urls))
    print("IMÁGENES ENCONTRADAS:", len(image_urls))

    account_new = 0

    # -----------------------------------------------------
    # PROCESAR VÍDEOS
    # -----------------------------------------------------

    for video_url in video_urls:

        try:

            print("DESCARGANDO VÍDEO...")

            media_data = download_media(video_url)

            story_id = hashlib.sha256(
                media_data
            ).hexdigest()

            if story_id in sent_stories:
                print("Vídeo ya enviado. Se ignora.")
                continue

            print(f"NUEVO VÍDEO DE @{username}")

            send_to_telegram(
                media_data,
                username,
                "video"
            )

            sent_stories.append(story_id)

            # Guardar inmediatamente tras el envío
            state[username] = sent_stories[-MAX_HISTORY:]
            sent_stories = state[username]
            save_state()

            total_new += 1
            account_new += 1

            print("VÍDEO ENVIADO Y GUARDADO.")

        except Exception as error:

            print(
                f"ERROR PROCESANDO VÍDEO DE "
                f"@{username}: {error}"
            )

            continue

    # -----------------------------------------------------
    # PROCESAR IMÁGENES
    # -----------------------------------------------------

    for image_url in image_urls:

        try:

            print("DESCARGANDO IMAGEN...")

            media_data = download_media(image_url)

            story_id = hashlib.sha256(
                media_data
            ).hexdigest()

            if story_id in sent_stories:
                print("Imagen ya enviada. Se ignora.")
                continue

            print(f"NUEVA IMAGEN DE @{username}")

            send_to_telegram(
                media_data,
                username,
                "photo"
            )

            sent_stories.append(story_id)

            # Guardar inmediatamente tras el envío
            state[username] = sent_stories[-MAX_HISTORY:]
            sent_stories = state[username]
            save_state()

            total_new += 1
            account_new += 1

            print("IMAGEN ENVIADA Y GUARDADA.")

        except Exception as error:

            print(
                f"ERROR PROCESANDO IMAGEN DE "
                f"@{username}: {error}"
            )

            continue

    # Guardar también aunque no haya contenido nuevo
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

        print("")
        print(f"FALLO EN @{username}: {error}")
        print("Se continúa con la siguiente cuenta.")

        continue


# =========================================================
# RESUMEN FINAL
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
