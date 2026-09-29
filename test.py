import os
import requests
from bs4 import BeautifulSoup

username = "frankgamora"

media_puller_url = "https://mediapuller.com/es/instagram-story-viewer"

telegram_token = os.environ["TELEGRAM_BOT_TOKEN"]
telegram_chat_id = os.environ["TELEGRAM_CHAT_ID"]

session = requests.Session()

# 1. Abrimos MediaPuller para obtener el token de seguridad
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

# 2. Buscamos el perfil
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

# 3. Buscar enlaces directos a imágenes de Instagram
story_urls = []

for link in soup.find_all("a", href=True):
    href = link.get("href")

    if "scontent-" in href and "/v/t51." in href:
        if href not in story_urls:
            story_urls.append(href)

print("IMAGENES DE INSTAGRAM ENCONTRADAS:", len(story_urls))

if not story_urls:
    print("NO SE ENCONTRO NINGUNA STORY")
    exit()

# Usamos la primera imagen encontrada
story_url = story_urls[0]

print("DESCARGANDO STORY...")

image_response = session.get(
    story_url,
    timeout=30
)

print("IMAGEN STATUS:", image_response.status_code)
print("TAMAÑO:", len(image_response.content))

if image_response.status_code != 200:
    print("NO SE PUDO DESCARGAR LA IMAGEN")
    exit()

# 4. Enviar la imagen a Telegram
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
print("TELEGRAM RESPUESTA:", telegram_response.text[:500])
