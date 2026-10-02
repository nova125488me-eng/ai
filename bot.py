```python
import os
import logging
import asyncio
import sqlite3
import json
import zoneinfo
import re
import html
from datetime import datetime

import yt_dlp

from flask import Flask
from threading import Thread

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from groq import Groq


# =========================================================
# CONFIG & LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# =========================================================
# FLASK
# =========================================================

app_flask = Flask("")


@app_flask.route("/")
def home():
    return "🚀 NOVA Ultra-Friendly Bot is live and running!"


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_flask.run(host="0.0.0.0", port=port)


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

TOKEN = os.environ.get("BOT_TOKEN")
GROQ_KEY = os.environ.get("GROQ_API_KEY")


if not TOKEN:
    raise ValueError("توکن ربات (BOT_TOKEN) یافت نشد!")

if not GROQ_KEY:
    raise ValueError("کلید گروق (GROQ_API_KEY) یافت نشد!")


# =========================================================
# BOT / AI
# =========================================================

bot = Bot(token=TOKEN)

dp = Dispatcher(storage=MemoryStorage())

client = Groq(api_key=GROQ_KEY)

chat_histories = {}

DB_NAME = "nova_assistant.db"


# =========================================================
# REGISTRATION STATES
# =========================================================

class Registration(StatesGroup):
    waiting_name = State()
    waiting_age = State()
    waiting_city = State()


# =========================================================
# DATABASE
# =========================================================

def init_db():

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            name TEXT,
            age INTEGER,
            city TEXT,
            joined_at TEXT
        )
    """)

    cur.execute("PRAGMA table_info(users)")
    columns = [row[1] for row in cur.fetchall()]

    if "name" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN name TEXT")

    if "age" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN age INTEGER")

    if "city" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN city TEXT")

    conn.commit()
    conn.close()


init_db()


# =========================================================
# DATABASE FUNCTIONS
# =========================================================

def save_user(user_id, username, first_name):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cur.execute("""
        INSERT OR IGNORE INTO users
        (user_id, username, first_name, joined_at)
        VALUES (?, ?, ?, ?)
    """, (
        user_id,
        username,
        first_name,
        now
    ))

    conn.commit()
    conn.close()


def save_user_name(user_id, name):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET name = ?
        WHERE user_id = ?
    """, (
        name,
        user_id
    ))

    conn.commit()
    conn.close()


def save_user_age(user_id, age):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET age = ?
        WHERE user_id = ?
    """, (
        age,
        user_id
    ))

    conn.commit()
    conn.close()


def save_user_city(user_id, city):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        UPDATE users
        SET city = ?
        WHERE user_id = ?
    """, (
        city,
        user_id
    ))

    conn.commit()
    conn.close()


def get_user(user_id):

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("""
        SELECT
            user_id,
            username,
            first_name,
            name,
            age,
            city,
            joined_at
        FROM users
        WHERE user_id = ?
    """, (user_id,))

    user = cur.fetchone()

    conn.close()

    return user


# =========================================================
# AI TOOLS
# =========================================================

def get_current_time(timezone_name: str = "Asia/Tehran"):

    try:

        tz = zoneinfo.ZoneInfo(timezone_name)

        now = datetime.now(tz)

        return json.dumps({
            "timezone": timezone_name,
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "day": now.strftime("%A")
        }, ensure_ascii=False)

    except Exception:

        now = datetime.now(
            zoneinfo.ZoneInfo("Asia/Tehran")
        )

        return json.dumps({
            "timezone": "Asia/Tehran",
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "error": "منطقه زمانی نامعتبر بود، ساعت تهران اعلام شد."
        }, ensure_ascii=False)


def set_alarm_reminder(
    delay_seconds: int,
    message_text: str,
    chat_id: int
):

    async def delayed_task():

        await asyncio.sleep(delay_seconds)

        try:

            await bot.send_message(
                chat_id=chat_id,
                text=f"⏰ الارمت دادا\n\n{message_text}"
            )

        except Exception as e:

            logging.error(
                f"Error sending alarm: {e}"
            )

    asyncio.create_task(
        delayed_task()
    )

    return json.dumps({
        "status": "success",
        "message":
            f"آلارم با موفقیت پس از "
            f"{delay_seconds} ثانیه تنظیم شد."
    })


tools = [

    {
        "type": "function",

        "function": {

            "name": "get_current_time",

            "description":
                "ساعت دقیق یک شهر یا منطقه زمانی را به دست می‌آورد.",

            "parameters": {

                "type": "object",

                "properties": {

                    "timezone_name": {

                        "type": "string",

                        "description":
                            "نام منطقه زمانی مثل Asia/Tehran"
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

            "description":
                "یک یادآور یا آلارم تنظیم می‌کند.",

            "parameters": {

                "type": "object",

                "properties": {

                    "delay_seconds": {

                        "type": "integer",

                        "description":
                            "تعداد ثانیه‌ها"
                    },

                    "message_text": {

                        "type": "string",

                        "description":
                            "متن یادآوری"
                    }
                },

                "required": [
                    "delay_seconds",
                    "message_text"
                ]
            }
        }
    }
]


# =========================================================
# SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = (

    "تو دستیار هوشمند، فوق‌العاده باحال، صمیمی و رفیق فابریک هستی. "

    "سازنده، خالق و پروژه‌ی تو NOVA است و توسط امیرعلی توسعه داده شده‌ای. "

    "اگر کسی پرسید سازنده‌ات کیه، با افتخار بگو ساخت NOVA هستی. "

    "تک‌تک جملاتت را با لحنی کاملاً خودمانی، پرانرژی، گرم و صمیمی بنویس. "

    "همیشه روان و فارسی صحبت کن. "

    "از ایموجی مناسب استفاده کن. "

    "قانون بسیار مهم برای کدنویسی: "

    "هر وقت کاربر کد خواست، حتماً کد را داخل Markdown Code Block قرار بده. "

    "برای پایتون از ```python استفاده کن. "

    "برای JavaScript از ```javascript استفاده کن. "

    "برای HTML از ```html استفاده کن. "

    "برای CSS از ```css استفاده کن. "

    "برای زبان‌های دیگر نیز نام زبان را بعد از ``` بنویس. "

    "هرگز کد را خارج از Code Block ارسال نکن. "

    "اگر پاسخ شامل توضیح و کد است، ابتدا توضیح کوتاه بده و سپس کد را داخل Code Block قرار بده. "

    "اگر چند قطعه کد داری، هر قطعه را جداگانه داخل Code Block قرار بده. "

    "کدها باید کامل، مرتب، قابل کپی و با تورفتگی صحیح باشند. "

    "می‌توانی ساعت را بگویی و آلارم تنظیم کنی."
)


# =========================================================
# CODE / HTML MESSAGE SENDER
# =========================================================

async def send_ai_message(
    message: types.Message,
    text: str
):
    """
    پاسخ AI را بررسی می‌کند.
    اگر Code Block داشته باشد،
    قسمت کد را به HTML <pre><code> تبدیل می‌کند
    تا تلگرام آن را به صورت مونو‌استایل نمایش دهد.
    """

    if not text:
        await message.answer(
            "داداش یه لحظه جوابم خالی شد 😂 دوباره بگو!"
        )
        return

    # پیدا کردن Code Block ها
    pattern = r"```([a-zA-Z0-9_+\-]*)\s*\n?(.*?)```"

    matches = list(
        re.finditer(
            pattern,
            text,
            flags=re.DOTALL
        )
    )

    # اگر هیچ Code Block وجود نداشت
    if not matches:

        try:

            await message.answer(
                text,
                parse_mode="HTML"
            )

        except Exception:

            # اگر متن دارای HTML نامعتبر بود
            await message.answer(
                html.escape(text)
            )

        return

    # ساخت پاسخ ترکیبی
    result = []

    last_end = 0

    for match in matches:

        # متن قبل از کد
        normal_text = text[
            last_end:match.start()
        ]

        if normal_text:

            result.append(
                html.escape(normal_text)
            )

        language = match.group(1).strip()

        code = match.group(2)

        # حذف یک خط خالی اضافی ابتدای کد
        if code.startswith("\n"):
            code = code[1:]

        # escape کردن کد برای HTML
        safe_code = html.escape(code)

        if language:

            code_block = (
                f'<pre><code class="language-{html.escape(language)}">'
                f'{safe_code}'
                f'</code></pre>'
            )

        else:

            code_block = (
                f"<pre><code>"
                f"{safe_code}"
                f"</code></pre>"
            )

        result.append(code_block)

        last_end = match.end()

    # متن بعد از آخرین کد
    remaining_text = text[last_end:]

    if remaining_text:

        result.append(
            html.escape(remaining_text)
        )

    final_text = "".join(result)

    # تلگرام محدودیت طول پیام دارد
    max_length = 4096

    if len(final_text) <= max_length:

        try:

            await message.answer(
                final_text,
                parse_mode="HTML"
            )

        except Exception as e:

            logging.error(
                f"HTML Send Error: {e}"
            )

            await message.answer(
                html.escape(text)
            )

    else:

        # اگر پاسخ خیلی طولانی بود
        # به قسمت‌های کوچک‌تر تقسیم می‌کنیم

        parts = []

        current = ""

        for line in final_text.split("\n"):

            if len(current) + len(line) + 1 > 4000:

                if current:

                    parts.append(current)

                current = line

            else:

                if current:

                    current += "\n"

                current += line

        if current:

            parts.append(current)

        for part in parts:

            try:

                await message.answer(
                    part,
                    parse_mode="HTML"
                )

            except Exception:

                await message.answer(
                    html.escape(
                        re.sub(
                            r"<[^>]+>",
                            "",
                            part
                        )
                    )
                )


# =========================================================
# MAIN MENU
# =========================================================

def get_main_menu():

    builder = InlineKeyboardBuilder()

    builder.row(

        types.InlineKeyboardButton(
            text="📥 راهنمای دانلود",
            callback_data="help_download"
        ),

        types.InlineKeyboardButton(
            text="☕️ درباره من",
            callback_data="about_bot"
        )
    )

    return builder.as_markup()


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def cmd_start(
    message: types.Message,
    state: FSMContext
):

    user_id = message.from_user.id

    username = message.from_user.username

    first_name = (
        message.from_user.first_name
        or "دوست من"
    )

    save_user(
        user_id,
        username,
        first_name
    )

    chat_histories[user_id] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    user = get_user(user_id)

    if user:

        saved_name = user[3]
        saved_age = user[4]
        saved_city = user[5]

        if saved_name and saved_age and saved_city:

            await state.clear()

            await message.answer(

                f"سلام دوباره {saved_name} جان! 😎❤️\n\n"
                f"خوش اومدی رفیق!\n"
                f"یادم هست که {saved_age} سالته و "
                f"از {saved_city} هستی. 🥰\n\n"
                "حالا بزن بریم باهم گفت‌وگو کنیم! 🤖🔥",

                reply_markup=get_main_menu()
            )

            return

    await state.set_state(
        Registration.waiting_name
    )

    await message.answer(

        "سلام! 👋😎\n\n"
        "خیلی خوش اومدی رفیق ❤️\n"
        "لطفاً اسمت رو بگو تا همیشه یادم بمونه 😊"
    )


# =========================================================
# GET NAME
# =========================================================

@dp.message(
    Registration.waiting_name
)
async def get_name(
    message: types.Message,
    state: FSMContext
):

    name = (
        message.text or ""
    ).strip()

    if not name:

        await message.answer(
            "داداش یه اسم بهم بگو 😄"
        )

        return

    if len(name) > 50:

        await message.answer(
            "اسم یکم طولانیه 😅\n"
            "لطفاً اسم کوتاه‌ترت رو بفرست."
        )

        return

    user_id = message.from_user.id

    save_user_name(
        user_id,
        name
    )

    await state.set_state(
        Registration.waiting_age
    )

    await message.answer(

        f"خیلی خوشبختم {name} جان! ❤️\n\n"
        "حالا بگو چند سالته؟ 🎂\n"
        "فقط عدد سنت رو بفرست."
    )


# =========================================================
# GET AGE
# =========================================================

@dp.message(
    Registration.waiting_age
)
async def get_age(
    message: types.Message,
    state: FSMContext
):

    text = (
        message.text or ""
    ).strip()

    translation_table = str.maketrans(
        "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
        "0123456789" * 2
    )

    text = text.translate(
        translation_table
    )

    if not text.isdigit():

        await message.answer(
            "سن رو فقط به صورت عدد بفرست 😄\n"
            "مثلاً: ۱۳"
        )

        return

    age = int(text)

    if age < 1 or age > 120:

        await message.answer(
            "داداش یه سن واقعی بین ۱ تا ۱۲۰ سال وارد کن 😅"
        )

        return

    user_id = message.from_user.id

    save_user_age(
        user_id,
        age
    )

    user = get_user(user_id)

    name = (
        user[3]
        if user and user[3]
        else "رفیق"
    )

    await state.set_state(
        Registration.waiting_city
    )

    await message.answer(

        f"عالیه {name} جان! 😎👌\n\n"
        "حالا بگو کدوم شهری؟ 🏙️"
    )


# =========================================================
# GET CITY
# =========================================================

@dp.message(
    Registration.waiting_city
)
async def get_city(
    message: types.Message,
    state: FSMContext
):

    city = (
        message.text or ""
    ).strip()

    if not city:

        await message.answer(
            "اسم شهرت رو بفرست داداش 😄"
        )

        return

    if len(city) > 100:

        await message.answer(
            "اسم شهر خیلی طولانیه 😅\n"
            "لطفاً اسم شهر رو کوتاه‌تر بفرست."
        )

        return

    user_id = message.from_user.id

    save_user_city(
        user_id,
        city
    )

    user = get_user(user_id)

    name = (
        user[3]
        if user and user[3]
        else "رفیق"
    )

    age = (
        user[4]
        if user
        else None
    )

    await state.clear()

    chat_histories[user_id] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    await message.answer(

        f"خیلی ازت متشکرم {name} جان! ❤️🙏\n\n"
        f"پس یادم موند که اسمت {name}، "
        f"{age} سالته و از {city} هستی. 😎\n\n"
        "حالا دیگه می‌تونیم باهم گفت‌وگو کنیم! 🤖🔥\n\n"
        "هر چی دوست داری بگو، من در خدمتم! 🚀",

        reply_markup=get_main_menu()
    )


# =========================================================
# HELP
# =========================================================

@dp.callback_query(
    F.data == "help_download"
)
async def help_cb(
    callback: types.CallbackQuery
):

    await callback.message.edit_text(

        "💡 راهنمای ربات\n\n"

        "▫️ کدنویسی: هر جا گیر کردی بگو تا برات کد بنویسم.\n"

        "▫️ دانلود: لینک اینستاگرام یا تیک‌تاک بفرست.\n"

        "▫️ ساعت: بپرس ساعت چنده.\n"

        "▫️ آلارم: می‌تونی ازم بخوای برات یادآوری تنظیم کنم.\n\n"

        "🤖 و البته می‌تونیم مثل دو تا رفیق باهم گفت‌وگو کنیم!",

        reply_markup=get_main_menu()
    )

    await callback.answer()


# =========================================================
# ABOUT
# =========================================================

@dp.callback_query(
    F.data == "about_bot"
)
async def about_cb(
    callback: types.CallbackQuery
):

    await callback.message.edit_text(

        "☕️ درباره NOVA\n\n"

        "من ربات هوش مصنوعی اختصاصی NOVA هستم! 🤖🚀\n\n"

        "می‌تونم باهات گفت‌وگو کنم، "
        "به سوالاتت جواب بدم، "
        "در کدنویسی کمکت کنم، "
        "ساعت رو بگم و آلارم تنظیم کنم. 😎🔥",

        reply_markup=get_main_menu()
    )

    await callback.answer()


# =========================================================
# VIDEO DOWNLOADER
# =========================================================

@dp.message(
    F.text.regexp(r"https?://[^\s]+")
)
async def download_video(
    message: types.Message
):

    url = message.text.strip()

    if (
        "youtube.com" in url
        or "youtu.be" in url
    ):

        await message.answer(
            "⚠️ داداش یوتیوب فعلاً اوکی نیست 😅\n"
            "بی‌زحمت لینک تیک‌تاک یا اینستا بفرست!"
        )

        return

    processing_msg = await message.answer(
        "⏳ لینک رو گرفتم داداش!\n"
        "الان دارم ویدیو رو آماده می‌کنم 😎🔥"
    )

    output_template = (
        f"downloaded_video_{message.chat.id}.%(ext)s"
    )

    ydl_opts = {

        "outtmpl": output_template,

        "format": "mp4/best",

        "max_filesize":
            50 * 1024 * 1024
    }

    try:

        def run_dl():

            with yt_dlp.YoutubeDL(
                ydl_opts
            ) as ydl:

                info = ydl.extract_info(
                    url,
                    download=True
                )

                return ydl.prepare_filename(
                    info
                )

        filename = await asyncio.to_thread(
            run_dl
        )

        if filename and os.path.exists(filename):

            await message.answer_video(

                types.FSInputFile(
                    filename
                ),

                caption="حالا حال کن 😎🔥"
            )

            try:
                os.remove(filename)
            except Exception:
                pass

            try:

                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )

            except Exception:
                pass

        else:

            try:

                await bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )

            except Exception:
                pass

            await message.answer(
                "❌ داداش لینک مشکل داشت، "
                "نتونستم دانلودش کنم."
            )

    except Exception as e:

        logging.error(
            f"Download Error: {e}"
        )

        try:

            await bot.delete_message(
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )

        except Exception:
            pass

        await message.answer(
            "❌ یه مشکلی موقع دانلود پیش اومد 😅\n"
            "دوباره امتحان کن."
        )


# =========================================================
# AI CHAT
# =========================================================

@dp.message()
async def handle_ai_message(
    message: types.Message
):

    user_id = message.from_user.id

    user_message = message.text

    if not user_message:

        await message.answer(
            "داداش فقط متن بفرست تا باهم صحبت کنیم 😄"
        )

        return

    if user_id not in chat_histories:

        chat_histories[user_id] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    chat_histories[user_id].append({

        "role": "user",

        "content": user_message
    })

    if len(chat_histories[user_id]) > 15:

        chat_histories[user_id] = [

            chat_histories[user_id][0]

        ] + chat_histories[user_id][-14:]

    try:

        response = client.chat.completions.create(

            model="openai/gpt-oss-120b",

            messages=chat_histories[user_id],

            tools=tools,

            tool_choice="auto",

            max_tokens=800
        )

        response_message = (
            response.choices[0].message
        )

        if response_message.tool_calls:

            chat_histories[user_id].append(
                response_message
            )

            for tool_call in response_message.tool_calls:

                function_name = (
                    tool_call.function.name
                )

                function_args = json.loads(
                    tool_call.function.arguments
                )

                tool_output = ""

                if function_name == "get_current_time":

                    tool_output = get_current_time(
                        **function_args
                    )

                elif function_name == "set_alarm_reminder":

                    function_args["chat_id"] = user_id

                    tool_output = set_alarm_reminder(
                        **function_args
                    )

                chat_histories[user_id].append({

                    "tool_call_id":
                        tool_call.id,

                    "role":
                        "tool",

                    "name":
                        function_name,

                    "content":
                        tool_output
                })

            second_response = client.chat.completions.create(

                model="openai/gpt-oss-120b",

                messages=chat_histories[user_id],

                max_tokens=800
            )

            final_reply = (
                second_response
                .choices[0]
                .message
                .content
            )

            chat_histories[user_id].append({

                "role":
                    "assistant",

                "content":
                    final_reply
            })

            # ارسال هوشمند پاسخ
            await send_ai_message(
                message,
                final_reply
            )

        else:

            bot_response = (
                response_message.content
            )

            if not bot_response:

                bot_response = (
                    "داداش یه لحظه ذهنم هنگ کرد 😂\n"
                    "دوباره بگو!"
                )

            chat_histories[user_id].append({

                "role":
                    "assistant",

                "content":
                    bot_response
            })

            # ارسال هوشمند پاسخ
            await send_ai_message(
                message,
                bot_response
            )

    except Exception as e:

        logging.error(
            f"AI Error: {e}"
        )

        await message.answer(

            "❌ داداش یه خطای کوچیک پیش اومد 😅\n"
            "دوباره بگو تا باهم حلش کنیم."
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    t = Thread(
        target=run_web,
        daemon=True
    )

    t.start()

    print(
        "🤖 ربات NOVA با موفقیت روشن شد و آماده است! 🚀"
    )

    await dp.start_polling(
        bot
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "❌ ربات متوقف شد."
        )
```
