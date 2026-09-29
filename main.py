import os
import re
import time
import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://tapi.bale.ai/bot{TOKEN}"

CHANNEL = "salar_jewelry"
TGJU = "https://www.tgju.org/profile/geram18"


def bale(method, data):
    r = requests.post(
        f"{API}/{method}",
        json=data,
        timeout=30
    )

    print(
        "BALE:",
        method,
        r.status_code,
        r.text,
        flush=True
    )

    r.raise_for_status()
    return r.json()


def normalize(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫،",
        "01234567890123456789.."
    )
    return text.translate(table)


def get_product(caption):
    text = normalize(caption or "")

    w = re.search(
        r"وزن\s*[:：]?\s*\*?\s*"
        r"([0-9]+(?:\.[0-9]+)?)",
        text
    )

    p = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*\*?\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*[٪%]?",
        text
    )

    if not w or not p:
        return None

    return float(w.group(1)), float(p.group(1))


def keyboard(weight, labor):
    return {
        "inline_keyboard": [
            [
                {
                    "text": "💰 مشاهده قیمت روز این محصول",
                    "callback_data":
                    f"price:{weight:g}:{labor:g}"
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


def process_post(msg):
    chat = msg.get("chat") or {}
    sender = msg.get("sender_chat") or {}

    username = (
        chat.get("username")
        or sender.get("username")
        or ""
    ).lstrip("@").lower()

    if username != CHANNEL:
        return

    caption = (
        msg.get("caption")
        or msg.get("text")
        or ""
    )

    product = get_product(caption)

    if not product:
        print(
            "NO PRODUCT DATA",
            flush=True
        )
        return

    weight, labor = product

    print(
        "PRODUCT:",
        weight,
        labor,
        flush=True
    )

    bale(
        "editMessageReplyMarkup",
        {
            "chat_id": chat.get("id"),
            "message_id": msg.get("message_id"),
            "reply_markup": keyboard(
                weight,
                labor
            )
        }
    )


def gold_price():
    r = requests.get(
        TGJU,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Linux; Android 15) "
            "AppleWebKit/537.36 Chrome Mobile"
        },
        timeout=20
    )

    r.raise_for_status()

    html = r.text

    patterns = [
        r'data-col="info\.last_trade\.PDrCotVal"'
        r'[^>]*>([\d,]+)<',

        r'"p"\s*:\s*"([\d,]+)"'
    ]

    for pattern in patterns:
        m = re.search(pattern, html)

        if not m:
            continue

        n = int(
            m.group(1).replace(",", "")
        )

        if n > 100_000_000:
            n //= 10

        if 1_000_000 < n < 100_000_000:
            return n

    raise RuntimeError(
        "Gold price not found"
    )


def answer_callback(callback_id, text):
    bale(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": text,
            "show_alert": True
        }
    )


def process_callback(cb):
    print(
        ">>> CALLBACK RECEIVED <<<",
        flush=True
    )
    print(
        repr(cb),
        flush=True
    )

    callback_id = cb.get("id")
    data = cb.get("data") or ""

    if not callback_id:
        return

    try:
        if data == "gold":
            price = gold_price()

            answer_callback(
                callback_id,
                "💰 قیمت طلای ۱۸ عیار\n\n"
                f"هر گرم: {price:,} تومان"
            )
            return

        if data.startswith("price:"):
            _, w, p = data.split(":")

            weight = float(w)
            labor = float(p)

            gram = gold_price()

            raw = weight * gram
            labor_value = raw * labor / 100
            total = round(raw + labor_value)

            answer_callback(
                callback_id,
                "💎 قیمت روز محصول\n\n"
                f"وزن: {weight:g} گرم\n"
                f"اجرت: {labor:g}٪\n"
                f"طلای ۱۸ عیار: {gram:,} تومان\n\n"
                f"قیمت نهایی: {total:,} تومان"
            )
            return

        answer_callback(
            callback_id,
            "دکمه نامعتبر است."
        )

    except Exception as e:
        print(
            "CALLBACK ERROR:",
            repr(e),
            flush=True
        )

        try:
            answer_callback(
                callback_id,
                "⚠️ دریافت قیمت ممکن نشد."
            )
        except Exception as e2:
            print(
                "ANSWER ERROR:",
                repr(e2),
                flush=True
            )


def main():
    offset = 0

    print(
        "=== SALAR BOT V2 STARTED ===",
        flush=True
    )

    while True:
        try:
            r = requests.post(
                f"{API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": 20,
                    "allowed_updates": [
                        "message",
                        "edited_message",
                        "callback_query"
                    ]
                },
                timeout=35
            )

            r.raise_for_status()
            result = r.json()

            for update in result.get("result", []):
                print(
                    "=== UPDATE ===",
                    flush=True
                )
                print(
                    repr(update),
                    flush=True
                )

                uid = update.get("update_id")

                if uid is not None:
                    offset = uid + 1

                cb = update.get("callback_query")

                if cb:
                    process_callback(cb)
                    continue

                msg = (
                    update.get("message")
                    or update.get("edited_message")
                )

                if msg:
                    process_post(msg)

        except requests.exceptions.ReadTimeout:
            continue

        except Exception as e:
            print(
                "MAIN ERROR:",
                repr(e),
                flush=True
            )
            time.sleep(3)


if __name__ == "__main__":
    main()
