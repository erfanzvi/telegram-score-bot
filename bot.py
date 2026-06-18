import sqlite3
import telebot
import os
from flask import Flask, request
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

ALLOWED_USERS = [8052203674]

# ================= DB =================
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
    score REAL,
    PRIMARY KEY(student_id, course)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_grades (
    student_id TEXT,
    course TEXT,
    score REAL
)
""")

conn.commit()

# ================= TEMP STATES =================
user_state = {}

# ================= KEYBOARDS =================


def admin_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📊 ثبت نمره"))
    kb.row(KeyboardButton("🗑 حذف دانشجو"), KeyboardButton("📋 لیست دانشجوها"))
    kb.row(KeyboardButton("🔄 تطبیق نمرات"))
    return kb


def student_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("register"), KeyboardButton("score"))
    return kb

# ================= START =================


@bot.message_handler(commands=['start'])
def start(message):
    uid = message.from_user.id
    if uid in ALLOWED_USERS:
        bot.send_message(message.chat.id, "سلام ادمین 👋",
                         reply_markup=admin_keyboard())
    else:
        bot.send_message(message.chat.id,
                         "سلام\nبه ربات نمره‌دهی ورودی بهمن 1403 پزشکی گیلان خوش آمدید.\n"
                         "برای ثبت اطلاعات روی register بزنید.",
                         reply_markup=student_keyboard()
                         )

# ================= REGISTER FLOW =================


@bot.message_handler(func=lambda m: m.text == "register")
def register(message):
    uid = message.from_user.id

    cursor.execute("SELECT * FROM students WHERE telegram_id=?", (uid,))
    if cursor.fetchone():
        bot.send_message(message.chat.id, "❌ شما قبلاً ثبت‌نام کرده‌اید.")
        return

    user_state[uid] = {"step": "name"}

    bot.send_message(message.chat.id,
                     "لطفا نام و نام خانوادگی خودت را به زبان فارسی وارد کنید:")


@bot.message_handler(func=lambda m: True)
def state_router(message):
    uid = message.from_user.id
    text = message.text.strip()

    if uid not in user_state:
        return

    state = user_state[uid]

    # جلوگیری از دستور وسط فرم
    if text.startswith("/"):
        bot.send_message(message.chat.id, "❌ ابتدا ثبت‌نام را کامل کنید.")
        return

    # NAME
    if state["step"] == "name":
        if not all('\u0600' <= c <= '\u06FF' or c == ' ' for c in text):
            bot.send_message(message.chat.id, "❌ فقط نام فارسی وارد کنید")
            return

        if len(text.split()) < 2:
            bot.send_message(message.chat.id, "❌ نام و نام خانوادگی وارد کنید")
            return

        state["name"] = text
        state["step"] = "sid"

        bot.send_message(message.chat.id,
                         "لطفا شماره دانشجویی خود را با اعداد انگلیسی وارد کنید:")

    # STUDENT ID
    elif state["step"] == "sid":
        if not text.isdigit():
            bot.send_message(message.chat.id, "❌ فقط عدد انگلیسی وارد کنید")
            return

        cursor.execute("SELECT * FROM students WHERE student_id=?", (text,))
        if cursor.fetchone():
            bot.send_message(message.chat.id, "❌ شماره دانشجویی تکراری است.")
            user_state.pop(uid, None)
            return

        cursor.execute("INSERT INTO students VALUES (?, ?, ?)",
                       (uid, state["name"], text))
        conn.commit()

        user_state.pop(uid, None)

        bot.send_message(message.chat.id,
                         "اطلاعات شما ثبت شد.✅️",
                         reply_markup=student_keyboard()
                         )

# ================= SCORE =================


@bot.message_handler(func=lambda m: m.text == "score")
def score(message):
    uid = message.from_user.id

    cursor.execute(
        "SELECT student_id FROM students WHERE telegram_id=?", (uid,))
    res = cursor.fetchone()
    if not res:
        bot.send_message(message.chat.id, "❌ ثبت‌نام نکرده‌اید")
        return

    sid = res[0]

    cursor.execute(
        "SELECT course, score FROM grades WHERE student_id=?", (sid,))
    rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "❌ نمره‌ای ثبت نشده")
        return

    txt = "📊 نمرات شما:\n"
    for c, s in rows:
        txt += f"{c}: {s}\n"

    bot.send_message(message.chat.id, txt)

# ================= ADMIN ACTION =================


@bot.message_handler(func=lambda m: m.from_user.id in ALLOWED_USERS and m.text in [
    "📊 ثبت نمره", "🗑 حذف دانشجو", "📋 لیست دانشجوها", "🔄 تطبیق نمرات"
])
def admin_actions(message):

    if message.text == "📊 ثبت نمره":
        msg = bot.send_message(message.chat.id,
                               "فرمت:\n"
                               "40123456 [درس] 19 [درس2] 18.5\n\n"
                               "یا چند دانشجو در چند خط")
        bot.register_next_step_handler(msg, set_scores)

    elif message.text == "📋 لیست دانشجوها":
        send_list(message)

    elif message.text == "🗑 حذف دانشجو":
        msg = bot.send_message(message.chat.id, "شماره دانشجویی را وارد کنید:")
        bot.register_next_step_handler(msg, delete_student)

    elif message.text == "🔄 تطبیق نمرات":
        sync_pending(message)

# ================= PARSER =================


def parse_line(line):
    parts = line.split()
    sid = parts[0]
    data = parts[1:]

    results = []
    i = 0

    while i < len(data):
        course = data[i]
        score = data[i+1]

        # اگر درس با [ ] نبود، چندکلمه‌ای در نظر بگیر
        if course.startswith("["):
            course_name = course[1:]
            while not data[i].endswith("]"):
                i += 1
                course_name += " " + data[i]
            course_name = course_name[:-1]
        else:
            course_name = course

        try:
            score_val = float(score)
        except:
            i += 2
            continue

        if 0 <= score_val <= 20:
            results.append((sid, course_name, score_val))

        i += 2

    return results

# ================= SET SCORES =================


def set_scores(message):
    lines = message.text.strip().split("\n")

    success = []
    fail = []

    for line in lines:
        try:
            parsed = parse_line(line)

            if not parsed:
                continue

            sid = parsed[0][0]

            cursor.execute(
                "SELECT telegram_id FROM students WHERE student_id=?", (sid,))
            user = cursor.fetchone()

            for sid, course, score in parsed:
                cursor.execute("""
                    INSERT OR REPLACE INTO grades VALUES (?, ?, ?)
                """, (sid, course, score))

            conn.commit()

            if user:
                tid = user[0]
                txt = "📢 نمره جدید ثبت شد:\n"
                for _, c, s in parsed:
                    txt += f"{c}: {s}\n"
                bot.send_message(tid, txt)
                success.append(sid)
            else:
                fail.append(sid)
                for _, c, s in parsed:
                    cursor.execute("INSERT INTO pending_grades VALUES (?, ?, ?)",
                                   (sid, c, s))
                conn.commit()

        except:
            continue

    bot.send_message(message.chat.id,
                     f"✅ ثبت شد:\n{success}\n\n❌ ثبت‌نام نکرده:\n{fail}")

# ================= SYNC =================


def sync_pending(message):
    cursor.execute("SELECT DISTINCT student_id FROM pending_grades")
    rows = cursor.fetchall()

    done = []
    still = []

    for (sid,) in rows:
        cursor.execute(
            "SELECT telegram_id FROM students WHERE student_id=?", (sid,))
        user = cursor.fetchone()

        cursor.execute(
            "SELECT course, score FROM pending_grades WHERE student_id=?", (sid,))
        grades = cursor.fetchall()

        if user:
            tid = user[0]

            for c, s in grades:
                cursor.execute("INSERT OR REPLACE INTO grades VALUES (?, ?, ?)",
                               (sid, c, s))

            cursor.execute(
                "DELETE FROM pending_grades WHERE student_id=?", (sid,))
            conn.commit()

            txt = "📢 نمرات جدید شما ثبت شد:\n"
            for c, s in grades:
                txt += f"{c}: {s}\n"
            bot.send_message(tid, txt)

            done.append(sid)
        else:
            still.append(sid)

    bot.send_message(message.chat.id,
                     f"🔄 انجام شد:\n{done}\n\n⏳ هنوز ثبت‌نام نکرده:\n{still}")

# ================= DELETE =================


def delete_student(message):
    sid = message.text.strip()

    cursor.execute("DELETE FROM students WHERE student_id=?", (sid,))
    cursor.execute("DELETE FROM grades WHERE student_id=?", (sid,))
    cursor.execute("DELETE FROM pending_grades WHERE student_id=?", (sid,))
    conn.commit()

    bot.send_message(message.chat.id, "✅ حذف شد")

# ================= LIST =================


def send_list(message):
    cursor.execute("SELECT name, student_id FROM students")
    rows = cursor.fetchall()

    if not rows:
        bot.send_message(message.chat.id, "لیستی وجود ندارد")
        return

    txt = "📋 لیست دانشجویان:\n\n"

    for name, sid in rows:
        cursor.execute(
            "SELECT course, score FROM grades WHERE student_id=?", (sid,))
        g = cursor.fetchall()
        gtxt = ", ".join([f"{c}:{s}" for c, s in g]) if g else "—"
        txt += f"{name} | {sid} | {gtxt}\n"

    bot.send_message(message.chat.id, txt)

# ================= WEBHOOK =================


@app.route('/', methods=['GET'])
def home():
    return "Bot is running!"


@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.get_data().decode('utf-8'))
    bot.process_new_updates([update])
    return "OK", 200


# ================= RUN =================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(
        url=f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
