import requests
import time
import hmac
import hashlib
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SERIAL = os.getenv("SERIAL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
CHECK_INTERVAL = 60

last_state = None

def sign_params(params):
    params_str = "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted(params.items()))
    sign_str = f"{params_str}&{SECRET_KEY}"
    signature = hmac.new(SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    return params

def get_device_data():
    params = {
        "accessKey": ACCESS_KEY,
        "nonce": str(int(time.time() * 1000))[:13],
        "timestamp": int(time.time() * 1000),
        "sn": SERIAL
    }
    params = sign_params(params)
    try:
        r = requests.get(API_URL, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"API error: {e}")
        return None

def get_state(data):
    if not data or "data" not in data:
        return None
    watts_in = data["data"].get("pd.wattsIn", 0)
    watts_out = data["data"].get("pd.wattsOut", 0)
    
    if watts_in > 30:
        return "charging"
    elif watts_out > 20:
        return "discharging"
    else:
        return "idle"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

send_telegram("EcoFlow моніторинг запущено ✅")

print("Моніторинг запущено...")

while True:
    try:
        data = get_device_data()
        state = get_state(data)
        
        if state and state != "idle" and state != last_state:
            if state == "charging":
                msg = "⚡ СВІТЛО Є!\nEcoFlow Delta 2 Max почав заряджатись від мережі"
            else:
                msg = "⚫ СВІТЛА НЕМАЄ!\nEcoFlow перейшов на батарею"
            
            send_telegram(msg)
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")
            last_state = state
        
        time.sleep(CHECK_INTERVAL)
        
    except Exception as e:
        print(f"Помилка: {e}")
        time.sleep(CHECK_INTERVAL)
