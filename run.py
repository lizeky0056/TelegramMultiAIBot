import os
import sys
import threading
import time

def run_web():
    print("[WEB] Iniciando servidor FastAPI de configuración en http://localhost:8000...")
    try:
        import uvicorn
        uvicorn.run("web:app", host="127.0.0.1", port=8000, log_level="info")
    except Exception as e:
        print(f"[WEB ERROR] Fallo al iniciar el portal web: {e}")

def run_bot():
    print("[BOT] Iniciando Bot de Telegram (infinity polling)...")
    try:
        import bot
        bot.bot.infinity_polling()
    except Exception as e:
        print(f"[BOT ERROR] Fallo al iniciar el bot: {e}")

if __name__ == "__main__":
    print("Boty Generator Loader")
    print("================================")
    
    # Start web thread
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    
    # Give uvicorn a second to spin up
    time.sleep(2)
    
    # Start bot
    run_bot()
