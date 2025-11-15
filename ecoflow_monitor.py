import requests, time, hmac, hashlib
from urllib.parse import quote_plus

# ← ВСТАВ СВОЇ ДАНІ СЮДИ (копіюй прямо з developer.ecoflow.com і телеграм-бота)
ACCESS_KEY = "9gZHSt6akN4bnsSWyPdOYHNsDfftXwkD"          # ← твій
SECRET_KEY = "iD1BP5w76HLbvV2erbq8CNWTK6MBp4HP"   # ← твій
SERIAL = "R351ZEB4HG490907"                            # ← твій
TELEGRAM_TOKEN = "8387721988:AAEKwg4Gj0-7pBD8JMjYkMU1GwCEAAkAzEk"               # ← твій
CHAT_ID = 317004830                                    # ← твій (число)

URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
last = None

def send(t):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": t}, timeout=10)
    except:
        pass

send("Хардкод версія запущена – зараз буде правда")

while True:
    try:
        p = {
            "accessKey": ACCESS_KEY,
            "nonce": str(int(time.time()*1000))[:13],
            "timestamp": int(time.time()*1000),
            "sn": SERIAL
        }
        s = "&".join(f"{k}={quote_plus(str(v))}" for k, v in sorted(p.items()))
        sign = hmac.new(SECRET_KEY.encode(), f"{s}&{SECRET_KEY}".encode(), hashlib.sha256).hexdigest()
        p["sign"] = sign

        r = requests.post(URL, json=p, headers={"User-Agent": "Mozilla/5.0"}, timeout=15).json()

        if r.get("code") != "0":
            send(f"EcoFlow помилка: {r.get('message')}")
            time.sleep(60)
            continue

        pd = r.get("data", {})
        if not pd and "quotaList" in r:
            for q in r["quotaList"]:
                if q.get("sn") == SERIAL:
                    pd = q.get("data", {})

        win = pd.get("wattsIn", 0) or pd.get("pd", {}).get("wattsIn", 0)
        wout = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)

        send(f"Успіх!\nЗарядка: {win}W\nНавантаження: {wout}W")

        state = "charging" if win >= 10 else "discharging" if wout >= 10 else "idle"
        if state != "idle" and state != last:
            send("СВІТЛО Є!" if state == "charging" else "СВІТЛА НЕМАЄ!")
            last = state

        time.sleep(65)
    except Exception as e:
        send(f"Помилка: {e}")
        time.sleep(65)
