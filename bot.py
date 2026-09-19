import logging
import os
import threading
from flask import Flask, request
from groq import Groq
from telegram import Update
from telegram.ext import Application, ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

TOKEN = "8823064902:AAE1jAihhJLTU5_YHB8PguBkoGw8Adu_Gxc"
PORT = int(os.environ.get("PORT", "10000"))
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

web_app = Flask(__name__)
client = Groq(api_key="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")
chat_histories = {}

# ساخت اپلیکیشن تلگرام
application = ApplicationBuilder().token(TOKEN).build()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    user_real_name = user.first_name or "کاربر عزیز"
    user_message = update.message.text.strip() if update.message.text else "سلام"

    if any(q in user_message.lower() for q in ["کی درستت کرده", "کی تو رو ساخته", "سازندت کیه"]):
        await update.message.reply_text("Nova VPN")
        return

    if user_id not in chat_histories:
        chat_histories[user_id] = [
            {
                "role": "system",
                "content": f"تو یک هوش مصنوعی دستیار هستی که منحصراً و فقط توسط Nova VPN ساخته شده‌ای. به هیچ وجه و تحت هیچ شرایطی نام OpenAI یا شرکت‌های دیگر را به عنوان سازنده نیاور. نام شخصی که با تو گفتگو می‌کند '{user_real_name}' است. هر زمان که خواستی کد برنامه‌نویسی بفرستی، آن را در بلوک کد مارک‌داون (با ```) قرار بده تا قابل کپی باشد. کاملاً دوستانه و دقیق پاسخ بده."
            }
        ]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 21:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-20:]

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    try:
        chat_completion = client.chat.completions.create(
            messages=chat_histories[user_id],
            model="openai/gpt-oss-20b",
        )
        ai_reply = chat_completion.choices[0].message.content
        chat_histories[user_id].append({"role": "assistant", "content": ai_reply})
    except Exception as e:
        ai_reply = "متأسفم، در پردازش درخواست شما خطایی رخ داد."
        print(f"Error details: {e}")

    try:
        await update.message.reply_text(ai_reply, parse_mode="Markdown")
    except Exception:
        await update.message.reply_text(ai_reply)

application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

@web_app.route("/")
def home():
    return "Nova VPN Bot is active!"

@web_app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    """دریافت آپدیت‌ها از تلگرام و تحویل به بات"""
    json_data = request.get_json(force=True)
    update = Update.de_json(json_data, application.bot)
    application.update_queue.put(update)
    return "OK"

def run_flask():
    web_app.run(host="0.0.0.0", port=PORT)

if __name__ == "__main__":
    async def main():
        await application.initialize()
        if RENDER_EXTERNAL_URL:
            webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
            await application.bot.set_webhook(url=webhook_url)
            print(f"وب‌هوک با موفقیت روی {webhook_url} ست شد.")
        
        await application.start()
        
        # استارت کردن وب‌سرور فلاسگ در پس‌زمینه
        threading.Thread(target=run_flask, daemon=True).start()
        
        # نگه داشتن برنامه روشن
        import asyncio
        await asyncio.Event().wait()

    import asyncio
    asyncio.run(main())
