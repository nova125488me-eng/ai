import logging
import os
from groq import Groq
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

client = Groq(api_key="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")

chat_histories = {}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    # خواندن اسم واقعی کاربر از پروفایل تلگرام (اولین نام یا نام کامل)
    user_real_name = user.first_name or "کاربر عزیز"
    user_message = update.message.text.strip()
    
    if any(q in user_message.lower() for q in ["کی درستت کرده", "کی تو رو ساخته", "سازندت کیه"]):
        await update.message.reply_text("Nova VPN")
        return

    # اگر کاربر جدید است، اسمش را از پروفایل تلگرام می‌خوانیم و به سیستم می‌دهیم
    if user_id not in chat_histories:
        chat_histories[user_id] = [
            {
                "role": "system",
                "content": f"تو یک هوش مصنوعی هستی که توسط Nova VPN ساخته و توسعه داده شده‌ای. نام شخصی که داری با او گفتگو می‌کنی '{user_real_name}' است (این نام از پروفایل تلگرامش خوانده شده است). اگر کسی پرسید تو را چه کسی ساخته، حتما بگو Nova VPN و در طول گفتگو با نام خودش ({user_real_name}) مخاطبش قرار بده."
            }
        ]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 21:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-20:]

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

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

    await update.message.reply_text(ai_reply)

if __name__ == "__main__":
    TOKEN = "8823064902:AAE1jAihhJLTU5_YHB8PguBkoGw8Adu_Gxc"
    PORT = int(os.environ.get("PORT", "8080"))
    RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL")

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=TOKEN,
            webhook_url=webhook_url,
        )
        print(f"ربات در حالت Webhook روی پورت {PORT} روشن شد...")
    else:
        print("ربات در حالت پولینگ روشن شد...")
        app.run_polling()
