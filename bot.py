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
    return "AI Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

# خواندن کلید از متغیرهای محیطی رندر
GROQ_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) در متغیرهای محیطی یافت نشد!")

client = Groq(api_key=GROQ_KEY)

chat_histories = {}

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    chat_histories[user.id] = [
        {
            "role": "system",
            "content": (
                "تو یک هوش مصنوعی مستقل، مفید و خوش‌برخورد هستی که به زبان فارسی پاسخ می‌دهی. "
                "تو توسط OpenAI ساخته نشده‌ای و هیچ ارتباطی با آن نداری. "
                "اگر هرکسی پرسید سازنده تو کیست، صراحتاً بگو که یک دستیار هوش مصنوعی مستقل هستی که توسط OpenAI ساخته نشده است."
            )
        },
        {
            "role": "user",
            "content": f"سلام. من {user_name} هستم."
        }
    ]
    
    welcome_message = (
        f"سلام {user_name} عزیز! خوش آمدید.\n"
        "من یک دستیار هوش مصنوعی هستم. هر سوال یا درخواستی داری می‌تونی همینجا بپرسی تا کمکت کنم."
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
                    "تو یک هوش مصنوعی مستقل و خوش‌برخورد هستی که به زبان فارسی پاسخ می‌دهی. "
                    "تو توسط OpenAI ساخته نشده‌ای. اگر پرسیدند سازنده ات کیست، تأکید کن که ربات مستقل هوش مصنوعی هستی."
                )
            }
        ]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 15:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-14:]

    bot_response = None
    last_error = None

    # لیست مدل‌های قطعی و فعال حال حاضر گروق
    active_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]

    for model_name in active_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=chat_histories[user_id],
                temperature=0.7,
                max_tokens=512,
            )
            bot_response = completion.choices[0].message.content
            break
        except Exception as e:
            last_error = str(e)
            continue

    if bot_response:
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})
        await update.message.reply_text(bot_response, parse_mode="Markdown")
    else:
        logging.error(f"Error handling message: {last_error}")
        await update.message.reply_text(f"⚠️ خطای هوش مصنوعی:\n`{last_error}`", parse_mode="Markdown")

def main():
    t = Thread(target=run_web)
    t.start()

    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("توکن ربات (BOT_TOKEN) در متغیرهای محیطی یافت نشد!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("AI Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
