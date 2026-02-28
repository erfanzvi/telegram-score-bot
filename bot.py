import sqlite3
import telebot
import os
from flask import Flask, request

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ================= امنیت =================
ALLOWED_USERS = [8052203674]  # آیدی ادمین‌ها

# ================= دیتابیس =================
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS students (
    telegram_id INTEGER PRIMARY KEY,
    name TEXT,
    student_id TEXT UNIQUE
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS grades (
    student_id TEXT,
    course TEXT,
    score TEXT,
    PRIMARY KEY(student_id, course)
)
""")
conn.commit()

# ================= وبهوک =================
@app.route('/', methods=['GET'])
def home():
    return "Bot is running!"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    json_str = request.get_data().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

# ================= دستورات عمومی =================
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
    cursor.execute(
        "INSERT OR REPLACE INTO students (telegram_id, name, student_id) VALUES (?, ?, ?)",
        (telegram_id, name, student_id)
    )
    conn.commit()
    bot.send_message(
        message.chat.id,
        "✅ ثبت شد.\nبرای دیدن نمره دستور /score رو بزن."
    )

@bot.message_handler(commands=['score'])
def score(message):
    telegram_id = message.from_user.id
    cursor.execute("SELECT student_id FROM students WHERE telegram_id = ?", (telegram_id,))
    res = cursor.fetchone()
    if not res:
        bot.send_message(message.chat.id, "❌ هنوز ثبت‌نام نکردید.")
        return

    student_id = res[0]
    cursor.execute("SELECT course, score FROM grades WHERE student_id = ?", (student_id,))
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ هنوز نمره‌ای ثبت نشده.")
        return

    text = "📊 نمرات شما:\n"
    for course, score in rows:
        text += f"{course}: {score}\n"
    bot.send_message(message.chat.id, text)

# ================= پنل ادمین =================
@bot.message_handler(commands=['setscore'])
def set_score(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return
    try:
        _, student_id, course, score = message.text.split(maxsplit=3)
        cursor.execute("""
            INSERT OR REPLACE INTO grades (student_id, course, score)
            VALUES (?, ?, ?)
        """, (student_id, course, score))
        conn.commit()

        cursor.execute("SELECT telegram_id FROM students WHERE student_id = ?", (student_id,))
        user = cursor.fetchone()
        if user:
            telegram_id = user[0]
            bot.send_message(
                telegram_id,
                f"📢 نمره جدید ثبت شد!\nدرس: {course}\n📊 نمره شما: {score}"
            )
        bot.send_message(message.chat.id, "✅ نمره ثبت شد و برای دانشجو ارسال شد.")
    except:
        bot.send_message(message.chat.id, "فرمت درست:\n/setscore شماره_دانشجویی درس نمره")

@bot.message_handler(commands=['list'])
def list_students(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return
    cursor.execute("SELECT name, student_id FROM students")
    students = cursor.fetchall()
    if not students:
        bot.send_message(message.chat.id, "لیستی وجود ندارد.")
        return
    text = "📋 لیست دانشجویان:\n\n"
    for name, sid in students:
        cursor.execute("SELECT course, score FROM grades WHERE student_id = ?", (sid,))
        grades = cursor.fetchall()
        grades_text = ", ".join([f"{c}:{s}" for c, s in grades]) if grades else "—"
        text += f"👤 {name} | {sid} | نمرات: {grades_text}\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['delete'])
def delete_student(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return
    try:
        _, student_id = message.text.split()
        cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        cursor.execute("DELETE FROM grades WHERE student_id = ?", (student_id,))
        conn.commit()
        bot.send_message(message.chat.id, "✅ دانشجو حذف شد.")
    except:
        bot.send_message(message.chat.id, "فرمت درست:\n/delete شماره_دانشجویی")

@bot.message_handler(commands=['add'])
def add_student(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return
    try:
        _, student_id, name = message.text.split(maxsplit=2)
        cursor.execute("INSERT INTO students (telegram_id, name, student_id) VALUES (?, ?, ?)", (0, name, student_id))
        conn.commit()
        bot.send_message(message.chat.id, "✅ دانشجو اضافه شد.")
    except:
        bot.send_message(message.chat.id, "فرمت درست:\n/add شماره_دانشجویی نام")

# ================= اجرای سرور =================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))