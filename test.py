import os
import json
import hashlib
import requests
from bs4 import BeautifulSoup

username = "frankgamora"

media_puller_url = "https://mediapuller.com/es/instagram-story-viewer"

telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

STATE_FILE = "state.json"

session = requests.Session()

# 1. Cargar Stories que ya hemos enviado
if os.path.exists(STATE_FILE):
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
else:
    state = {"sent": []}

sent_stories = state.get("sent", [])

# 2. Abrir MediaPuller
response = session.get(media_puller_url, timeout=30)

print("GET STATUS:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

token = soup.find(
    "input",
    {"name": "__RequestVerificationToken"}
)

if not token:
    print("NO SE ENCONTRO EL TOKEN DE MEDIAPULLER")
    exit()

token_value = token.get("value")

# 3. Buscar el perfil
data = {
    "Url": username,
    "__RequestVerificationToken": token_value
}

response = session.post(
    media_puller_url,
    data=data,
    timeout=30
)

print("POST STATUS:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

# 4. Buscar imágenes de Stories
story_urls = []

for link in soup.find_all("a", href=True):
    href = link.get("href")

    if "scontent-" in href and "/v/t51." in href:
        if href not in story_urls:
            story_urls.append(href)

print("IMAGENES ENCONTRADAS:", len(story_urls))

if not story_urls:
    print("NO SE ENCONTRARON STORIES")
    exit()

# 5. Revisar cada Story
new_stories = 0

for story_url in story_urls:

    # Creamos una identificación de la Story
    story_id = hashlib.sha256(
        story_url.encode()
    ).hexdigest()

    if story_id in sent_stories:
        print("Story ya enviada, se ignora.")
        continue

    print("NUEVA STORY ENCONTRADA")

    # Descargar imagen
    image_response = session.get(
        story_url,
        timeout=30
    )

    print("IMAGEN STATUS:", image_response.status_code)

    if image_response.status_code != 200:
        print("NO SE PUDO DESCARGAR")
        continue

    # Enviar a Telegram
    telegram_url = (
        f"https://api.telegram.org/bot"
        f"{telegram_token}/sendPhoto"
    )

    files = {
        "photo": (
            "story.jpg",
            image_response.content,
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

# 6. Guardar las Stories enviadas
state["sent"] = sent_stories[-100:]

with open(STATE_FILE, "w") as f:
    json.dump(state, f)

print("NUEVAS STORIES ENVIADAS:", new_stories)
