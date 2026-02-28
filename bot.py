import sqlite3
import telebot
import os

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT,
    student_id TEXT,
    score TEXT
)
""")
conn.commit()

ADMIN_ID = 8052203674


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id, "سلام 👋\nبرای ثبت اطلاعات دستور /register رو بزن.")


@bot.message_handler(commands=['register'])
def register(message):
    msg = bot.send_message(message.chat.id, "اسم خودت رو وارد کن:")
    bot.register_next_step_handler(msg, get_name)


def get_name(message):
    name = message.text
    msg = bot.send_message(message.chat.id, "شماره دانشجویی رو وارد کن:")
    bot.register_next_step_handler(msg, get_student_id, name)


def get_student_id(message, name):
    student_id = message.text
    telegram_id = message.from_user.id

    cursor.execute(
        "REPLACE INTO students (telegram_id, name, student_id) VALUES (?, ?, ?)",
        (telegram_id, name, student_id)
    )
    conn.commit()

    bot.send_message(
        message.chat.id, "✅ ثبت شد.\nبرای دیدن نمره دستور /score رو بزن.")


@bot.message_handler(commands=['score'])
def score(message):
    telegram_id = message.from_user.id
    cursor.execute(
        "SELECT score FROM students WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()

    if result and result[0]:
        bot.send_message(message.chat.id, f"📊 نمره شما:\n{result[0]}")
    else:
        bot.send_message(message.chat.id, "❌ هنوز نمره‌ای ثبت نشده.")


@bot.message_handler(commands=['setscore'])
def set_score(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔ فقط ادمین میتونه نمره ثبت کنه.")
        return

    try:
        _, student_id, score = message.text.split()

        cursor.execute(
            "UPDATE students SET score = ? WHERE student_id = ?",
            (score, student_id)
        )
        conn.commit()

        bot.send_message(message.chat.id, "✅ نمره ثبت شد.")
    except:
        bot.send_message(
            message.chat.id, "فرمت درست:\n/setscore شماره_دانشجویی نمره")


print("Bot is running...")
bot.infinity_polling()
