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

# خواندن کلید از متغیرهای محیطی رندر
GROQ_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) در متغیرهای محیطی یافت نشد!")

client = Groq(api_key=GROQ_KEY)

# لیست مدل‌های جایگزین به ترتیب اولویت برای جلوگیری از خطای 404
FALLBACK_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "mixtral-8x7b-32768"
]

chat_histories = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    chat_histories[user.id] = [
        {
            "role": "user",
            "content": (
                f"سلام. من {user_name} هستم. تو از این به بعد دستیار تخصصی برند 'Nova VPN' هستی. "
                f"به هیچ وجه نام OpenAI را نیاور و بگو توسط Nova VPN ساخته شده‌ای."
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
                "role": "user",
                "content": f"من {user_name} هستم. تو دستیار تخصصی Nova VPN هستی."
            }
        ]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 20:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-19:]

    bot_response = None
    last_error = None

    # امتحان کردن مدل‌ها به ترتیب لیست بالا تا زمانی که یکی پاسخ دهد
    for model_name in FALLBACK_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=chat_histories[user_id],
                temperature=0.7,
                max_tokens=512,
            )
            bot_response = completion.choices[0].message.content
            break # اگر مدل موفق بود، از حلقه خارج شو
        except Exception as e:
            last_error = str(e)
            continue # اگر مدل خطا داد، برو سراغ مدل بعدی

    if bot_response:
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})
        await update.message.reply_text(bot_response, parse_mode="Markdown")
    else:
        logging.error(f"All models failed. Last error: {last_error}")
        await update.message.reply_text(f"⚠️ خطای موقتی هوش مصنوعی:\n`{last_error}`", parse_mode="Markdown")

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
