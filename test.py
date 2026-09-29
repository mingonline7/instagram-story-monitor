import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

username = "frankgamora"

url = "https://mediapuller.com/es/instagram-story-viewer"

session = requests.Session()

# 1. Obtener la página y el token
response = session.get(url, timeout=30)

print("GET STATUS:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

token = soup.find(
    "input",
    {"name": "__RequestVerificationToken"}
)

if not token:
    print("NO SE ENCONTRO EL TOKEN")
    exit()

token_value = token.get("value")

# 2. Realizar la búsqueda
data = {
    "Url": username,
    "__RequestVerificationToken": token_value
}

response = session.post(
    url,
    data=data,
    timeout=30
)

print("POST STATUS:", response.status_code)
print("URL FINAL:", response.url)

soup = BeautifulSoup(response.text, "html.parser")

print("\n--- IMAGENES ENCONTRADAS ---")

for img in soup.find_all("img"):
    src = img.get("src")
    data_src = img.get("data-src")

    if src:
        print("IMG:", urljoin(response.url, src))

    if data_src:
        print("DATA-SRC:", urljoin(response.url, data_src))


print("\n--- VIDEOS ENCONTRADOS ---")

for video in soup.find_all("video"):
    print("VIDEO:", urljoin(response.url, video.get("src", "")))

    for source in video.find_all("source"):
        src = source.get("src")
        if src:
            print("SOURCE:", urljoin(response.url, src))


print("\n--- ENLACES A ARCHIVOS ---")

for link in soup.find_all("a", href=True):
    href = link.get("href")

    if any(ext in href.lower() for ext in [
        ".jpg", ".jpeg", ".png", ".webp",
        ".mp4", ".mov", ".m3u8"
    ]):
        print("ARCHIVO:", urljoin(response.url, href))

print("\n--- RESULTADO ---")
print(text[:5000])
