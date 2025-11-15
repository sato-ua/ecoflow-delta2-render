# ecoflow_monitor.py — МІНІМАЛЬНА робоча версія (гарантовано стартує)
import requests
import time
import hmac
import hashlib
from urllib.parse import quote_plus
import os

# ВКАЖИ СВОЇ ДАНІ ПРЯМО ТУТ (тимчасово, поки Railway не виправиться)
ACCESS_KEY = "9gZHSt6akN4bnsSWyPdOYHNsDfftXwkD"
SECRET_KEY = "iD1BP5w76HLbvV2erbq8CNWTK6MBp4HP"
SERIAL = "R351ZEB4HG490907"          # ← свій серійник
TELEGRAM_TOKEN = "8387721988:AAEKwg4Gj0-7pBD8JMjYkMU1GwCEAAkAzEk"   # ← свій токен
CHAT_ID = 317004830                 # ← свій chat_id (число)

# Якщо хочеш брати з змінних — раскоментуй рядки нижче (після виправлення Railway)
# ACCESS_KEY = os.getenv("ACCESS_KEY")
# SECRET_KEY = os.getenv("SECRET_KEY")
# SERIAL = os.getenv("SERIAL")
# TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
# CHAT_ID = int(os.getenv("CHAT_ID", 0))

API_URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
CHECK_INTERVAL = 65
last_state = None

def send(msg):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

def get_data():
    params = {
        "accessKey": ACCESS_KEY,
        "nonce": str(int(time.time()*1000))[:13],
        "timestamp": int(time.time()*1000),
        "sn": SERIAL
    }
    # підпис
    s = "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted(params.items()))
    sign = hmac.new(SECRET_KEY.encode(), f"{s}&{SECRET_KEY}".encode(), hashlib.sha256).hexdigest()
    params["sign"] = sign

    try:
        r = requests.post(API_URL, json=params,
                          headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                          timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        send(f"API помилка: {e}")
        return None

send("МІНІМАЛЬНА версія запущена – зараз перевірю EcoFlow")

while True:
    try:
        data = get_data()
        if not data:
            time.sleep(CHECK_INTERVAL)
            continue

        if data.get("code") != "0":
            send(f"EcoFlow помилка: {data.get('message')}")
            time.sleep(CHECK_INTERVAL)
            continue

        # шукаємо pd
        pd = data.get("data", {})
        if not pd and "quotaList" in data:
            for q in data["quotaList"]:
                if q.get("sn") == SERIAL:
                    pd = q.get("data", {})
                    break

        watts_in = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
        watts_out = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)

        send(f"Тест EcoFlow\nЗарядка: {watts_in}W\nНавантаження: {watts_out}W")

        state = "charging" if watts_in >= 10 else "discharging" if watts_out >= 10 else "idle"
        if state != "idle" and state != last_state:
            send("СВІТЛО Є!" if state == "charging" else "СВІТЛА НЕМАЄ!")
            last_state = state

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        send(f"Критична помилка: {e}")
        time.sleep(CHECK_INTERVAL)
