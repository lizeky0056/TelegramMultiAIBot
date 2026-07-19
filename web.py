from fastapi import FastAPI, Form, Query, HTTPException
from fastapi.responses import HTMLResponse
import os
import config
from ai import MODELS
from dotenv import load_dotenv
import urllib.request
import urllib.parse

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8886104559:AAHclO0tYWadm4eMMrPB1C3PjQI6uqOps4U")

app = FastAPI(title="Boty Generator Telegram Config Panel")

LOGIN_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuración de Boty Generator</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(17, 24, 39, 0.75);
            --primary: #8b5cf6;
            --primary-glow: rgba(139, 92, 246, 0.4);
            --secondary: #ec4899;
            --text-color: #f3f4f6;
            --input-bg: rgba(31, 41, 55, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Outfit', sans-serif;
        }}
        
        body {{
            background: radial-gradient(circle at top right, #1e1b4b, var(--bg-color));
            color: var(--text-color);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
            overflow-x: hidden;
            position: relative;
        }}

        .g-sphere {{
            position: absolute;
            width: 400px;
            height: 400px;
            border-radius: 50%;
            background: var(--primary);
            filter: blur(150px);
            opacity: 0.12;
            z-index: 0;
            pointer-events: none;
        }}
        .g-sphere-1 {{ top: -5%; left: -5%; background: var(--secondary); }}
        .g-sphere-2 {{ bottom: -5%; right: -5%; }}

        .container {{
            position: relative;
            background: var(--card-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 28px;
            padding: 35px;
            width: 100%;
            max-width: 600px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            z-index: 10;
            animation: fadeIn 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(20px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        .header {{
            text-align: center;
            margin-bottom: 25px;
        }}

        .logo {{
            font-size: 2.2rem;
            font-weight: 800;
            background: linear-gradient(135deg, #a78bfa, var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 5px;
        }}

        .subtitle {{
            color: #9ca3af;
            font-size: 0.95rem;
        }}

        .form-group {{
            margin-bottom: 18px;
        }}

        label {{
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            font-size: 0.9rem;
            color: #d1d5db;
        }}

        .input-wrapper {{
            position: relative;
        }}

        input[type="password"], input[type="text"], select {{
            width: 100%;
            padding: 14px 16px;
            background: var(--input-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            color: #fff;
            font-size: 0.95rem;
            transition: all 0.3s;
            outline: none;
        }}

        input:focus, select:focus {{
            border-color: var(--primary);
            box-shadow: 0 0 12px var(--primary-glow);
        }}

        .provider-cards {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 12px;
            margin-bottom: 25px;
        }}

        .provider-card {{
            background: rgba(31, 41, 55, 0.3);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 16px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            user-select: none;
            position: relative;
            overflow: hidden;
        }}

        .provider-card:hover {{
            border-color: rgba(139, 92, 246, 0.4);
            background: rgba(31, 41, 55, 0.5);
            transform: translateY(-2px);
        }}

        .provider-card.active {{
            border-color: var(--primary);
            background: rgba(139, 92, 246, 0.15);
            box-shadow: 0 0 15px rgba(139, 92, 246, 0.25);
        }}

        .provider-card.active::after {{
            content: '✓';
            position: absolute;
            top: 5px;
            right: 12px;
            color: var(--primary);
            font-weight: bold;
            font-size: 1.2rem;
        }}

        .provider-name {{
            font-weight: 600;
            font-size: 1rem;
            margin-top: 4px;
        }}

        .section-title {{
            font-size: 1.1rem;
            font-weight: 600;
            margin: 25px 0 15px 0;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            color: #a78bfa;
        }}

        .btn-submit {{
            display: block;
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            border: none;
            border-radius: 12px;
            color: white;
            font-size: 1rem;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 15px rgba(236, 72, 153, 0.3);
            margin-top: 30px;
        }}

        .btn-submit:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(236, 72, 153, 0.5);
        }}

        .btn-submit:active {{
            transform: translateY(1px);
        }}

        .model-select-group {{
            display: none;
        }}

        .model-select-group.active {{
            display: block;
        }}

        .toggle-password {{
            position: absolute;
            right: 15px;
            top: 50%;
            transform: translateY(-50%);
            cursor: pointer;
            color: #9ca3af;
            font-size: 0.75rem;
            user-select: none;
            font-weight: bold;
            letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    <div class="g-sphere g-sphere-1"></div>
    <div class="g-sphere g-sphere-2"></div>

    <div class="container">
        <div class="header">
            <div class="logo">😈 Boty Generator 🤖</div>
            <div class="subtitle">Panel de Configuración de API Keys para tu Bot</div>
        </div>

        <form action="/save" method="POST">
            <input type="hidden" name="token" value="{token}">

            <div class="section-title">1. Selecciona tu Proveedor Activo</div>
            <input type="hidden" name="current_provider" id="current_provider" value="{current_provider}">
            <div class="provider-cards">
                <div class="provider-card {gemini_card_active}" onclick="selectProvider('gemini')">
                    <div class="provider-name">Google Gemini</div>
                </div>
                <div class="provider-card {openai_card_active}" onclick="selectProvider('openai')">
                    <div class="provider-name">ChatGPT (OpenAI)</div>
                </div>
                <div class="provider-card {anthropic_card_active}" onclick="selectProvider('anthropic')">
                    <div class="provider-name">Claude (Anthropic)</div>
                </div>
                <div class="provider-card {grok_card_active}" onclick="selectProvider('grok')">
                    <div class="provider-name">Grok (xAI)</div>
                </div>
            </div>

            <div class="section-title">2. API Keys de Acceso</div>
            
            <div class="form-group">
                <label>Gemini API Key</label>
                <div class="input-wrapper">
                    <input type="password" name="key_gemini" value="{key_gemini}" placeholder="AIzaSy...">
                    <span class="toggle-password" onclick="toggleVisibility(this)">VER</span>
                </div>
            </div>

            <div class="form-group">
                <label>OpenAI API Key</label>
                <div class="input-wrapper">
                    <input type="password" name="key_openai" value="{key_openai}" placeholder="sk-proj-...">
                    <span class="toggle-password" onclick="toggleVisibility(this)">VER</span>
                </div>
            </div>

            <div class="form-group">
                <label>Claude API Key</label>
                <div class="input-wrapper">
                    <input type="password" name="key_anthropic" value="{key_anthropic}" placeholder="sk-ant-...">
                    <span class="toggle-password" onclick="toggleVisibility(this)">VER</span>
                </div>
            </div>

            <div class="form-group">
                <label>Grok API Key</label>
                <div class="input-wrapper">
                    <input type="password" name="key_grok" value="{key_grok}" placeholder="xai-...">
                    <span class="toggle-password" onclick="toggleVisibility(this)">VER</span>
                </div>
            </div>

            <div class="section-title">3. Selecciona el Modelo Activo</div>

            <div id="models-gemini" class="form-group model-select-group {gemini_models_active}">
                <label>Modelo Gemini</label>
                <select name="model_gemini">
                    {gemini_model_options}
                </select>
            </div>

            <div id="models-openai" class="form-group model-select-group {openai_models_active}">
                <label>Modelo ChatGPT</label>
                <select name="model_openai">
                    {openai_model_options}
                </select>
            </div>

            <div id="models-anthropic" class="form-group model-select-group {anthropic_models_active}">
                <label>Modelo Claude</label>
                <select name="model_anthropic">
                    {anthropic_model_options}
                </select>
            </div>

            <div id="models-grok" class="form-group model-select-group {grok_models_active}">
                <label>Modelo Grok</label>
                <select name="model_grok">
                    {grok_model_options}
                </select>
            </div>

            <button type="submit" class="btn-submit">Guardar Configuración ✨</button>
        </form>
    </div>

    <script>
        function selectProvider(prov) {{
            document.getElementById('current_provider').value = prov;
            
            const cards = document.querySelectorAll('.provider-card');
            cards.forEach(c => c.classList.remove('active'));
            event.currentTarget.classList.add('active');
            
            const dropdowns = document.querySelectorAll('.model-select-group');
            dropdowns.forEach(d => d.classList.remove('active'));
            document.getElementById('models-' + prov).classList.add('active');
        }}

        function toggleVisibility(btn) {{
            const input = btn.previousElementSibling;
            if (input.type === "password") {{
                input.type = "text";
                btn.textContent = "OCULTAR";
            }} else {{
                input.type = "password";
                btn.textContent = "VER";
            }}
        }}
    </script>
</body>
</html>"""

SUCCESS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Configuración Guardada</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;700&display=swap" rel="stylesheet">
    <style>
        body {{
            background: #0b0f19;
            color: #fff;
            font-family: 'Outfit', sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }}
        .card {{
            background: rgba(17, 24, 39, 0.7);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            max-width: 450px;
        }}
        .icon {{
            font-size: 4rem;
            margin-bottom: 20px;
            animation: pulse 1.5s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(1); }}
            50% {{ transform: scale(1.1); }}
            100% {{ transform: scale(1); }}
        }}
        h2 {{ margin-bottom: 10px; background: linear-gradient(135deg, #a78bfa, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        p {{ color: #9ca3af; font-size: 0.95rem; line-height: 1.5; }}
    </style>
    <script>
        setTimeout(function() {{
            window.location.href = "https://t.me/Boty_generatorbot";
        }}, 2500);
    </script>
</head>
<body>
    <div class="card">
        <div class="icon">✨</div>
        <h2>¡Configuración Guardada!</h2>
        <p>Tus API Keys y preferencias se han actualizado con éxito en el sistema.<br>Redireccionando de vuelta a Telegram...</p>
    </div>
</body>
</html>"""

def make_options(provider, selected):
    opts = []
    for model in MODELS.get(provider, []):
        sel = "selected" if model == selected else ""
        opts.append(f'<option value="{model}" {sel}>{model}</option>')
    return "\n".join(opts)

def notify_user_via_bot(user_id, message):
    if not BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": user_id,
            "text": message,
            "parse_mode": "Markdown"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Error sending bot notification: {e}")

@app.get("/login", response_class=HTMLResponse)
def login(token: str = Query(...)):
    user_id = config.get_user_by_token(token)
    if not user_id:
        return HTMLResponse("<h2>⚠️ Token de acceso inválido o expirado.</h2><p>Por favor solicita un nuevo link en el bot con el comando /login.</p>", status_code=400)
    
    cfg = config.get_user_config(user_id)
    
    # Fill in formatting variables
    prov = cfg.get("current_provider", "gemini")
    api_keys = cfg.get("api_keys", {})
    selected_models = cfg.get("selected_models", {})
    
    html = LOGIN_HTML_TEMPLATE.format(
        token=token,
        current_provider=prov,
        gemini_card_active="active" if prov == "gemini" else "",
        openai_card_active="active" if prov == "openai" else "",
        anthropic_card_active="active" if prov == "anthropic" else "",
        grok_card_active="active" if prov == "grok" else "",
        key_gemini=api_keys.get("gemini", ""),
        key_openai=api_keys.get("openai", ""),
        key_anthropic=api_keys.get("anthropic", ""),
        key_grok=api_keys.get("grok", ""),
        gemini_models_active="active" if prov == "gemini" else "",
        openai_models_active="active" if prov == "openai" else "",
        anthropic_models_active="active" if prov == "anthropic" else "",
        grok_models_active="active" if prov == "grok" else "",
        gemini_model_options=make_options("gemini", selected_models.get("gemini", "gemini-1.5-flash")),
        openai_model_options=make_options("openai", selected_models.get("openai", "gpt-4o-mini")),
        anthropic_model_options=make_options("anthropic", selected_models.get("anthropic", "claude-3-5-haiku-latest")),
        grok_model_options=make_options("grok", selected_models.get("grok", "grok-2-1212"))
    )
    return html

@app.post("/save", response_class=HTMLResponse)
def save_config(
    token: str = Form(...),
    current_provider: str = Form(...),
    key_gemini: str = Form(""),
    key_openai: str = Form(""),
    key_anthropic: str = Form(""),
    key_grok: str = Form(""),
    model_gemini: str = Form(""),
    model_openai: str = Form(""),
    model_anthropic: str = Form(""),
    model_grok: str = Form("")
):
    user_id = config.get_user_by_token(token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Token inválido o expirado")
        
    cfg = config.get_user_config(user_id)
    cfg["current_provider"] = current_provider
    cfg["api_keys"]["gemini"] = key_gemini.strip()
    cfg["api_keys"]["openai"] = key_openai.strip()
    cfg["api_keys"]["anthropic"] = key_anthropic.strip()
    cfg["api_keys"]["grok"] = key_grok.strip()
    
    if model_gemini:
        cfg["selected_models"]["gemini"] = model_gemini
    if model_openai:
        cfg["selected_models"]["openai"] = model_openai
    if model_anthropic:
        cfg["selected_models"]["anthropic"] = model_anthropic
    if model_grok:
        cfg["selected_models"]["grok"] = model_grok
        
    config.save_user_config(user_id, cfg)
    
    # Notify user on Telegram
    prov_label = current_provider.upper()
    active_model = cfg["selected_models"].get(current_provider, "default")
    message = (
        f"✅ *¡Configuración cargada exitosamente!*\n\n"
        f"🔌 *Proveedor Activo*: {prov_label}\n"
        f"🤖 *Modelo Activo*: `{active_model}`\n\n"
        f"Ya puedes escribirme cualquier cosa y te responderé con este modelo."
    )
    notify_user_via_bot(user_id, message)
    
    # Consume token
    config.consume_token(token)
    
    return SUCCESS_HTML_TEMPLATE
