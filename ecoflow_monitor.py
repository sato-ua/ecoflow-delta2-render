# ecoflow_monitor.py
import requests
import time
import hmac
import hashlib
from urllib.parse import quote_plus
from dotenv import load_dotenv
import os

# Завантажуємо змінні з .env (Railway/Fly.io тощо)
load_dotenv()

ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
SERIAL = os.getenv("SERIAL")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Перевірка, що всі змінні є
if not all([ACCESS_KEY, SECRET_KEY, SERIAL, TELEGRAM_TOKEN, CHAT_ID]):
    print("Помилка: не вистачає змінних середовища!")
    exit(1)

API_URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
CHECK_INTERVAL = 60  # кожну хвилину

last_state = None  # "charging", "discharging", None

def sign_params(params: dict) -> dict:
    # Сортуємо і формуємо рядок для підпису
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    }

    try:
        # Тепер обов’язково POST + json у body
        r = requests.post(API_URL, json=params, headers=headers, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP помилка: {e} | Відповідь: {getattr(e.response, 'text', '')[:200]}")
        return None
    except Exception as e:
        print(f"Помилка з’єднання: {e}")
        return None

def get_current_state(data):
    if not data or "data" not in data:
        return None

    pd = data["data"]
    watts_in = pd.get("pd.wattsIn", 0)    # зарядка від мережі
    watts_out = pd.get("pd.wattsOut", 0)  # навантаження на інверторі

    if watts_in > 30:        # заряджається від мережі → світло Є
        return "charging"
    elif watts_out > 20:     # інвертор працює → світла НЕМАЄ
        return "discharging"
    else:
        return "idle"        # стоїть без справи

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_notification": False
    }
    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass  # не падаємо, якщо Telegram тимчасово недоступний

# === ЗАПУСК ===
print("EcoFlow Delta 2 Max моніторинг запущено...")
send_telegram("EcoFlow моніторинг запущено (Railway/Fly.io)")

while True:
    try:
        data = get_device_data()
        state = get_current_state(data)

        if state and state != "idle" and state != last_state:
            if state == "charging":
                msg = "СВІТЛО Є!\nEcoFlow почав заряджатись від мережі"
            else:
                msg = "СВІТЛА НЕМАЄ!\nEcoFlow перейшов на батарею (розряд)"

            send_telegram(msg)
            print(f"[{time.strftime('%H:%M:%S')}] {msg}")
            last_state = state

        time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        send_telegram("Моніторинг зупинено вручну")
        break
    except Exception as e:
        print(f"Невідома помилка: {e}")
        time.sleep(CHECK_INTERVAL)
