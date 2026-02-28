import sqlite3
import telebot
import os
from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

# -------------------- تنظیمات امنیتی --------------------

ALLOWED_USERS = [8052203674]  # ادمین‌ها (اگر خواستی بیشتر اضافه کن)

# -------------------- دیتابیس --------------------

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT,
    student_id TEXT UNIQUE,
    score TEXT
)
""")
conn.commit()

# -------------------- مسیر تست سرور --------------------


@app.route('/', methods=['GET'])
def home():
    return "Bot is running!"

# -------------------- وبهوک تلگرام --------------------


@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# -------------------- دستورات ربات --------------------


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "سلام 👋\nبرای ثبت اطلاعات دستور /register رو بزن."
    )


@bot.message_handler(commands=['register'])
def register(message):
    msg = bot.send_message(message.chat.id, "اسم خودت رو وارد کن:")
    bot.register_next_step_handler(msg, get_name)


def get_name(message):
    name = message.text.strip()
    msg = bot.send_message(message.chat.id, "شماره دانشجویی رو وارد کن:")
    bot.register_next_step_handler(msg, get_student_id, name)


def get_student_id(message, name):
    student_id = message.text.strip()
    telegram_id = message.from_user.id

    try:
        cursor.execute(
            "INSERT OR REPLACE INTO students (telegram_id, name, student_id) VALUES (?, ?, ?)",
            (telegram_id, name, student_id)
        )
        conn.commit()

        bot.send_message(
            message.chat.id,
            "✅ ثبت شد.\nبرای دیدن نمره دستور /score رو بزن."
        )
    except:
        bot.send_message(message.chat.id, "❌ خطا در ثبت اطلاعات.")


@bot.message_handler(commands=['score'])
def score(message):
    telegram_id = message.from_user.id
    cursor.execute(
        "SELECT score FROM students WHERE telegram_id = ?",
        (telegram_id,)
    )
    result = cursor.fetchone()

    if result and result[0]:
        bot.send_message(
            message.chat.id,
            f"📊 نمره شما:\n{result[0]}"
        )
    else:
        bot.send_message(
            message.chat.id,
            "❌ هنوز نمره‌ای ثبت نشده."
        )


@bot.message_handler(commands=['setscore'])
def set_score(message):

    # امنیت: فقط ادمین‌ها
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return

    try:
        _, student_id, score = message.text.split()

        # پیدا کردن دانشجو
        cursor.execute(
            "SELECT telegram_id FROM students WHERE student_id = ?",
            (student_id,)
        )
        user = cursor.fetchone()

        if user:
            telegram_id = user[0]

            cursor.execute(
                "UPDATE students SET score = ? WHERE student_id = ?",
                (score, student_id)
            )
            conn.commit()

            # ارسال خودکار به دانشجو
            bot.send_message(
                telegram_id,
                f"📢 نمره جدید ثبت شد!\n\n📊 نمره شما: {score}"
            )

            bot.send_message(
                message.chat.id,
                "✅ نمره ثبت شد و برای دانشجو ارسال شد."
            )
        else:
            bot.send_message(
                message.chat.id,
                "❌ چنین شماره دانشجویی ثبت نشده."
            )

    except:
        bot.send_message(
            message.chat.id,
            "فرمت درست:\n/setscore شماره_دانشجویی نمره"
        )

# -------------------- اجرای سرور --------------------


if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(
        url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    )
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
