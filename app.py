# app.py
from flask import Flask, request, jsonify, render_template, current_app as app
from flask_cors import CORS
import time
import os

# Use the new OpenAI client interface for openai>=1.0.0
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    app.logger.warning("OPENAI_API_KEY not set. /remedy will use canned fallback.")
    client = None
else:
    if OpenAI is None:
        app.logger.error("openai>=1.0.0 client library not available.")
        client = None
    else:
        # You may alternatively call OpenAI() with no args and rely on env var
        client = OpenAI(api_key=OPENAI_API_KEY)

# store latest readings per user
users = {}

# seconds between automatic remedy generations (server-side enforcement)
REMEDY_TTL = 20.0  # seconds

# Simple canned remedies used when OpenAI is not configured or call fails
CANNED_REMEDIES = [
    "1) Take three slow deep breaths (inhale 4s, hold 4s, exhale 6s). 2) Sit quietly and relax shoulders. 3) Take a short walk. Seek help if chest pain or fainting occurs.",
    "1) Do progressive muscle relaxation for 2 minutes. 2) Splash cool water on your face. 3) Breathe slowly for 60 seconds. See a doctor if palpitations persist.",
    "1) Try 5 minutes of focused breathing. 2) Reduce stimulants (caffeine) for the day. 3) Drink water and rest. If symptoms worsen, seek medical care."
]

def compute_stress_index(bpm, temp_c):
    if bpm is None or temp_c is None:
        return None
    try:
        bpm = float(bpm)
        temp_c = float(temp_c)
    except Exception:
        return None

    # avoid unrealistic low skin readings affecting normalization too much
    if temp_c < 34.0:
        temp_c = 34.0

    # normalize heart rate in approximate 60..120 range
    hr_norm = (bpm - 60.0) / (120.0 - 60.0)
    hr_norm = min(max(hr_norm, 0.0), 1.0)

    # normalize temperature in approximate 32..50 range
    temp_norm = (temp_c - 32.0) / (50.0 - 32.0)
    temp_norm = min(max(temp_norm, 0.0), 1.0)

    stress_index = 0.7 * hr_norm + 0.3 * temp_norm
    return stress_index

def classify_state(index):
    if index is None:
        return "Unknown"
    if index < 0.3:
        return "Relaxed"
    if index < 0.6:
        return "Normal"
    return "Stressed"

@app.route('/data', methods=['POST'])
def receive_data():
    try:
        d = request.get_json(force=True)
    except Exception as e:
        app.logger.exception("Invalid JSON in /data")
        return jsonify({"ok": False, "error": "Invalid JSON", "detail": str(e)}), 400

    role = d.get('role')
    user_id = d.get('user_id', 'user1')
    now = time.time()

    # Initialize user entry if needed
    if user_id not in users:
        users[user_id] = {
            "bpm": None,
            "temp": None,
            "ts_bpm": None,
            "ts_temp": None,
            "stress_index": None,
            "state": "Unknown",
            "remedy": None,
            "ts_remedy": None
        }

    # Accept pulse or temp roles
    if role == 'pulse' and 'bpm' in d:
        try:
            users[user_id]['bpm'] = float(d['bpm'])
            users[user_id]['ts_bpm'] = now
        except Exception:
            app.logger.exception("Invalid BPM value")
            return jsonify({"ok": False, "error": "Invalid bpm value"}), 400

    elif role == 'temp' and 'skin_temp_c' in d:
        try:
            users[user_id]['temp'] = float(d['skin_temp_c'])
            users[user_id]['ts_temp'] = now
        except Exception:
            app.logger.exception("Invalid temperature value")
            return jsonify({"ok": False, "error": "Invalid skin_temp_c value"}), 400
    else:
        return jsonify({"ok": False, "error": "invalid payload"}), 400

    # Compute stress if both readings are present
    if users[user_id]['bpm'] is not None and users[user_id]['temp'] is not None:
        si = compute_stress_index(users[user_id]['bpm'], users[user_id]['temp'])
        users[user_id]['stress_index'] = si
        users[user_id]['state'] = classify_state(si)

    return jsonify({"ok": True, "user_id": user_id, "state": users[user_id]['state']}), 200

@app.route('/latest_all')
def latest_all():
    # Return the whole users dict (safe for demo)
    return jsonify(users), 200

def generate_canned_remedy(user_id):
    # Basic simple canned remedy using user's state
    user = users.get(user_id, {})
    state = user.get('state', 'Unknown')
    bpm = user.get('bpm')
    temp = user.get('temp')
    idx = int(time.time()) % len(CANNED_REMEDIES)
    base = CANNED_REMEDIES[idx]
    return f"State: {state}. Readings: BPM={bpm}, Temp={temp}. Suggestions: {base}"

def extract_chat_text(resp):
    """
    Defensive extractor for chat completion responses.
    Returns a string (possibly empty) with the assistant's textual reply.
    Handles both new client object shapes and dict-like responses.
    """
    try:
        # dict-like response
        if isinstance(resp, dict):
            choices = resp.get("choices") or []
        else:
            choices = getattr(resp, "choices", None)
            if choices is None and hasattr(resp, "get"):
                # some SDKs return a Mapping-like object
                try:
                    choices = resp.get("choices", [])
                except Exception:
                    choices = None

        if not choices:
            return ""

        first = choices[0]

        # case: dict-like first choice
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict):
                return (msg.get("content") or "").strip()
            return (first.get("text") or "").strip()

        # case: object-like first choice
        msg_obj = getattr(first, "message", None)
        if msg_obj is not None:
            content = getattr(msg_obj, "content", None)
            if isinstance(content, str):
                return content.strip()
            if isinstance(msg_obj, dict):
                return (msg_obj.get("content") or "").strip()

        # fallback to .text attribute
        text_attr = getattr(first, "text", None)
        if isinstance(text_attr, str):
            return text_attr.strip()

        # last resort: stringify the response (short)
        return str(resp)[:1000].strip()
    except Exception:
        # Don't raise here; return empty string so caller can fallback
        return ""

@app.route('/remedy', methods=['POST'])
def remedy():
    """
    POST JSON: { "user_id": "user1" }
    Server caches remedy in users[user_id]['remedy'] and enforces REMEDY_TTL seconds between actual OpenAI calls.
    """
    try:
        d = request.get_json(force=True)
    except Exception as e:
        app.logger.exception("Invalid JSON in /remedy")
        return jsonify({"ok": False, "error": "Invalid JSON", "detail": str(e)}), 400

    user_id = d.get('user_id', 'user1')
    if not user_id:
        return jsonify({"ok": False, "error": "Missing field: user_id"}), 400

    if user_id not in users:
        return jsonify({"ok": False, "error": "unknown user"}), 404

    now = time.time()
    user = users[user_id]

    # TTL/caching check
    ts_remedy = user.get('ts_remedy')
    if ts_remedy is not None and (now - ts_remedy) < REMEDY_TTL:
        return jsonify({"ok": True, "user_id": user_id, "remedy": user.get('remedy'), "cached": True}), 200

    # If OpenAI client unavailable, return canned remedy
    if client is None:
        ai_text = generate_canned_remedy(user_id)
        user['remedy'] = ai_text
        user['ts_remedy'] = now
        return jsonify({"ok": True, "user_id": user_id, "remedy": ai_text, "cached": False, "note": "used_canned"}), 200

    # Build prompt/context
    prompt = (
        f"You are a helpful health assistant. Provide a short (max 4 bullet points or 3 sentences) "
        f"practical, non-medical stress-relief routine tailored to this person's readings.\n\n"
        f"Readings:\n"
        f"- User ID: {user_id}\n"
        f"- BPM: {user.get('bpm')}\n"
        f"- Skin temp (°C): {user.get('temp')}\n"
        f"- State: {user.get('state')}\n\n"
        "Give: 1) 3 quick actions they can do now, and 2) one brief note when to seek professional help. "
        "Keep tone calm and actionable."
    )

    # Call new OpenAI client: client.chat.completions.create(...)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a calm and concise health assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.6,
        )
    except Exception as e:
        # Log and fallback to canned remedy
        app.logger.exception("OpenAI call failed in /remedy")
        ai_text = generate_canned_remedy(user_id)
        user['remedy'] = ai_text
        user['ts_remedy'] = now
        return jsonify({"ok": True, "user_id": user_id, "remedy": ai_text, "cached": False, "note": "openai_failed_used_canned", "error": str(e)}), 200

    # Extract content defensively from the new response format
    try:
        ai_text = extract_chat_text(resp)
        if not ai_text:
            app.logger.error("OpenAI returned no usable text; full resp: %s", resp)
            ai_text = generate_canned_remedy(user_id)
    except Exception as e:
        app.logger.exception("Failed to parse OpenAI response")
        ai_text = generate_canned_remedy(user_id)

    # persist remedy
    try:
        user['remedy'] = ai_text
        user['ts_remedy'] = now
    except Exception as e:
        app.logger.exception("Failed to save remedy to users dict")
        return jsonify({
            "ok": True,
            "user_id": user_id,
            "remedy": ai_text,
            "cached": False,
            "warning": "Failed to persist to users storage: " + str(e)
        }), 200

    return jsonify({"ok": True, "user_id": user_id, "remedy": ai_text, "cached": False}), 200

@app.route('/')
def index():
    return render_template('index.html', users=users)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
