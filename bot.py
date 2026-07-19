import os
import re
import uuid
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
import config
import ai
import downloader

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8886104559:AAHclO0tYWadm4eMMrPB1C3PjQI6uqOps4U")
WEB_URL = os.getenv("WEB_URL", "http://localhost:8000")

bot = telebot.TeleBot(BOT_TOKEN)

# Memory storage for pending download links: {short_id: url}
pending_downloads = {}

# Trace if we are waiting for a key input via chat: {user_id: provider_name}
waiting_for_key = {}

def get_status_text(user_id):
    cfg = config.get_user_config(user_id)
    prov = cfg.get("current_provider", "gemini")
    model = cfg.get("selected_models", {}).get(prov, "default")
    keys = cfg.get("api_keys", {})
    
    status = "📊 *Estado de tu Configuración*\n\n"
    status += f"🔌 *Proveedor Activo*: {prov.upper()}\n"
    status += f"🤖 *Modelo Activo*: `{model}`\n\n"
    status += "🔑 *API Keys Registradas*:\n"
    
    for p in ["gemini", "openai", "anthropic", "grok"]:
        k = keys.get(p, "")
        if k:
            masked = k[:6] + "..." + k[-4:] if len(k) > 10 else "Configurada ✓"
            status += f"• {p.upper()}: `{masked}`\n"
        else:
            status += f"• {p.upper()}: ❌ _Sin registrar_\n"
            
    return status

def get_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    btn_prov = InlineKeyboardButton("🔌 Cambiar Proveedor", callback_data="select_provider")
    btn_model = InlineKeyboardButton("🤖 Cambiar Modelo", callback_data="select_model")
    btn_status = InlineKeyboardButton("📊 Ver Estado / Keys", callback_data="show_status")
    btn_clear = InlineKeyboardButton("🧹 Limpiar Chat", callback_data="clear_hist")
    
    markup.add(btn_prov, btn_model)
    markup.add(btn_status, btn_clear)
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"
    
    welcome_text = (
        f"😈 *¡Hola, {first_name}! Soy Boty Generator* 🤖🔥\n\n"
        "Estoy lista para conectarte a las mejores Inteligencias Artificiales del mundo: "
        "*Gemini, ChatGPT, Claude y Grok*.\n\n"
        "📥 *¡También soy Descargadora de Videos!* Envíame cualquier enlace de **TikTok, YouTube, Instagram, Facebook, Twitter/X, Kwai, etc.** y te daré opciones para convertirlo a MP4 o MP3.\n\n"
        f"🔑 *Configuración Web Directa*:\n"
        f"👉 [Abrir Panel de Configuración Web]({url})\n\n"
        "Usa los botones de abajo para cambiar de proveedor, modelo o limpiar el chat."
    )
    bot.send_message(user_id, welcome_text, parse_mode="Markdown", reply_markup=get_main_keyboard())

@bot.message_handler(commands=['login', 'web'])
def send_login_link(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"
    
    markup = InlineKeyboardMarkup()
    btn_back = InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu")
    markup.add(btn_back)
    
    bot.send_message(
        user_id,
        f"✨ *Acceso Seguro al Panel Web*\n\n"
        f"👉 [Haz clic aquí para abrir tu configuración web]({url})\n\n"
        f"Este enlace es personal y expirará en 30 minutos.",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['provider'])
def command_provider(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Google Gemini", callback_data="set_prov_gemini"),
        InlineKeyboardButton("ChatGPT (OpenAI)", callback_data="set_prov_openai"),
        InlineKeyboardButton("Claude (Anthropic)", callback_data="set_prov_anthropic"),
        InlineKeyboardButton("Grok (xAI)", callback_data="set_prov_grok")
    )
    markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
    bot.send_message(user_id, "🔌 *Selecciona el Proveedor de IA:*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['model'])
def command_model(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    cfg = config.get_user_config(user_id)
    prov = cfg.get("current_provider", "gemini")
    
    markup = InlineKeyboardMarkup(row_width=1)
    models = ai.MODELS.get(prov, [])
    for m in models:
        markup.add(InlineKeyboardButton(m, callback_data=f"set_model_{m}"))
    markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
    bot.send_message(
        user_id,
        f"🤖 *Selecciona el modelo para {prov.upper()}:*",
        parse_mode="Markdown",
        reply_markup=markup
    )

@bot.message_handler(commands=['status'])
def command_status(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    status_txt = get_status_text(user_id)
    
    token = config.generate_login_token(user_id)
    url = f"{WEB_URL}/login?token={token}"
    
    status_txt += f"\n🔗 *Configuración Web*: [Abrir Portal]({url})"
    
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
        InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu")
    )
    
    bot.send_message(user_id, status_txt, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['clear'])
def command_clear(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    ai.clear_history(user_id)
    
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
    
    bot.send_message(user_id, "🧹 *Historial de chat limpiado.*", parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(commands=['help'])
def command_help(message):
    user_id = message.from_user.id
    if user_id in waiting_for_key:
        del waiting_for_key[user_id]
        
    help_text = (
        "😈 *Comandos disponibles:* 🐰\n\n"
        "• `/start` - Menú principal interactivo.\n"
        "• `/login` - Enlace de configuración web temporal.\n"
        "• `/provider` - Cambia el proveedor de IA activo.\n"
        "• `/model` - Cambia el modelo del proveedor activo.\n"
        "• `/status` - Muestra la configuración y API keys.\n"
        "• `/clear` - Limpia la memoria del chat.\n"
        "• `/help` - Muestra este mensaje de ayuda.\n\n"
        "📥 *Descarga de videos*: Solo envíame un enlace de TikTok, YouTube, Instagram, Facebook, etc., y te saldrán los botones de conversión automáticamente."
    )
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
    bot.send_message(user_id, help_text, parse_mode="Markdown", reply_markup=markup)

def process_download_thread(user_id, message_id, url, dtype, short_id):
    try:
        # Download media
        filepath, title, err = downloader.download_media(url, dtype)
        
        if err:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=f"❌ *Error al descargar el archivo:*\n`{err}`",
                parse_mode="Markdown"
            )
            return
            
        if not filepath or not os.path.exists(filepath):
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text="❌ *Error*: No se pudo localizar el archivo descargado en el disco local.",
                parse_mode="Markdown"
            )
            return
            
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > 49.9:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=message_id,
                text=f"⚠️ *El archivo es demasiado grande ({size_mb:.1f} MB)*.\n\nTelegram limita a los bots a subir un máximo de 50 MB. Intenta descargar en formato MP3 (audio) en su lugar.",
                parse_mode="Markdown"
            )
            try:
                os.remove(filepath)
            except Exception:
                pass
            return
            
        bot.edit_message_text(
            chat_id=user_id,
            message_id=message_id,
            text=f"📤 *Descarga completada.*\n\n*Título*: `{title}`\n*Tamaño*: `{size_mb:.1f} MB`\n\nEnviando archivo a Telegram, por favor espera...",
            parse_mode="Markdown"
        )
        
        # Send file
        with open(filepath, 'rb') as f:
            if dtype == "mp3":
                bot.send_audio(
                    chat_id=user_id,
                    audio=f,
                    title=title,
                    caption=f"🎵 {title}\nDescargado con 😈 Boty Generator 🤖"
                )
            else:
                bot.send_video(
                    chat_id=user_id,
                    video=f,
                    caption=f"🎥 {title}\nDescargado con 😈 Boty Generator 🤖"
                )
                
        # Delete progress message
        try:
            bot.delete_message(user_id, message_id)
        except Exception:
            pass
            
        # Clean up files from disk immediately
        try:
            os.remove(filepath)
        except Exception as e:
            print(f"Error cleaning file: {e}")
            
        # Clear from pending download memory dictionary
        if short_id in pending_downloads:
            del pending_downloads[short_id]
            
    except Exception as e:
        bot.send_message(user_id, f"❌ *Error inesperado enviando el archivo:*\n`{str(e)}`", parse_mode="Markdown")

# Handle Callback Queries
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = call.from_user.id
    data = call.data
    
    if data == "show_main_menu":
        if user_id in waiting_for_key:
            del waiting_for_key[user_id]
            
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        
        welcome_text = (
            f"😈 *Menú Principal — Boty Generator* 🤖🔥\n\n"
            "Elige una de las siguientes opciones dinámicas para configurar tu experiencia de chat:\n\n"
            f"🔑 *Configuración Web Directa*:\n"
            f"👉 [Abrir Panel de Configuración Web]({url})"
        )
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=welcome_text,
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        bot.answer_callback_query(call.id)
        
    elif data == "web_login":
        if user_id in waiting_for_key:
            del waiting_for_key[user_id]
            
        token = config.generate_login_token(user_id)
        url = f"{WEB_URL}/login?token={token}"
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu")
        )
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=(
                f"🔗 *Panel de Configuración Web*\n\n"
                f"👉 [Haz clic aquí para abrir el portal web]({url})\n\n"
                f"Este enlace expirará en 30 minutos por seguridad."
            ),
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data == "select_provider":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Google Gemini", callback_data="set_prov_gemini"),
            InlineKeyboardButton("ChatGPT (OpenAI),", callback_data="set_prov_openai"),
            InlineKeyboardButton("Claude (Anthropic)", callback_data="set_prov_anthropic"),
            InlineKeyboardButton("Grok (xAI)", callback_data="set_prov_grok")
        )
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="🔌 *Selecciona el Proveedor de IA:*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data.startswith("set_prov_"):
        prov = data.split("set_prov_")[1]
        cfg = config.get_user_config(user_id)
        cfg["current_provider"] = prov
        config.save_user_config(user_id, cfg)
        
        markup = InlineKeyboardMarkup(row_width=1)
        models = ai.MODELS.get(prov, [])
        for m in models:
            markup.add(InlineKeyboardButton(m, callback_data=f"set_model_{m}"))
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=f"🔌 Proveedor cambiado a *{prov.upper()}*.\n\n🤖 *Elige ahora el modelo activo para {prov.upper()}:*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, f"Proveedor cambiado a {prov.upper()}")
        
    elif data == "select_model":
        cfg = config.get_user_config(user_id)
        prov = cfg.get("current_provider", "gemini")
        
        markup = InlineKeyboardMarkup(row_width=1)
        models = ai.MODELS.get(prov, [])
        for m in models:
            markup.add(InlineKeyboardButton(m, callback_data=f"set_model_{m}"))
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
            
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=f"🤖 *Selecciona el modelo para {prov.upper()}:*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data.startswith("set_model_"):
        model_name = data.split("set_model_")[1]
        cfg = config.get_user_config(user_id)
        prov = cfg.get("current_provider", "gemini")
        cfg["selected_models"][prov] = model_name
        config.save_user_config(user_id, cfg)
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=f"🤖 Modelo activo para *{prov.upper()}* cambiado a `{model_name}`.",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, f"Modelo cambiado a {model_name}")
        
    elif data == "show_status":
        status_txt = get_status_text(user_id)
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("🔑 Configurar por Chat", callback_data="key_chat_menu"),
            InlineKeyboardButton("🔗 Configurar por Web", callback_data="web_login")
        )
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=status_txt,
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data == "clear_hist":
        ai.clear_history(user_id)
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="🧹 *Historial de chat borrado.*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id, "Historial limpiado")
        
    elif data == "key_chat_menu":
        markup = InlineKeyboardMarkup(row_width=2)
        markup.add(
            InlineKeyboardButton("Gemini Key", callback_data="setup_key_gemini"),
            InlineKeyboardButton("OpenAI Key", callback_data="setup_key_openai"),
            InlineKeyboardButton("Claude Key", callback_data="setup_key_anthropic"),
            InlineKeyboardButton("Grok Key", callback_data="setup_key_grok")
        )
        markup.add(InlineKeyboardButton("⬅️ Volver", callback_data="show_status"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="🔑 *Elige qué API Key deseas configurar por chat:*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data.startswith("setup_key_"):
        prov = data.split("setup_key_")[1]
        waiting_for_key[user_id] = prov
        
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("❌ Cancelar", callback_data="cancel_key_setup"))
        
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=(
                f"🔑 *Configurando API Key para {prov.upper()}*\n\n"
                f"Por favor, escribe y envíame tu API Key en el próximo mensaje.\n\n"
                f"⚠️ *Nota*: Tu mensaje será borrado del historial de chat inmediatamente después de guardarse por razones de privacidad y seguridad."
            ),
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    elif data == "cancel_key_setup":
        if user_id in waiting_for_key:
            del waiting_for_key[user_id]
            
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="❌ *Configuración de API Key cancelada.*",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)
        
    # Media download handlers
    elif data.startswith("dl_mp4_") or data.startswith("dl_mp3_"):
        parts = data.split("_")
        dtype = parts[1] # "mp4" or "mp3"
        short_id = parts[2]
        
        url = pending_downloads.get(short_id)
        if not url:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text="⚠️ *Error*: El enlace ha caducado. Vuelve a enviarlo por favor."
            )
            bot.answer_callback_query(call.id)
            return
            
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text=f"📥 *Iniciando descarga ({dtype.upper()}) de:* \n`{url}`\n\n⚙️ Descargando y procesando, por favor espera...",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id, "Descargando...")
        
        # Start download process in a separate thread
        threading.Thread(
            target=process_download_thread, 
            args=(user_id, call.message.message_id, url, dtype, short_id), 
            daemon=True
        ).start()
        
    elif data.startswith("ai_chat_"):
        short_id = data.split("ai_chat_")[1]
        url = pending_downloads.get(short_id)
        if not url:
            bot.edit_message_text(
                chat_id=user_id,
                message_id=call.message.message_id,
                text="⚠️ *Error*: El enlace ha caducado. Vuelve a enviarlo."
            )
            bot.answer_callback_query(call.id)
            return
            
        if short_id in pending_downloads:
            del pending_downloads[short_id]
            
        bot.edit_message_text(
            chat_id=user_id,
            message_id=call.message.message_id,
            text="💬 *Procesando link con la IA...*",
            parse_mode="Markdown"
        )
        bot.answer_callback_query(call.id)
        
        bot.send_chat_action(user_id, "typing")
        cfg = config.get_user_config(user_id)
        reply = ai.generate_response(user_id, f"Háblame de este link y haz un resumen del contenido: {url}", cfg)
        bot.send_message(user_id, reply, parse_mode="Markdown")

# Handle normal messages
@bot.message_handler(func=lambda msg: True)
def handle_message(message):
    user_id = message.from_user.id
    prompt = message.text
    
    # 1. Check if we were waiting for an API Key input
    if user_id in waiting_for_key:
        prov = waiting_for_key[user_id]
        
        # Save Key
        cfg = config.get_user_config(user_id)
        cfg["api_keys"][prov] = prompt.strip()
        config.save_user_config(user_id, cfg)
        
        # Delete user message containing the key
        try:
            bot.delete_message(message.chat.id, message.message_id)
        except Exception as e:
            print(f"Error deleting user key message: {e}")
            
        # Clean waiting state
        del waiting_for_key[user_id]
        
        # Send confirmation
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Volver al Menú", callback_data="show_main_menu"))
        
        bot.send_message(
            user_id,
            f"✅ *¡API Key de {prov.upper()} guardada con éxito!*\n\n"
            f"Tu mensaje con la llave ha sido borrado del chat por seguridad.",
            parse_mode="Markdown",
            reply_markup=markup
        )
        return
        
    # 2. Check for media link URLs
    urls = re.findall(r'(https?://[^\s]+)', prompt)
    if urls:
        link = urls[0]
        # Match popular social media links
        is_media = any(domain in link.lower() for domain in [
            "youtube.com", "youtu.be", "tiktok.com", "instagram.com", 
            "facebook.com", "twitter.com", "x.com", "vimeo.com", 
            "kwai.com", "pinterest.com", "twitch.tv"
        ])
        
        if is_media:
            # Generate short id to avoid 64-byte Telegram callback_data limit
            short_id = str(uuid.uuid4())[:8]
            pending_downloads[short_id] = link
            
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("🎥 Video (MP4)", callback_data=f"dl_mp4_{short_id}"),
                InlineKeyboardButton("🎵 Audio (MP3)", callback_data=f"dl_mp3_{short_id}")
            )
            markup.add(
                InlineKeyboardButton("💬 Consultar a la IA sobre el link", callback_data=f"ai_chat_{short_id}")
            )
            
            bot.send_message(
                user_id,
                f"📥 *He detectado un enlace de medios:*\n`{link}`\n\n¿Qué te gustaría hacer con él?",
                parse_mode="Markdown",
                reply_markup=markup
            )
            return
            
    # 3. General AI Chat handler
    bot.send_chat_action(user_id, "typing")
    cfg = config.get_user_config(user_id)
    reply = ai.generate_response(user_id, prompt, cfg)
    
    # Send reply
    bot.send_message(user_id, reply, parse_mode="Markdown")

if __name__ == '__main__':
    print("Iniciando Boty Generator...")
    bot.infinity_polling()
