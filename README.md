# 😈 Boty Generator Bot de Telegram 🤖🔥

Un sistema integral que corre un Bot de Telegram con soporte multimodelos y un portal web local para configurar tus API Keys de manera segura y visual.

## 🚀 Características principales
- **Multiproveedor**: Soporta **Google Gemini**, **ChatGPT (OpenAI)**, **Claude (Anthropic)** y **Grok (xAI)**.
- **Multimodelo**: Elige entre múltiples modelos para cada proveedor (ej. `gemini-2.5-flash`, `gpt-4o`, `claude-3-5-sonnet-latest`, etc.).
- **Memoria de Contexto**: El bot recuerda los últimos 10 turnos de chat para mantener una conversación fluida.
- **Panel Web Premium**: Configura tus API Keys y preferencias de forma visual con una interfaz interactiva de estilo oscuro con *glassmorphism*.
- **Acceso Temporal Seguro**: Inicia sesión mediante un token dinámico que expira tras 30 minutos.
- **Notificaciones Dinámicas**: El bot te avisa en Telegram cuando guardas los cambios en la web.

## 📂 Estructura del proyecto en `D:\TelegramMultiAIBot`
- `bot.py`: Lógica del bot de Telegram y comandos de interacción.
- `web.py`: Servidor FastAPI que hospeda la página web de configuración.
- `ai.py`: Capa de abstracción de llamadas a las APIs de IA con control de historial.
- `config.py`: Gestor de base de datos (`db.json`) y tokens temporales (`tokens.json`).
- `run.py`: Script unificado para iniciar el servidor FastAPI y el bot al mismo tiempo.
- `.env`: Contiene las variables del entorno (token del bot y URL local).

## ⚙️ Comandos del Bot
- `/start` o `/menu` - Muestra el menú principal y botones interactivos.
- `/login` o `/web` - Genera un enlace temporal de configuración web.
- `/provider` - Cambia el proveedor de IA activo.
- `/model` - Cambia el modelo activo del proveedor.
- `/key <API_KEY>` - Configura la key del proveedor activo directamente en el chat.
- `/status` - Muestra el proveedor y modelo activo, junto con las keys registradas.
- `/clear` - Limpia la memoria de conversación.
- `/help` - Muestra el menú de ayuda.

## 🛠️ Ejecución Manual
Para iniciar el sistema de forma manual en el futuro, abre una terminal en esta carpeta y corre:
```bash
# Activar entorno virtual
venv\Scripts\activate

# Iniciar bot y servidor web
python -u run.py
```
El portal de configuración se levantará automáticamente en `http://localhost:8000`.
