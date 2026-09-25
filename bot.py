import os
import logging
import asyncio
import sqlite3
import json
import zoneinfo
from datetime import datetime
import yt_dlp
from flask import Flask
from threading import Thread
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from groq import Groq

# ================= CONFIG & LOGGING =================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)

app_flask = Flask('')

@app_flask.route('/')
def home():
    return "🚀 NOVA Ultra-Friendly Bot is live and running!"

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
dp = Dispatcher(storage=MemoryStorage())
client = Groq(api_key=GROQ_KEY)

chat_histories = {}
DB_NAME = "nova_assistant.db"

# ================= DATABASE ENGINE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def save_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur.execute("""
        INSERT OR IGNORE INTO users (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, username, first_name, now))
    conn.commit()
    conn.close()

# ================= AI TOOLS =================
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
            await bot.send_message(chat_id=chat_id, text=f"⏰ **یادآوری رفاقتی:**\n\n{message_text}")
        except Exception as e:
            logging.error(f"Error sending alarm: {e}")

    asyncio.create_task(delayed_task())
    return json.dumps({"status": "success", "message": f"آلارم با موفقیت پس از {delay_seconds} ثانیه تنظیم شد."})

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "ساعت دقیق یک شهر یا منطقه زمانی را به دست می‌آورد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_name": {
                        "type": "string",
                        "description": "نام منطقه زمانی مثل Asia/Tehran"
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
            "description": "یک یادآور یا آلارم تنظیم می‌کند تا بعد از گذشت ثانیه‌های مشخص شده، پیام بفرستد.",
            "parameters": {
                "type": "object",
                "properties": {
                    "delay_seconds": {
                        "type": "integer",
                        "description": "تعداد ثانیه‌ها"
                    },
                    "message_text": {
                        "type": "string",
                        "description": "متن یادآوری"
                    }
                },
                "required": ["delay_seconds", "message_text"]
            }
        }
    }
]

# پرامپت سیستمی کاملاً خودمانی، فارسی و رفاقتی
SYSTEM_PROMPT = (
    "تو دستیار هوشمند، فوق‌العاده باحال، صمیمی و رفیق فابریکِ امیرعلی هستی. "
    "یادت باشه: سازنده، خالق و پروژه‌ی تو «NOVA VPN» است و توسط امیرعلی توسعه داده شده‌ای! اگر کسی پرسید سازنده‌ات کیه، با افتخار بگو ساخت تیم NOVA VPN هستی. "
    "تک‌تک جملاتت رو با لحنی کاملاً خودمانی، پرانرژی، گرم و صمیمی بنویس. "
    "قانون مهم نگارشی: در پاسخ‌های معمولی و متنی به هیچ وجه از علامت ستاره (**) یا کاراکترهای نشانه‌گذاری شلوغ استفاده نکن! متن‌ها باید کاملاً ساده، خط‌به‌خط، با فاصله‌گذاری مناسب و بدون ستاره نوشته شوند تا چشم کاربر خسته نشود. "
    "به هیچ وجه از کلمات یا کاراکترهای چینی، ژاپنی یا زبان‌های دیگه استفاده نکن و همیشه کاملاً روان، فارسی و شیرین صحبت کن. "
    "قانون حیاتی برای کدنویسی: فقط و فقط برای کدهای پایتون یا اسکریپت‌ها، از باکس‌های مونو استایل (Code Blocks) استفاده کن تا کاربر بتواند با یک کلیک آن‌ها را کپی کند. کدها باید خط‌به‌خط، تمیز و با توررفتگی دقیق باشند. "
    "می‌تونی ساعت رو بگی، آلارم تنظیم کنی و لینک‌های اینستاگرام یا تیک‌تاک رو هم خیلی تمیز مدیریت کنی."
)
# ================= KEYBOARDS =================
def get_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📥 راهنمای دانلود", callback_data="help_download"),
        types.InlineKeyboardButton(text="☕️ درباره من", callback_data="about_bot")
    )
    return builder.as_markup()

# ================= HANDLERS =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_name = message.from_user.first_name
    user_id = message.from_user.id
    username = message.from_user.username
    
    save_user(user_id, username, user_name)
    chat_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    welcome_text = (
        f"سلام {user_name} جان، چطوری داش؟! 🚀😎\n\n"
        "من اومدم تا به عنوان رفیقِ شفیقت توی کدنویسی، دانلود ویدیوهای اینستا و تیک‌تاک، و کارهای باحالِ دیگه کمکت کنم. هر چی می‌خوای بگو تا با هم ردیفش کنیم! 🔥"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu())

@dp.callback_query(F.data == "help_download")
async def help_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💡 **راهنمای رفاقتی:**\n\n"
        "▫️ **کدنویسی:** هر جا گیر کردی بگو تا برات کد پایتون بنویسم.\n"
        "▫️ **دانلود:** لینک اینستاگرام یا تیک‌تاک بفرست تا مستقیم فایلش رو بفرستم.\n"
        "▫️ **ساعت و آلارم:** کافیه بپرس ساعت چنده یا یادآوری تنظیم کنی!",
        reply_markup=get_main_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "about_bot")
async def about_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "☕️ من رباتِ اختصاصیِ خودِ توام؛ سریع، باهوش، صمیمی و بدون هیچ‌گونه ادا و اصول اضافه‌ای! هر کمکی خواستی روی من حساب کن. 😎",
        reply_markup=get_main_menu()
    )
    await callback.answer()

# ================= VIDEO DOWNLOADER =================
@dp.message(F.text.regexp(r'https?://[^\s]+'))
async def download_video(message: types.Message):
    url = message.text.strip()
    
    if "youtube.com" in url or "youtu.be" in url:
        await message.answer("⚠️ داش یوتیوب فعلاً تعطیله، لطفاً لینک معتبر **اینستاگرام یا تیک‌تاک** بفرست! 😉")
        return

    processing_msg = await message.answer("⏳ دمت گرم، صبور باش دارم ویدیو رو می‌کشم بیرون...")
    
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
            await message.answer_video(types.FSInputFile(filename), caption="✅ بیا اینم ویدیوت، حالشو ببر! 😎")
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
            await message.answer("❌ داداش لینکه‌ مشکل داشت، نتونستم دانلود کنم.")
            
    except Exception as e:
        logging.error(f"Download Error: {e}")
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
        except:
            pass
        await message.answer("❌ اوه اوه، یه جای کار لنگ زد یا لینک معتبر نبود.")

# ================= AI CHAT & TOOL EXECUTION =================
@dp.message()
async def handle_ai_message(message: types.Message):
    user_id = message.from_user.id
    user_message = message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    if len(chat_histories[user_id]) > 15:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-14:]

    try:
        # تغییر مدل به نسخه قدرتمند جدید با هوش بالا و بدون چینی‌بازی
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=chat_histories[user_id],
            tools=tools,
            tool_choice="auto",
            max_tokens=800
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            chat_histories[user_id].append(response_message)
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                tool_output = ""
                if function_name == "get_current_time":
                    tool_output = get_current_time(**function_args)
                elif function_name == "set_alarm_reminder":
                    function_args["chat_id"] = user_id
                    tool_output = set_alarm_reminder(**function_args)
                
                chat_histories[user_id].append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_output,
                })
            
            second_response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=chat_histories[user_id],
                max_tokens=800
            )
            final_reply = second_response.choices[0].message.content
            chat_histories[user_id].append({"role": "assistant", "content": final_reply})
            await message.answer(final_reply)
        else:
            bot_response = response_message.content
            chat_histories[user_id].append({"role": "assistant", "content": bot_response})
            await message.answer(bot_response)

    except Exception as e:
        logging.error(f"AI Error: {e}")
        await message.answer("❌ داداش یه خطای کوچیک پیش اومد، دوباره بگو تا حلش کنیم.")

# ================= MAIN ENTRY =================
async def main():
    t = Thread(target=run_web)
    t.start()

    print("🤖 ربات رفیق و باحالِ امیرعلی با موفقیت روشن شد و آماده‌ی ترکوندنه...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ ربات متوقف شد.")
