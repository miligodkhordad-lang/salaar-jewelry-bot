import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")


def money(number):
    return f"{int(round(number)):,}".replace(",", "٬")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = """
سلام 👋

برای محاسبه قیمت طلا از دستور زیر استفاده کن:

/price وزن قیمت_هر_گرم اجرت_درصد مالیات_درصد

مثال:

/price 9.51 19502687 1 0
"""
    await update.message.reply_text(text)


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if len(context.args) < 4:
            await update.message.reply_text(
                "❌ فرمت اشتباهه.\n\n"
                "مثال:\n"
                "/price 9.51 19502687 1 0"
            )
            return

        weight = float(context.args[0])
        gold_price = float(context.args[1])
        labor_percent = float(context.args[2])
        tax_percent = float(context.args[3])

        gold_value = weight * gold_price

        labor = gold_value * labor_percent / 100

        subtotal = gold_value + labor

        tax = subtotal * tax_percent / 100

        final_price = subtotal + tax

        if tax_percent == 0:
            tax_text = "❌ ندارد"
        else:
            tax_text = f"💰 {money(tax)} تومان"

        result = f"""
✨ قیمت روز محصول

🟡 طلای ۱۸ عیار: {money(gold_price)} تومان

⚖️ وزن: {weight:g} گرم

🧾 مالیات: {tax_text}

💎 اجرت: {labor_percent:g}٪

💵 اجرت به تومان: {money(labor)} تومان

💰 مبلغ نهایی: {money(final_price)} تومان
"""

        await update.message.reply_text(result)

        # اگر CHANNEL_ID تنظیم شده باشد، همین متن را به کانال هم می‌فرستد
        if CHANNEL_ID:
            await context.bot.send_message(
                chat_id=CHANNEL_ID,
                text=result
            )

    except ValueError:
        await update.message.reply_text(
            "❌ اطلاعات وارد شده صحیح نیست.\n\n"
            "مثال:\n"
            "/price 9.51 19502687 1 0"
        )


def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN تنظیم نشده است")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
