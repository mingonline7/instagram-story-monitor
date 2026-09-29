import requests
from bs4 import BeautifulSoup

username = "hilaguneta"

url = "https://mediapuller.com/es/instagram-story-viewer"

session = requests.Session()

response = session.get(url, timeout=30)

print("GET STATUS:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

token = soup.find(
    "input",
    {"name": "__RequestVerificationToken"}
)

data = {
    "Url": username,
    "__RequestVerificationToken": token.get("value")
}

response = session.post(
    url,
    data=data,
    timeout=30
)

print("POST STATUS:", response.status_code)

soup = BeautifulSoup(response.text, "html.parser")

print("")
print("===== VIDEOS =====")

videos = soup.find_all("video")

print("VIDEOS ENCONTRADOS:", len(videos))

for video in videos:
    print("VIDEO:", video)

print("")
print("===== SOURCES =====")

sources = soup.find_all("source")

print("SOURCES ENCONTRADAS:", len(sources))

for source in sources:
    print("SOURCE:", source)

print("")
print("===== ENLACES MP4 =====")

for link in soup.find_all("a", href=True):
    href = link.get("href")

    if ".mp4" in href or "video" in href.lower():
        print("VIDEO LINK:", href)
