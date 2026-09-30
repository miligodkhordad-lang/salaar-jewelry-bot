import os
import re
import time
import threading
import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://tapi.bale.ai/bot{TOKEN}"

CHANNEL_ID = 5655498921
TGJU = "https://www.tgju.org/profile/geram18"

# آخرین قیمت معتبر طلا
gold_price_cache = None
gold_price_time = 0
gold_lock = threading.Lock()


def api(method, data):
    r = requests.post(
        f"{API}/{method}",
        json=data,
        timeout=15
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
    return (text or "").translate(table)


def get_product(text):
    text = normalize(text)

    weight_match = re.search(
        r"وزن\s*[:：]?\s*\*?\s*"
        r"([0-9]+(?:\.[0-9]+)?)",
        text
    )

    labor_match = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*\*?\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*[٪%]?",
        text
    )

    if not weight_match or not labor_match:
        return None

    return (
        float(weight_match.group(1)),
        float(labor_match.group(1))
    )


def make_keyboard(weight, labor):
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


def fetch_gold_price():
    """
    دریافت نرخ طلای ۱۸ عیار / 750 از TGJU
    قیمت صفحه به ریال است و به تومان تبدیل می‌شود.
    """

    r = requests.get(
        TGJU,
        headers={
            "User-Agent":
            "Mozilla/5.0 (Linux; Android 15) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/140.0 Mobile Safari/537.36",

            "Accept":
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8",

            "Accept-Language":
            "fa-IR,fa;q=0.9,en;q=0.7",

            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        },
        params={
            "_": int(time.time())
        },
        timeout=10
    )

    r.raise_for_status()
    html = r.text

    match = re.search(
        r'data-col=["\']'
        r'info\.last_trade\.PDrCotVal'
        r'["\'][^>]*>\s*'
        r'([0-9۰-۹٠-٩,٬]+)',
        html,
        re.IGNORECASE
    )

    if not match:
        raise RuntimeError(
            "Current geram18 price not found"
        )

    raw_price = normalize(match.group(1))

    raw_price = (
        raw_price
        .replace(",", "")
        .replace("٬", "")
    )

    price_rial = int(raw_price)

    if not (
        100_000_000
        < price_rial
        < 1_000_000_000
    ):
        raise RuntimeError(
            f"Invalid TGJU price: {price_rial}"
        )

    price_toman = price_rial // 10

    return price_toman


def update_gold_price():
    """
    هر 60 ثانیه قیمت را در پس‌زمینه تازه می‌کند.
    """

    global gold_price_cache
    global gold_price_time

    while True:
        try:
            new_price = fetch_gold_price()

            with gold_lock:
                gold_price_cache = new_price
                gold_price_time = time.time()

            print(
                "GOLD CACHE UPDATED:",
                f"{new_price:,} toman",
                flush=True
            )

        except Exception as e:
            # اگر TGJU موقتاً خطا داد،
            # آخرین قیمت معتبر حفظ می‌شود.
            print(
                "GOLD UPDATE ERROR:",
                repr(e),
                flush=True
            )

        time.sleep(60)


def get_cached_gold_price():
    with gold_lock:
        return gold_price_cache, gold_price_time


def answer_callback(callback_id, text):
    return api(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
            "text": text,
            "show_alert": True
        }
    )


def handle_callback(cb):
    callback_id = cb.get("id")
    data = cb.get("data") or ""

    print(
        "CALLBACK:",
        data,
        flush=True
    )

    if not callback_id:
        return

    try:
        # اینجا دیگر هیچ درخواست اینترنتی به TGJU
        # هنگام کلیک مشتری انجام نمی‌شود.
        gram, updated_at = get_cached_gold_price()

        if gram is None:
            answer_callback(
                callback_id,
                "⏳ قیمت طلا در حال دریافت است. "
                "چند لحظه دیگر دوباره امتحان کنید."
            )
            return

        if data == "gold":
            text = (
                "💰 قیمت روز طلای ۱۸ عیار\n\n"
                f"🟡 هر گرم: {gram:,} تومان"
            )

            answer_callback(
                callback_id,
                text
            )
            return

        if data.startswith("price:"):
            parts = data.split(":")

            if len(parts) != 3:
                raise ValueError(
                    "Invalid callback data"
                )

            weight = float(parts[1])
            labor = float(parts[2])

            gold_value = round(
                weight * gram
            )

            # اجرت در مبلغ نهایی حساب می‌شود
            # ولی مبلغ اجرت جداگانه نمایش داده نمی‌شود.
            labor_value = round(
                gold_value * labor / 100
            )

            final_price = (
                gold_value + labor_value
            )

            text = (
                "✨ قیمت روز محصول\n\n"

                f"🟡 طلای ۱۸ عیار: "
                f"{gram:,} تومان\n\n"

                f"⚖️ وزن: "
                f"{weight:g} گرم\n"

                f"💎 اجرت: "
                f"{labor:g}٪\n\n"

                f"💰 مبلغ نهایی: "
                f"{final_price:,} تومان"
            )

            answer_callback(
                callback_id,
                text
            )
            return

        answer_callback(
            callback_id,
            "دکمه معتبر نیست."
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


def publish_product(msg):
    chat = msg.get("chat") or {}

    if chat.get("type") in (
        "channel",
        "group",
        "supergroup"
    ):
        return

    caption = (
        msg.get("caption")
        or msg.get("text")
        or ""
    )

    product = get_product(caption)

    if not product:
        return

    weight, labor = product

    photos = msg.get("photo") or []

    if not photos:
        api(
            "sendMessage",
            {
                "chat_id": chat.get("id"),
                "text":
                "⚠️ لطفاً عکس محصول را همراه "
                "با وزن و اجرت برای من ارسال کنید."
            }
        )
        return

    photo = photos[-1]
    file_id = photo.get("file_id")

    if not file_id:
        return

    result = api(
        "sendPhoto",
        {
            "chat_id": CHANNEL_ID,
            "photo": file_id,
            "caption": caption,
            "reply_markup":
                make_keyboard(
                    weight,
                    labor
                )
        }
    )

    if result.get("ok"):
        api(
            "sendMessage",
            {
                "chat_id": chat.get("id"),
                "text":
                "✅ محصول با دکمه قیمت "
                "در کانال منتشر شد."
            }
        )


def main():
    try:
        api(
            "deleteWebhook",
            {
                "drop_pending_updates": False
            }
        )
    except Exception as e:
        print(
            "DELETE WEBHOOK:",
            repr(e),
            flush=True
        )

    # دریافت قیمت در پس‌زمینه
    gold_thread = threading.Thread(
        target=update_gold_price,
        daemon=True
    )

    gold_thread.start()

    offset = 0

    print(
        "=== SALAR JEWELRY FAST BOT STARTED ===",
        flush=True
    )

    while True:
        try:
            r = requests.post(
                f"{API}/getUpdates",
                json={
                    "offset": offset,
                    "timeout": 20
                },
                timeout=30
            )

            r.raise_for_status()
            response = r.json()

            for update in response.get(
                "result",
                []
            ):
                print(
                    "UPDATE:",
                    repr(update),
                    flush=True
                )

                update_id = update.get(
                    "update_id"
                )

                if update_id is not None:
                    offset = update_id + 1

                callback = update.get(
                    "callback_query"
                )

                if callback:
                    handle_callback(
                        callback
                    )
                    continue

                msg = (
                    update.get("message")
                    or
                    update.get("edited_message")
                )

                if msg:
                    publish_product(msg)

        except requests.exceptions.ReadTimeout:
            continue

        except Exception as e:
            print(
                "MAIN ERROR:",
                repr(e),
                flush=True
            )

            time.sleep(2)


if __name__ == "__main__":
    main()
