import os
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# تنظیمات لاگ‌گرفتن
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# راه‌اندازی وب‌سرور برای پاسخ به پورت رندر
app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Nova VPN Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# اتصال به گروق با کلید شما
client = Groq(api_key="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")

# لیست مدل‌های مختلف برای تست خودکار
CANDIDATE_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "gemma-7b-it"
]

chat_histories = {}

def get_working_completion(messages):
    """تابع هوشمند برای تست و پیدا کردن مدلی که روی این کلید API فعال است"""
    last_error = None
    for model in CANDIDATE_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=3072,
            )
            return completion.choices[0].message.content
        except Exception as e:
            last_error = e
            continue
    raise last_error

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
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
        chat_histories[user_id][0]["content"] = (
            f"تو یک مهندس ارشد نرم‌افزار، متخصص هوش مصنوعی و دستیار اختصاصی برند 'Nova VPN' هستی. "
            f"به هیچ وجه نام OpenAI را نیاور. نام کاربر جاری '{user_name}' است. "
            f"کدهای برنامه‌نویسی را در بلوک مارک‌داون (```) بفرست."
        )

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 22:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-21:]

    try:
        # استفاده از تابع تست خودکار مدل
        bot_response = get_working_completion(chat_histories[user_id])
        
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})
        await update.message.reply_text(bot_response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error handling message with all models: {e}")
        await update.message.reply_text("مشکلی موقتی در پردازش درخواست رخ داد. لطفاً دوباره تلاش کنید.")

def main():
    t = Thread(target=run_web)
    t.start()

    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("توکن ربات (BOT_TOKEN) در متغیرهای محیطی یافت نشد!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("Nova VPN Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
