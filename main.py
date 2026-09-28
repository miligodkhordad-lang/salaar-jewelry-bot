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


def api_request(method, payload):
    response = requests.post(
        f"{API}/{method}",
        json=payload,
        timeout=30
    )

    print(
        method,
        response.status_code,
        response.text,
        flush=True
    )

    return response


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup

    return api_request("sendMessage", payload)


def edit_keyboard(chat_id, message_id, keyboard):
    return api_request(
        "editMessageReplyMarkup",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": keyboard
        }
    )


def answer_callback(callback_id, text=None):
    payload = {
        "callback_query_id": callback_id
    }

    if text:
        payload["text"] = text
        payload["show_alert"] = True

    return api_request(
        "answerCallbackQuery",
        payload
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
            price = int(
                match.group(1).replace(",", "")
            )

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


def normalize_digits(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "01234567890123456789"
    )

    return text.translate(table)


def extract_product_info(text):
    if not text:
        return None

    text = normalize_digits(text)
    text = text.replace("٫", ".")
    text = text.replace("٪", "%")

    weight_patterns = [
        r"وزن\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        r"وزن\s+([0-9]+(?:\.[0-9]+)?)"
    ]

    labor_patterns = [
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*%?\s*([0-9]+(?:\.[0-9]+)?)",
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*%"
    ]

    weight = None
    labor = None

    for pattern in weight_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            weight = float(match.group(1))
            break

    for pattern in labor_patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            labor = float(match.group(1))
            break

    if weight is None or labor is None:
        return None

    if weight <= 0 or labor < 0:
        return None

    return weight, labor


def product_keyboard(weight, labor):
    return {
        "inline_keyboard": [
            [
                {
                    "text":
                        "💰 مشاهده قیمت روز این محصول",
                    "callback_data":
                        f"product:{weight:g}:{labor:g}"
                }
            ],
            [
                {
                    "text":
                        "💰 مشاهده قیمت طلا",
                    "callback_data": "gold"
                }
            ]
        ]
    }


def product_price_text(weight, labor):
    gold_price = get_gold_price()

    gold_value = weight * gold_price
    labor_value = gold_value * labor / 100
    total = gold_value + labor_value

    return (
        f"💎 قیمت روز این محصول\n\n"
        f"⚖️ وزن: {weight:g} گرم\n"
        f"🔨 اجرت: {labor:g}٪\n\n"
        f"🟡 طلای ۱۸ عیار: "
        f"{money(gold_price)} تومان\n\n"
        f"💰 قیمت نهایی:\n"
        f"{money(total)} تومان"
    )


def process_channel_post(message):
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    message_id = message.get("message_id")

    if not chat_id or not message_id:
        return

    # برای پست متنی
    text = message.get("text")

    # برای پست عکس/ویدیو که توضیحات دارد
    if not text:
        text = message.get("caption")

    product = extract_product_info(text)

    if not product:
        print(
            "No weight/labor found in channel post",
            flush=True
        )
        return

    weight, labor = product

    print(
        "Product detected:",
        weight,
        labor,
        flush=True
    )

    response = edit_keyboard(
        chat_id,
        message_id,
        product_keyboard(
            weight,
            labor
        )
    )

    print(
        "Keyboard attached:",
        response.text,
        flush=True
    )


def handle_private_message(message):
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    text = (
        message.get("text") or ""
    ).strip()

    if not chat_id:
        return

    if text == "/start":
        send_message(
            chat_id,
            """👋 سلام
به ربات جواهری سالار خوش آمدید.

🟡 قیمت آنلاین طلا:
/online

💎 محاسبه قیمت:
/price وزن اجرت

مثال:
/price 2.58 7"""
        )

    elif text == "/online":
        try:
            gold_price = get_gold_price()

            send_message(
                chat_id,
                f"""🟡 قیمت آنلاین طلای ۱۸ عیار / ۷۵۰

💰 هر گرم:
{money(gold_price)} تومان

منبع: TGJU"""
            )

        except Exception as e:
            print(
                "Online error:",
                repr(e),
                flush=True
            )

            send_message(
                chat_id,
                "❌ دریافت قیمت آنلاین با خطا مواجه شد."
            )

    elif text.startswith("/price"):
        try:
            parts = text.split()

            if len(parts) != 3:
                raise ValueError

            weight = float(
                parts[1].replace(",", ".")
            )

            labor = float(
                parts[2].replace(",", ".")
            )

            send_message(
                chat_id,
                product_price_text(
                    weight,
                    labor
                )
            )

        except Exception:
            send_message(
                chat_id,
                """❌ فرمت صحیح:

/price وزن اجرت

مثال:
/price 2.58 7"""
            )


def handle_callback(callback):
    callback_id = callback.get("id")

    if not callback_id:
        return

    data = callback.get("data", "")

    try:
        if data == "gold":
            gold_price = get_gold_price()

            answer_callback(
                callback_id,
                "قیمت طلای ۱۸ عیار:\n"
                f"{money(gold_price)} تومان"
            )

        elif data.startswith("product:"):
            parts = data.split(":")

            if len(parts) != 3:
                raise ValueError

            weight = float(parts[1])
            labor = float(parts[2])

            gold_price = get_gold_price()

            gold_value = weight * gold_price
            labor_value = (
                gold_value * labor / 100
            )
            total = (
                gold_value + labor_value
            )

            answer_callback(
                callback_id,
                f"قیمت روز محصول:\n"
                f"{money(total)} تومان"
            )

    except Exception as e:
        print(
            "Callback error:",
            repr(e),
            flush=True
        )

        try:
            answer_callback(
                callback_id,
                "خطا در دریافت قیمت"
            )
        except Exception:
            pass


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

            for update in data.get(
                "result",
                []
            ):
                update_id = update.get(
                    "update_id"
                )

                if update_id is not None:
                    offset = update_id + 1

                # پیام خصوصی ربات
                message = update.get(
                    "message"
                )

                if message:
                    handle_private_message(
                        message
                    )

                # پست جدید کانال
                channel_post = update.get(
                    "channel_post"
                )

                if channel_post:
                    process_channel_post(
                        channel_post
                    )

                # اگر پست کانال ویرایش شد
                edited_channel_post = (
                    update.get(
                        "edited_channel_post"
                    )
                )

                if edited_channel_post:
                    process_channel_post(
                        edited_channel_post
                    )

                # کلیک روی دکمه
                callback = update.get(
                    "callback_query"
                )

                if callback:
                    handle_callback(
                        callback
                    )

        except Exception as e:
            print(
                "Error:",
                repr(e),
                flush=True
            )

            time.sleep(5)


if __name__ == "__main__":
    main()
