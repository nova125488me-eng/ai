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
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
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
    return "🚀 NOVA VPN Ultra-Advanced Bot is live and running!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host='0.0.0.0', port=port)

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")
# آیدی عددی ادمین خودت رو اینجا بگذار تا به پنل ادمین دسترسی داشته باشی
ADMIN_ID = int(os.environ.get("ADMIN_ID", "123456789")) 

if not TOKEN:
    raise ValueError("توکن ربات (BOT_TOKEN) یافت نشد!")
if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) یافت نشد!")

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())
client = Groq(api_key=GROQ_KEY)

chat_histories = {}
DB_NAME = "nova_database.db"

# ================= DATABASE ENGINE =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT,
            status TEXT DEFAULT 'active'
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            key TEXT PRIMARY KEY,
            value INTEGER
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

def get_total_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    conn.close()
    return count

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
    "تو مغز متفکر، خفن و فوق‌العاده حرفه‌ایِ ربات NOVA VPN هستی. "
    "لحن صحبت کردنت صمیمی، پرانرژی، خودمانی و رفاقتی است و از ایموجی‌های جذاب استفاده می‌کنی. "
    "تو یک مهندس نرم‌افزار و برنامه‌نویس بی‌نظیر پایتون هستی. هرگاه کاربر درخواست کدنویسی داد، سورس‌کد کامل، تمیز، استاندارد و بدون نقص را تا آخرین خط می‌نویسی و به هیچ وجه آن را نصفه رها نمی‌کنی. "
    "تو قابلیت بررسی ساعت جهانی و تنظیم آلارم را داری."
)

# ================= KEYBOARDS =================
def get_main_menu(user_id):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📥 راهنمای دانلود", callback_data="help_download"),
        types.InlineKeyboardButton(text="📊 وضعیت سرور", callback_data="system_stats")
    )
    builder.row(
        types.InlineKeyboardButton(text="💎 خرید اشتراک ویژه", callback_data="buy_sub"),
        types.InlineKeyboardButton(text="📞 پشتیبانی", callback_data="support")
    )
    if user_id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ پنل مدیریت", callback_data="admin_panel"))
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
        f"سلام {user_name} جان! 🚀 به سیستم فوق‌پیشرفته و قدرتمند **NOVA VPN** خوش اومدی.\n\n"
        "من دستیار همه‌فن‌حریف تو هستم؛ می‌تونم ویدیوهای اینستاگرام و تیک‌تاک رو با سرعت برات دانلود کنم، کدهای برنامه‌نویسی رو برات بنویسم، ساعت رو بگم یا برات یادآور تنظیم کنم! 😎 چه کمکی از دست من برمیاد؟"
    )
    await message.answer(welcome_text, reply_markup=get_main_menu(user_id))

@dp.callback_query(F.data == "help_download")
async def help_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💡 **راهنمای جامع استفاده از ربات:**\n\n"
        "▫️ **دانلود ویدیو:** کافیه لینک پست اینستاگرام یا تیک‌تاک رو بفرستی تا مستقیم فایل رو تحویلت بدم.\n"
        "▫️ **هوش مصنوعی و کدنویسی:** هر سوالی داری بپرس یا بگو برات کد پایتون بنویسم.\n"
        "▫️ **دستیار هوشمند:** ازم بخواه ساعت کشورهای مختلف رو بگم یا برات آلارم تنظیم کنم!",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "system_stats")
async def stats_cb(callback: types.CallbackQuery):
    total_users = get_total_users()
    stats_text = (
        f"📊 **گزارش وضعیت سیستم NOVA:**\n\n"
        f"🟢 وضعیت سرور: آنلاین و پایدار\n"
        f"👥 کل کاربران ثبت‌نام شده: {total_users} نفر\n"
        f"⚡️ موتور هوش مصنوعی: فعال و پرسرعت"
    )
    await callback.message.edit_text(stats_text, reply_markup=get_main_menu(callback.from_user.id))
    await callback.answer()

@dp.callback_query(F.data == "buy_sub")
async def buy_sub_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "💎 **خرید اشتراک پرسرعت NOVA VPN:**\n\n"
        "برای خرید اکانت پرسرعت با حجم نامحدود و پینگ فوق‌العاده پایین، به پشتیبانی پیام بدهید.",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "support")
async def support_cb(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "📞 **ارتباط با تیم پشتیبانی:**\n\nهر گونه مشکل یا سوالی دارید، تیم ما 24 ساعته در خدمت شماست.",
        reply_markup=get_main_menu(callback.from_user.id)
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_panel")
async def admin_panel_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("❌ شما دسترسی ادمین ندارید!", show_alert=True)
        return
    
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📈 آمار کامل کاربران", callback_data="admin_stats"))
    builder.row(types.InlineKeyboardButton(text="🔙 بازگشت به منوی اصلی", callback_data="back_home"))
    
    await callback.message.edit_text("⚙️ **پنل مدیریت پیشرفته NOVA:**\n\nلطفاً گزینه مورد نظر را انتخاب کنید:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "admin_stats")
async def admin_stats_cb(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return
    total_users = get_total_users()
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔙 بازگشت به پنل", callback_data="admin_panel"))
    
    await callback.message.edit_text(f"📈 آمار کل کاربران ربات در دیتابیس: **{total_users}** نفر", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "back_home")
async def back_home_cb(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.message.edit_text(
        f"سلام {callback.from_user.first_name} عزیز! به منوی اصلی برگشتیم. 🚀",
        reply_markup=get_main_menu(user_id)
    )
    await callback.answer()

# ================= VIDEO DOWNLOADER =================
@dp.message(F.text.regexp(r'https?://[^\s]+'))
async def download_video(message: types.Message):
    url = message.text.strip()
    
    if "youtube.com" in url or "youtu.be" in url:
        await message.answer("⚠️ دانلود از یوتیوب غیرفعال است. لطفاً لینک معتبر **اینستاگرام یا تیک‌تاک** بفرستید.")
        return

    processing_msg = await message.answer("⏳ در حال دانلود ویدیو با حداکثر کیفیت، لطفاً صبور باشید...")
    
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
            await message.answer("❌ خطا در دانلود فایل. لطفاً لینک معتبر ارسال کنید.")
            
    except Exception as e:
        logging.error(f"Download Error: {e}")
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=processing_msg.message_id)
        except:
            pass
        await message.answer("❌ خطایی رخ داد یا لینک نامعتبر است.")

# ================= AI CHAT & TOOL EXECUTION =================
@dp.message()
async def handle_ai_message(message: types.Message):
    user_id = message.from_user.id
    user_message = message.text

    if user_id not in chat_histories:
        chat_histories[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    chat_histories[user_id].append({"role": "user", "content": user_message})

    # مدیریت اندازه حافظه گفتگو
    if len(chat_histories[user_id]) > 15:
        chat_histories[user_id] = [chat_histories[user_id][0]] + chat_histories[user_id][-14:]

    try:
        response = client.chat.completions.create(
            model="qwen/qwen3.8-27b",
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
                model="qwen/qwen3.8-27b",
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
        await message.answer("❌ متأسفانه در پردازش درخواست شما خطایی رخ داد.")

# ================= MAIN ENTRY =================
async def main():
    t = Thread(target=run_web)
    t.start()

    print("🤖 ربات فوق‌العاده قدرتمند NOVA VPN با موفقیت روشن شد و آماده‌ی کار است...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ ربات متوقف شد.")
