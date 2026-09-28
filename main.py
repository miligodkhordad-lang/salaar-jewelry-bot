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


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    response = requests.post(
        f"{API}/sendMessage",
        json=payload,
        timeout=30
    )

    print(
        "sendMessage:",
        response.status_code,
        response.text,
        flush=True
    )

    return response


def answer_callback(callback_query_id, text=None):
    payload = {
        "callback_query_id": callback_query_id
    }

    if text:
        payload["text"] = text

    try:
        requests.post(
            f"{API}/answerCallbackQuery",
            json=payload,
            timeout=30
        )
    except Exception as e:
        print(
            "answerCallbackQuery error:",
            repr(e),
            flush=True
        )


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

    return f"""💎 قیمت روز این محصول

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


def product_keyboard(weight, labor_percent):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "💰 مشاهده قیمت روز این محصول",
                    "callback_data": (
                        f"product:{weight}:{labor_percent}"
                    )
                }
            ],
            [
                {
                    "text": "💰 مشاهده قیمت طلا",
                    "callback_data": "gold"
                }
            ]
        ]
    }


def start_text():
    return """👋 سلام
به ربات جواهری سالار خوش آمدید.

🟡 مشاهده قیمت آنلاین طلا:
/online

💎 محاسبه قیمت محصول:
/price وزن اجرت

مثال:
/price 9.51 5

🔘 ساخت دکمه قیمت محصول:
/product وزن اجرت

مثال:
/product 9.51 5"""


def help_text():
    return """💎 راهنمای ربات جواهری سالار

قیمت آنلاین طلا:
/online

محاسبه قیمت:
/price وزن اجرت

مثال:
/price 9.51 5

ساخت دکمه محصول:
/product وزن اجرت

مثال:
/product 9.51 5"""


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
            send_message(
                chat_id,
                online_price_text()
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
                "❌ دریافت قیمت آنلاین طلا با خطا مواجه شد."
            )

    elif text.startswith("/product"):
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

            keyboard = product_keyboard(
                weight,
                labor_percent
            )

            send_message(
                chat_id,
                f"""💎 جواهری سالار

⚖️ وزن محصول: {weight:g} گرم
🔨 اجرت: {labor_percent:g}٪

برای مشاهده قیمت روز، دکمه زیر را بزنید 👇""",
                keyboard
            )

        except ValueError:
            send_message(
                chat_id,
                """❌ اطلاعات وارد شده صحیح نیست.

فرمت صحیح:
/product وزن اجرت

مثال:
/product 9.51 5"""
            )


def handle_callback(callback):
    callback_id = callback.get("id")
    data = callback.get("data", "")

    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not chat_id:
        return

    try:
        if data == "gold":
            gold_price = get_gold_price()

            send_message(
                chat_id,
                f"""🟡 قیمت آنلاین طلای ۱۸ عیار / ۷۵۰

💰 هر گرم:
{money(gold_price)} تومان

منبع: TGJU"""
            )

            if callback_id:
                answer_callback(callback_id)

        elif data.startswith("product:"):
            parts = data.split(":")

            if len(parts) != 3:
                raise ValueError

            weight = float(parts[1])
            labor_percent = float(parts[2])

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

            if callback_id:
                answer_callback(callback_id)

    except Exception as e:
        print(
            "Callback error:",
            repr(e),
            flush=True
        )

        if callback_id:
            answer_callback(
                callback_id,
                "خطا در دریافت قیمت"
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

                callback = update.get("callback_query")

                if callback:
                    handle_callback(callback)

        except Exception as e:
            print(
                "Error:",
                repr(e),
                flush=True
            )

            time.sleep(5)


if __name__ == "__main__":
    main()
