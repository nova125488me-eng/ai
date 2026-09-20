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

def get_working_model():
    """لیست مدل‌ها را می‌گیرد و مدل‌های امنیتی یا دسته‌بندی (Guard/Classification) را رد می‌کند"""
    try:
        models_response = client.models.list()
        available_models = [m.id for m in models_response.data]
        print(f"--> Available models: {available_models}")
        
        for model_id in available_models:
            # رد کردن مدل‌های غیرچت، امنیتی یا دسته‌بندی
            if any(bad_keyword in model_id.lower() for bad_keyword in ["guard", "classif", "embed", "whisper", "vision", "audio", "tool-use"]):
                continue
            # انتخاب مدل‌های استاندارد چت
            if "llama" in model_id or "gemma" in model_id or "mixtral" in model_id or "versatile" in model_id:
                print(f"--> Selected valid chat model: {model_id}")
                return model_id
                
    except Exception as e:
        print(f"--> Error fetching model list: {e}")
        
    return "llama-3.3-70b-versatile" # مدل پیش‌فرض مطمئن برای چت

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

    try:
        current_model = get_working_model()
        
        completion = client.chat.completions.create(
            model=current_model,
            messages=chat_histories[user_id],
            temperature=0.7,
            max_tokens=512,
        )
        bot_response = completion.choices[0].message.content
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})
        await update.message.reply_text(bot_response, parse_mode="Markdown")
        
    except Exception as e:
        logging.error(f"Error handling message: {e}")
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
