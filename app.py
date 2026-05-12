from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from functools import wraps, lru_cache
import secrets
import time
from database_setup import (
    initialize_database,
    authenticate_user,
    register_user,
    get_user_by_email,
    get_user_settings,
    set_user_setting,
    append_history,
    get_history,
    delete_history_item,
    clear_history,
    update_user_plan,
)
from main import Agent

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Performance optimizations
app.config['JSON_SORT_KEYS'] = False
app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

# Add performance headers
@app.after_request
def add_performance_headers(response):
    """Add headers to improve performance"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    # Enable gzip compression in production
    response.headers['Vary'] = 'Accept-Encoding'
    return response

initialize_database()

# Simple response caching for settings
_settings_cache = {}
_cache_timeout = 300  # 5 minutes

LANGUAGE_OPTIONS = ["English", "French", "German", "Kinyarwanda"]
PLAN_OPTIONS = ["basic", "pro", "promax"]
DEFAULT_SETTINGS = {
    "language": "English",
    "theme": "Light",
    "use_google": "No",
}

agent = Agent(
    name="sisky_ai",
    model="gemini-2.5-flash",
    instruction=(
        "You are a helpful AI assistant for entrepreneurs in Kigali. "
        "Use Google Search for current data when available. "
        "You speak English, French, German, and Kinyarwanda."
    ),
    tools=["google_search"],
)


def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session and "guest" not in session:
            return jsonify({"error": "Not authenticated"}), 401
        return f(*args, **kwargs)
    return decorated_function


def get_session_settings():
    """Get settings with simple caching to reduce DB queries"""
    if "user_id" in session:
        user_id = session["user_id"]
        cache_key = f"settings_{user_id}"
        
        # Check cache first
        if cache_key in _settings_cache:
            cached_data, timestamp = _settings_cache[cache_key]
            if time.time() - timestamp < _cache_timeout:
                return cached_data
        
        # Fetch from DB and cache
        settings = get_user_settings(user_id)
        _settings_cache[cache_key] = (settings, time.time())
        return settings
    
    settings = session.get("settings", DEFAULT_SETTINGS.copy())
    for key, value in DEFAULT_SETTINGS.items():
        settings.setdefault(key, value)
    return settings


def set_session_setting(key: str, value: str) -> None:
    """Set setting and invalidate cache"""
    if "user_id" in session:
        set_user_setting(session["user_id"], key, value)
        # Invalidate cache
        cache_key = f"settings_{session['user_id']}"
        if cache_key in _settings_cache:
            del _settings_cache[cache_key]
    else:
        session.setdefault("settings", DEFAULT_SETTINGS.copy())
        session["settings"][key] = value


def append_session_history(role: str, message: str) -> None:
    if "user_id" in session:
        append_history(session["user_id"], role, message)
        return
    history = session.get("history", [])
    next_id = (session.get("history_counter", 0) + 1)
    session["history_counter"] = next_id
    history.append({"id": next_id, "role": role, "message": message, "created_at": ""})
    session["history"] = history


def get_session_history() -> list:
    if "user_id" in session:
        return get_history(session["user_id"])
    return session.get("history", [])


def delete_session_history_item(history_id: int) -> None:
    if "user_id" in session:
        delete_history_item(session["user_id"], history_id)
        return
    history = session.get("history", [])
    session["history"] = [item for item in history if item["id"] != history_id]


def clear_session_history() -> None:
    if "user_id" in session:
        clear_history(session["user_id"])
        return
    session["history"] = []


def set_session_plan(plan: str) -> None:
    if "user_id" in session:
        update_user_plan(session["user_id"], plan)
    session["plan"] = plan


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    confirm_password = data.get("confirm_password", "")
    plan = data.get("plan", "basic")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    if password != confirm_password:
        return jsonify({"error": "Passwords do not match"}), 400

    if get_user_by_email(email):
        return jsonify({"error": "Account already exists"}), 400

    user = register_user(email, password, plan)
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["plan"] = user["plan"]
    return jsonify({"success": True, "user": user}), 201


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.json
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400

    user = authenticate_user(email, password)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401

    session.clear()
    session["user_id"] = user["id"]
    session["email"] = user["email"]
    session["plan"] = user["plan"]
    return jsonify({"success": True, "user": user}), 200


@app.route("/api/auth/skip", methods=["POST"])
def api_skip():
    session.clear()
    session["guest"] = True
    session["email"] = "Guest"
    session["plan"] = "basic"
    session["settings"] = DEFAULT_SETTINGS.copy()
    session["history"] = []
    session["history_counter"] = 0
    return jsonify({"success": True, "guest": True, "email": "Guest", "plan": "basic"}), 200


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True}), 200


@app.route("/api/auth/session", methods=["GET"])
def api_session():
    if "user_id" not in session and "guest" not in session:
        return jsonify({"authenticated": False}), 200
    return jsonify({
        "authenticated": True,
        "guest": session.get("guest", False),
        "user_id": session.get("user_id"),
        "email": session.get("email"),
        "plan": session.get("plan", "basic"),
    }), 200


@app.route("/api/chat", methods=["POST"])
@auth_required
def api_chat():
    data = request.json
    prompt = data.get("message", "").strip()

    if not prompt:
        return jsonify({"error": "Message cannot be empty"}), 400

    settings = get_session_settings()
    try:
        # Add message to history (async-like, but synchronous for now)
        append_session_history("user", prompt)
        
        # Get response from agent (faster model, lower tokens by default)
        response = agent.respond(prompt, {**settings, "plan": session.get("plan", "basic")})
        
        # Add response to history
        append_session_history("assistant", response)
        
        return jsonify({"response": response}), 200
    except Exception as e:
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500


@app.route("/api/history", methods=["GET"])
@auth_required
def api_get_history():
    rows = get_session_history()
    return jsonify({"history": rows}), 200


@app.route("/api/history/<int:history_id>", methods=["DELETE"])
@auth_required
def api_delete_history(history_id):
    delete_session_history_item(history_id)
    return jsonify({"success": True}), 200


@app.route("/api/history/clear", methods=["POST"])
@auth_required
def api_clear_history():
    clear_session_history()
    return jsonify({"success": True}), 200


@app.route("/api/settings", methods=["GET"])
@auth_required
def api_get_settings():
    settings = get_session_settings()
    return jsonify({
        "settings": settings,
        "language_options": LANGUAGE_OPTIONS,
    }), 200


@app.route("/api/settings", methods=["PUT"])
@auth_required
def api_update_setting():
    data = request.json
    key = data.get("key")
    value = data.get("value")

    if not key or not value:
        return jsonify({"error": "Key and value required"}), 400

    set_session_setting(key, value)
    return jsonify({"success": True}), 200


@app.route("/api/payments", methods=["GET"])
@auth_required
def api_get_payments():
    plan = session.get("plan", "basic")
    return jsonify({
        "current_plan": plan,
        "plans": PLAN_OPTIONS,
        "features": {
            "basic": ["Free trial support", "Limited history"],
            "pro": ["Extended history", "Faster responses"],
            "promax": ["Priority support", "Advanced tools"],
        },
    }), 200


@app.route("/api/payments/upgrade", methods=["POST"])
@auth_required
def api_upgrade_plan():
    data = request.json
    new_plan = data.get("plan")

    if new_plan not in PLAN_OPTIONS:
        return jsonify({"error": "Invalid plan"}), 400

    set_session_plan(new_plan)
    return jsonify({"success": True, "new_plan": new_plan}), 200


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
