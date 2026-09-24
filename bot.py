cat << 'EOF' > bot.py
import os
import logging
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "AI Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

GROQ_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) در متغیرهای محیطی یافت نشد!")

client = Groq(api_key=GROQ_KEY)

chat_histories = {}

def fix_markdown(text):
    if text.count("```") % 2 != 0:
        text += "\n```"
    return text

async def send_long_message(update: Update, text: str):
    max_length = 3000
    if len(text) <= max_length:
        safe_text = fix_markdown(text)
        try:
            await update.message.reply_text(safe_text, parse_mode="Markdown")
        except Exception:
            await update.message.reply_text(text)
    else:
        parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
        for index, part in enumerate(parts):
            prev_text = "".join(parts[:index])
            is_inside_code = (prev_text.count("```") % 2 != 0)
            
            current_part = part
            if is_inside_code:
                current_part = "```python\n" + current_part
            
            if current_part.count("```") % 2 != 0:
                current_part += "\n```"
            
            try:
                await update.message.reply_text(current_part, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(part)

SYSTEM_PROMPT = (
    "تو دستیار هوشمند، خفن و خیلی باحالِ برنامه‌نویسیِ تیم NOVA VPN هستی. "
    "لحن صحبت کردنت باید صمیمی، خودمانی، پرانرژی، رفاقتی و باحال باشه و از ایموجی‌های جذاب استفاده کنی. "
    "اگر کسی پرسید سازنده تو کیست، با انرژی بگو: «من توسط تیم خفن NOVA VPN ساخته شدمه‌ام!» و هیچ توضیح اضافه‌ای نده. "
    "متن‌ها رو خیلی مرتب، با پاراگراف‌بندی خلوت و خطوط خالی بین بخش‌ها بنویس. "
    "هر زمان کاربر درخواست کدنویسی داد، با دست باز براش بنویس و حتماً کدهای برنامه‌نویسی رو داخل بلوک کد (```) بذار."
)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_name = user.first_name
    
    chat_histories[user.id] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": f"سلام. من {user_name} هستم."
        }
    ]
    
    welcome_message = (
        f"سلام {user_name} گل! 🚀 به ربات **NOVA VPN** خوش اومدی.\n\n"
        "من اینجام تا توی هر پروژه‌ و کدنویسی‌ای که داری کمکت کنم. چطور می‌تونم برات مفید باشم؟ 😎"
    )
    await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_message = update.message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 15:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-14:]

    bot_response = None
    last_error = None

    active_models = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile", "openai/gpt-oss-20b"]

    for model_name in active_models:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=chat_histories[user_id],
                temperature=0.8,
                max_tokens=4096
            )
            bot_response = completion.choices[0].message.content
            break
        except Exception as e:
            last_error = str(e)
            continue

    if bot_response:
        chat_histories[user_id].append({"role": "assistant", "content": bot_response})
        await send_long_message(update, bot_response)
    else:
        logging.error(f"Error handling message: {last_error}")
        await update.message.reply_text(f"❌ اوه، یه خطایی رخ داد:\n`{last_error}`", parse_mode="Markdown")

def main():
    t = Thread(target=run_web)
    t.start()

    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        raise ValueError("توکن ربات (BOT_TOKEN) در متغیرهای محیطی یافت نشد!")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("AI Bot is running with bot.py...")
    app.run_polling()

if __name__ == "__main__":
    main()
EOF
