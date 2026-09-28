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


def get_gold_price():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.get(
        GOLD_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    html = response.text

    patterns = [
        r'data-col="info\.last_trade\.PDrCotVal">([\d,]+)',
        r'<span[^>]*class="[^"]*value[^"]*"[^>]*>([\d,]+)</span>',
        r'([\d,]{8,})'
    ]

    for pattern in patterns:
        match = re.search(pattern, html)

        if match:
            value = match.group(1).replace(",", "")
            price = int(value)

            # TGJU may provide the value in rial.
            # Convert to toman when needed.
            if price > 100_000_000:
                price = price // 10

            if 1_000_000 < price < 100_000_000:
                return price

    raise ValueError("Gold price not found")


def online_price_text():
    gold_price = get_gold_price()

    return f"""🟡 قیمت آنلاین طلای ۱۸ عیار / ۷۵۰

💰 هر گرم:
{money(gold_price)} تومان

منبع: TGJU"""


def calculate_price(weight, gold_price, labor_percent):
    gold_value = weight * gold_price

    labor = gold_value * labor_percent / 100

    total = gold_value + labor

    return f"""💎 قیمت نهایی

⚖️ وزن: {weight:g} گرم
🟡 قیمت هر گرم طلای ۱۸ عیار: {money(gold_price)} تومان
💰 طلای خام: {money(gold_value)} تومان
🔨 اجرت: {labor_percent:g}٪

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

برای مشاهده قیمت آنلاین طلا:
/online

برای محاسبه قیمت محصول:

/price وزن اجرت

مثال:
/price 9.51 5"""
        )

    elif text == "/online":
        try:
            send_message(
                chat_id,
                online_price_text()
            )

        except Exception as e:
            print("Gold price error:", e)

            send_message(
                chat_id,
                """❌ دریافت قیمت آنلاین طلا با خطا مواجه شد.

لطفاً چند لحظه بعد دوباره /online را ارسال کنید."""
            )

    elif text.startswith("/price"):
        try:
            parts = text.split()

            if len(parts) != 3:
                raise ValueError

            weight = float(
                parts[1].replace(",", ".")
            )

            labor_percent = float(
                parts[2].replace(",", ".")
            )

            if weight <= 0:
                raise ValueError

            if labor_percent < 0:
               
