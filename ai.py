import os
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Modelos actualizados con las versiones más recientes de 2025
MODELS = {
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "o3-mini",
        "o1-mini",
    ],
    "anthropic": [
        "claude-sonnet-4-5",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-20240229",
    ],
    "grok": [
        "grok-3",
        "grok-3-mini",
        "grok-2-1212",
        "grok-2-vision-1212",
    ]
}

# Límite de historial configurable (20 mensajes = 10 turnos)
HISTORY_LIMIT = 20

# Cache en memoria: {uid: [{"role": "user"/"assistant", "content": "..."}]}
_history: dict[str, list[dict]] = {}

def get_history(user_id) -> list:
    uid = str(user_id)
    if uid not in _history:
        _history[uid] = []
    return _history[uid]

def clear_history(user_id) -> None:
    uid = str(user_id)
    _history[uid] = []

def add_message(user_id, role: str, content: str) -> None:
    uid = str(user_id)
    hist = get_history(uid)
    hist.append({"role": role, "content": content})
    # Mantener solo los últimos N mensajes
    if len(hist) > HISTORY_LIMIT:
        _history[uid] = hist[-HISTORY_LIMIT:]

def _build_error(provider: str, model: str, err: Exception) -> str:
    """Formatea el error de la IA de forma uniforme y útil."""
    err_str = str(err)
    # Detectar errores comunes y dar sugerencias útiles
    if "API_KEY_INVALID" in err_str or "Incorrect API key" in err_str or "authentication" in err_str.lower():
        return (
            f"🔑 *Error de API Key en {provider.upper()}*\n\n"
            f"La key configurada para `{provider}` no es válida o ha expirado.\n"
            f"Usa el botón *Ver Estado / Keys* del menú o el *Panel Web* para actualizarla."
        )
    if "quota" in err_str.lower() or "rate" in err_str.lower() or "429" in err_str:
        return (
            f"⏳ *Límite de peticiones alcanzado en {provider.upper()}*\n\n"
            f"Tu plan de `{model}` ha alcanzado el límite de solicitudes por minuto.\n"
            f"Espera unos segundos y vuelve a intentarlo, o cambia de modelo/proveedor."
        )
    if "model" in err_str.lower() and ("not found" in err_str.lower() or "does not exist" in err_str.lower()):
        return (
            f"🤖 *Modelo no disponible: `{model}`*\n\n"
            f"Este modelo ya no está disponible en {provider.upper()}.\n"
            f"Usa el botón *Cambiar Modelo* del menú para seleccionar uno disponible."
        )
    return f"❌ *Error en {provider.upper()} (`{model}`)*:\n`{err_str[:300]}`"

def generate_response(user_id, prompt: str, cfg: dict) -> str:
    uid = str(user_id)
    provider = cfg.get("current_provider", "gemini")
    api_keys = cfg.get("api_keys", {})
    key = api_keys.get(provider, "").strip()
    selected_models = cfg.get("selected_models", {})
    model_name = selected_models.get(provider, "") or (MODELS[provider][0] if provider in MODELS else "default")

    if not key:
        return (
            f"⚠️ *Sin API Key para {provider.upper()}*\n\n"
            f"No has configurado tu key para `{provider}`.\n"
            f"Usa el menú → *Ver Estado / Keys* → *Configurar por Chat* o abre el *Panel Web* con `/login`."
        )

    try:
        add_message(uid, "user", prompt)
        hist = get_history(uid)

        result: Optional[str] = None

        if provider == "gemini":
            genai.configure(api_key=key)
            gemini_history = [
                {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                for m in hist[:-1]
            ]
            model = genai.GenerativeModel(
                model_name,
                system_instruction="Eres un asistente de IA útil, amable y preciso. Responde siempre en el idioma del usuario."
            )
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(prompt)
            result = response.text

        elif provider == "openai":
            client = OpenAI(api_key=key)
            messages = [
                {"role": "system", "content": "Eres un asistente de IA útil, amable y preciso. Responde siempre en el idioma del usuario."}
            ] + [{"role": m["role"], "content": m["content"]} for m in hist]
            response = client.chat.completions.create(model=model_name, messages=messages)
            result = response.choices[0].message.content

        elif provider == "grok":
            client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
            messages = [
                {"role": "system", "content": "Eres un asistente de IA útil, amable y preciso. Responde siempre en el idioma del usuario."}
            ] + [{"role": m["role"], "content": m["content"]} for m in hist]
            response = client.chat.completions.create(model=model_name, messages=messages)
            result = response.choices[0].message.content

        elif provider == "anthropic":
            client = Anthropic(api_key=key)
            anthropic_msgs = [
                {"role": "user" if m["role"] == "user" else "assistant", "content": m["content"]}
                for m in hist
            ]
            # Anthropic requiere que el primer mensaje sea del usuario
            if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
                anthropic_msgs = anthropic_msgs[1:]
            
            message = client.messages.create(
                model=model_name,
                max_tokens=4096,
                system="Eres un asistente de IA útil, amable y preciso. Responde siempre en el idioma del usuario.",
                messages=anthropic_msgs
            )
            result = message.content[0].text
        else:
            result = f"❌ Proveedor `{provider}` no soportado."

        add_message(uid, "assistant", result)
        return result

    except Exception as e:
        # Revertir el último mensaje del usuario en caso de fallo
        hist = get_history(uid)
        if hist and hist[-1]["role"] == "user" and hist[-1]["content"] == prompt:
            hist.pop()
        logger.error(f"[AI] Error generando respuesta ({provider}/{model_name}): {e}")
        return _build_error(provider, model_name, e)
