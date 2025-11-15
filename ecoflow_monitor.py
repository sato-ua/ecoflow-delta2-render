# ecoflow_monitor.py — остання версія з діагностикою (листопад 2025)
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

def sign_params(params: dict) -> dict:
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

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        r = requests.post(API_URL, json=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Помилка API: {e}")
        return None

def get_current_state(data):
    if not data or "data" not in data:
        return None

    pd = data["data"]
    watts_in = pd.get("pd.wattsIn", 0)
    watts_out = pd.get("pd.wattsOut", 0)
    soc = pd.get("pd.soc", 0)        # рівень заряду %
    ac_on = pd.get("pd.acOutFreq", 0) > 40  # якщо інвертор увімкнений — частота ~50 Гц

    print(f"DEBUG → wattsIn: {watts_in}W | wattsOut: {watts_out}W | SOC: {soc}% | AC on: {ac_on}")

    # Логіка 2025 року (перевірена на Delta 2 Max)
    if watts_in >= 15:                    # зарядка від мережі (зменшив поріг)
        return "charging"
    elif watts_out >= 15 or (ac_on and soc < 99):  # інвертор працює або розряджається
        return "discharging"
    else:
        return "idle"

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except:
        pass

send_telegram("EcoFlow моніторинг перезапущено з діагностикою")

while True:
    try:
        data = get_device_data()
        state = get_current_state(data)

        # Надсилаємо діагностику перші 3 цикли + при кожній зміні
        if data and (last_state is None or state != last_state):
            watts_in = data["data"].get("pd.wattsIn", 0)
            watts_out = data["data"].get("pd.wattsOut", 0)
            soc = data["data"].get("pd.soc", 0)
            debug_msg = (f"Діагностика EcoFlow:\n"
                         f"wattsIn: {watts_in} W\n"
                         f"wattsOut: {watts_out} W\n"
                         f"SOC: {soc} %\n"
                         f"Стан: {state}")
            send_telegram(debug_msg)

        if state and state != "idle" and state != last_state:
            if state == "charging":
                msg = "СВІТЛО З'ЯВИЛОСЬ!\nEcoFlow почав заряджатись"
            else:
                msg = "СВІТЛА НЕМАЄ!\nEcoFlow перейшов на батарею"

            send_telegram(msg)
            print(f"Сповіщення: {msg}")
            last_state = state

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print(f"Критична помилка: {e}")
        send_telegram(f"Помилка скрипта: {e}")
        time.sleep(CHECK_INTERVAL)
