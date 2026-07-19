import json
import os
import uuid
import time
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")
TOKENS_PATH = os.path.join(os.path.dirname(__file__), "tokens.json")

# Token de sesión expira en 30 minutos
TOKEN_TTL = 1800

# Lock para evitar condiciones de carrera en escrituras simultáneas al JSON
_db_lock = threading.Lock()
_tokens_lock = threading.Lock()

# Cache en memoria para no leer el disco en cada mensaje
_db_cache: Optional[dict] = None
_db_cache_mtime: float = 0.0

def _read_json(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error leyendo {path}: {e}")
        return {}

def _write_json(path: str, data: dict) -> None:
    try:
        # Escritura atómica: primero a un archivo temporal, luego renombramos
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except IOError as e:
        logger.error(f"Error escribiendo {path}: {e}")

def load_db() -> dict:
    global _db_cache, _db_cache_mtime
    with _db_lock:
        try:
            mtime = os.path.getmtime(DB_PATH) if os.path.exists(DB_PATH) else 0
        except OSError:
            mtime = 0
        # Si el archivo no ha cambiado desde la última lectura, usamos caché
        if _db_cache is not None and mtime == _db_cache_mtime:
            return dict(_db_cache)
        _db_cache = _read_json(DB_PATH)
        _db_cache_mtime = mtime
        return dict(_db_cache)

def save_db(db: dict) -> None:
    global _db_cache, _db_cache_mtime
    with _db_lock:
        _write_json(DB_PATH, db)
        _db_cache = dict(db)
        try:
            _db_cache_mtime = os.path.getmtime(DB_PATH)
        except OSError:
            _db_cache_mtime = 0.0

DEFAULT_USER_CONFIG = {
    "current_provider": "gemini",
    "api_keys": {
        "gemini": "",
        "openai": "",
        "anthropic": "",
        "grok": ""
    },
    "selected_models": {
        "gemini": "gemini-2.5-flash",
        "openai": "gpt-4o-mini",
        "anthropic": "claude-sonnet-4-5",
        "grok": "grok-3-mini"
    }
}

def get_user_config(user_id) -> dict:
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {k: (v.copy() if isinstance(v, dict) else v) for k, v in DEFAULT_USER_CONFIG.items()}
        save_db(db)
    return db[uid]

def save_user_config(user_id, user_cfg: dict) -> None:
    db = load_db()
    db[str(user_id)] = user_cfg
    save_db(db)

# ── Tokens de sesión ────────────────────────────────────────────────────────

def _load_tokens() -> dict:
    with _tokens_lock:
        return _read_json(TOKENS_PATH)

def _save_tokens(tokens: dict) -> None:
    with _tokens_lock:
        _write_json(TOKENS_PATH, tokens)

def _clean_expired_tokens(tokens: dict) -> dict:
    now = time.time()
    return {k: v for k, v in tokens.items() if now - v["created_at"] < TOKEN_TTL}

def generate_login_token(user_id) -> str:
    tokens = _load_tokens()
    tokens = _clean_expired_tokens(tokens)
    token = str(uuid.uuid4())
    tokens[token] = {
        "user_id": str(user_id),
        "created_at": time.time()
    }
    _save_tokens(tokens)
    return token

def get_user_by_token(token: str) -> Optional[str]:
    tokens = _load_tokens()
    now = time.time()
    data = tokens.get(token)
    if data and now - data["created_at"] < TOKEN_TTL:
        return data["user_id"]
    return None

def consume_token(token: str) -> None:
    tokens = _load_tokens()
    if token in tokens:
        del tokens[token]
        _save_tokens(tokens)

def validate_login_token(token: str) -> Optional[str]:
    tokens = _load_tokens()
    tokens = _clean_expired_tokens(tokens)
    data = tokens.pop(token, None)
    _save_tokens(tokens)
    return data["user_id"] if data else None
