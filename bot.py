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

# ── Configuración de logging ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
WEB_URL = os.getenv("WEB_URL", "http://localhost:8000")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN no está configurado. Agrega la variable de entorno BOT_TOKEN.")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# ── Estado temporal en memoria ────────────────────────────────────────────────
# {short_id: url} — URL originales de los botones de descarga
pending_downloads: dict[str, str] = {}
# {user_id: provider_name} — Usuarios esperando input de API Key
waiting_for_key: dict[int, str] = {}

PROVIDER_LABELS = {
    "gemini": "🌟 Google Gemini",
    "openai": "🧠 ChatGPT (OpenAI)",
    "anthropic": "🎭 Claude (Anthropic)",
    "grok": "⚡ Grok (xAI)",
}

# ── Helpers de UI ─────────────────────────────────────────────────────────────

def get_main_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔌 Cambiar Proveedor", callback_data="select_provider"),
        InlineKeyboardButton("🤖 Cambiar Modelo", callback_data="select_model"),
        InlineKeyboardButton("📊 Ver Estado / Keys", callback_data="show_status"),
        InlineKeyboardButton("🧹 Limpiar Chat", callback_data="clear_hist"),
        InlineKeyboardButton("🌐 Panel Web", callback_data="web_login"),
        InlineKeyboardButton("❓ Ayuda", callback_data="show_help"),
    )
    return markup

def get_status_text(user_id) -> str:
    cfg = config.get_user_config(user_id)
    prov = cfg.get("current_provider", "gemini")
    model = cfg.get("selected_models", {}).get(prov, "default")
    keys = cfg.get("api_keys", {})

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

def safe_edit(call, text: str, markup=None, parse_mode="Markdown"):
    """Edita un mensaje de forma segura evitando errores de 'message not modified'."""
    try:
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=markup
        )
    except telebot.apihelper.ApiTelegramException as e:
        if "message is not modified" not in str(e):
            logger.warning(f"safe_edit error: {e}")

# ── Handlers de comandos ──────────────────────────────────────────────────────

@bot.message_handler(commands=["start", "menu"])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "usuario"
    waiting_for_key.pop(user_id, None)

    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"

    text = (
        f"😈 *¡Hola, {first_name}! Soy Boty Generator* 🤖🔥\n\n"
        "Soy tu asistente multi-IA con acceso a:\n"
        f"  {PROVIDER_LABELS['gemini']}\n"
        f"  {PROVIDER_LABELS['openai']}\n"
        f"  {PROVIDER_LABELS['anthropic']}\n"
        f"  {PROVIDER_LABELS['grok']}\n\n"
        "📥 *Descargador de Videos:* Envíame cualquier enlace de TikTok, YouTube, Instagram, "
        "Facebook, Twitter/X, Kwai y más — te daré botones para descargar en MP4 o MP3.\n\n"
        f"🔑 [Configurar tus API Keys en el Panel Web]({url})"
    )
    bot.send_message(user_id, text, reply_markup=get_main_keyboard())

@bot.message_handler(commands=["login", "web"])
def send_login_link(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
    bot.send_message(
        user_id,
        f"🌐 *Panel de Configuración Web*\n\n"
        f"👉 [Haz clic aquí para abrir tu panel]({url})\n\n"
        f"⚠️ Este enlace expira en *30 minutos* por seguridad.",
        reply_markup=markup
    )

@bot.message_handler(commands=["provider"])
def command_provider(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    markup = _build_provider_markup()
    bot.send_message(user_id, "🔌 *Selecciona el Proveedor de IA:*", reply_markup=markup)

@bot.message_handler(commands=["model"])
def command_model(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    cfg = config.get_user_config(user_id)
    prov = cfg.get("current_provider", "gemini")
    markup = _build_model_markup(prov)
    bot.send_message(user_id, f"🤖 *Selecciona el modelo para {PROVIDER_LABELS.get(prov, prov.upper())}:*", reply_markup=markup)

@bot.message_handler(commands=["status"])
def command_status(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
        InlineKeyboardButton("🌐 Configurar por Web", callback_data="web_login"),
        InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"),
    )
    text = get_status_text(user_id) + f"\n\n🔗 [Abrir Panel Web]({url})"
    bot.send_message(user_id, text, reply_markup=markup)

@bot.message_handler(commands=["clear"])
def command_clear(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    ai.clear_history(user_id)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    bot.send_message(user_id, "🧹 *Historial de chat borrado con éxito.*", reply_markup=markup)

@bot.message_handler(commands=["help"])
def command_help(message):
    user_id = message.from_user.id
    waiting_for_key.pop(user_id, None)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    bot.send_message(user_id, _help_text(), reply_markup=markup)

def _help_text() -> str:
    return (
        "😈 *Comandos de Boty Generator* 🤖\n\n"
        "• `/start` — Menú principal interactivo\n"
        "• `/login` — Genera enlace al Panel Web de configuración\n"
        "• `/provider` — Cambia el proveedor de IA activo\n"
        "• `/model` — Cambia el modelo del proveedor activo\n"
        "• `/status` — Muestra tu configuración y API Keys\n"
        "• `/clear` — Limpia el historial de la conversación\n"
        "• `/help` — Muestra este mensaje\n\n"
        "📥 *Descarga de videos:*\n"
        "Envíame un enlace de TikTok, YouTube, Instagram, Facebook, "
        "Twitter/X, Kwai, Pinterest, Vimeo o Twitch.\n\n"
        "💬 *Chat con IA:*\n"
        "Escríbeme cualquier cosa y te responderé con el proveedor y modelo que tengas activo."
    )

# ── Helpers internos para teclados ───────────────────────────────────────────

def _build_provider_markup() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(PROVIDER_LABELS["gemini"], callback_data="set_prov_gemini"),
        InlineKeyboardButton(PROVIDER_LABELS["openai"], callback_data="set_prov_openai"),
        InlineKeyboardButton(PROVIDER_LABELS["anthropic"], callback_data="set_prov_anthropic"),
        InlineKeyboardButton(PROVIDER_LABELS["grok"], callback_data="set_prov_grok"),
    )
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    return markup

def _build_model_markup(provider: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for m in ai.MODELS.get(provider, []):
        markup.add(InlineKeyboardButton(m, callback_data=f"set_model_{m}"))
    markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
    return markup

# ── Descarga en hilo separado ─────────────────────────────────────────────────

def _process_download_thread(user_id: int, message_id: int, url: str, dtype: str, short_id: str):
    try:
        filepath, title, err = downloader.download_media(url, dtype)

        if err or not filepath or not os.path.exists(filepath):
            bot.edit_message_text(
                chat_id=user_id, message_id=message_id,
                text=f"❌ *Error al descargar:*\n`{err or 'Archivo no encontrado.'}`",
            )
            return

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > 49.9:
            bot.edit_message_text(
                chat_id=user_id, message_id=message_id,
                text=(
                    f"⚠️ *Archivo demasiado grande ({size_mb:.1f} MB)*\n\n"
                    f"Telegram limita los bots a 50 MB. Intenta descargar en formato MP3."
                ),
            )
            _safe_remove(filepath)
            return

        bot.edit_message_text(
            chat_id=user_id, message_id=message_id,
            text=f"📤 *Descarga lista:* `{title}` ({size_mb:.1f} MB)\nEnviando archivo a Telegram...",
        )

        with open(filepath, "rb") as f:
            if dtype == "mp3":
                bot.send_audio(user_id, f, title=title,
                               caption=f"🎵 *{title}*\n_Descargado con 😈 Boty Generator_")
            else:
                bot.send_video(user_id, f,
                               caption=f"🎥 *{title}*\n_Descargado con 😈 Boty Generator_")

        try:
            bot.delete_message(user_id, message_id)
        except Exception:
            pass

        _safe_remove(filepath)
        pending_downloads.pop(short_id, None)

    except Exception as e:
        logger.error(f"[Downloader] Error inesperado para {user_id}: {e}")
        try:
            bot.send_message(user_id, f"❌ *Error inesperado enviando el archivo:*\n`{e}`")
        except Exception:
            pass

def _safe_remove(path: str):
    try:
        os.remove(path)
    except Exception:
        pass

# ── Callback handler unificado ───────────────────────────────────────────────

@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data

    # ── Menú principal ──────────────────────────────────────────────────────
    if data == "show_main_menu":
        waiting_for_key.pop(user_id, None)
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        text = (
            "😈 *Menú Principal — Boty Generator* 🤖🔥\n\n"
            "Elige una opción para configurar tu experiencia de IA:\n\n"
            f"🌐 [Abrir Panel Web de Configuración]({url})"
        )
        safe_edit(call, text, markup=get_main_keyboard())
        bot.answer_callback_query(call.id)

    elif data == "show_help":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        safe_edit(call, _help_text(), markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "web_login":
        waiting_for_key.pop(user_id, None)
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        safe_edit(
            call,
            f"🌐 *Panel Web de Configuración*\n\n"
            f"👉 [Haz clic aquí para abrir tu panel]({url})\n\n"
            f"⚠️ Este enlace expira en *30 minutos*.",
            markup=markup
        )
        bot.answer_callback_query(call.id)

    # ── Selección de proveedor ──────────────────────────────────────────────
    elif data == "select_provider":
        safe_edit(call, "🔌 *Selecciona el Proveedor de IA:*", markup=_build_provider_markup())
        bot.answer_callback_query(call.id)

    elif data.startswith("set_prov_"):
        prov = data[len("set_prov_"):]
        cfg = config.get_user_config(user_id)
        cfg["current_provider"] = prov
        config.save_user_config(user_id, cfg)
        safe_edit(
            call,
            f"✅ Proveedor cambiado a *{PROVIDER_LABELS.get(prov, prov.upper())}*.\n\n"
            f"🤖 *Selecciona el modelo activo:*",
            markup=_build_model_markup(prov)
        )
        bot.answer_callback_query(call.id, f"Proveedor: {prov.upper()}")

    # ── Selección de modelo ─────────────────────────────────────────────────
    elif data == "select_model":
        cfg = config.get_user_config(user_id)
        prov = cfg.get("current_provider", "gemini")
        safe_edit(
            call,
            f"🤖 *Selecciona el modelo para {PROVIDER_LABELS.get(prov, prov.upper())}:*",
            markup=_build_model_markup(prov)
        )
        bot.answer_callback_query(call.id)

    elif data.startswith("set_model_"):
        model_name = data[len("set_model_"):]
        cfg = config.get_user_config(user_id)
        prov = cfg.get("current_provider", "gemini")
        cfg.setdefault("selected_models", {})[prov] = model_name
        config.save_user_config(user_id, cfg)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        safe_edit(
            call,
            f"✅ Modelo activo para *{PROVIDER_LABELS.get(prov, prov.upper())}* cambiado a `{model_name}`.",
            markup=markup
        )
        bot.answer_callback_query(call.id, f"Modelo: {model_name}")

    # ── Status ──────────────────────────────────────────────────────────────
    elif data == "show_status":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
            InlineKeyboardButton("🌐 Configurar por Web", callback_data="web_login"),
            InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"),
        )
        safe_edit(call, get_status_text(user_id), markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "clear_hist":
        ai.clear_history(user_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        safe_edit(call, "🧹 *Historial de chat borrado con éxito.*", markup=markup)
        bot.answer_callback_query(call.id, "Historial limpiado")

    # ── Configuración de keys por chat ──────────────────────────────────────
    elif data == "key_chat_menu":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🌟 Gemini Key", callback_data="setup_key_gemini"),
            InlineKeyboardButton("🧠 OpenAI Key", callback_data="setup_key_openai"),
            InlineKeyboardButton("🎭 Claude Key", callback_data="setup_key_anthropic"),
            InlineKeyboardButton("⚡ Grok Key", callback_data="setup_key_grok"),
        )
        markup.add(InlineKeyboardButton("⬅️ Volver", callback_data="show_status"))
        safe_edit(call, "🔑 *¿Qué API Key deseas configurar?*", markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("setup_key_"):
        prov = data[len("setup_key_"):]
        waiting_for_key[user_id] = prov
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="cancel_key_setup"))
        safe_edit(
            call,
            f"🔑 *Configurando API Key para {PROVIDER_LABELS.get(prov, prov.upper())}*\n\n"
            f"Escribe y envíame tu API Key en el siguiente mensaje.\n\n"
            f"⚠️ Tu mensaje será eliminado del chat de forma inmediata después de guardarse.",
            markup=markup
        )
        bot.answer_callback_query(call.id)

    elif data == "cancel_key_setup":
        waiting_for_key.pop(user_id, None)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        safe_edit(call, "❌ *Configuración de API Key cancelada.*", markup=markup)
        bot.answer_callback_query(call.id)

    # ── Descarga de medios ──────────────────────────────────────────────────
    elif data.startswith("dl_mp4_") or data.startswith("dl_mp3_"):
        parts = data.split("_")
        dtype = parts[1]
        short_id = parts[2]
        url = pending_downloads.get(short_id)
        if not url:
            safe_edit(call, "⚠️ *El enlace ha caducado.* Vuelve a enviar el link por favor.")
            bot.answer_callback_query(call.id)
            return

        safe_edit(
            call,
            f"📥 *Iniciando descarga {dtype.upper()} de:*\n`{url}`\n\n⚙️ Procesando, por favor espera...",
        )
        bot.answer_callback_query(call.id, f"Descargando {dtype.upper()}...")
        threading.Thread(
            target=_process_download_thread,
            args=(user_id, call.message.message_id, url, dtype, short_id),
            daemon=True
        ).start()

    elif data.startswith("ai_chat_"):
        short_id = data[len("ai_chat_"):]
        url = pending_downloads.pop(short_id, None)
        if not url:
            safe_edit(call, "⚠️ *El enlace ha caducado.* Vuelve a enviarlo.")
            bot.answer_callback_query(call.id)
            return

        safe_edit(call, "💬 *Consultando a la IA sobre el link...*")
        bot.answer_callback_query(call.id)
        bot.send_chat_action(user_id, "typing")
        cfg = config.get_user_config(user_id)
        reply = ai.generate_response(
            user_id,
            f"Analiza este enlace y haz un resumen detallado del contenido que describe o enlaza: {url}",
            cfg
        )
        bot.send_message(user_id, reply)

# ── Handler de mensajes de texto ─────────────────────────────────────────────

MEDIA_DOMAINS = [
    "youtube.com", "youtu.be", "tiktok.com", "instagram.com",
    "facebook.com", "twitter.com", "x.com", "vimeo.com",
    "kwai.com", "pinterest.com", "twitch.tv", "dailymotion.com",
    "reddit.com", "soundcloud.com", "bilibili.com",
]

URL_PATTERN = re.compile(r"https?://[^\s]+")

@bot.message_handler(func=lambda msg: True, content_types=["text"])
def handle_message(message):
    user_id = message.from_user.id
    prompt = message.text or ""

    # 1. Si el usuario está enviando una API Key
    if user_id in waiting_for_key:
        prov = waiting_for_key.pop(user_id)
        cfg = config.get_user_config(user_id)
        cfg.setdefault("api_keys", {})[prov] = prompt.strip()
        config.save_user_config(user_id, cfg)

        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception:
            pass

        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Menú Principal", callback_data="show_main_menu"))
        bot.send_message(
            user_id,
            f"✅ *API Key de {PROVIDER_LABELS.get(prov, prov.upper())} guardada correctamente.*\n\n"
            f"Tu mensaje fue eliminado del chat por seguridad.",
            reply_markup=markup
        )
        return

    # 2. Detectar enlaces de descarga de medios
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
                InlineKeyboardButton("💬 Consultar a la IA sobre el link", callback_data=f"ai_chat_{short_id}"),
            )
            bot.send_message(
                user_id,
                f"📥 *Enlace de medios detectado:*\n`{link}`\n\n¿Qué deseas hacer con él?",
                reply_markup=markup
            )
            return

    # 3. Chat con IA
    bot.send_chat_action(user_id, "typing")
    cfg = config.get_user_config(user_id)
    reply = ai.generate_response(user_id, prompt, cfg)

    # Manejar respuestas muy largas (límite de Telegram: 4096 chars)
    if len(reply) > 4096:
        for i in range(0, len(reply), 4096):
            bot.send_message(user_id, reply[i:i + 4096])
    else:
        bot.send_message(user_id, reply)

# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info("🚀 Iniciando Boty Generator...")
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
