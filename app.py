# app.py
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import time
import os
#import openai //Uncheck

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    print("WARNING: OPENAI_API_KEY not set. /remedy will fail without it.")
#openai.api_key = OPENAI_API_KEY //Uncheck

# store latest readings per user
users = {}

# seconds between automatic remedy generations (server-side enforcement)
REMEDY_TTL = 20.0  # seconds

def compute_stress_index(bpm, temp_c):
    if bpm is None or temp_c is None:
        return None
    try:
        bpm = float(bpm)
        temp_c = float(temp_c)
    except:
        return None

    if temp_c < 34.0:
        temp_c = 34.0

    hr_norm = (bpm - 60.0) / (120.0 - 60.0)
    hr_norm = min(max(hr_norm, 0.0), 1.0)

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
    d = request.get_json(force=True)
    role = d.get('role')
    user_id = d.get('user_id', 'user1')
    now = time.time()

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

    if role == 'pulse' and 'bpm' in d:
        users[user_id]['bpm'] = d['bpm']
        users[user_id]['ts_bpm'] = now
    elif role == 'temp' and 'skin_temp_c' in d:
        users[user_id]['temp'] = d['skin_temp_c']
        users[user_id]['ts_temp'] = now
    else:
        return jsonify({"ok": False, "error": "invalid payload"}), 400

    # Compute stress if both readings are present
    if users[user_id]['bpm'] is not None and users[user_id]['temp'] is not None:
        si = compute_stress_index(users[user_id]['bpm'], users[user_id]['temp'])
        users[user_id]['stress_index'] = si
        users[user_id]['state'] = classify_state(si)

    return jsonify({"ok": True, "user_id": user_id, "state": users[user_id]['state']})

@app.route('/latest_all')
def latest_all():
    # Return the whole users dict (safe for demo)
    return jsonify(users)

@app.route('/remedy', methods=['POST'])
def remedy():
    """
    POST JSON: { "user_id": "user1" }
    Server caches remedy in users[user_id]['remedy'] and enforces REMEDY_TTL seconds between actual OpenAI calls.
    """
    if OPENAI_API_KEY is None:
        return jsonify({"ok": False, "error": "OpenAI API key not configured on server"}), 500

    d = request.get_json(force=True)
    user_id = d.get('user_id', 'user1')

    if user_id not in users:
        return jsonify({"ok": False, "error": "unknown user"}), 404

    now = time.time()
    user = users[user_id]

    # If we have a cached remedy and it's fresh enough, return it (avoid calling OpenAI too often)
    ts_remedy = user.get('ts_remedy')
    if ts_remedy is not None and (now - ts_remedy) < REMEDY_TTL:
        return jsonify({"ok": True, "user_id": user_id, "remedy": user.get('remedy'), "cached": True})

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

    # try:
    #     resp = openai.ChatCompletion.create(
    #         model="gpt-4o-mini",
    #         messages=[
    #             {"role":"system","content":"You are a calm and concise health assistant."},
    #             {"role":"user","content":prompt}
    #         ],
    #         max_tokens=150,
    #         temperature=0.6,
    #     )
    #     ai_text = resp['choices'][0]['message']['content'].strip()
    # except Exception as e:
    #     return jsonify({"ok": False, "error": f"OpenAI call failed: {e}"}), 500

    # users[user_id]['remedy'] = ai_text
    # users[user_id]['ts_remedy'] = now

    # return jsonify({"ok": True, "user_id": user_id, "remedy": ai_text, "cached": False})
 ## Uncheck the whole
@app.route('/')
def index():
    return render_template('index.html', users=users)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
