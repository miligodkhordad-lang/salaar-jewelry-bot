import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"

# قیمت هر گرم طلای 18 عیار
# فعلاً برای تست دستی است؛ بعد از سالم شدن ربات
# قیمت آنلاین را به آن وصل می‌کنیم.
GOLD_PRICE = 24200000


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
        response.text,
        flush=True
    )

    return response


def calculate_price(weight, labor_percent):
    gold_value = weight * GOLD_PRICE
    labor = gold_value * labor_percent / 100
    total = gold_value + labor

    return f"""💎 جواهری سالار

⚖️ وزن: {weight:g} گرم

💰 قیمت هر گرم طلای ۱۸ عیار:
{money(GOLD_PRICE)} تومان

🔸 قیمت طلای خام:
{money(gold_value)} تومان

🔸 اجرت: {labor_percent:g}٪
{money(labor)} تومان

💵 قیمت نهایی:
{money(total)} تومان

🌱 @salar_jewelry"""


def help_text():
    return """💎 ربات جواهری سالار

برای محاسبه قیمت محصول بنویس:

/price وزن اجرت

مثال:

/price 9.51 5

یعنی:
وزن 9.51 گرم
اجرت 5 درصد"""


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
به ربات جواهری سالار خوش آمدید.

برای مشاهده راهنما:
/help

برای محاسبه قیمت:
/price وزن اجرت

مثال:
/price 9.51 5"""
        )

    elif text == "/help":
        send_message(chat_id, help_text())

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

            result = calculate_price(
                weight,
                labor_percent
            )

            send_message(
                chat_id,
                result
            )

        except (ValueError, TypeError):
            send_message(
                chat_id,
                """❌ اطلاعات درست وارد نشده.

فرمت صحیح:

/price وزن اجرت

مثال:

/price 9.51 5"""
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

            print(
                "getUpdates:",
                response.status_code,
                flush=True
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
