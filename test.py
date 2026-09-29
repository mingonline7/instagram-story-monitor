import requests
from bs4 import BeautifulSoup

url = "https://mediapuller.com/es/instagram-story-viewer"

response = requests.get(url, timeout=30)

print("STATUS:", response.status_code)
print("URL FINAL:", response.url)

soup = BeautifulSoup(response.text, "html.parser")

print("\n--- FORMULARIOS ENCONTRADOS ---")

for form in soup.find_all("form"):
    print("FORM ACTION:", form.get("action"))
    print("FORM METHOD:", form.get("method"))

    for inp in form.find_all(["input", "button"]):
        print(
            "ELEMENTO:",
            inp.name,
            "name=", inp.get("name"),
            "type=", inp.get("type"),
            "value=", inp.get("value")
        )

print("\n--- ENLACES RELACIONADOS ---")

for link in soup.find_all("a", href=True):
    text = link.get_text(" ", strip=True)
    href = link.get("href")

    if "story" in text.lower() or "story" in href.lower():
        print(text, "=>", href)
