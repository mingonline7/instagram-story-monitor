import requests
from bs4 import BeautifulSoup

username = "frankgamora"

url = "https://mediapuller.com/es/instagram-story-viewer"

session = requests.Session()

# 1. Abrimos la página para obtener el token de seguridad
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

print("TOKEN ENCONTRADO")

# 2. Enviamos el usuario al formulario
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
print("TAMAÑO:", len(response.text))

# 3. Analizamos la respuesta
soup = BeautifulSoup(response.text, "html.parser")

text = soup.get_text(" ", strip=True)

print("\n--- RESULTADO ---")
print(text[:5000])
