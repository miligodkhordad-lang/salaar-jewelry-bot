import os
import time
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN")

API = f"https://tapi.bale.ai/bot{BOT_TOKEN}"


def money(number):
    return f"{int(round(number)):,}".replace(",", "٬")


def send_message(chat_id, text):
    requests.post(
        f"{API}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text
        },
        timeout=30
    )


def calculate_price(weight, gold_price, labor_percent, tax_percent):
    gold_value = weight * gold_price
    labor = gold_value * labor_percent / 100
    subtotal = gold_value + labor
    tax = subtotal * tax_percent / 100
    total = subtotal + tax

    if tax_percent == 0:
        tax_text = "❌ ندارد"
    else:
        tax_text = f"💰 {money(tax)} تومان"

    return f"""💎 قیمت نهایی

طلای خام: {money(gold_value)} تومان
اجرت: {labor_percent}٪
مالیات: {tax_text}

━━━━━━━━━━━━

💰 قیمت نهایی:
{money(total)} تومان
"""


def handle_message(message):
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id:
        return

    if text == "/start":
        send_message(
            chat_id,
            """سلام 👋

برای محاسبه قیمت طلا از دستور زیر استفاده کن:

/price وزن_گرم قیمت_هر_گرم اجرت_درصد مالیات_درصد

مثال:

/price 9.51 19502687 1 0"""
        )

    elif text.startswith("/price"):
        try:
            parts = text.split()

            if len(parts) != 5:
                raise ValueError

            weight = float(parts[1])
            gold_price = float(parts[2])
            labor_percent = float(parts[3])
            tax_percent = float(parts[4])

            result = calculate_price(
                weight,
                gold_price,
                labor_percent,
                tax_percent
            )

            send_message(chat_id, result)

        except (ValueError, TypeError):
            send_message(
                chat_id,
                """❌ اطلاعات وارد شده صحیح نیست.

مثال:

/price 9.51 19502687 1 0"""
            )


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN تنظیم نشده است")

    offset = 0

    print("Bale bot is running...")

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
                print(data)
                time.sleep(5)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                message = update.get("message")

                if message:
                    handle_message(message)

        except Exception as e:
            print("Error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
