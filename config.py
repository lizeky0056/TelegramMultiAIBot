import json
import os
import uuid
import time

DB_PATH = os.path.join(os.path.dirname(__file__), "db.json")
TOKENS_PATH = os.path.join(os.path.dirname(__file__), "tokens.json")

def load_db():
    if not os.path.exists(DB_PATH):
        return {}
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_db(db):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving DB: {e}")

def get_user_config(user_id):
    db = load_db()
    uid = str(user_id)
    if uid not in db:
        db[uid] = {
            "current_provider": "gemini",
            "api_keys": {
                "gemini": "",
                "openai": "",
                "anthropic": "",
                "grok": ""
            },
            "selected_models": {
                "gemini": "gemini-1.5-flash",
                "openai": "gpt-4o-mini",
                "anthropic": "claude-3-5-haiku-latest",
                "grok": "grok-2-1212"
            }
        }
        save_db(db)
    return db[uid]

def save_user_config(user_id, config):
    db = load_db()
    db[str(user_id)] = config
    save_db(db)

def load_tokens():
    if not os.path.exists(TOKENS_PATH):
        return {}
    try:
        with open(TOKENS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_tokens(tokens):
    try:
        with open(TOKENS_PATH, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving tokens: {e}")

def generate_login_token(user_id):
    tokens = load_tokens()
    # Clean expired tokens (> 30 mins)
    now = time.time()
    tokens = {k: v for k, v in tokens.items() if now - v["created_at"] < 1800}
    
    token = str(uuid.uuid4())
    tokens[token] = {
        "user_id": str(user_id),
        "created_at": now
    }
    save_tokens(tokens)
    return token

def get_user_by_token(token):
    tokens = load_tokens()
    now = time.time()
    if token in tokens:
        data = tokens[token]
        if now - data["created_at"] < 1800:
            return data["user_id"]
    return None

def consume_token(token):
    tokens = load_tokens()
    if token in tokens:
        del tokens[token]
        save_tokens(tokens)

def validate_login_token(token):
    tokens = load_tokens()
    now = time.time()
    # Clean expired tokens
    tokens = {k: v for k, v in tokens.items() if now - v["created_at"] < 1800}
    
    if token in tokens:
        data = tokens[token]
        user_id = data["user_id"]
        # Delete token after validation
        del tokens[token]
        save_tokens(tokens)
        return user_id
    return None
