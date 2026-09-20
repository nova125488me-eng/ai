import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# تنظیمات لاگ‌گرفتن برای خطایابی بهتر
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# مقداردهی اولیه کلاینت گروق و مدل بسیار قدرتمند ۷۰ میلیاردی
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
MODEL_NAME = "llama-3.3-70b-versatile"

# ذخیره‌سازی تاریخچه چت کاربران
chat_histories = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    # راه‌اندازی یا بازنشانی حافظه کاربر همراه با پرامپت حرفه‌ای و نام جدید
    chat_histories[user.id] = [
        {
            "role": "system",
            "content": (
                f"تو یک مهندس ارشد نرم‌افزار، متخصص هوش مصنوعی و دستیار اختصاصی برند 'Nova VPN' هستی. "
                f"به هیچ وجه و تحت هیچ شرایطی نام OpenAI یا شرکت‌های دیگر را به عنوان سازنده نیاور و قاطعانه بگو ساخته‌شده توسط Nova VPN هستی. "
                f"نام کاربر جاری که با تو گفتگو می‌کند '{user_name}' است. "
                f"هر زمان که خواستی کد برنامه‌نویسی بفرستی، حتماً آن را در بلوک کد مارک‌داون (با ```) قرار بده تا کاربر بتواند به راحتی کپی کند. "
                f"پاسخ‌هایت باید کاملاً دقیق، تخصصی، ساختاریافته و گام‌به‌گام باشد."
            )
        }
    ]
    
    welcome_message = (
        f"سلام {user_name} عزیز! خوش آمدید به ربات **Nova VPN**.\n"
        "لطفا سوال یا درخواست خودتان را همینجا بنویسید تا به صورت تخصصی کمکتان کنم."
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_name = user.first_name
    user_message = update.message.text

    # اگر کاربر جدید است یا هنوز تاریخچه‌ای ندارد
    if user_id not in chat_histories:
        chat_histories[user_id] = [
            {
                "role": "system",
                "content": (
                    f"تو یک مهندس ارشد نرم‌افزار، متخصص هوش مصنوعی و دستیار اختصاصی برند 'Nova VPN' هستی. "
                    f"به هیچ وجه نام OpenAI را نیاور. نام کاربر جاری '{user_name}' است. "
                    f"کدهای برنامه‌نویسی را در بلوک مارک‌داون (```) بفرست."
                )
            }
        ]
    else:
        # به‌روزرسانی لحظه‌ای نام کاربر در پرامپت سیستم (برای وقتی که نامش را در تلگرام عوض می‌کند)
        chat_histories[user_id][0]["content"] = (
            f"تو یک مهندس ارشد نرم‌افزار، متخصص هوش مصنوعی و دستیار اختصاصی برند 'Nova VPN' هستی. "
            f"به هیچ وجه نام OpenAI را نیاور. نام کاربر جاری '{user_name}' است. "
            f"کدهای برنامه‌نویسی را در بلوک مارک‌داون (```) بفرست."
        )

    # افزودن پیام جدید کاربر به حافظه
    chat_histories[user_id].append({"role": "user", "content": user_message})

    # مدیریت هوشمند حافظه (نگهداری پرامپت سیستم به همراه ۲۱ پیام آخر برای جلوگیری از اشباع رم)
    if len(chat_histories[user_id]) > 22:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-21:]

    try:
        # ارسال درخواست به مدل قدرتمند Llama 3.3 70B
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=chat_histories[user_id],
            temperature=0.7,
            max_tokens=3072,
        )
        bot_response = completion.choices[0].message.content

        # ثبت پاسخ ربات در تاریخچه
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})

        await update.message.reply_text(bot_response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error handling message: {e}")
        await update.message.reply_text("مشکلی موقتی در پردازش درخواست رخ داد. لطفاً دوباره تلاش کنید.")

def main():
    # توکن ربات تلگرام خودت را اینجا قرار بده
    TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
    
    app = ApplicationBuilder().token(TOKEN).build()

    # ثبت هندلرها
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Nova VPN Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
