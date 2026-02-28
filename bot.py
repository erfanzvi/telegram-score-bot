import sqlite3
import telebot
import os
from flask import Flask, request
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

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
    telegram_id INTEGER UNIQUE,
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

# ================= دکمه‌ها =================


def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 ثبت نمره"))
    kb.row(KeyboardButton("🗑 حذف دانشجو"), KeyboardButton("📋 لیست دانشجوها"))
    return kb


def student_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("/register"), KeyboardButton("/score"))
    return kb

# ================= دستورات عمومی =================


@bot.message_handler(commands=['start'])
def start(message):
    telegram_id = message.from_user.id
    if telegram_id in ALLOWED_USERS:
        bot.send_message(
            message.chat.id, "سلام ادمین 👋\nبه پنل مدیریتی خوش آمدید.", reply_markup=admin_keyboard())
    else:
        bot.send_message(
            message.chat.id,
            "سلام\nبه ربات نمره‌دهی ورودی بهمن 1403 پزشکی گیلان خوش آمدید.\n\n"
            "دانشجوی گرامی جهت ثبت اطلاعات خود از /register استفاده کنید.\n"
            "دقت کنید که نام و نام خانوادگی خود را به زبان فارسی و در مرحله بعد شماره دانشجویی را با اعداد انگلیسی وارد کنید.\n"
            "لطفا دقت شود که هر فرد می‌تواند یک شماره دانشجویی ثبت نماید.",
            reply_markup=student_keyboard()
        )

# ================= ثبت دانشجو =================


@bot.message_handler(commands=['register'])
def register(message):
    telegram_id = message.from_user.id
    cursor.execute(
        "SELECT * FROM students WHERE telegram_id = ?", (telegram_id,))
    if cursor.fetchone():
        bot.send_message(
            message.chat.id, "❌ شما مجاز به ثبت بیش از یک شماره دانشجویی نیستید.")
        return
    msg = bot.send_message(
        message.chat.id, "لطفا نام و نام خانوادگی خودت را به زبان فارسی وارد کنید:")
    bot.register_next_step_handler(msg, get_name)


def get_name(message):
    name = message.text.strip()
    msg = bot.send_message(
        message.chat.id, "لطفا شماره دانشجویی خود را با اعداد انگلیسی وارد کنید:")
    bot.register_next_step_handler(msg, get_student_id, name)


def get_student_id(message, name):
    student_id = message.text.strip()
    telegram_id = message.from_user.id
    cursor.execute(
        "SELECT * FROM students WHERE student_id = ?", (student_id,))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ شماره دانشجویی تکراری است.")
        return
    cursor.execute("INSERT INTO students (telegram_id, name, student_id) VALUES (?, ?, ?)",
                   (telegram_id, name, student_id))
    conn.commit()
    bot.send_message(
        message.chat.id,
        "اطلاعات شما ثبت شد.✅️\nبرای دیدن نمرات خود از دستور /score استفاده کنید",
        reply_markup=student_keyboard()
    )


@bot.message_handler(commands=['score'])
def score(message):
    telegram_id = message.from_user.id
    cursor.execute(
        "SELECT student_id FROM students WHERE telegram_id = ?", (telegram_id,))
    res = cursor.fetchone()
    if not res:
        bot.send_message(message.chat.id, "❌ هنوز ثبت‌نام نکردید.")
        return
    student_id = res[0]
    cursor.execute(
        "SELECT course, score FROM grades WHERE student_id = ?", (student_id,))
    rows = cursor.fetchall()
    if not rows:
        bot.send_message(message.chat.id, "❌ هنوز نمره‌ای ثبت نشده.")
        return
    text = "📊 نمرات شما:\n"
    for course, score in rows:
        text += f"{course}: {score}\n"
    bot.send_message(message.chat.id, text)

# ================= دکمه‌های ادمین =================


@bot.message_handler(func=lambda message: message.text in ["📊 ثبت نمره", "🗑 حذف دانشجو", "📋 لیست دانشجوها"])
def admin_actions(message):
    if message.from_user.id not in ALLOWED_USERS:
        bot.send_message(message.chat.id, "⛔ دسترسی غیرمجاز.")
        return
    if message.text == "📊 ثبت نمره":
        msg = bot.send_message(
            message.chat.id, "فرمت: شماره_دانشجویی درس1 نمره1 درس2 نمره2 ...\nمثال: 40123456 گوارش 19 آناتومی 18")
        bot.register_next_step_handler(msg, set_score_handler)
    elif message.text == "🗑 حذف دانشجو":
        msg = bot.send_message(
            message.chat.id, "شماره دانشجویی دانشجو برای حذف را وارد کنید:")
        bot.register_next_step_handler(msg, delete_handler)
    elif message.text == "📋 لیست دانشجوها":
        send_list(message)

# ================= توابع ادمین =================


def set_score_handler(message):
    try:
        parts = message.text.split()
        student_id = parts[0]
        grades_list = parts[1:]
        if len(grades_list) % 2 != 0:
            bot.send_message(
                message.chat.id, "فرمت درست:\nشماره_دانشجویی درس1 نمره1 درس2 نمره2 ...")
            return
        for i in range(0, len(grades_list), 2):
            course = grades_list[i]
            score = grades_list[i+1]
            cursor.execute("INSERT OR REPLACE INTO grades (student_id, course, score) VALUES (?, ?, ?)",
                           (student_id, course, score))
        conn.commit()
        cursor.execute(
            "SELECT telegram_id FROM students WHERE student_id = ?", (student_id,))
        user = cursor.fetchone()
        if user:
            telegram_id = user[0]
            text = "📢 نمره جدید ثبت شد:\n"
            for i in range(0, len(grades_list), 2):
                text += f"{grades_list[i]}: {grades_list[i+1]}\n"
            bot.send_message(telegram_id, text)
        bot.send_message(
            message.chat.id, "✅ نمرات ثبت شد و برای دانشجو ارسال شد.", reply_markup=admin_keyboard())
    except:
        bot.send_message(
            message.chat.id, "فرمت درست:\nشماره_دانشجویی درس1 نمره1 درس2 نمره2 ...")


def delete_handler(message):
    student_id = message.text.strip()
    cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
    cursor.execute("DELETE FROM grades WHERE student_id = ?", (student_id,))
    conn.commit()
    bot.send_message(message.chat.id, "✅ دانشجو حذف شد.",
                     reply_markup=admin_keyboard())


def send_list(message):
    cursor.execute("SELECT name, student_id FROM students")
    students = cursor.fetchall()
    if not students:
        bot.send_message(message.chat.id, "لیستی وجود ندارد.",
                         reply_markup=admin_keyboard())
        return
    text = "📋 لیست دانشجویان:\n\n"
    for name, sid in students:
        cursor.execute(
            "SELECT course, score FROM grades WHERE student_id = ?", (sid,))
        grades = cursor.fetchall()
        grades_text = ", ".join(
            [f"{c}:{s}" for c, s in grades]) if grades else "—"
        text += f"👤 {name} | {sid} | نمرات: {grades_text}\n"
    bot.send_message(message.chat.id, text, reply_markup=admin_keyboard())


# ================= اجرای سرور =================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(
        url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
