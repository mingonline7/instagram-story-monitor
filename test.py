import requests
from bs4 import BeautifulSoup

username = "frankgamora"

url = "https://mediapuller.com/es/instagram-story-viewer"

response = requests.get(url, timeout=30)

print("Status:", response.status_code)
print("Tamaño:", len(response.text))

soup = BeautifulSoup(response.text, "html.parser")

text = soup.get_text(" ", strip=True)

if username.lower() in text.lower():
    print("USUARIO ENCONTRADO")
else:
    print("USUARIO NO ENCONTRADO")

print(text[:3000])
