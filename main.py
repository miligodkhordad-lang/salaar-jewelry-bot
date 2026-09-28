import os
import re
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

GOLD_URL = "https://www.tgju.org/profile/geram18"


def money(number):
    return f"{int(round(number)):,}"


def send_message(chat_id, text):
    response = requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )

    print(
        "sendMessage:",
        response.status_code,
        flush=True
    )

    return response


def get_gold_price():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 10; Mobile) "
            "AppleWebKit/537.36 "
            "Chrome/120.0 Mobile Safari/537.36"
        )
    }

    response = requests.get(
        GOLD_URL,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    html = response.text

    patterns = [
        r'data-col="info\.last_trade\.PDrCotVal"[^>]*>([\d,]+)<',
        r'<span[^>]*class="[^"]*value[^"]*"[^>]*>([\d,]+)</span>',
        r'"p"\s*:\s*"([\d,]+)"'
    ]

    for pattern in patterns:
        match = re.search(pattern, html)

        if match:
            raw_price = match.group(1).replace(",", "")
            price = int(raw_price)

            # TGJU ممکن است قیمت را به ریال برگرداند
            if price > 100_000_000:
                price = price / 10

            if 1_000_000 < price < 100_000_000:
                return price

    numbers = re.findall(
        r'\b\d{7,10}\b',
        html.replace(",", "")
    )

    for item in numbers:
        price = int(item)

        if price > 100_000_000:
            price = price / 10

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
    labor_value = gold_value * labor_percent / 100
    total = gold_value + labor_value

    return f"""💎 قیمت نهایی

⚖️ وزن: {weight:g} گرم

🟡 قیمت هر گرم طلای ۱۸ عیار:
{money(gold_price)} تومان

💰 طلای خام:
{money(gold_value)} تومان

🔨 اجرت: {labor_percent:g}٪
{money(labor_value)} تومان

💰 قیمت نهایی:
{money(total)} تومان

🌱 @salar_jewelry"""


def start_text():
    return """👋 سلام
به ربات جواهری سالار خوش آمدید.

🟡 مشاهده قیمت آنلاین طلا:
/online

💎 محاسبه قیمت محصول:
/price وزن اجرت

مثال:
/price 9.51 5"""


def help_text():
    return """💎 راهنمای ربات جواهری سالار

برای مشاهده قیمت آنلاین طلای ۱۸ عیار:
/online

برای محاسبه قیمت محصول:

/price وزن اجرت

مثال:

/price 9.51 5

یعنی:
⚖️ وزن: 9.51 گرم
🔨 اجرت: 5 درصد"""


def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")

    text = (
        message.get("text") or ""
    ).strip()

    if not chat_id:
        return

    if text == "/start":
        send_message(
            chat_id,
            start_text()
        )

    elif text == "/help":
        send_message(
            chat_id,
            help_text()
        )

    elif text == "/online":
        try:
            result = online_price_text()

            send_message(
                chat_id,
                result
            )

        except Exception as e:
            print(
                "Gold price error:",
                repr(e),
                flush=True
            )

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
                raise ValueError

            gold_price = get_gold_price()

            result = calculate_price(
                weight,
                gold_price,
                labor_percent
            )

            send_message(
                chat_id,
                result
            )

        except ValueError:
            send_message(
                chat_id,
                """❌ اطلاعات وارد شده صحیح نیست.

فرمت صحیح:

/price وزن اجرت

مثال:

/price 9.51 5"""
            )

        except Exception as e:
            print(
                "Price error:",
                repr(e),
                flush=True
            )

            send_message(
                chat_id,
                """❌ دریافت قیمت آنلاین طلا با خطا مواجه شد.

لطفاً چند لحظه بعد دوباره امتحان کنید."""
            )


def main():
    offset = 0

    print(
        "Salar Jewelry Bot is running...",
        flush=True
    )

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
                print(
                    "Bale API error:",
                    data,
                    flush=True
                )

                time.sleep(5)
                continue

            for update in data.get("result", []):
                update_id = update.get("update_id")

                if update_id is not None:
                    offset = update_id + 1

                message = update.get("message")

                if message:
                    handle_message(message)

        except Exception as e:
            print(
                "Error:",
                repr(e),
                flush=True
            )

            time.sleep(5)


if __name__ == "__main__":
    main()
