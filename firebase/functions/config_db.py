import os
import uuid
import time
from firebase_admin import firestore

# Retrieve firestore client
db = firestore.client()

def get_user_config(user_id):
    uid = str(user_id)
    doc_ref = db.collection("boty_users").document(uid)
    doc = doc_ref.get()
    
    if not doc.exists:
        default_config = {
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
        doc_ref.set(default_config)
        return default_config
    return doc.to_dict()

def save_user_config(user_id, config):
    uid = str(user_id)
    db.collection("boty_users").document(uid).set(config, merge=True)

def generate_login_token(user_id):
    uid = str(user_id)
    token = str(uuid.uuid4())
    now = time.time()
    
    db.collection("boty_tokens").document(token).set({
        "user_id": uid,
        "created_at": now
    })
    return token

def get_user_by_token(token):
    doc_ref = db.collection("boty_tokens").document(token)
    doc = doc_ref.get()
    if doc.exists:
        data = doc.to_dict()
        now = time.time()
        if now - data["created_at"] < 1800: # 30 mins
            return data["user_id"]
    return None

def consume_token(token):
    db.collection("boty_tokens").document(token).delete()
