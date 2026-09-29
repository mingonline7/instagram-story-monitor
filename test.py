import requests

url = "https://mediapuller.com/es/instagram-story-viewer"

r = requests.get(url, timeout=20)

print("Status:", r.status_code)
print("URL:", r.url)
print("Tamaño:", len(r.text))
print(r.text[:500])
