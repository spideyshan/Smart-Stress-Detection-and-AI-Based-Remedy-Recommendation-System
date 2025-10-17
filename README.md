Smart Stress Detection and AI-Based Remedy Recommendation System

An IoT-powered wellness project that detects human stress levels in real time using **NodeMCU** sensors and provides **AI-generated stress remedies** through a Flask-based web dashboard.

---

## 📖 Overview

The **Smart Stress Detection and AI-Based Remedy Recommendation System** combines IoT and Artificial Intelligence to help monitor and manage stress effectively.

- The system uses **two NodeMCU boards**:
  - One measures **heart rate (BPM)**.
  - Another measures **body/skin temperature**.
- The devices send data to a **Flask server** hosted on a local machine (e.g., your MacBook).
- The server computes a **stress index** and classifies the user’s state as:
  - 🟢 *Relaxed*
  - 🟡 *Normal*
  - 🔴 *Stressed*
- Every 20 seconds, an **AI model (OpenAI GPT)** generates a short, personalized, non-medical stress-relief recommendation.
- The web dashboard updates automatically every 7 seconds to display the latest readings and AI suggestions.

---

## 🏗️ System Architecture

[ Pulse NodeMCU ] --->|
|--> Flask Server --> AI Remedy (OpenAI API) --> Web Dashboard
[ Temp NodeMCU ] ---->|

yaml
Copy code

- **Hardware:** NodeMCU (ESP8266), optional Pulse and Temperature sensors  
- **Network:** Wi-Fi communication over HTTP (local IP)  
- **Software:** Python (Flask, OpenAI SDK), HTML/CSS/JS for dashboard  
- **AI Integration:** OpenAI API (GPT models) for remedy generation  

---

## ⚙️ Features

✅ Real-time stress detection using heart rate and temperature  
✅ AI-generated stress-relief suggestions (updated every 20 seconds)  
✅ Auto-refresh dashboard (7 seconds)  
✅ Manual refresh and copy buttons  
✅ JSON API endpoints for developers  
✅ Simple to deploy on macOS/Linux/Windows  


---

## 🖥️ Installation (macOS Example)

### 1. Clone or download this repository
```bash
git clone https://github.com/<yourname>/smart_stress.git
cd smart_stress
2. Create and activate a virtual environment
bash
Copy code
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
bash
Copy code
pip install -r requirements.txt
If you don’t have a requirements.txt, install manually:

bash
Copy code
pip install flask flask-cors openai
4. Set your OpenAI API key (replace with your actual key)
bash
Copy code
export OPENAI_API_KEY="sk-xxxxxxxxxxxxxxxx"
export OPENAI_MODEL="gpt-3.5-turbo"  # or gpt-4o if available
(To make it permanent, add these lines to your ~/.zshrc.)

5. Run the Flask server
bash
Copy code
python app.py
