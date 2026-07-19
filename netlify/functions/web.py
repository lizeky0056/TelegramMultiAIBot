import sys
import os
import json
import logging

# ── Agregar la raíz del proyecto al path ─────────────────────────────────────
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

# ── Imports del proyecto ──────────────────────────────────────────────────────
from web import app            # FastAPI app (panel web de configuración)
from mangum import Mangum      # Adaptador AWS Lambda / Netlify Functions para ASGI

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Webhook handler de Telegram ───────────────────────────────────────────────
# Importamos el bot SOLO para el manejo de updates vía Webhook.
# El bot NO usa infinity_polling() en producción serverless.
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

def _handle_telegram_webhook(event: dict) -> dict:
    """
    Procesa una actualización entrante de Telegram enviada por Webhook.
    Retorna la respuesta HTTP para Netlify Functions.
    """
    try:
        import telebot
        from bot import bot as telegram_bot
        
        body = event.get("body", "")
        if isinstance(body, str):
            update_data = json.loads(body)
        else:
            update_data = body

        logger.info(f"[Webhook] Update recibido: {update_data.get('update_id', 'N/A')}")

        update = telebot.types.Update.de_json(update_data)
        telegram_bot.process_new_updates([update])

        return {
            "statusCode": 200,
            "body": json.dumps({"ok": True}),
            "headers": {"Content-Type": "application/json"}
        }
    except Exception as e:
        logger.error(f"[Webhook] Error procesando update: {e}", exc_info=True)
        return {
            "statusCode": 200,  # Siempre 200 a Telegram para que no reintente
            "body": json.dumps({"ok": False, "error": str(e)}),
            "headers": {"Content-Type": "application/json"}
        }


def handler(event, context):
    """
    Entry point para Netlify Functions.
    - Si es un POST a /webhook → procesar update de Telegram
    - Todo lo demás → delegar a la app FastAPI (panel web)
    """
    http_method = event.get("httpMethod", "GET").upper()
    path = event.get("path", "/")

    # Webhook de Telegram: POST a la ruta /webhook
    if http_method == "POST" and "/webhook" in path:
        return _handle_telegram_webhook(event)

    # Todo lo demás: panel web FastAPI (login, save, health, etc.)
    asgi_handler = Mangum(app, lifespan="off")
    return asgi_handler(event, context)
