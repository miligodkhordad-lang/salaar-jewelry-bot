import os
import re
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

# کانال خودت
CHANNEL_USERNAME = "salar_jewelry"


def api_call(method, payload):
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


def normalize_number(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫",
        "01234567890123456789."
    )

    return text.translate(table)


def extract_weight_and_labor(caption):
    if not caption:
        return None, None

    text = normalize_number(caption)

    # وزن
    weight_match = re.search(
        r"وزن\s*[:：]?\s*\*?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE
    )

    # اجرت
    labor_match = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*\*?\s*٪?\s*%?\s*([0-9]+(?:\.[0-9]+)?)",
        text,
        re.IGNORECASE
    )

    # اگر درصد قبل از عدد نوشته شده باشد
    if not labor_match:
        labor_match = re.search(
            r"اجرت(?:\s*فقط)?\s*[:：]?\s*\*?\s*([0-9]+(?:\.[0-9]+)?)\s*[٪%]",
            text,
            re.IGNORECASE
        )

    if not weight_match or not labor_match:
        return None, None

    weight = float(weight_match.group(1))
    labor = float(labor_match.group(1))

    return weight, labor


def make_keyboard(weight, labor):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "💰 مشاهده قیمت روز این محصول",
                    "callback_data": f"product:{weight:g}:{labor:g}"
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


def add_buttons_to_post(chat_id, message_id, weight, labor):
    keyboard = make_keyboard(weight, labor)

    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": keyboard
    }

    return api_call(
        "editMessageReplyMarkup",
        payload
    )


def process_channel_message(message):
    chat = message.get("chat") or {}
    sender_chat = message.get("sender_chat") or {}

    chat_id = chat.get("id")
    message_id = message.get("message_id")

    username = (
        chat.get("username")
        or sender_chat.get("username")
        or ""
    )

    username = username.lstrip("@").lower()

    if username != CHANNEL_USERNAME.lower():
        return

    caption = message.get("caption") or message.get("text") or ""

    print(
        "CHANNEL POST:",
        chat_id,
        message_id,
        repr(caption),
        flush=True
    )

    weight, labor = extract_weight_and_labor(caption)

    if weight is None or labor is None:
        print(
            "Weight/labor not found - ignored",
            flush=True
        )
        return

    print(
        f"FOUND weight={weight} labor={labor}",
        flush=True
    )

    response = add_buttons_to_post(
        chat_id,
        message_id,
        weight,
        labor
    )

    print(
        "BUTTON RESULT:",
        response.text,
        flush=True
    )


def main():
    offset = 0

    print(
        "=== SALAR JEWELRY BOT STARTED ===",
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
                    "BALE API ERROR:",
                    data,
                    flush=True
                )

                time.sleep(3)
                continue

            for update in data.get("result", []):
                update_id = update.get("update_id")

                if update_id is not None:
                    offset = update_id + 1

                # چیزی که در لاگ خودت دیدیم
                message = update.get("message")

                if message:
                    process_channel_message(message)

                # برای سازگاری در صورتی که بله
                # پست کانال را با این نام برگرداند
                channel_post = update.get("channel_post")

                if channel_post:
                    process_channel_message(channel_post)

        except requests.exceptions.ReadTimeout:
            # در Long Polling طبیعی است
            continue

        except requests.exceptions.RequestException as e:
            print(
                "NETWORK ERROR:",
                repr(e),
                flush=True
            )

            time.sleep(3)

        except Exception as e:
            print(
                "ERROR:",
                repr(e),
                flush=True
            )

            time.sleep(3)


if __name__ == "__main__":
    main()
