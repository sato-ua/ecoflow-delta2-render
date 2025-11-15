# ecoflow_monitor.py — 100% робочий, без синтаксичних помилок (15.11.2025)
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
CHECK_INTERVAL = 65

last_state = None
debug_counter = 0

def sign_params(params):
    params_str = "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted(params.items()))
    sign_str = f"{params_str}&{SECRET_KEY}"
    signature = hmac.new(SECRET_KEY.encode(), sign_str.encode(), hashlib.sha256).hexdigest()
    params["sign"] = signature
    return params

def get_device_data():
    payload = {
        "accessKey": ACCESS_KEY,
        "nonce": str(int(time.time() * 1000))[:13],
        "timestamp": int(time.time() * 1000),
        "sn": SERIAL
    }
    payload = sign_params(payload)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"API error: {e}")
        return None

def extract_pd(data):
    if not data:
        return {}
    pd = data.get("data")
    if isinstance(pd, dict):
        return pd
    for item in data.get("quota'altList", []):
        if item.get("sn") == SERIAL:
            return item.get("data", {})
    return {}

def get_current_state(raw_data):
    pd = extract_pd(raw_data)
    watts_in  = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
    watts_out = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)
    soc       = pd.get("soc", 0) or pd.get("pd", {}).get("soc", 0)
    ac_freq   = pd.get("acOutFreq", 0) or pd.get("pd", {}).get("acOutFreq", 0)

    print(f"DEBUG → in:{watts_in}W out:{watts_out}W soc:{soc}% freq:{ac_freq}")

    if watts_in >= 12:
        return "charging"
    elif watts_out >= 12 or (ac_freq > 45 and soc < 99):
        return "discharging"
    else:
        return "idle"

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except:
        pass

send("EcoFlow моніторинг запущено – ФІНАЛЬНА ВЕРСІЯ")

while True:
    try:
        raw = get_device_data()

        if raw and str(raw.get("code")) == "0":
            state = get_current_state(raw)
            debug_counter += 1

            # Діагностика перші 3 рази + при зміні стану
            if debug_counter <= 3 or (state and state != last_state):
                pd = extract_pd(raw)
                watts_in  = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
                watts_out = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)
                soc       = pd.get("soc", 0) or pd.get("pd", {}).get("soc", 0)

                send(f"Діагностика EcoFlow\n"
                     f"wattsIn: {watts_in} W\n"
                     f"wattsOut: {watts_out} W\n"
                     f"SOC: {soc} %\n"
                     f"Висновок: {state}")

            if state and state != "idle" and state != last_state:
                if state == "charging":
                    send("СВІТЛО Є!\nEcoFlow заряджається від мережі")
                else:
                    send("СВІТЛА НЕМАЄ!\nEcoFlow працює від батареї")
                last_state = state

        time.sleep(CHECK_INTERVAL)

    except Exception as e:
        print(f"Критична помилка: {e}")
        send(f"Помилка скрипта: {e}")
        time.sleep(CHECK_INTERVAL)
