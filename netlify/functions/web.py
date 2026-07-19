import sys
import os
import json
import logging

# ── Path del proyecto raíz ────────────────────────────────────────────────────
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── App FastAPI (panel web) ───────────────────────────────────────────────────
from web import app
from mangum import Mangum

_mangum_handler = Mangum(app, lifespan="off")

# ── Handler principal de Netlify Functions ────────────────────────────────────
def handler(event, context):
    """
    Entry point para Netlify Functions.

    Rutas:
    - POST /webhook  → procesar update de Telegram (modo Webhook)
    - Todo lo demás  → panel web FastAPI (login, save, health, etc.)
    """
    http_method = event.get("httpMethod", "GET").upper()
    path        = event.get("path", "/")

    logger.info(f"[Function] {http_method} {path}")

    # ── Webhook de Telegram ──────────────────────────────────────────────────
    if http_method == "POST" and path.rstrip("/") in ("/webhook", "/.netlify/functions/web/webhook"):
        try:
            import telebot
            from bot import get_bot

            body        = event.get("body", "{}")
            update_data = json.loads(body) if isinstance(body, str) else body
            logger.info(f"[Webhook] Update ID: {update_data.get('update_id', 'N/A')}")

            update = telebot.types.Update.de_json(update_data)
            get_bot().process_new_updates([update])

            return {
                "statusCode": 200,
                "headers":    {"Content-Type": "application/json"},
                "body":       json.dumps({"ok": True})
            }
        except Exception as e:
            logger.error(f"[Webhook] Error: {e}", exc_info=True)
            # Siempre responder 200 a Telegram para que NO reintente el update
            return {
                "statusCode": 200,
                "headers":    {"Content-Type": "application/json"},
                "body":       json.dumps({"ok": False, "error": str(e)})
            }

    # ── Panel web FastAPI ────────────────────────────────────────────────────
    return _mangum_handler(event, context)
