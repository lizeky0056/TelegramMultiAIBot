import os
import google.generativeai as genai
from openai import OpenAI
from anthropic import Anthropic

# Model lists
MODELS = {
    "gemini": [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash-exp",
        "gemini-2.5-flash",
        "gemini-2.5-pro"
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o3-mini"
    ],
    "anthropic": [
        "claude-3-5-haiku-latest",
        "claude-3-5-sonnet-latest",
        "claude-3-opus-20240229"
    ],
    "grok": [
        "grok-2-1212",
        "grok-beta",
        "grok-2-vision-1212"
    ]
}

# In-memory history cache: {user_id: [{"role": "user"/"assistant", "content": "..."}]}
_history = {}

def get_history(user_id):
    uid = str(user_id)
    if uid not in _history:
        _history[uid] = []
    return _history[uid]

def clear_history(user_id):
    uid = str(user_id)
    if uid in _history:
        _history[uid] = []

def add_message(user_id, role, content):
    uid = str(user_id)
    hist = get_history(uid)
    hist.append({"role": role, "content": content})
    # Keep last 10 turns (20 messages)
    if len(hist) > 20:
        _history[uid] = hist[-20:]

def generate_response(user_id, prompt, config):
    uid = str(user_id)
    provider = config.get("current_provider", "gemini")
    api_keys = config.get("api_keys", {})
    key = api_keys.get(provider, "")
    selected_models = config.get("selected_models", {})
    model_name = selected_models.get(provider, "")
    
    if not key:
        return f"⚠️ No has configurado la API Key para *{provider.upper()}*.\n\nPor favor usa el comando `/key` para guardarla, o pulsa en el botón de configuración web para iniciar sesión de manera segura."

    if not model_name:
        if provider in MODELS and len(MODELS[provider]) > 0:
            model_name = MODELS[provider][0]
        else:
            model_name = "default"

    try:
        # Add user prompt to history
        add_message(uid, "user", prompt)
        hist = get_history(uid)

        if provider == "gemini":
            genai.configure(api_key=key)
            gemini_history = []
            for msg in hist[:-1]:
                g_role = "user" if msg["role"] == "user" else "model"
                gemini_history.append({"role": g_role, "parts": [msg["content"]]})
            
            model = genai.GenerativeModel(model_name)
            chat = model.start_chat(history=gemini_history)
            response = chat.send_message(prompt)
            result = response.text
            
        elif provider == "openai":
            client = OpenAI(api_key=key)
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in hist]
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            result = response.choices[0].message.content
            
        elif provider == "grok":
            client = OpenAI(api_key=key, base_url="https://api.x.ai/v1")
            messages = [{"role": msg["role"], "content": msg["content"]} for msg in hist]
            response = client.chat.completions.create(
                model=model_name,
                messages=messages
            )
            result = response.choices[0].message.content
            
        elif provider == "anthropic":
            client = Anthropic(api_key=key)
            anthropic_messages = []
            for msg in hist:
                role = "user" if msg["role"] == "user" else "assistant"
                anthropic_messages.append({"role": role, "content": msg["content"]})
            
            message = client.messages.create(
                model=model_name,
                max_tokens=2048,
                messages=anthropic_messages
            )
            result = message.content[0].text
        else:
            result = f"Error: Proveedor '{provider}' no soportado."
            
        # Add assistant response
        add_message(uid, "assistant", result)
        return result

    except Exception as e:
        hist = get_history(uid)
        if hist and hist[-1]["content"] == prompt:
            hist.pop()
        return f"❌ *Error en {provider.upper()} ({model_name})*:\n`{str(e)}`"
