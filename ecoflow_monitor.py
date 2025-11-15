# ecoflow_monitor.py — ДІАГНОСТИЧНА версія (надсилає повну відповідь)
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
diag_sent = 0

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
        r = requests.post(API_URL, json=payload,
                          headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                          timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("API error:", e)
        return None

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

send("ДІАГНОСТИЧНА версія запущена\nЗараз надішлю повну відповідь EcoFlow 2 рази")

while True:
    try:
        raw = get_data()

        # Надсилаємо повну відповідь перші 2 рази
        global diag_sent
        if raw and diag_sent < 2:
            pretty = json.dumps(raw, indent=2, ensure_ascii=False)
            # Telegram обмежує 4096 символів → обрізаємо
            if len(pretty) > 4000:
                pretty = pretty[:3990] + "\n... (обрізано)"
            send(f"<pre>Повна відповідь EcoFlow #{diag_sent+1}\n{pretty}</pre>")
            diag_sent += 1

        # Звичайна логіка (з дуже низькими порогами)
        if raw and str(raw.get("code")) == "0":
            # шукаємо pd по всіх можливих шляхах
            pd = {}
            if "data" in raw and isinstance(raw["data"], dict):
                pd = raw["data"]
            elif "quotaList" in raw:
                for q in raw["quotaList"]:
                    if q.get("sn") == SERIAL and "data" in q:
                        pd = q["data"]

            watts_in  = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
            watts_out = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)
            soc       = pd.get("soc", 0) or pd.get("pd", {}).get("soc", 0)

            print(f"in:{watts_in} out:{watts_out} soc:{soc}")

            state = None
            if watts_in >= 8:               # дуже низький поріг
                state = "charging"
            elif watts_out >= 8 or soc < 99:
                state = "discharging"

            if state and state != last_state:
                if state == "charging":
                    send("СВІТЛО З'ЯВИЛОСЬ!\nEcoFlow заряджається")
                else:
                    send("СВІТЛО ЗНИКЛО!\nEcoFlow на батареї")
                last_state = state

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print("Критична помилка:", e)
        send(f"Помилка: {e}")
        time.sleep(CHECK_INTERVAL)
