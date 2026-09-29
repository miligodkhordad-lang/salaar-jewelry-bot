import os
import re
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"
CHANNEL_USERNAME = "salar_jewelry"

TGJU_URL = "https://www.tgju.org/profile/geram18"


# -----------------------------
# BALE API
# -----------------------------

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


# -----------------------------
# تبدیل اعداد فارسی به انگلیسی
# -----------------------------

def normalize_number(text):
    table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫",
        "01234567890123456789."
    )

    return text.translate(table)


# -----------------------------
# خواندن وزن و اجرت از پست
# -----------------------------

def extract_weight_and_labor(caption):
    if not caption:
        return None, None

    text = normalize_number(caption)

    weight_match = re.search(
        r"وزن\s*[:：]?\s*\*?\s*([0-9]+(?:[.,][0-9]+)?)",
        text
    )

    labor_match = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*\*?\s*([0-9]+(?:[.,][0-9]+)?)\s*[٪%]?",
        text
    )

    if not weight_match or not labor_match:
        return None, None

    weight = float(
        weight_match.group(1).replace(",", ".")
    )

    labor = float(
        labor_match.group(1).replace(",", ".")
    )

    return weight, labor


# -----------------------------
# قیمت آنلاین طلای ۱۸ عیار
# -----------------------------

def get_gold_price():

    headers = {
        "User-Agent":
        "Mozilla/5.0 (Linux; Android 15) "
        "AppleWebKit/537.36 Chrome/140 Mobile Safari/537.36"
    }

    response = requests.get(
        TGJU_URL,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    html = response.text

    patterns = [
        r'data-col="info\.last_trade\.PDrCotVal"[^>]*>([\d,]+)<',
        r'<span[^>]*class="[^"]*value[^"]*"[^>]*>([\d,]+)</span>',
        r'"p"\s*:\s*"([\d,]+)"'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html
        )

        if match:

            value = int(
                match.group(1).replace(",", "")
            )

            # تبدیل ریال به تومان
            if value > 100_000_000:
                value //= 10

            if 1_000_000 < value < 100_000_000:
                return value

    # روش پشتیبان
    numbers = re.findall(
        r'\b[\d,]{7,12}\b',
        html
    )

    for number in numbers:

        try:
            value = int(
                number.replace(",", "")
            )

            if value > 100_000_000:
                value //= 10

            if 1_000_000 < value < 100_000_000:
                return value

        except:
            pass

    raise ValueError(
        "Gold price not found"
    )


# -----------------------------
# ساخت دکمه‌ها
# -----------------------------

def make_keyboard(weight, labor):

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

                    "callback_data":
                    "gold"
                }
            ]
        ]
    }


# -----------------------------
# اضافه کردن دکمه زیر همان پست
# -----------------------------

def add_buttons_to_post(
    chat_id,
    message_id,
    weight,
    labor
):

    return api_call(
        "editMessageReplyMarkup",
        {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup":
            make_keyboard(
                weight,
                labor
            )
        }
    )


# -----------------------------
# پردازش پست کانال
# -----------------------------

def process_channel_message(message):

    chat = message.get("chat") or {}
    sender_chat = (
        message.get("sender_chat")
        or {}
    )

    chat_id = chat.get("id")
    message_id = message.get("message_id")

    username = (
        chat.get("username")
        or sender_chat.get("username")
        or ""
    )

    username = (
        username
        .lstrip("@")
        .lower()
    )

    if username != CHANNEL_USERNAME.lower():
        return

    caption = (
        message.get("caption")
        or message.get("text")
        or ""
    )

    weight, labor = (
        extract_weight_and_labor(
            caption
        )
    )

    if weight is None or labor is None:

        print(
            "Weight/labor not found",
            flush=True
        )

        return

    print(
        f"PRODUCT FOUND: "
        f"weight={weight} "
        f"labor={labor}",
        flush=True
    )

    add_buttons_to_post(
        chat_id,
        message_id,
        weight,
        labor
    )


# -----------------------------
# جواب دکمه
# -----------------------------

def answer_callback(
    callback_id,
    text
):

    return api_call(
        "answerCallbackQuery",
        {
            "callback_query_id":
            callback_id,

            "text": text,

            "show_alert": True
        }
    )


# -----------------------------
# کلیک روی دکمه‌ها
# -----------------------------

def process_callback(callback):

    callback_id = callback.get("id")
    data = callback.get("data", "")

    if not callback_id:
        return

    print(
        "CALLBACK:",
        data,
        flush=True
    )

    try:

        # -----------------
        # قیمت طلا
        # -----------------

        if data == "gold":

            gold_price = get_gold_price()

            text = (
                "💰 قیمت آنلاین طلای ۱۸ عیار\n\n"
                f"هر گرم: "
                f"{gold_price:,} تومان\n\n"
                "منبع: TGJU"
            )

            answer_callback(
                callback_id,
                text
            )

            return


        # -----------------
        # قیمت محصول
        # -----------------

        if data.startswith("product:"):

            parts = data.split(":")

            if len(parts) != 3:
                raise ValueError(
                    "Invalid product data"
                )

            weight = float(parts[1])
            labor = float(parts[2])

            gold_price = get_gold_price()

            raw_price = (
                weight * gold_price
            )

            labor_amount = (
                raw_price *
                labor / 100
            )

            final_price = (
                raw_price +
                labor_amount
            )

            text = (
                "💎 قیمت روز این محصول\n\n"

                f"وزن: "
                f"{weight:g} گرم\n"

                f"اجرت: "
                f"{labor:g}٪\n\n"

                f"قیمت هر گرم طلا: "
                f"{gold_price:,} تومان\n\n"

                f"قیمت نهایی: "
                f"{round(final_price):,} تومان"
            )

            answer_callback(
                callback_id,
                text
            )

            return


        answer_callback(
            callback_id,
            "درخواست نامعتبر است."
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
                "⚠️ دریافت قیمت آنلاین ممکن نشد. لطفاً دوباره امتحان کنید."
            )
        except:
            pass


# -----------------------------
# اجرای ربات
# -----------------------------

def main():

    offset = 0

    print(
        "=== SALAR JEWELRY PRICE BOT STARTED ===",
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


            for update in data.get(
                "result",
                []
            ):

                update_id = (
                    update.get(
                        "update_id"
                    )
                )

                if update_id is not None:
                    offset = update_id + 1


                # کلیک روی دکمه
                callback = update.get(
                    "callback_query"
                )

                if callback:
                    process_callback(
                        callback
                    )


                # پست کانال
                message = update.get(
                    "message"
                )

                if message:
                    process_channel_message(
                        message
                    )


                channel_post = update.get(
                    "channel_post"
                )

                if channel_post:
                    process_channel_message(
                        channel_post
                    )


        except requests.exceptions.ReadTimeout:
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
