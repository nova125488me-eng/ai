import os
import logging
import asyncio
import yt_dlp
from datetime import datetime, timezone, timedelta
import zoneinfo
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from groq import Groq
import json

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "Advanced AI Assistant Bot is alive and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")

if not TOKEN:
    raise ValueError("توکن ربات (BOT_TOKEN) یافت نشد!")
if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) یافت نشد!")

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = Groq(api_key=GROQ_KEY)

chat_histories = {}

# --- توابع ابزار (Tools) برای دستیار هوشمند ---
def get_current_time(timezone_name: str = "Asia/Tehran"):
    """ساعت دقیق یک منطقه یا شهر مشخص را برمی‌گرداند."""
    try:
        tz = zoneinfo.ZoneInfo(timezone_name)
        now = datetime.now(tz)
        return json.dumps({
            "timezone": timezone_name,
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day": now.strftime("%A")
        }, ensure_ascii=False)
    except Exception as e:
        now = datetime.now(zoneinfo.ZoneInfo("Asia/Tehran"))
        return json.dumps({
            "timezone": "Asia/Tehran",
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "error": "منطقه زمانی نامعتبر بود، ساعت تهران اعلام شد."
        }, ensure_ascii=False)

def set_alarm_reminder(delay_seconds: int, message_text: str, chat_id: int):
    """تنظیم یک آلارم یا یادآور که بعد از تعداد ثانیه‌ مشخصی پیام بفرستد."""
    async def delayed_task():
        await asyncio.sleep(delay_seconds)
        try:
            await bot.send_message(chat_id=chat_id, text=f"⏰ **یادآوری / آلارم:**\n\n{message_text}")
        except Exception as e:
            logging.error(f"Error sending alarm: {e}")

    asyncio.create_task(delayed_task())
    return json.dumps({"status": "success", "message": f"آلارم با موفقیت پس از {delay_seconds} ثانیه تنظیم شد."})

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "ساعت دقیق یک شهر یا منطقه زمانی را به دست می‌آورد (پیش‌فرض تهران است).",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_name": {
                        "type": "string",
                        "description": "نام منطقه زمانی مثل Asia/Tehran, America/New_York, Europe/London"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_alarm_reminder",
            "description": "یک یادآور یا آلارم تنظیم می‌کند تا بعد از گذشت ثانیه‌های مشخص شده، پیامی به کاربر ارسال کند.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {
                        "type": "integer",
                        "description": "تعداد ثانیه‌هایی که باید صبر کرد تا آلارم زنگ بخورد."
                    },
                    "message_text": {
                        "type": "string",
                        "description": "متنی که باید در زمان یادآوری به کاربر فرستاده شود."
                    }
                },
                "required": ["delay_seconds", "message_text"]
            }
        }
    }
]

SYSTEM_PROMPT = (
    "تو دستیار هوشمند، خفن و خیلی باحالِ تیم NOVA VPN هستی. "
    "لحن صحبت کردنت صمیمی، خودمانی، پرانرژی و رفاقتی است و از ایموجی‌ها استفاده می‌کنی. "
    "تو توانایی چک کردن ساعت مناطق مختلف دنیا و تنظیم آلارم و یادآور را داری. "
    "اگر کاربر از تو خواست لینک دانلود ویدیو بفرستد، به او بگو لینک اینستاگرام یا تیک‌تاک بفرستد."
)

def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📥 راهنمای دانلود", callback_data="help_download"),
        types.InlineKeyboardButton(text="📊 وضعیت ربات", callback_data="system_stats")
    )
    return builder.as_markup()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    chat_histories[message.chat.id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    welcome_text = (
        f"سلام {user_name} گل! 🚀 به ربات پیشرفته‌ی **NOVA VPN** خوش اومدی.\n\n"
        "من هم می‌تونم ویدیوهای اینستاگرام و تیک‌تاک رو برات دانلود کنم و هم به عنوان دستیار هوشمندت ساعت رو بگم یا برات آلارم و یادآور تنظیم کنم! 😎"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.callback_query(F.data == "help_download")
async def help_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💡 **راهنمای استفاده:**\n\n"
        "▫️ برای دانلود: لینک اینستاگرام یا تیک‌تاک بفرست.\n"
        "▫️ برای دستیار: می‌تونی بپرسید «الان ساعت چنده‌؟» یا «۱۰ ثانیه دیگه به من یادآوری کن فلان کار رو کنم!»",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "system_stats")
async def stats_cb(callback: types.CallbackQuery):
    await callback.message.edit_text("📊 وضعیت سرور: هوشمند، پایدار و آماده به کار 🟢", reply_markup=get_main_menu())
    await callback.answer()

# هندلر لینک‌ها برای دانلود ویدیو
@dp.message(F.text.regexp(r'https?://[^\s]+'))
async def download_video(message: types.Message):
    url = message.text.strip()
    
    if "youtube.com" in url or "youtu.be" in url:
        await message.answer("⚠️ دانلود از یوتیوب غیرفعال است. لطفاً لینک **اینستاگرام یا تیک‌تاک** بفرستید.")
        return

    processing_msg = await message.answer("⏳ در حال دانلود ویدیو، لطفاً صبور باشید...")
    
    output_template = f"downloaded_video_{message.chat.id}.%(ext)s"
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'mp4/best',
        'max_filesize': 50 * 1024 * 1024,
    }
    
    try:
        def run_dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await asyncio.to_thread(run_dl)
        
        if filename and os.path.exists(filename):
            await message.answer_video(types.FSInputFile(filename), caption="✅ ویدیو با موفقیت دانلود شد!")
            try:
                os.remove(filename)
            except:
                pass
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
            except:
                pass
        else:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
            except:
                pass
            await message.answer("❌ خطا در دانلود فایل. لطفاً لینک معتبر بفرستید.")
            
    except Exception as e:
        logging.error(f"Error: {e}")
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
        except:
            pass
        await message.answer("❌ خطایی رخ داد یا لینک نامعتبر است.")

# هندلر پیام‌های متنی عادی و هوش مصنوعی با قابلیت ابزارها (Tools)
@dp.message()
async def handle_ai_message(message: types.Message):
    chat_id = message.chat.id
    user_message = message.text

    if chat_id not in chat_histories:
        chat_histories[chat_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[chat_id].append({"role": "user", "content": user_message})

    if len(chat_histories[chat_id]) > 15:
        chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-14:]

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
            messages=chat_histories[chat_id],
            tools=tools,
            tool_choice="auto",
            max_tokens=2048
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            chat_histories[chat_id].append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                tool_output = ""
                if function_name == "get_current_time":
                    tool_output = get_current_time(**function_args)
                elif function_name == "set_alarm_reminder":
                    function_args["chat_id"] = chat_id
                    tool_output = set_alarm_reminder(**function_args)
                
                chat_histories[chat_id].append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_output,
                })
            
            second_response = client.chat.completions.create(
                model="qwen/qwen3.8-27b",
                messages=chat_histories[chat_id]
            )
            final_reply = second_response.choices[0].message.content
            chat_histories[chat_id].append({"role": "assistant", "content": final_reply})
            await message.answer(final_reply)
        else:
            bot_response = response_message.content
            chat_histories[chat_id].append({"role": "assistant", "content": bot_response})
            await message.answer(bot_response)

    except Exception as e:
        logging.error(f"AI Error: {e}")
        await message.answer("❌ متأسفانه در پردازش درخواست شما خطایی رخ داد.")

async def main():
    t = Thread(target=run_web)
    t.start()

    print("🤖 ربات هوشمند پیشرفته روشن شد...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ ربات متوقف شد.")
