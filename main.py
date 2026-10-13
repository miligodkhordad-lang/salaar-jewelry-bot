import os
import re
import time
import threading
import requests

# =====================================
# SALAR JEWELRY BALE BOT
# =====================================

TOKEN = os.environ["BOT_TOKEN"]

API = f"https://tapi.bale.ai/bot{TOKEN}"

CHANNEL_ID = int(
    os.getenv("CHANNEL_ID", "5655498921")
)

OWNER_ID = int(
    os.getenv("OWNER_ID", "0")
)

TGJU = "https://www.tgju.org/profile/geram18"

session = requests.Session()

editing = {}

last_price = None
last_update = 0

lock = threading.Lock()


# =====================================
# BALE API
# =====================================

def api(method, data, timeout=20):

    response = session.post(
        f"{API}/{method}",
        json=data,
        timeout=timeout
    )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(
            f"{method}: {result}"
        )

    return result.get("result")


# =====================================
# PERSIAN DIGITS
# =====================================

def digits(value):

    return str(value or "").translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫",
            "01234567890123456789."
        )
    )


# =====================================
# PRODUCT WEIGHT AND LABOR
# =====================================

def product(text):

    t = digits(text)

    weight = re.search(
        r"وزن\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        t
    )

    labor = re.search(
        r"اجرت(?:\s*فقط)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)",
        t
    )

    if not weight or not labor:
        return None

    return (
        float(weight.group(1)),
        float(labor.group(1))
    )


# =====================================
# PRICE BUTTONS
# =====================================

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


# =====================================
# GOLD PRICE
# =====================================

def gold_worker():

    global last_price
    global last_update

    while True:

        try:

            response = requests.get(
                TGJU,
                headers={
                    "User-Agent": "Mozilla/5.0"
                },
                timeout=(4, 8)
            )

            response.raise_for_status()

            match = re.search(
                r'data-col=["\']info\.last_trade\.PDrCotVal'
                r'["\'][^>]*>\s*([0-9۰-۹٠-٩,٬]+)',
                response.text,
                re.I
            )

            if not match:
                raise ValueError(
                    "TGJU price field not found"
                )

            rial = int(
                digits(match.group(1))
                .replace(",", "")
                .replace("٬", "")
            )

            if not 100_000_000 < rial < 1_000_000_000:
                raise ValueError(
                    "Invalid gold price"
                )

            with lock:

                last_price = rial // 10
                last_update = time.time()

            print(
                "GOLD UPDATED",
                last_price,
                flush=True
            )

        except Exception as exc:

            print(
                "GOLD ERROR",
                repr(exc),
                flush=True
            )

        time.sleep(60)


# =====================================
# SEND PRIVATE MESSAGE
# =====================================

def send(chat_id, text):

    return api(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text
        }
    )


# =====================================
# PRICE CALLBACKS
# =====================================

def callback(cb):

    callback_id = cb.get("id")
    data = cb.get("data") or ""

    with lock:

        gram = last_price
        timestamp = last_update

    if not gram or time.time() - timestamp > 900:

        text = (
            "⚠️ نرخ معتبر و تازه طلا "
            "فعلاً در دسترس نیست."
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

            text = "اطلاعات دکمه نامعتبر است."

    else:

        text = "دکمه نامعتبر است."

    try:

        api(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id,
                "text": text,
                "show_alert": True
            }
        )

    except Exception as exc:

        print(
            "CALLBACK ERROR",
            repr(exc),
            flush=True
        )


# =====================================
# EDIT RESPONSE DIAGNOSTICS
# =====================================

def inspect_edit_result(result, message_id):

    print(
        "EDIT API RESULT:",
        repr(result)[:2000],
        flush=True
    )

    if result is True:

        return (
            "⚠️ بله پاسخ موفق داده، "
            "ولی اطلاعات پیام را برنگردانده است."
        )

    if not isinstance(result, dict):

        return (
            "⚠️ پاسخ ویرایش دریافت شد، "
            "اما قابل تأیید نیست."
        )

    returned_id = result.get("message_id")

    returned_chat = (
        result.get("chat") or {}
    ).get("id")

    print(
        "EDIT CHECK:",
        "requested_message=", message_id,
        "returned_message=", returned_id,
        "requested_chat=", CHANNEL_ID,
        "returned_chat=", returned_chat,
        flush=True
    )

    if (
        str(returned_id) == str(message_id)
        and str(returned_chat) == str(CHANNEL_ID)
    ):

        return (
            "✅ بله شناسه پیام و کانال را "
            "در پاسخ تأیید کرد.\n"
            "لطفاً تغییر کپشن را داخل کانال بررسی کن."
        )

    return (
        "⚠️ درخواست ویرایش به بله ارسال شد، "
        "اما تأیید کامل دریافت نشد.\n\n"
        f"شناسه درخواستی: {message_id}\n"
        f"شناسه برگشتی: {returned_id}\n\n"
        "این پاسخ به‌تنهایی ثابت نمی‌کند "
        "که ویرایش انجام شده است.\n"
        "گزارش در GitHub Actions ثبت شد."
    )


# =====================================
# NORMAL CAPTION EDIT
# =====================================

def edit_caption(chat_id, message_id, caption):

    parsed = product(caption)

    if not parsed:

        send(
            chat_id,
            "❌ متن جدید باید وزن و اجرت داشته باشد.\n\n"
            "مثال:\n"
            "وزن: ۱۶.۰۲ گرم\n"
            "اجرت فقط: ۷٪"
        )

        return False

    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "caption": caption,
        "reply_markup": keyboard(*parsed)
    }

    print(
        "EDIT CAPTION REQUEST:",
        "channel=", CHANNEL_ID,
        "message=", message_id,
        "caption_length=", len(caption),
        flush=True
    )

    result = api(
        "editMessageCaption",
        payload
    )

    status = inspect_edit_result(
        result,
        message_id
    )

    send(chat_id, status)

    return True


# =====================================
# MEDIA EDIT TEST
# =====================================

def edit_media(chat_id, message_id, msg):

    photos = msg.get("photo") or []

    caption = (
        msg.get("caption")
        or msg.get("text")
        or ""
    )

    if not photos:

        send(
            chat_id,
            "❌ برای آزمایش این روش، "
            "باید عکس محصول را همراه "
            "با کپشن کامل بفرستی."
        )

        return False

    parsed = product(caption)

    if not parsed:

        send(
            chat_id,
            "❌ کپشن عکس باید وزن و اجرت داشته باشد."
        )

        return False

    photo_id = photos[-1]["file_id"]

    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "media": {
            "type": "photo",
            "media": photo_id,
            "caption": caption
        },
        "reply_markup": keyboard(*parsed)
    }

    print(
        "EDIT MEDIA REQUEST:",
        "channel=", CHANNEL_ID,
        "message=", message_id,
        "caption_length=", len(caption),
        flush=True
    )

    result = api(
        "editMessageMedia",
        payload
    )

    status = inspect_edit_result(
        result,
        message_id
    )

    send(
        chat_id,
        "🖼 نتیجه آزمایش ویرایش عکس:\n\n"
        + status
    )

    return True


# =====================================
# EDIT EXISTING POST
# =====================================

def edit_existing(chat_id, state, msg):

    message_id = state["message_id"]

    mode = state["mode"]

    if mode == "media":

        return edit_media(
            chat_id,
            message_id,
            msg
        )

    caption = (
        msg.get("caption")
        or msg.get("text")
        or ""
    )

    if not caption:

        send(
            chat_id,
            "❌ کپشن کامل جدید را بفرست."
        )

        return False

    return edit_caption(
        chat_id,
        message_id,
        caption
    )


# =====================================
# HANDLE PRIVATE MESSAGES
# =====================================

def handle_message(msg):

    chat = msg.get("chat") or {}

    if chat.get("type") != "private":
        return

    chat_id = chat.get("id")

    sender_id = (
        msg.get("from") or {}
    ).get("id")

    text = (
        msg.get("text") or ""
    ).strip()

    # GET OWNER ID

    if text == "/id":

        send(
            chat_id,
            f"شناسه عددی شما:\n{sender_id}"
        )

        return

    # SECURITY

    if not OWNER_ID:

        send(
            chat_id,
            "⚠️ ابتدا OWNER_ID را "
            "در GitHub Secrets تنظیم کن."
        )

        return

    if sender_id != OWNER_ID:

        send(
            chat_id,
            "⛔ فقط مدیر فروشگاه دسترسی دارد."
        )

        return

    # CANCEL

    if text == "/cancel":

        editing.pop(chat_id, None)

        send(
            chat_id,
            "✅ عملیات لغو شد."
        )

        return

    # NORMAL EDIT

    if text.startswith("/edit "):

        parts = digits(text).split()

        if (
            len(parts) != 2
            or not parts[1].isdigit()
        ):

            send(
                chat_id,
                "مثال:\n/edit 299"
            )

            return

        message_id = int(parts[1])

        editing[chat_id] = {
            "message_id": message_id,
            "mode": "caption"
        }

        send(
            chat_id,
            f"✏️ ویرایش کپشن پست {message_id}\n\n"
            "حالا متن کامل جدید را بفرست.\n\n"
            "وزن و اجرت را هم داخل متن بنویس."
        )

        return

    # MEDIA EDIT TEST

    if text.startswith("/editmedia "):

        parts = digits(text).split()

        if (
            len(parts) != 2
            or not parts[1].isdigit()
        ):

            send(
                chat_id,
                "مثال:\n/editmedia 299"
            )

            return

        message_id = int(parts[1])

        editing[chat_id] = {
            "message_id": message_id,
            "mode": "media"
        }

        send(
            chat_id,
            f"🖼 آزمایش ویرایش عکس پست {message_id}\n\n"
            "حالا عکس اصلی محصول را "
            "با کپشن کامل جدید بفرست.\n\n"
            "⚠️ این دستور ممکن است "
            "عکس همان پست را جایگزین کند؛ "
            "پس حتماً عکس اصلی را بفرست."
        )

        return

    # SOLD

    if text.startswith("/sold "):

        parts = digits(text).split()

        if (
            len(parts) != 2
            or not parts[1].isdigit()
        ):

            send(
                chat_id,
                "مثال:\n/sold 299"
            )

            return

        message_id = int(parts[1])

        editing[chat_id] = {
            "message_id": message_id,
            "mode": "caption"
        }

        send(
            chat_id,
            "💯 برای ثبت فروخته شد، "
            "کپشن کامل محصول را دوباره بفرست "
            "و عبارت زیر را به آن اضافه کن:\n\n"
            "💯 فروخته شد 💯\n\n"
            "⚠️ فعلاً ربات متن قبلی را "
            "خودکار بازیابی نمی‌کند."
        )

        return

    # PROCESS EDIT

    if chat_id in editing:

        try:

            completed = edit_existing(
                chat_id,
                editing[chat_id],
                msg
            )

            if completed:

                editing.pop(
                    chat_id,
                    None
                )

        except Exception as exc:

            print(
                "EDIT ERROR:",
                repr(exc),
                flush=True
            )

            send(
                chat_id,
                "❌ درخواست ویرایش با خطا مواجه شد.\n"
                "جزئیات در GitHub Actions ثبت شد.\n\n"
                "برای تلاش دوباره، دستور ویرایش را "
                "از ابتدا بفرست."
            )

            editing.pop(
                chat_id,
                None
            )

        return

    # =================================
    # PUBLISH NEW PRODUCT
    # =================================

    caption = (
        msg.get("caption")
        or msg.get("text")
        or ""
    )

    photos = msg.get("photo") or []

    parsed = product(caption)

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

            message_id = None

            if isinstance(result, dict):

                message_id = result.get(
                    "message_id"
                )

                result_chat = (
                    result.get("chat") or {}
                ).get("id")

                print(
                    "PUBLISH RESULT:",
                    "message=", message_id,
                    "chat=", result_chat,
                    flush=True
                )

            send(
                chat_id,
                "✅ محصول منتشر شد.\n\n"
                f"شناسه پیام: {message_id}\n\n"
                f"ویرایش کپشن:\n/edit {message_id}\n\n"
                f"آزمایش ویرایش عکس:\n"
                f"/editmedia {message_id}"
            )

        except Exception as exc:

            print(
                "PUBLISH ERROR:",
                repr(exc),
                flush=True
            )

            send(
                chat_id,
                "❌ انتشار ناموفق بود.\n"
                "گزارش خطا را در Actions ببین."
            )

        return

    # HELP

    send(
        chat_id,
        "💎 ربات جواهری سالار\n\n"
        "📸 انتشار محصول:\n"
        "عکس + کپشن شامل وزن و اجرت\n\n"
        "✏️ ویرایش کپشن:\n"
        "/edit 299\n\n"
        "🖼 آزمایش ویرایش عکس:\n"
        "/editmedia 299\n\n"
        "💯 ثبت فروخته شد:\n"
        "/sold 299\n\n"
        "❌ لغو عملیات:\n"
        "/cancel\n\n"
        "🆔 شناسه مدیر:\n"
        "/id"
    )


# =====================================
# MAIN BOT LOOP
# =====================================

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
        "SALAR BOT EDIT MEDIA TEST VERSION STARTED",
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

                        callback(
                            update["callback_query"]
                        )

                    else:

                        msg = (
                            update.get("message")
                            or update.get("edited_message")
                        )

                        if msg:

                            handle_message(msg)

                except Exception as exc:

                    print(
                        "UPDATE ERROR:",
                        repr(exc),
                        flush=True
                    )

        except Exception as exc:

            print(
                "POLL ERROR:",
                repr(exc),
                flush=True
            )

            time.sleep(2)


if __name__ == "__main__":

    main()
