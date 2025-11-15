# ecoflow_monitor.py — ДІАГНОСТИЧНА версія БЕЗ global (працює 100%)
import requests
import time
import hmac
import hashlib
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os
import json

load_dotenv()

ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SERIAL = os.getenv("SERIAL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

API_URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
CHECK_INTERVAL = 65

last_state = None
diag_sent = 0          # просто глобальна змінна, без global

def sign_params(p):
    s = "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted(p.items()))
    sign = hmac.new(SECRET_KEY.encode(), f"{s}&{SECRET_KEY}".encode(), hashlib.sha256).hexdigest()
    p["sign"] = sign
    return p

def get_data():
    payload = sign_params({
        "accessKey": ACCESS_KEY,
        "nonce": str(int(time.time() * 1000))[:13],
        "timestamp": int(time.time() * 1000),
        "sn": SERIAL
    })
    try:
        r = requests.post(
            API_URL,
            json=payload,
            headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
            timeout=15
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("API error:", e)
        return None

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

send("ДІАГНОСТИЧНА версія запущена\nЗараз надішлю повну відповідь EcoFlow 2 рази")

while True:
    try:
        raw = get_data()

        # Надсилаємо повну відповідь перші 2 рази
        if raw and diag_sent < 2:
            pretty = json.dumps(raw, indent=2, ensure_ascii=False)
            if len(pretty) > 4000:
                pretty = pretty[:3990] + "\n... (обрізано)"
            send(f"<pre>Відповідь EcoFlow #{diag_sent+1}\n{pretty}</pre>")
            diag_sent += 1   # просто змінюємо змінну, без global

        # Звичайна логіка з дуже низькими порогами
        if raw and str(raw.get("code")) == "0":
            pd = {}
            if "data" in raw and isinstance(raw["data"], dict):
                pd = raw["data"]
            elif "quotaList" in raw:
                for item in raw["quotaList"]:
                    if item.get("sn") == SERIAL:
                        pd = item.get("data", {})

            watts_in  = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
            watts_out = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)
            soc       = pd.get("soc", 0) or pd.get("pd", {}).get("soc", 0)

            state = None
            if watts_in >= 8:
                state = "charging"
            elif watts_out >= 8 or soc < 99:
                state = "discharging"

            if state and state != last_state:
                if state == "charging":
                    send("СВІТЛО Є!\nEcoFlow заряджається")
                else:
                    send("СВІТЛА НЕМАЄ!\nEcoFlow на батареї")
                last_state = state

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Критична помилка:", e)
        send(f"Помилка: {e}")
        time.sleep(CHECK_INTERVAL)
