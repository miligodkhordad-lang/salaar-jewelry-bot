import os
import re
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")
API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

GOLD_URL = "https://www.tgju.org/profile/geram18"


def money(number):
    return f"{int(round(number)):,}"


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def get_online_gold_price():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        GOLD_URL,
        headers=headers,
        timeout=20
    )
    response.raise_for_status()

    html = response.text

    patterns = [
        r'نرخ فعلی[^0-9]{0,100}([0-9][0-9,]{5,})',
        r'price[^0-9]{0,100}([0-9][0-9,]{5,})'
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)

        if match:
            price_rial = int(match.group(1).replace(",", ""))

            # کنترل ایمنی برای جلوگیری از قیمت غیرعادی
            if 50_000_000 <= price_rial <= 1_000_000_000:
                return price_rial / 10

    raise ValueError("Gold price not found")


def calculate_price(weight, gold_price, labor_percent, tax_percent):
    gold_value = weight * gold_price
    labor = gold_value * labor_percent / 100
    subtotal = gold_value + labor
    tax = subtotal * tax_percent / 100
    total = subtotal + tax

    if tax_percent == 0:
        tax_text = "❌ ندارد"
    else:
        tax_text = f"{money(tax)} تومان"

    return f"""💎 قیمت نهایی

⚖️ وزن: {weight} گرم
🟡 قیمت هر گرم طلای ۱۸ عیار: {money(gold_price)} تومان
💰 طلای خام: {money(gold_value)} تومان
🔨 اجرت: {labor_percent}٪
🧾 مالیات: {tax_text}

💰 قیمت نهایی:
{money(total)} تومان"""


def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "").strip()

    if not chat_id:
        return

    if text == "/start":
        send_message(
            chat_id,
            """👋 سلام

💎 ربات قیمت‌گذاری جواهری سالار

دریافت قیمت آنلاین:
/online

محاسبه آنلاین:
/price وزن اجرت

مثال:
/price 9.51 5"""
        )

    elif text == "/online":
        try:
            gold_price = get_online_gold_price()

            send_message(
                chat_id,
                f"""🟡 قیمت آنلاین طلای ۱۸ عیار / ۷۵۰

💰 هر گرم:
{money(gold_price)} تومان

منبع: TGJU"""
            )

        except Exception as e:
            print("Gold price error:", e)

            send_message(
                chat_id,
                """⚠️ دریافت قیمت آنلاین طلا ناموفق بود.

برای جلوگیری از محاسبه اشتباه، هیچ قیمتی نمایش داده نشد."""
            )

    elif text.startswith("/price"):
        try:
            parts = text.split()

            if len(parts) != 3:
                raise ValueError

            weight = float(parts[1])
            labor_percent = float(parts[2])

            if weight <= 0 or labor_percent < 0:
                raise ValueError

            gold_price = get_online_gold_price()

            result = calculate_price(
                weight,
                gold_price,
                labor_percent,
                0
            )

            send_message(chat_id, result)

        except ValueError:
            send_message(
                chat_id,
                """❌ دستور صحیح نیست.

مثال:
/price 9.51 5"""
            )

        except Exception as e:
            print("Price error:", e)

            send_message(
                chat_id,
                """⚠️ فعلاً قیمت آنلاین طلا دریافت نشد.

برای جلوگیری از اعلام قیمت اشتباه، محاسبه انجام نشد."""
            )


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN is missing")

    offset = 0

    print("Bale bot is running...")

    while True:
        try:
            response = requests.post(
                f"{API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": 20
                },
                timeout=30
            )

            data = response.json()

            if not data.get("ok"):
                print(data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message")

                if message:
                    handle_message(message)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
