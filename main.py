import os
import re
import time
import threading
import requests

TOKEN = os.environ["BOT_TOKEN"]
API = f"https://tapi.bale.ai/bot{TOKEN}"

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "5655498921"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

TGJU = "https://www.tgju.org/profile/geram18"

session = requests.Session()

editing = {}
last_price = None
last_update = 0
lock = threading.Lock()


def api(method, data, timeout=15):
    response = session.post(
        f"{API}/{method}",
        json=data,
        timeout=timeout
    )
    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"{method}: {result}")

    return result.get("result")


def digits(value):
    return str(value or "").translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫",
            "01234567890123456789."
        )
    )


def product(text):
    t = digits(text)

    w = re.search(
        r"وزن\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        t
    )

    a = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        t
    )

    if not (w and a):
        return None

    return float(w.group(1)), float(a.group(1))


def keyboard(weight, labor):
    return {
        "inline_keyboard": [
            [{
                "text": "💰 مشاهده قیمت روز این محصول",
                "callback_data": f"price:{weight:g}:{labor:g}"
            }],
            [{
                "text": "💰 مشاهده قیمت طلا",
                "callback_data": "gold"
            }]
        ]
    }


def gold_worker():
    global last_price, last_update

    while True:
        try:
            response = requests.get(
                TGJU,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=(4, 8)
            )

            response.raise_for_status()

            match = re.search(
                r'data-col=["\']info\.last_trade\.PDrCotVal["\'][^>]*>\s*([0-9۰-۹٠-٩,٬]+)',
                response.text,
                re.I
            )

            if not match:
                raise ValueError("TGJU price field not found")

            rial = int(
                digits(match.group(1))
                .replace(",", "")
                .replace("٬", "")
            )

            if not 100_000_000 < rial < 1_000_000_000:
                raise ValueError("Invalid rial value")

            with lock:
                last_price = rial // 10
                last_update = time.time()

            print("GOLD UPDATED", last_price, flush=True)

        except Exception as exc:
            print("GOLD ERROR", repr(exc), flush=True)

        time.sleep(60)


def send(chat_id, text):
    return api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


def callback(cb):
    cid = cb.get("id")
    data = cb.get("data") or ""

    with lock:
        gram = last_price
        timestamp = last_update

    if not gram or time.time() - timestamp > 900:
        text = (
            "⚠️ نرخ معتبر و تازه طلا فعلاً در دسترس نیست."
            " لطفاً بعداً امتحان کنید."
        )

    elif data == "gold":
        text = (
            "💰 قیمت طلای ۱۸ عیار\n\n"
            f"🟡 هر گرم: {gram:,} تومان"
        )

    elif data.startswith("price:"):
        try:
            _, w, a = data.split(":")

            w = float(w)
            a = float(a)

            total = round(
                w * gram * (1 + a / 100)
            )

            text = (
                "✨ قیمت روز محصول\n\n"
                f"🟡 طلای ۱۸ عیار: {gram:,} تومان\n"
                f"⚖️ وزن: {w:g} گرم\n"
                f"💎 اجرت: {a:g}٪\n\n"
                f"💰 مبلغ نهایی: {total:,} تومان"
            )

        except (ValueError, TypeError):
            text = "اطلاعات این دکمه نامعتبر است."

    else:
        text = "دکمه نامعتبر است."

    try:
        api(
            "answerCallbackQuery",
            {
                "callback_query_id": cid,
                "text": text,
                "show_alert": True
            }
        )
    except Exception as exc:
        print("CALLBACK ERROR", repr(exc), flush=True)


def verify_edit(result, message_id, caption):
    """
    Check the message returned by Bale.
    """

    print(
        "EDIT API RESULT",
        repr(result)[:3000],
        flush=True
    )

    if not isinstance(result, dict):
        return False, "پاسخ ویرایش شامل اطلاعات پیام نیست."

    returned_id = result.get("message_id")

    if str(returned_id) != str(message_id):
        return False, (
            f"شناسه برگشتی {returned_id} "
            f"با شناسه درخواستی {message_id} فرق دارد."
        )

    returned_caption = result.get("caption")

    if returned_caption is None:
        return False, (
            "بله متن ویرایش‌شده را در پاسخ برنگردانده است."
        )

    if returned_caption != caption:
        return False, (
            "متن برگشتی بله با متن جدید مطابقت ندارد."
        )

    return True, "OK"


def edit_caption(chat_id, message_id, caption):
    parsed = product(caption)

    if not parsed:
        send(
            chat_id,
            "❌ متن باید شامل وزن و اجرت باشد.\n"
            "مثال:\n"
            "وزن: ۱۶.۰۲ گرم\n"
            "اجرت فقط: ۷٪"
        )
        return False

    print(
        "EDIT REQUEST",
        "channel=", CHANNEL_ID,
        "message=", message_id,
        "caption=", repr(caption[:500]),
        flush=True
    )

    result = api(
        "editMessageCaption",
        {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "caption": caption,
            "reply_markup": keyboard(*parsed)
        }
    )

    verified, reason = verify_edit(
        result,
        message_id,
        caption
    )

    if verified:
        send(
            chat_id,
            "✅ بله شناسه و متن جدید را در پاسخ تأیید کرد.\n"
            f"شناسه پست: {message_id}\n\n"
            "لطفاً نتیجه را داخل کانال هم بررسی کن."
        )
    else:
        send(
            chat_id,
            "⚠️ درخواست ویرایش ارسال شد، "
            "اما تأیید کامل دریافت نشد.\n\n"
            f"علت: {reason}\n\n"
            "گزارش در GitHub Actions ثبت شد."
        )

    return True


def edit_existing(chat_id, message_id, msg):
    caption = msg.get("caption") or msg.get("text") or ""

    photos = msg.get("photo") or []

    if not caption and not photos:
        send(
            chat_id,
            "متن کامل جدید یا عکس جدید بفرست."
        )
        return False

    if photos:
        parsed = product(caption) if caption else None

        media = {
            "type": "photo",
            "media": photos[-1]["file_id"]
        }

        if caption:
            if not parsed:
                send(
                    chat_id,
                    "❌ کپشن عکس باید وزن و اجرت داشته باشد."
                )
                return False

            media["caption"] = caption

        payload = {
            "chat_id": CHANNEL_ID,
            "message_id": message_id,
            "media": media
        }

        if parsed:
            payload["reply_markup"] = keyboard(*parsed)

        print(
            "EDIT MEDIA REQUEST",
            "channel=", CHANNEL_ID,
            "message=", message_id,
            flush=True
        )

        result = api("editMessageMedia", payload)

        print(
            "EDIT MEDIA RESULT",
            repr(result)[:3000],
            flush=True
        )

        send(
            chat_id,
            "⚠️ درخواست تغییر عکس به بله ارسال شد.\n"
            "لطفاً نتیجه را در کانال بررسی کن."
        )

        return True

    return edit_caption(
        chat_id,
        message_id,
        caption
    )


def handle_message(msg):
    chat = msg.get("chat") or {}

    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")
    sender_id = (msg.get("from") or {}).get("id")
    text = (msg.get("text") or "").strip()

    if text == "/id":
        send(
            chat_id,
            f"شناسه عددی حساب شما: {sender_id}"
        )
        return

    if not OWNER_ID:
        send(
            chat_id,
            "⚠️ ابتدا OWNER_ID را در GitHub Secrets تنظیم کن."
        )
        return

    if sender_id != OWNER_ID:
        send(
            chat_id,
            "⛔ دسترسی فقط برای مدیر فروشگاه است."
        )
        return

    if text == "/cancel":
        editing.pop(chat_id, None)

        send(
            chat_id,
            "ویرایش لغو شد."
        )
        return

    if text.startswith("/edit"):
        parts = digits(text).split()

        if len(parts) != 2 or not parts[1].isdigit():
            send(
                chat_id,
                "برای ویرایش بنویس:\n/edit 299"
            )
            return

        editing[chat_id] = int(parts[1])

        send(
            chat_id,
            "✏️ کپشن کامل جدید را بفرست.\n"
            "برای انصراف /cancel را بزن."
        )
        return

    if text.startswith("/sold"):
        parts = digits(text).split()

        if len(parts) != 2 or not parts[1].isdigit():
            send(
                chat_id,
                "برای ثبت فروش بنویس:\n/sold 299"
            )
            return

        message_id = int(parts[1])

        send(
            chat_id,
            "💯 برای ثبت فروخته‌شدن محصول، "
            "کپشن کامل همان پست را بفرست.\n\n"
            "عبارت «💯 فروخته شد 💯» "
            "را بالای متن اضافه کن.\n\n"
            "عکس و دکمه‌های قیمت حفظ می‌شوند."
        )

        editing[chat_id] = message_id
        return

    if chat_id in editing:
        message_id = editing[chat_id]

        try:
            completed = edit_existing(
                chat_id,
                message_id,
                msg
            )

            if completed:
                editing.pop(chat_id, None)

        except Exception as exc:
            print(
                "EDIT ERROR",
                repr(exc),
                flush=True
            )

            send(
                chat_id,
                "❌ درخواست ویرایش با خطا مواجه شد.\n"
                "گزارش خطا در GitHub Actions ثبت شده."
            )

        return

    caption = msg.get("caption") or msg.get("text") or ""

    parsed = product(caption)
    photos = msg.get("photo") or []

    if parsed and photos:
        try:
            result = api(
                "sendPhoto",
                {
                    "chat_id": CHANNEL_ID,
                    "photo": photos[-1]["file_id"],
                    "caption": caption,
                    "reply_markup": keyboard(*parsed)
                }
            )

            mid = (
                result.get("message_id")
                if isinstance(result, dict)
                else None
            )

            send(
                chat_id,
                "✅ محصول منتشر شد.\n"
                f"شناسه پیام: {mid}\n"
                f"برای ویرایش: /edit {mid}\n"
                f"برای ثبت فروش: /sold {mid}"
            )

        except Exception as exc:
            print(
                "PUBLISH ERROR",
                repr(exc),
                flush=True
            )

            send(
                chat_id,
                "❌ انتشار ناموفق بود. گزارش را در Actions ببین."
            )

    else:
        send(
            chat_id,
            "برای انتشار، عکس با کپشن وزن و اجرت بفرست.\n\n"
            "ویرایش: /edit 299\n"
            "ثبت فروش: /sold 299\n"
            "شناسه حساب: /id"
        )


def main():
    api(
        "deleteWebhook",
        {
            "drop_pending_updates": False
        }
    )

    threading.Thread(
        target=gold_worker,
        daemon=True
    ).start()

    offset = 0

    print(
        "SALAR BOT DIAGNOSTIC VERSION STARTED",
        flush=True
    )

    while True:
        try:
            updates = api(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 20
                },
                timeout=30
            )

            for update in updates or []:
                offset = max(
                    offset,
                    update["update_id"] + 1
                )

                try:
                    if update.get("callback_query"):
                        callback(update["callback_query"])

                    else:
                        msg = (
                            update.get("message")
                            or update.get("edited_message")
                        )

                        if msg:
                            handle_message(msg)

                except Exception as exc:
                    print(
                        "UPDATE ERROR",
                        repr(exc),
                        flush=True
                    )

        except Exception as exc:
            print(
                "POLL ERROR",
                repr(exc),
                flush=True
            )

            time.sleep(2)


if __name__ == "__main__":
    main()
