import requests, time, hmac, hashlib
from urllib.parse import quote_plus as qp

# ТВОЇ ДАНІ (вже перевірені, працюють)
ACCESS_KEY = "9gZHSt6akN4bnsSWyPdOYHNsDfftXwkD"
SECRET_KEY = "iD1BP5w76HLbvV2erbq8CNWTK6MBp4HP"
SERIAL = "R351ZEB4HG490907"
TELEGRAM_TOKEN = "8387721988:AAEKwg4Gj0-7pBD8JMjYkMU1GwCEAAkAzEk"
CHAT_ID = 317004830

URL = "https://api.ecoflow.com/iot-open/sign/device/quota"
last = None

def send(t):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
                      data={"chat_id": CHAT_ID, "text": t}, timeout=10)
    except:
        pass

send("EcoFlow моніторинг запущено назавжди")

while True:
    try:
        p = {
            "accessKey": ACCESS_KEY,
            "nonce": str(int(time.time()*1000))[:13],
            "timestamp": int(time.time()*1000),
            "sn": SERIAL
        }
        s = "&".join(f"{k}={qp(str(v))}" for k, v in sorted(p.items()))
        p["sign"] = hmac.new(SECRET_KEY.encode(), f"{s}&{SECRET_KEY}".encode(), hashlib.sha256).hexdigest()

        r = requests.post(URL, json=p, headers={"User-Agent": "Mozilla/5.0"}).json()

        if r.get("code") != "0":
            send(f"Помилка EcoFlow: {r.get('message')}")
            time.sleep(60)
            continue

        pd = r.get("data", {})
        if not pd and "quotaList" in r:
            for item in r["quotaList"]:
                if item.get("sn") == SERIAL:
                    pd = item.get("data", {})

        win  = pd.get("wattsIn", 0)  or pd.get("pd", {}).get("wattsIn", 0)
        wout = pd.get("wattsOut", 0) or pd.get("pd", {}).get("wattsOut", 0)

        state = "charging" if win >= 10 else "discharging" if wout >= 10 else "idle"

        if state != "idle" and state != last:
            send("СВІТЛО Є!" if state == "charging" else "СВІТЛА НЕМАЄ!")
            last = state

        # Для впевненості — раз на 10 хвилин шлемо статус
        if int(time.time()) % 600 < 65:
            send(f"Статус: зарядка {win}W | вихід {wout}W")

        time.sleep(65)

    except Exception as e:
        send(f"Критична помилка: {e}")
        time.sleep(65)
