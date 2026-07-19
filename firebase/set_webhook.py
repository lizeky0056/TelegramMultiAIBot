import urllib.request
import urllib.parse
import os
from dotenv import load_dotenv

# Attempt to load token from .env
if os.path.exists("../.env"):
    load_dotenv("../.env")
else:
    load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8886104559:AAHclO0tYWadm4eMMrPB1C3PjQI6uqOps4U")

print("🤖 Registro de Webhook para Boty Generator Cloud")
print("================================================")
print(f"Token de Bot detectado: {BOT_TOKEN[:15]}...")

func_url = input("Ingresa la URL de tu Firebase Cloud Function (ej. https://us-central1-tikreader-e4c39.cloudfunctions.net/boty_generator): ").strip()
if not func_url:
    print("URL inválida.")
    exit()

# Append /webhook if not present
webhook_url = func_url if func_url.endswith("/webhook") else f"{func_url}/webhook"

print(f"\nEstableciendo Webhook de Telegram a:\n👉 {webhook_url}\n")

try:
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={urllib.parse.quote(webhook_url)}"
    req = urllib.request.Request(api_url)
    with urllib.request.urlopen(req, timeout=10) as response:
        result = response.read().decode('utf-8')
        print("Respuesta de Telegram:")
        print(result)
except Exception as e:
    print(f"❌ Error al conectar con el API de Telegram: {e}")
