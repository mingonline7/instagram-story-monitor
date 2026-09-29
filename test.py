import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup

usernames = [
    "frankgamora",
    "omarcs88",
    "wesliph",
    "alex.facchi",
    "angel11ump",
    "victorleon4"
    "hilaguneta",
]

media_puller_url = "https://mediapuller.com/es/instagram-story-viewer"

telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"

session = requests.Session()

# Cargar historial
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {}

# Compatibilidad con el historial antiguo de frankgamora
if "sent" in state and "frankgamora" not in state:
    state["frankgamora"] = state.pop("sent")

total_new = 0

for username in usernames:

    print("")
    print("=" * 50)
    print(f"COMPROBANDO @{username}")
    print("=" * 50)

    sent_stories = state.get(username, [])

    # 1. Abrir MediaPuller
    response = session.get(
        media_puller_url,
        timeout=30
    )

    print("GET STATUS:", response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")

    token = soup.find(
        "input",
        {"name": "__RequestVerificationToken"}
    )

    if not token:
        print("NO SE ENCONTRO EL TOKEN")
        continue

    # 2. Buscar perfil
    data = {
        "Url": username,
        "__RequestVerificationToken": token.get("value")
    }

    response = session.post(
        media_puller_url,
        data=data,
        timeout=30
    )

    print("POST STATUS:", response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")

    # 3. Buscar imágenes de Stories
    story_urls = []

    for link in soup.find_all("a", href=True):
        href = link.get("href")

        if "scontent-" in href and "/v/t51." in href:
            if href not in story_urls:
                story_urls.append(href)

    print("IMAGENES ENCONTRADAS:", len(story_urls))

    if not story_urls:
        print("NO HAY STORIES ACTIVAS")
        state[username] = sent_stories
        continue

    new_stories = 0

    # 4. Comprobar cada Story
    for story_url in story_urls:

        image_response = session.get(
            story_url,
            timeout=30
        )

        print("IMAGEN STATUS:", image_response.status_code)

        if image_response.status_code != 200:
            continue

        image_data = image_response.content

        # Identificador basado en el contenido de la imagen
        story_id = hashlib.sha256(image_data).hexdigest()

        if story_id in sent_stories:
            print("Story ya enviada, se ignora.")
            continue

        print(f"NUEVA STORY DE @{username}")

        # 5. Enviar a Telegram
        telegram_url = (
            f"https://api.telegram.org/bot"
            f"{telegram_token}/sendPhoto"
        )

        files = {
            "photo": (
                "story.jpg",
                image_data,
                "image/jpeg"
            )
        }

        data = {
            "chat_id": telegram_chat_id,
            "caption": f"📸 Nueva Story de @{username}"
        }

        telegram_response = requests.post(
            telegram_url,
            data=data,
            files=files,
            timeout=60
        )

        print("TELEGRAM STATUS:", telegram_response.status_code)

        if telegram_response.status_code == 200:
            sent_stories.append(story_id)
            new_stories += 1
            total_new += 1

    # Guardar historial de esta cuenta
    state[username] = sent_stories[-100:]

    print(f"NUEVAS STORIES DE @{username}:", new_stories)

# Guardar todo el historial
with open(STATE_FILE, "w") as f:
    json.dump(state, f, indent=2)

print("")
print("=" * 50)
print("TOTAL DE STORIES NUEVAS ENVIADAS:", total_new)
print("=" * 50)
