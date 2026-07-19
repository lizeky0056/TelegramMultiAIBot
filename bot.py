"""
bot.py — Motor del Telegram Bot de Boty Generator.

Diseñado para funcionar en DOS modos:
  1. POLLING (local / Render): python run.py  → bot.infinity_polling()
  2. WEBHOOK (Netlify serverless): La función web.py importa `get_bot()` y llama
     a  bot.process_new_updates([update])  por cada petición POST de Telegram.
"""

from __future__ import annotations
import os
import re
import uuid
import logging
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import config
import ai
import downloader

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEB_URL   = os.getenv("WEB_URL", "https://botychat1.netlify.app")

# ── Estado global compartido ──────────────────────────────────────────────────
pending_downloads: dict[str, str] = {}   # {short_id: url}
waiting_for_key:   dict[int, str] = {}   # {user_id: provider}

PROVIDER_LABELS = {
    "gemini":    "🌟 Google Gemini",
    "openai":    "🧠 ChatGPT (OpenAI)",
    "anthropic": "🎭 Claude (Anthropic)",
    "grok":      "⚡ Grok (xAI)",
}

MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
    "facebook.com", "twitter.com", "x.com", "vimeo.com",
    "kwai.com", "pinterest.com", "twitch.tv", "dailymotion.com",
    "reddit.com", "soundcloud.com", "bilibili.com",
]
URL_PATTERN = re.compile(r"https?://[^\s]+")


# ═════════════════════════════════════════════════════════════════════════════
# Helpers de UI
# ═════════════════════════════════════════════════════════════════════════════

def get_main_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔌 Cambiar Proveedor",  callback_data="select_provider"),
        InlineKeyboardButton("🤖 Cambiar Modelo",     callback_data="select_model"),
        InlineKeyboardButton("📊 Ver Estado / Keys",  callback_data="show_status"),
        InlineKeyboardButton("🧹 Limpiar Chat",       callback_data="clear_hist"),
        InlineKeyboardButton("🌐 Panel Web",           callback_data="web_login"),
        InlineKeyboardButton("❓ Ayuda",               callback_data="show_help"),
    )
    return markup

def get_status_text(user_id) -> str:
    cfg   = config.get_user_config(user_id)
    prov  = cfg.get("current_provider", "gemini")
    model = cfg.get("selected_models", {}).get(prov, "default")
    keys  = cfg.get("api_keys", {})
    lines = [
        "📊 *Estado de tu Configuración*\n",
        f"🔌 *Proveedor Activo*: {PROVIDER_LABELS.get(prov, prov.upper())}",
        f"🤖 *Modelo Activo*: `{model}`\n",
        "🔑 *API Keys Registradas*:",
    ]
    for p in ["gemini", "openai", "anthropic", "grok"]:
        k = keys.get(p, "")
        if k:
            masked = f"`{k[:6]}...{k[-4:]}`" if len(k) > 10 else "`Configurada ✓`"
            lines.append(f"  ✅ {PROVIDER_LABELS.get(p, p.upper())}: {masked}")
        else:
            lines.append(f"  ❌ {PROVIDER_LABELS.get(p, p.upper())}: _Sin registrar_")
    return "\n".join(lines)

def _build_provider_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(PROVIDER_LABELS["gemini"],    callback_data="set_prov_gemini"),
        InlineKeyboardButton(PROVIDER_LABELS["openai"],    callback_data="set_prov_openai"),
        InlineKeyboardButton(PROVIDER_LABELS["anthropic"], callback_data="set_prov_anthropic"),
        InlineKeyboardButton(PROVIDER_LABELS["grok"],      callback_data="set_prov_grok"),
    )
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    return markup

def _build_model_markup(provider: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for m in ai.MODELS.get(provider, []):
        markup.add(InlineKeyboardButton(m, callback_data=f"set_model_{m}"))
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    return markup

def _help_text() -> str:
    return (
        "😈 *Comandos de Boty Generator* 🤖\n\n"
        "• `/start` — Menú principal interactivo\n"
        "• `/login` — Genera enlace al Panel Web\n"
        "• `/provider` — Cambia el proveedor de IA\n"
        "• `/model` — Cambia el modelo activo\n"
        "• `/status` — Muestra tu configuración\n"
        "• `/clear` — Limpia el historial\n"
        "• `/help` — Este mensaje\n\n"
        "📥 *Descarga de videos:*\n"
        "Envía un enlace de TikTok, YouTube, Instagram, Facebook, "
        "Twitter/X, Kwai, Pinterest, Vimeo, Reddit, SoundCloud o Twitch.\n\n"
        "💬 *Chat con IA:*\n"
        "Escríbeme cualquier cosa y te responderé con el proveedor y modelo activo."
    )


# ═════════════════════════════════════════════════════════════════════════════
# Descarga de medios (hilo separado)
# ═════════════════════════════════════════════════════════════════════════════

def _safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

def _process_download_thread(b: telebot.TeleBot, user_id: int,
                              message_id: int, url: str,
                              dtype: str, short_id: str):
    try:
        filepath, title, err = downloader.download_media(url, dtype)
        if err or not filepath or not os.path.exists(filepath):
            b.edit_message_text(
                chat_id=user_id, message_id=message_id,
                text=f"❌ *Error al descargar:*\n`{err or 'Archivo no encontrado.'}`",
            )
            return

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > 49.9:
            b.edit_message_text(
                chat_id=user_id, message_id=message_id,
                text=f"⚠️ *Archivo demasiado grande ({size_mb:.1f} MB)*\n\nTelegram limita los bots a 50 MB. Intenta descargar en MP3.",
            )
            _safe_remove(filepath)
            return

        b.edit_message_text(
            chat_id=user_id, message_id=message_id,
            text=f"📤 *Descarga lista:* `{title}` ({size_mb:.1f} MB)\nEnviando archivo a Telegram...",
        )
        with open(filepath, "rb") as f:
            if dtype == "mp3":
                b.send_audio(user_id, f, title=title,
                             caption=f"🎵 *{title}*\n_Descargado con 😈 Boty Generator_")
            else:
                b.send_video(user_id, f,
                             caption=f"🎥 *{title}*\n_Descargado con 😈 Boty Generator_")
        try:
            b.delete_message(user_id, message_id)
        except Exception:
            pass
        _safe_remove(filepath)
        pending_downloads.pop(short_id, None)
    except Exception as e:
        logger.error(f"[Downloader] Error inesperado: {e}")
        try:
            b.send_message(user_id, f"❌ *Error inesperado enviando el archivo:*\n`{e}`")
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════════
# Registro de handlers (separado de la inicialización del bot)
# ═════════════════════════════════════════════════════════════════════════════

def _register_handlers(b: telebot.TeleBot):
    """Registra todos los handlers en la instancia del bot recibida."""

    def safe_edit(call, text: str, markup=None):
        try:
            b.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text, parse_mode="Markdown", reply_markup=markup
            )
        except telebot.apihelper.ApiTelegramException as e:
            if "message is not modified" not in str(e):
                logger.warning(f"safe_edit: {e}")

    # ── /start /menu ────────────────────────────────────────────────────────
    @b.message_handler(commands=["start", "menu"])
    def send_welcome(message):
        user_id = message.from_user.id
        first_name = message.from_user.first_name or "usuario"
        waiting_for_key.pop(user_id, None)
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        b.send_message(
            user_id,
            f"😈 *¡Hola, {first_name}! Soy Boty Generator* 🤖🔥\n\n"
            f"Conectado a: {' · '.join(PROVIDER_LABELS.values())}\n\n"
            f"📥 *Descargador de Videos:* Envíame cualquier enlace de TikTok, YouTube, "
            f"Instagram, Facebook, Twitter/X y más.\n\n"
            f"🔑 [Configurar API Keys en el Panel Web]({url})",
            reply_markup=get_main_keyboard()
        )

    # ── /login /web ─────────────────────────────────────────────────────────
    @b.message_handler(commands=["login", "web"])
    def send_login_link(message):
        user_id = message.from_user.id
        waiting_for_key.pop(user_id, None)
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        b.send_message(user_id,
            f"🌐 *Panel Web de Configuración*\n\n"
            f"👉 [Haz clic aquí para abrir tu panel]({url})\n\n"
            f"⚠️ Expira en *30 minutos*.",
            reply_markup=markup)

    # ── /provider ───────────────────────────────────────────────────────────
    @b.message_handler(commands=["provider"])
    def command_provider(message):
        waiting_for_key.pop(message.from_user.id, None)
        b.send_message(message.from_user.id, "🔌 *Selecciona el Proveedor de IA:*",
                       reply_markup=_build_provider_markup())

    # ── /model ──────────────────────────────────────────────────────────────
    @b.message_handler(commands=["model"])
    def command_model(message):
        user_id = message.from_user.id
        waiting_for_key.pop(user_id, None)
        cfg  = config.get_user_config(user_id)
        prov = cfg.get("current_provider", "gemini")
        b.send_message(user_id,
            f"🤖 *Selecciona el modelo para {PROVIDER_LABELS.get(prov, prov.upper())}:*",
            reply_markup=_build_model_markup(prov))

    # ── /status ─────────────────────────────────────────────────────────────
    @b.message_handler(commands=["status"])
    def command_status(message):
        user_id = message.from_user.id
        waiting_for_key.pop(user_id, None)
        token = config.generate_login_token(user_id)
        url   = f"{WEB_URL}/login?token={token}"
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
            InlineKeyboardButton("🌐 Panel Web",           callback_data="web_login"),
            InlineKeyboardButton("⬅️ Menú Principal",     callback_data="show_main_menu"),
        )
        b.send_message(user_id, get_status_text(user_id) + f"\n\n🔗 [Abrir Panel Web]({url})",
                       reply_markup=markup)

    # ── /clear ──────────────────────────────────────────────────────────────
    @b.message_handler(commands=["clear"])
    def command_clear(message):
        user_id = message.from_user.id
        waiting_for_key.pop(user_id, None)
        ai.clear_history(user_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        b.send_message(user_id, "🧹 *Historial borrado con éxito.*", reply_markup=markup)

    # ── /help ───────────────────────────────────────────────────────────────
    @b.message_handler(commands=["help"])
    def command_help(message):
        user_id = message.from_user.id
        waiting_for_key.pop(user_id, None)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        b.send_message(user_id, _help_text(), reply_markup=markup)

    # ── Callbacks ───────────────────────────────────────────────────────────
    @b.callback_query_handler(func=lambda call: True)
    def handle_callbacks(call):
        user_id = call.from_user.id
        data    = call.data

        if data == "show_main_menu":
            waiting_for_key.pop(user_id, None)
            token = config.generate_login_token(user_id)
            url   = f"{WEB_URL}/login?token={token}"
            safe_edit(call,
                "😈 *Menú Principal — Boty Generator* 🤖🔥\n\n"
                f"🌐 [Abrir Panel Web de Configuración]({url})",
                markup=get_main_keyboard())
            b.answer_callback_query(call.id)

        elif data == "show_help":
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            safe_edit(call, _help_text(), markup=markup)
            b.answer_callback_query(call.id)

        elif data == "web_login":
            waiting_for_key.pop(user_id, None)
            token = config.generate_login_token(user_id)
            url   = f"{WEB_URL}/login?token={token}"
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            safe_edit(call,
                f"🌐 *Panel Web*\n\n👉 [Abre tu panel aquí]({url})\n\n⚠️ Expira en *30 min*.",
                markup=markup)
            b.answer_callback_query(call.id)

        elif data == "select_provider":
            safe_edit(call, "🔌 *Selecciona el Proveedor de IA:*", markup=_build_provider_markup())
            b.answer_callback_query(call.id)

        elif data.startswith("set_prov_"):
            prov = data[len("set_prov_"):]
            cfg  = config.get_user_config(user_id)
            cfg["current_provider"] = prov
            config.save_user_config(user_id, cfg)
            safe_edit(call,
                f"✅ Proveedor cambiado a *{PROVIDER_LABELS.get(prov, prov.upper())}*.\n\n"
                f"🤖 *Selecciona el modelo activo:*",
                markup=_build_model_markup(prov))
            b.answer_callback_query(call.id, f"Proveedor: {prov.upper()}")

        elif data == "select_model":
            cfg  = config.get_user_config(user_id)
            prov = cfg.get("current_provider", "gemini")
            safe_edit(call,
                f"🤖 *Selecciona el modelo para {PROVIDER_LABELS.get(prov, prov.upper())}:*",
                markup=_build_model_markup(prov))
            b.answer_callback_query(call.id)

        elif data.startswith("set_model_"):
            model_name = data[len("set_model_"):]
            cfg  = config.get_user_config(user_id)
            prov = cfg.get("current_provider", "gemini")
            cfg.setdefault("selected_models", {})[prov] = model_name
            config.save_user_config(user_id, cfg)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            safe_edit(call,
                f"✅ Modelo para *{PROVIDER_LABELS.get(prov, prov.upper())}* cambiado a `{model_name}`.",
                markup=markup)
            b.answer_callback_query(call.id, f"Modelo: {model_name}")

        elif data == "show_status":
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
                InlineKeyboardButton("🌐 Panel Web",           callback_data="web_login"),
                InlineKeyboardButton("⬅️ Menú Principal",     callback_data="show_main_menu"),
            )
            safe_edit(call, get_status_text(user_id), markup=markup)
            b.answer_callback_query(call.id)

        elif data == "clear_hist":
            ai.clear_history(user_id)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            safe_edit(call, "🧹 *Historial borrado con éxito.*", markup=markup)
            b.answer_callback_query(call.id, "Historial limpiado")

        elif data == "key_chat_menu":
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🌟 Gemini Key",    callback_data="setup_key_gemini"),
                InlineKeyboardButton("🧠 OpenAI Key",    callback_data="setup_key_openai"),
                InlineKeyboardButton("🎭 Claude Key",    callback_data="setup_key_anthropic"),
                InlineKeyboardButton("⚡ Grok Key",      callback_data="setup_key_grok"),
            )
            markup.add(InlineKeyboardButton("⬅️ Volver", callback_data="show_status"))
            safe_edit(call, "🔑 *¿Qué API Key deseas configurar?*", markup=markup)
            b.answer_callback_query(call.id)

        elif data.startswith("setup_key_"):
            prov = data[len("setup_key_"):]
            waiting_for_key[user_id] = prov
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="cancel_key_setup"))
            safe_edit(call,
                f"🔑 *Configurando API Key para {PROVIDER_LABELS.get(prov, prov.upper())}*\n\n"
                f"Escribe tu API Key en el próximo mensaje.\n\n"
                f"⚠️ Tu mensaje se borrará del chat de inmediato.",
                markup=markup)
            b.answer_callback_query(call.id)

        elif data == "cancel_key_setup":
            waiting_for_key.pop(user_id, None)
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            safe_edit(call, "❌ *Configuración de API Key cancelada.*", markup=markup)
            b.answer_callback_query(call.id)

        elif data.startswith("dl_mp4_") or data.startswith("dl_mp3_"):
            parts    = data.split("_")
            dtype    = parts[1]
            short_id = parts[2]
            url      = pending_downloads.get(short_id)
            if not url:
                safe_edit(call, "⚠️ *Enlace caducado.* Vuelve a enviarlo.")
                b.answer_callback_query(call.id)
                return
            safe_edit(call,
                f"📥 *Iniciando descarga {dtype.upper()} de:*\n`{url}`\n\n⚙️ Procesando...")
            b.answer_callback_query(call.id, f"Descargando {dtype.upper()}...")
            threading.Thread(
                target=_process_download_thread,
                args=(b, user_id, call.message.message_id, url, dtype, short_id),
                daemon=True
            ).start()

        elif data.startswith("ai_chat_"):
            short_id = data[len("ai_chat_"):]
            url      = pending_downloads.pop(short_id, None)
            if not url:
                safe_edit(call, "⚠️ *Enlace caducado.* Vuelve a enviarlo.")
                b.answer_callback_query(call.id)
                return
            safe_edit(call, "💬 *Consultando a la IA sobre el link...*")
            b.answer_callback_query(call.id)
            b.send_chat_action(user_id, "typing")
            cfg   = config.get_user_config(user_id)
            reply = ai.generate_response(
                user_id,
                f"Analiza este enlace y haz un resumen detallado del contenido: {url}",
                cfg
            )
            b.send_message(user_id, reply)

    # ── Mensajes de texto ────────────────────────────────────────────────────
    @b.message_handler(func=lambda msg: True, content_types=["text"])
    def handle_message(message):
        user_id = message.from_user.id
        prompt  = message.text or ""

        # 1. API Key input
        if user_id in waiting_for_key:
            prov = waiting_for_key.pop(user_id)
            cfg  = config.get_user_config(user_id)
            cfg.setdefault("api_keys", {})[prov] = prompt.strip()
            config.save_user_config(user_id, cfg)
            try:
                b.delete_message(message.chat.id, message.message_id)
            except Exception:
                pass
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
            b.send_message(user_id,
                f"✅ *API Key de {PROVIDER_LABELS.get(prov, prov.upper())} guardada.*\n\n"
                f"Mensaje eliminado por seguridad.",
                reply_markup=markup)
            return

        # 2. Detección de links de descarga
        urls = URL_PATTERN.findall(prompt)
        if urls:
            link = urls[0]
            if any(d in link.lower() for d in MEDIA_DOMAINS):
                short_id = str(uuid.uuid4())[:8]
                pending_downloads[short_id] = link
                markup = InlineKeyboardMarkup(row_width=2)
                markup.add(
                    InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"dl_mp4_{short_id}"),
                    InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl_mp3_{short_id}"),
                    InlineKeyboardButton("💬 Consultar IA sobre el link", callback_data=f"ai_chat_{short_id}"),
                )
                b.send_message(user_id,
                    f"📥 *Enlace detectado:*\n`{link}`\n\n¿Qué deseas hacer?",
                    reply_markup=markup)
                return

        # 3. Chat con IA
        b.send_chat_action(user_id, "typing")
        cfg   = config.get_user_config(user_id)
        reply = ai.generate_response(user_id, prompt, cfg)
        if len(reply) > 4096:
            for chunk in [reply[i:i+4096] for i in range(0, len(reply), 4096)]:
                b.send_message(user_id, chunk)
        else:
            b.send_message(user_id, reply)

    logger.info("[Bot] Handlers registrados correctamente.")


# ═════════════════════════════════════════════════════════════════════════════
# Lazy initialization — segura para imports en entornos serverless
# ═════════════════════════════════════════════════════════════════════════════

_bot_instance: telebot.TeleBot | None = None

def get_bot() -> telebot.TeleBot:
    """
    Devuelve la instancia única del bot, creándola si no existe.
    Uso en modo Webhook (Netlify):
        from bot import get_bot
        update = telebot.types.Update.de_json(data)
        get_bot().process_new_updates([update])
    """
    global _bot_instance
    if _bot_instance is None:
        token = os.getenv("BOT_TOKEN", BOT_TOKEN)
        if not token:
            raise RuntimeError(
                "BOT_TOKEN no está configurado. "
                "Agrégala como variable de entorno en Netlify o en tu archivo .env."
            )
        _bot_instance = telebot.TeleBot(token, parse_mode="Markdown")
        _register_handlers(_bot_instance)
        logger.info("[Bot] Instancia creada e inicializada (modo Webhook/Serverless).")
    return _bot_instance


# ═════════════════════════════════════════════════════════════════════════════
# Entry point — Modo Polling (ejecución directa: python bot.py o via run.py)
# ═════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("🚀 Iniciando Boty Generator en modo POLLING...")
    get_bot().infinity_polling(timeout=20, long_polling_timeout=20)
