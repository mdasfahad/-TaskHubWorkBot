#!/usr/bin/env python3
"""
Earn Bot — Full Featured
Main Admin: 8289191009 (never removable)

User: Balance, Tasks, Profile, Referral, Withdraw, Deposit,
      Post Task (costs points), History, Support, FAQ, Update

Admin: Users, Stats, Balance +/-, Tasks, Submissions, User Posts,
       Withdrawals, Deposits, Channels, Payment Methods,
       Referral, Settings, Verify ON/OFF, Maintenance, Withdraw ON/OFF,
       Broadcast, Add/Remove Admin, Ownership Transfer, User Panel
"""

import logging
import sqlite3
import random
import string
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
    JobQueue,
)
from telegram.constants import ParseMode

# ================== CONFIG ==================
BOT_TOKEN = "8954125751:AAHAZ6HH2W6cZYf4e9Yr9ubvYGckWFVI0QI"
MAIN_ADMIN_ID = 8289191009
DB_NAME = "earn_bot.db"
BOT_VERSION = "1.2.0"

(
    ADD_CHANNEL,
    ADD_CHANNEL_TITLE,
    ADD_CHANNEL_LINK,
    CREATE_TASK_TITLE,
    CREATE_TASK_DESC,
    CREATE_TASK_REWARD,
    CREATE_TASK_LINK,
    WAIT_PHOTO,
    WAIT_VIDEO,
    SET_REF_BONUS,
    SET_MIN_WD,
    SET_SUPPORT,
    SET_POST_COST,
    SET_POINT_BDT,
    SET_FAQ,
    BALANCE_UID,
    BALANCE_AMT,
    WD_AMOUNT,
    WD_METHOD,
    DEP_AMOUNT,
    DEP_PROOF,
    POST_TASK_TITLE,
    POST_TASK_DESC,
    POST_TASK_REWARD,
    PAY_METHOD_NAME,
    PAY_METHOD_INFO,
    BROADCAST_MSG,
    ADD_ADMIN_ID,
    REMOVE_ADMIN_ID,
    TRANSFER_OWNER_ID,
    CAPTCHA_ANSWER,
    PHONE_SHARE,
) = range(32)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ================== DB ==================
def get_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            points REAL DEFAULT 0,
            referrer_id INTEGER,
            is_blocked INTEGER DEFAULT 0,
            phone TEXT,
            device_id TEXT,
            captcha_ok INTEGER DEFAULT 0,
            phone_ok INTEGER DEFAULT 0,
            device_ok INTEGER DEFAULT 0,
            joined_at TEXT,
            last_active TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin',
            added_by INTEGER,
            added_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forced_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE,
            title TEXT,
            invite_link TEXT,
            added_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            reward_points REAL,
            task_link TEXT,
            created_by INTEGER,
            is_user_post INTEGER DEFAULT 0,
            created_at TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            user_id INTEGER,
            proof_photo TEXT,
            proof_video TEXT,
            status TEXT DEFAULT 'pending',
            submitted_at TEXT,
            reviewed_at TEXT,
            reviewed_by INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS withdraws (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            method TEXT,
            details TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deposits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            proof_file_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            processed_at TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            info TEXT,
            is_active INTEGER DEFAULT 1
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            kind TEXT,
            amount REAL,
            note TEXT,
            created_at TEXT
        )
    """)

    # migrate columns
    for col, typ in [
        ("phone", "TEXT"),
        ("device_id", "TEXT"),
        ("captcha_ok", "INTEGER DEFAULT 0"),
        ("phone_ok", "INTEGER DEFAULT 0"),
        ("device_ok", "INTEGER DEFAULT 0"),
    ]:
        try:
            cur.execute(f"ALTER TABLE users ADD COLUMN {col} {typ}")
        except Exception:
            pass

    defaults = {
        "min_withdraw": "100",
        "referral_bonus": "10",
        "support_username": "",
        "maintenance": "0",
        "withdraw_enabled": "1",
        "post_task_cost": "50",
        "point_value_bdt": "0.10",
        "verify_device": "0",
        "verify_phone": "0",
        "verify_captcha": "0",
        "verify_captcha_math": "1",
        "verify_captcha_animal": "0",
        "developer_username": "",
        "lang_default": "bn",
        "faq_text": (
            "ℹ️ <b>FAQ — বাটন গাইড</b>\n\n"
            "💰 <b>Balance</b> — পয়েন্ট ও BDT দেখুন\n"
            "📋 <b>Tasks</b> — টাস্ক করে পয়েন্ট আয়\n"
            "👤 <b>Profile</b> — প্রোফাইল তথ্য\n"
            "👥 <b>Referral</b> — রেফার লিংক শেয়ার করে বোনাস\n"
            "💸 <b>Withdraw</b> — পয়েন্ট উইথড্র\n"
            "💳 <b>Deposit</b> — পেমেন্ট করে ব্যালেন্স বাড়ান\n"
            "➕ <b>Post Task</b> — পয়েন্ট খরচ করে টাস্ক পোস্ট\n"
            "📜 <b>History</b> — লেনদেনের হিস্ট্রি\n"
            "🆘 <b>Support</b> — সাপোর্টে মেসেজ\n"
            "ℹ️ <b>FAQ</b> — এই গাইড\n"
            "🔄 <b>Update</b> — মেনু রিফ্রেশ\n"
            "👨‍💻 <b>Developer</b> — ডেভেলপারের সাথে যোগাযোগ\n"
            "🌐 <b>Language</b> — ভাষা পরিবর্তন\n\n"
            "সমস্যা হলে Support ব্যবহার করুন।"
        ),
        "welcome_text": "🎉 স্বাগতম! নিচের বাটনগুলো ব্যবহার করুন।",
        "update_note": f"🔄 Bot version {BOT_VERSION}\nসব ফিচার আপডেট ও সক্রিয়।",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id, role, added_by, added_at) VALUES (?, 'main', ?, ?)",
        (MAIN_ADMIN_ID, MAIN_ADMIN_ID, datetime.now().isoformat()),
    )
    # seed common payment methods if empty
    cur.execute("SELECT COUNT(*) c FROM payment_methods")
    if cur.fetchone()["c"] == 0:
        for name, info in [
            ("bKash", "নম্বর: 01XXXXXXXXX (Personal)"),
            ("Nagad", "নম্বর: 01XXXXXXXXX (Personal)"),
            ("Rocket", "নম্বর: 01XXXXXXXXX"),
            ("Binance", "UID / Pay ID দিন"),
        ]:
            cur.execute(
                "INSERT INTO payment_methods (name, info) VALUES (?, ?)", (name, info)
            )

    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def is_admin(uid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM admins WHERE user_id = ?", (uid,))
    ok = cur.fetchone() is not None
    conn.close()
    return ok


def is_main(uid: int) -> bool:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT role FROM admins WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    return bool(row and row["role"] == "main")


def get_user(uid: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (uid,))
    row = cur.fetchone()
    conn.close()
    return row


def ensure_user(uid, username=None, full_name=None, referrer_id=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (uid,))
    if not cur.fetchone():
        cur.execute(
            """INSERT INTO users (user_id, username, full_name, referrer_id, joined_at, last_active)
               VALUES (?,?,?,?,?,?)""",
            (uid, username, full_name, referrer_id,
             datetime.now().isoformat(), datetime.now().isoformat()),
        )
        if referrer_id:
            bonus = float(get_setting("referral_bonus", "10"))
            cur.execute(
                "UPDATE users SET points = points + ? WHERE user_id = ?",
                (bonus, referrer_id),
            )
            cur.execute(
                "INSERT INTO history (user_id, kind, amount, note, created_at) VALUES (?,?,?,?,?)",
                (referrer_id, "referral", bonus, f"ref {uid}", datetime.now().isoformat()),
            )
    else:
        cur.execute(
            "UPDATE users SET username=?, full_name=?, last_active=? WHERE user_id=?",
            (username, full_name, datetime.now().isoformat(), uid),
        )
    conn.commit()
    conn.close()


def add_history(uid, kind, amount, note=""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (user_id, kind, amount, note, created_at) VALUES (?,?,?,?,?)",
        (uid, kind, amount, note, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def is_blocked(uid: int) -> bool:
    u = get_user(uid)
    return bool(u and u["is_blocked"] == 1)


def get_channels():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM forced_channels ORDER BY id")
    rows = cur.fetchall()
    conn.close()
    return rows


# ================== KEYBOARDS ==================
def user_keyboard(show_admin: bool = False):
    rows = [
        ["💰 Balance", "📋 Tasks"],
        ["👤 Profile", "👥 Referral"],
        ["💸 Withdraw", "💳 Deposit"],
        ["➕ Post Task", "📜 History"],
        ["🆘 Support", "ℹ️ FAQ"],
        ["🔄 Update", "👨‍💻 Developer"],
        ["🌐 Language"],
    ]
    if show_admin:
        rows.append(["🔧 Admin Panel"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_keyboard(main: bool = False):
    rows = [
        ["👥 Users", "📊 Statistics"],
        ["➕ Add Balance", "➖ Remove Balance"],
        ["📋 Manage Tasks", "📥 Submissions"],
        ["📝 User Posts", "📢 Broadcast"],
        ["💸 Withdrawals", "💳 Deposits"],
        ["📢 Channels", "💳 Payment Methods"],
        ["🎁 Referral Settings", "⚙️ Settings"],
        ["🔐 Verify Settings", "💰 Post Cost / BDT"],
        ["👨‍💻 Set Developer", "🌐 Lang / FAQ"],
        ["🔧 Maintenance ON/OFF", "💸 Withdraw ON/OFF"],
    ]
    if main:
        rows.append(["👑 Add/Remove Admin", "🔄 Ownership Transfer"])
    rows.append(["🏠 User Panel"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


# ================== VERIFY ==================
ANIMALS = [
    ("🐶", "dog"), ("🐱", "cat"), ("🦁", "lion"), ("🐯", "tiger"),
    ("🐮", "cow"), ("🐷", "pig"), ("🐸", "frog"), ("🐵", "monkey"),
    ("🐔", "chicken"), ("🦄", "unicorn"),
]


def _gen_math_captcha():
    a, b = random.randint(1, 12), random.randint(1, 12)
    return f"{a}+{b}", str(a + b)


def _gen_animal_captcha():
    correct = random.choice(ANIMALS)
    options = [correct]
    while len(options) < 4:
        a = random.choice(ANIMALS)
        if a not in options:
            options.append(a)
    random.shuffle(options)
    return correct, options


async def _send_captcha(update, context):
    """Pick captcha type based on admin settings."""
    use_animal = get_setting("verify_captcha_animal", "0") == "1"
    use_math = get_setting("verify_captcha_math", "1") == "1"
    # prefer animal if both, random
    if use_animal and use_math:
        kind = random.choice(["math", "animal"])
    elif use_animal:
        kind = "animal"
    else:
        kind = "math"

    if kind == "animal":
        correct, options = _gen_animal_captcha()
        context.user_data["captcha_ans"] = correct[1]
        context.user_data["captcha_kind"] = "animal"
        context.user_data["awaiting_captcha"] = True
        buttons = [
            [InlineKeyboardButton(f"{o[0]} {o[1]}", callback_data=f"capani_{o[1]}")]
            for o in options
        ]
        await update.effective_message.reply_text(
            f"🔐 <b>Captcha</b>\n\nসঠিক প্রাণী বেছে নিন:\n"
            f"<b>{correct[0]}</b> কোন প্রাণী?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        q, ans = _gen_math_captcha()
        context.user_data["captcha_ans"] = ans
        context.user_data["captcha_kind"] = "math"
        context.user_data["awaiting_captcha"] = True
        await update.effective_message.reply_text(
            f"🔐 <b>Captcha</b>\n\nপ্রশ্ন: <b>{q} = ?</b>\nউত্তর সংখ্যায় লিখুন:",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )


async def check_verifications(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user passed all enabled verifies."""
    user = update.effective_user
    u = get_user(user.id)
    if not u:
        ensure_user(user.id, user.username, user.full_name)
        u = get_user(user.id)

    need_device = get_setting("verify_device", "0") == "1"
    need_phone = get_setting("verify_phone", "0") == "1"
    need_captcha = get_setting("verify_captcha", "0") == "1"

    # Device verify — Open App style button (Telegram limit: real IP needs web server)
    if need_device and not u["device_ok"]:
        token = "".join(random.choices(string.ascii_letters + string.digits, k=12))
        context.user_data["device_pending"] = token
        buttons = [[InlineKeyboardButton(
            "📲 Open App · Device Verify",
            callback_data=f"devfy_{token}",
        )]]
        await update.effective_message.reply_text(
            "📱 <b>Device Verify</b>\n\n"
            "নিচের বাটনে ক্লিক করে ডিভাইস ভেরিফাই করুন।\n"
            "(একটি ডিভাইসে একবার বাইন্ড হবে)",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return False

    if need_phone and not u["phone_ok"]:
        kb = ReplyKeyboardMarkup(
            [[KeyboardButton("📱 নম্বর শেয়ার করুন", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await update.effective_message.reply_text(
            "📱 <b>Phone Verify</b>\nনিচের বাটনে নম্বর শেয়ার করুন।",
            parse_mode=ParseMode.HTML,
            reply_markup=kb,
        )
        return False

    if need_captcha and not u["captcha_ok"]:
        await _send_captcha(update, context)
        return False

    return True


async def device_verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    token = q.data.replace("devfy_", "", 1)
    pending = context.user_data.get("device_pending")
    uid = q.from_user.id
    if pending and token != pending:
        await q.edit_message_text("❌ টোকেন মিলছে না। /start আবার চাপুন।")
        return
    did = f"tg_{uid}_{token[:8]}"
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET device_id=?, device_ok=1 WHERE user_id=?",
        (did, uid),
    )
    conn.commit()
    conn.close()
    context.user_data.pop("device_pending", None)
    await q.edit_message_text(
        f"✅ Device verified!\nID: <code>{did}</code>",
        parse_mode=ParseMode.HTML,
    )
    # continue other verifies
    fake_update = update
    if not await check_verifications(fake_update, context):
        return
    await context.bot.send_message(
        uid,
        get_setting("welcome_text", "স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )


async def animal_captcha_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chosen = q.data.replace("capani_", "", 1)
    ans = context.user_data.get("captcha_ans")
    uid = q.from_user.id
    if chosen != ans:
        await q.edit_message_text("❌ ভুল প্রাণী। আবার চেষ্টা...")
        # resend
        class _U:
            effective_message = q.message
            effective_user = q.from_user
        await _send_captcha(_U(), context)
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET captcha_ok=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    context.user_data.pop("captcha_ans", None)
    context.user_data.pop("awaiting_captcha", None)
    await q.edit_message_text("✅ Captcha OK!")
    await context.bot.send_message(
        uid,
        get_setting("welcome_text", "স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )


async def on_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    if not contact or contact.user_id != update.effective_user.id:
        await update.message.reply_text("নিজের নম্বর শেয়ার করুন।")
        return
    uid = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET phone=?, phone_ok=1 WHERE user_id=?",
        (contact.phone_number, uid),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ ফোন ভেরিফাই হয়েছে!",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    u = get_user(uid)
    if get_setting("verify_captcha", "0") == "1" and not u["captcha_ok"]:
        await _send_captcha(update, context)
        return
    await update.message.reply_text(
        get_setting("welcome_text", "স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )


async def on_captcha_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_captcha") and "captcha_ans" not in context.user_data:
        return False
    if context.user_data.get("captcha_kind") == "animal":
        return False  # handled by callback
    ans = context.user_data.get("captcha_ans")
    if not ans:
        return False
    if update.message.text.strip() != ans:
        q, new_ans = _gen_math_captcha()
        context.user_data["captcha_ans"] = new_ans
        await update.message.reply_text(
            f"❌ ভুল। আবার: <b>{q} = ?</b>", parse_mode=ParseMode.HTML
        )
        return True
    uid = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET captcha_ok=1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    context.user_data.pop("captcha_ans", None)
    context.user_data.pop("awaiting_captcha", None)
    await update.message.reply_text(
        "✅ Captcha OK!",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    return True


# ================== FORCE JOIN ==================
async def _member_ok(bot, chat_id, user_id) -> bool:
    raw = str(chat_id).strip()
    cands = []
    if raw.lstrip("-").isdigit():
        cands += [int(raw), raw]
    else:
        cands.append(raw if raw.startswith("@") else "@" + raw)
    for cid in cands:
        try:
            m = await bot.get_chat_member(chat_id=cid, user_id=user_id)
            st = str(m.status).lower()
            if st in ("left", "kicked"):
                return False
            return True
        except Exception as e:
            logger.warning(f"member {cid}: {e}")
    return False


async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    channels = get_channels()
    if not channels:
        return True
    missing = []
    for ch in channels:
        if not await _member_ok(context.bot, ch["chat_id"], user.id):
            missing.append(ch)
    if not missing:
        return True
    buttons = []
    for ch in missing:
        link = ch["invite_link"]
        if not link and not str(ch["chat_id"]).lstrip("-").isdigit():
            link = f"https://t.me/{str(ch['chat_id']).lstrip('@')}"
        if link:
            buttons.append(
                [InlineKeyboardButton(f"🔗 {ch['title'] or ch['chat_id']}", url=link)]
            )
    buttons.append([InlineKeyboardButton("✅ আমি জয়েন করেছি", callback_data="check_join")])
    text = "⚠️ প্রথমে চ্যানেল জয়েন করুন, তারপর ✅ চাপুন।"
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text, reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await update.effective_message.reply_text(
                text, reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception:
        await context.bot.send_message(
            user.id, text, reply_markup=InlineKeyboardMarkup(buttons)
        )
    return False


async def check_join_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("চেক...")
    user = q.from_user
    channels = get_channels()
    missing = [ch for ch in channels if not await _member_ok(context.bot, ch["chat_id"], user.id)]
    if missing:
        buttons = []
        for ch in missing:
            if ch["invite_link"]:
                buttons.append(
                    [InlineKeyboardButton(f"🔗 {ch['title'] or ch['chat_id']}", url=ch["invite_link"])]
                )
        buttons.append([InlineKeyboardButton("✅ আমি জয়েন করেছি", callback_data="check_join")])
        await q.edit_message_text(
            "⚠️ এখনো সব চ্যানেলে জয়েন হয়নি।",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return
    try:
        await q.edit_message_text("✅ জয়েন ভেরিফাইড!")
    except Exception:
        pass
    await context.bot.send_message(
        user.id,
        get_setting("welcome_text", "স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(user.id)),
    )


# ================== START ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_blocked(user.id):
        await update.message.reply_text("আপনি ব্লক।")
        return
    if get_setting("maintenance", "0") == "1" and not is_admin(user.id):
        await update.message.reply_text("🔧 Maintenance মোড। পরে আসুন।")
        return

    ref = None
    if context.args:
        try:
            ref = int(context.args[0])
            if ref == user.id:
                ref = None
        except ValueError:
            pass
    ensure_user(user.id, user.username, user.full_name, ref)

    if not await check_force_join(update, context):
        return
    if not await check_verifications(update, context):
        if get_setting("verify_captcha", "0") == "1":
            u = get_user(user.id)
            if not u["captcha_ok"]:
                context.user_data["awaiting_captcha"] = True
        return

    await update.message.reply_text(
        get_setting("welcome_text", "🎉 স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(user.id)),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    await update.message.reply_text(
        "বাতিল।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    return ConversationHandler.END


# ================== USER MENUS ==================
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    pts = u["points"] if u else 0
    bdt = float(get_setting("point_value_bdt", "0.10"))
    await update.message.reply_text(
        f"💰 <b>Balance:</b> {pts} পয়েন্ট\n≈ {pts * bdt:.2f} BDT",
        parse_mode=ParseMode.HTML,
    )


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    if not u:
        await update.message.reply_text("আগে /start করুন।")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (u["user_id"],))
    refs = cur.fetchone()["c"]
    conn.close()
    await update.message.reply_text(
        f"👤 <b>Profile</b>\n\n"
        f"ID: <code>{u['user_id']}</code>\n"
        f"Name: {u['full_name'] or '-'}\n"
        f"Username: @{u['username'] or '-'}\n"
        f"💰 Balance: {u['points']}\n"
        f"📱 Phone: {u['phone'] or '-'}\n"
        f"👥 Referral: {refs}\n"
        f"📅 Join: {(u['joined_at'] or '')[:10]}",
        parse_mode=ParseMode.HTML,
    )


async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    bonus = get_setting("referral_bonus", "10")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM users WHERE referrer_id=?", (uid,))
    cnt = cur.fetchone()["c"]
    conn.close()
    await update.message.reply_text(
        f"👥 <b>Referral</b>\n\nলিংক:\n<code>{link}</code>\n\n"
        f"বোনাস: {bonus} / রেফার\nমোট: {cnt} জন",
        parse_mode=ParseMode.HTML,
    )


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM history WHERE user_id=? ORDER BY id DESC LIMIT 15", (uid,)
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("📜 History খালি।")
        return
    text = "📜 <b>History</b>\n\n"
    for r in rows:
        text += f"• {r['kind']}: {r['amount']} — {r['note'] or ''} ({(r['created_at'] or '')[:16]})\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def cmd_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    un = get_setting("support_username", "").lstrip("@")
    if not un:
        await update.message.reply_text("সাপোর্ট সেট নেই।")
        return
    await update.message.reply_text(
        "🆘 Support",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("💬 মেসেজ", url=f"https://t.me/{un}")]]
        ),
    )


async def cmd_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        get_setting("faq_text", "FAQ"),
        parse_mode=ParseMode.HTML,
    )


async def cmd_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Refresh menu + show update note (admin can change update_note)."""
    uid = update.effective_user.id
    note = get_setting("update_note", f"Version {BOT_VERSION}")
    await update.message.reply_text(
        f"🔄 <b>Update</b>\n\n{note}\n\nমেনু রিফ্রেশ হয়েছে।",
        parse_mode=ParseMode.HTML,
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )


async def cmd_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    un = get_setting("developer_username", "").strip().lstrip("@")
    if not un:
        await update.message.reply_text("ডেভেলপার ইউজারনেম এখনো সেট নেই।")
        return
    await update.message.reply_text(
        "👨‍💻 <b>Developer</b>\nনিচের বাটনে ক্লিক করে যোগাযোগ করুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("👨‍💻 Developer", url=f"https://t.me/{un}")]]
        ),
    )


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="lang_bn")],
        [InlineKeyboardButton("🇺🇸 English", callback_data="lang_en")],
        [InlineKeyboardButton("🇮🇳 हिन्दी", callback_data="lang_hi")],
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru")],
    ]
    await update.message.reply_text(
        "🌐 <b>Language / ভাষা</b>\nChoose your language:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def lang_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.replace("lang_", "", 1)
    uid = q.from_user.id
    # store per-user in context / could use settings table user-specific — use history note
    context.user_data["lang"] = lang
    msgs = {
        "bn": "✅ ভাষা: বাংলা",
        "en": "✅ Language: English",
        "hi": "✅ भाषा: हिन्दी",
        "ar": "✅ اللغة: العربية",
        "ru": "✅ Язык: Русский",
    }
    await q.edit_message_text(msgs.get(lang, "✅ OK"))
    await context.bot.send_message(
        uid,
        msgs.get(lang, "OK"),
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )


# ================== TASKS ==================
async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_blocked(uid):
        return
    if not await check_force_join(update, context):
        return
    if not await check_verifications(update, context):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT t.id, t.title, t.reward_points FROM tasks t
           WHERE t.is_active=1
           AND t.id NOT IN (
             SELECT task_id FROM submissions
             WHERE user_id=? AND status IN ('pending','approved')
           )
           ORDER BY t.id DESC LIMIT 30""",
        (uid,),
    )
    tasks = cur.fetchall()
    conn.close()
    if not tasks:
        await update.message.reply_text("📋 নতুন টাস্ক নেই।")
        return
    buttons = [
        [
            InlineKeyboardButton(
                f"📋 {t['title']} (+{t['reward_points']})",
                callback_data=f"task_{t['id']}",
            )
        ]
        for t in tasks
    ]
    await update.message.reply_text("📋 Tasks:", reply_markup=InlineKeyboardMarkup(buttons))


async def task_detail_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=? AND is_active=1", (tid,))
    t = cur.fetchone()
    conn.close()
    if not t:
        await q.edit_message_text("টাস্ক নেই।")
        return
    text = (
        f"📋 <b>{t['title']}</b>\n\n"
        f"রিওয়ার্ড: <b>+{t['reward_points']}</b>\n\n"
        f"{t['description']}\n\n"
        f"স্ক্রিনশট + ভিডিও প্রুফ লাগবে।"
    )
    buttons = []
    if t["task_link"]:
        buttons.append([InlineKeyboardButton("🔗 লিংকে যান", url=t["task_link"])])
    buttons.append(
        [InlineKeyboardButton("✅ কাজ করেছি · প্রুফ দিন", callback_data=f"proof_{tid}")]
    )
    await q.edit_message_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def proof_start_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    tid = int(q.data.split("_")[1])
    uid = q.from_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM submissions WHERE task_id=? AND user_id=? AND status IN ('pending','approved')",
        (tid, uid),
    )
    if cur.fetchone():
        conn.close()
        await q.edit_message_text("আগেই সাবমিট করা হয়েছে।")
        return ConversationHandler.END
    conn.close()
    context.user_data["task_id"] = tid
    await q.edit_message_text("📷 স্ক্রিনশট পাঠান।")
    return WAIT_PHOTO


async def proof_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("ছবি পাঠান।")
        return WAIT_PHOTO
    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ স্ক্রিনশট OK। এখন ভিডিও পাঠান।")
    return WAIT_VIDEO


async def proof_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("ভিডিও পাঠান।")
        return WAIT_VIDEO
    tid = context.user_data.get("task_id")
    photo = context.user_data.get("photo")
    uid = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO submissions (task_id,user_id,proof_photo,proof_video,submitted_at)
           VALUES (?,?,?,?,?)""",
        (tid, uid, photo, update.message.video.file_id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ প্রুফ সাবমিট! অ্যাডমিন রিভিউ করবে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ================== POST TASK (costs points) ==================
async def post_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cost = float(get_setting("post_task_cost", "50"))
    u = get_user(uid)
    pts = u["points"] if u else 0
    bdt = float(get_setting("point_value_bdt", "0.10"))
    if pts < cost:
        await update.message.reply_text(
            f"❌ পোস্ট করতে <b>{cost}</b> পয়েন্ট লাগবে "
            f"(≈ {cost * bdt:.2f} BDT)।\nআপনার: {pts}",
            parse_mode=ParseMode.HTML,
        )
        return ConversationHandler.END
    await update.message.reply_text(
        f"➕ Post Task\nখরচ: <b>{cost}</b> পয়েন্ট (≈ {cost * bdt:.2f} BDT)\n\n"
        f"টাইটেল লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    return POST_TASK_TITLE


async def post_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pt_title"] = update.message.text.strip()
    await update.message.reply_text("নির্দেশনা লিখুন:")
    return POST_TASK_DESC


async def post_task_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pt_desc"] = update.message.text.strip()
    await update.message.reply_text("রিওয়ার্ড পয়েন্ট (ইউজার পাবে):")
    return POST_TASK_REWARD


async def post_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reward = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সংখ্যা লিখুন।")
        return POST_TASK_REWARD

    uid = update.effective_user.id
    cost = float(get_setting("post_task_cost", "50"))
    u = get_user(uid)
    if not u or u["points"] < cost:
        await update.message.reply_text("❌ পর্যাপ্ত পয়েন্ট নেই।", reply_markup=user_keyboard(is_admin(uid)))
        context.user_data.clear()
        return ConversationHandler.END

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (cost, uid))
    cur.execute(
        """INSERT INTO tasks (title,description,reward_points,created_by,is_user_post,created_at,is_active)
           VALUES (?,?,?,?,1,?,0)""",
        (
            context.user_data["pt_title"],
            context.user_data["pt_desc"],
            reward,
            uid,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    add_history(uid, "post_task_cost", -cost, context.user_data["pt_title"])

    await update.message.reply_text(
        f"✅ টাস্ক পোস্ট সাবমিট!\n-{cost} পয়েন্ট কাটা হয়েছে।\n"
        f"অ্যাডমিন অ্যাপ্রুভ করলে লাইভ হবে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    try:
        await context.bot.send_message(
            MAIN_ADMIN_ID,
            f"📝 User Post Task\nUser: `{uid}`\n"
            f"{context.user_data['pt_title']}\nReward: {reward}\nCost paid: {cost}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END


# ================== WITHDRAW / DEPOSIT ==================
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("withdraw_enabled", "1") != "1":
        await update.message.reply_text("💸 উইথড্র বন্ধ।")
        return ConversationHandler.END
    u = get_user(update.effective_user.id)
    min_w = float(get_setting("min_withdraw", "100"))
    pts = u["points"] if u else 0
    if pts < min_w:
        await update.message.reply_text(f"মিন {min_w} লাগবে। আপনার: {pts}")
        return ConversationHandler.END
    await update.message.reply_text(
        f"ব্যালেন্স: {pts}\nকত উইথড্র? (মিন {min_w})",
        reply_markup=ReplyKeyboardRemove(),
    )
    return WD_AMOUNT


async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সংখ্যা লিখুন।")
        return WD_AMOUNT
    u = get_user(update.effective_user.id)
    min_w = float(get_setting("min_withdraw", "100"))
    if amt < min_w or amt > u["points"]:
        await update.message.reply_text("অবৈধ পরিমাণ।")
        return WD_AMOUNT
    context.user_data["wd_amt"] = amt
    # show payment methods
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT name FROM payment_methods WHERE is_active=1")
    methods = [r["name"] for r in cur.fetchall()]
    conn.close()
    hint = ", ".join(methods) if methods else "bKash/Nagad/Binance"
    await update.message.reply_text(
        f"মেথড ও ডিটেইলস লিখুন ({hint}):\nউদাহরণ: Nagad 01XXXXXXXXX"
    )
    return WD_METHOD


async def withdraw_method(update: Update, context: ContextTypes.DEFAULT_TYPE):
    details = update.message.text.strip()
    amt = context.user_data["wd_amt"]
    uid = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (amt, uid))
    cur.execute(
        """INSERT INTO withdraws (user_id,amount,method,details,created_at)
           VALUES (?,?,?,?,?)""",
        (uid, amt, "manual", details, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    add_history(uid, "withdraw", -amt, details)
    await update.message.reply_text(
        "✅ উইথড্র রিকোয়েস্ট পাঠানো হয়েছে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    try:
        await context.bot.send_message(
            MAIN_ADMIN_ID,
            f"💸 Withdraw `{uid}`\n{amt}\n{details}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END


async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payment_methods WHERE is_active=1")
    methods = cur.fetchall()
    conn.close()
    text = "💳 <b>Deposit</b>\n\n"
    if methods:
        for m in methods:
            text += f"• <b>{m['name']}</b>\n{m['info']}\n\n"
    text += "পরিমাণ লিখুন:"
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove()
    )
    return DEP_AMOUNT


async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সঠিক পরিমাণ।")
        return DEP_AMOUNT
    context.user_data["dep_amt"] = amt
    await update.message.reply_text("পেমেন্ট স্ক্রিনশট পাঠান:")
    return DEP_PROOF


async def deposit_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("ছবি পাঠান।")
        return DEP_PROOF
    uid = update.effective_user.id
    amt = context.user_data["dep_amt"]
    fid = update.message.photo[-1].file_id
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO deposits (user_id,amount,proof_file_id,created_at) VALUES (?,?,?,?)",
        (uid, amt, fid, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ ডিপোজিট রিকোয়েস্ট পাঠানো হয়েছে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    try:
        await context.bot.send_photo(
            MAIN_ADMIN_ID,
            fid,
            caption=f"💳 Deposit `{uid}` Amount: {amt}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END


# ================== ADMIN ==================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("অ্যাডমিন নন।")
        return
    await update.message.reply_text(
        "🔧 Admin Panel",
        reply_markup=admin_keyboard(main=is_main(update.effective_user.id)),
    )


async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM users")
    total = cur.fetchone()["c"]
    cur.execute(
        "SELECT user_id, username, points, is_blocked FROM users ORDER BY user_id DESC LIMIT 20"
    )
    rows = cur.fetchall()
    conn.close()
    text = f"👥 <b>Users</b> ({total})\n\n"
    for r in rows:
        flag = "🚫" if r["is_blocked"] else "✅"
        text += f"{flag} `{r['user_id']}` @{r['username'] or '-'} — {r['points']}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) c FROM users")
    users = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) c FROM tasks WHERE is_active=1")
    tasks = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) c FROM submissions WHERE status='pending'")
    subs = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) c FROM withdraws WHERE status='pending'")
    wds = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) c FROM deposits WHERE status='pending'")
    deps = cur.fetchone()["c"]
    cur.execute(
        "SELECT COUNT(*) c FROM tasks WHERE is_user_post=1 AND is_active=0"
    )
    uposts = cur.fetchone()["c"]
    cur.execute("SELECT COALESCE(SUM(points),0) s FROM users")
    pts = cur.fetchone()["s"]
    conn.close()
    await update.message.reply_text(
        f"📊 <b>Statistics</b>\n\n"
        f"👥 Users: {users}\n📋 Active Tasks: {tasks}\n"
        f"📥 Pending Subs: {subs}\n📝 Pending User Posts: {uposts}\n"
        f"💸 Pending WD: {wds}\n💳 Pending Dep: {deps}\n"
        f"💰 Total points: {pts}",
        parse_mode=ParseMode.HTML,
    )


async def balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    op = "add" if "Add" in (update.message.text or "") else "remove"
    context.user_data["bal_op"] = op
    await update.message.reply_text("User ID:", reply_markup=ReplyKeyboardRemove())
    return BALANCE_UID


async def balance_uid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সঠিক ID।")
        return BALANCE_UID
    u = get_user(uid)
    if not u:
        await update.message.reply_text("ইউজার নেই।")
        return BALANCE_UID
    context.user_data["bal_uid"] = uid
    await update.message.reply_text(f"বর্তমান: {u['points']}\nপরিমাণ:")
    return BALANCE_AMT


async def balance_amt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সঠিক সংখ্যা।")
        return BALANCE_AMT
    uid = context.user_data["bal_uid"]
    op = context.user_data.get("bal_op", "add")
    admin = update.effective_user.id
    conn = get_db()
    cur = conn.cursor()
    if op == "remove":
        cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
        p = cur.fetchone()["points"]
        if p < amt:
            conn.close()
            await update.message.reply_text(
                f"পর্যাপ্ত নেই ({p})",
                reply_markup=admin_keyboard(is_main(admin)),
            )
            context.user_data.clear()
            return ConversationHandler.END
        cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (amt, uid))
        add_history(uid, "admin_remove", -amt, "admin")
        msg = f"✅ {amt} কাটা হয়েছে।"
        # no user notify on remove
    else:
        cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amt, uid))
        add_history(uid, "admin_add", amt, "admin")
        msg = f"✅ {amt} অ্যাড।"
        try:
            await context.bot.send_message(uid, f"🎉 অ্যাডমিন {amt} পয়েন্ট দিয়েছেন।")
        except Exception:
            pass
    cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
    new_p = cur.fetchone()["points"]
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"{msg}\n`{uid}` → {new_p}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(is_main(admin)),
    )
    context.user_data.clear()
    return ConversationHandler.END


# Admin create task
async def admin_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, reward_points, is_active, is_user_post FROM tasks ORDER BY id DESC LIMIT 20"
    )
    rows = cur.fetchall()
    conn.close()
    buttons = [[InlineKeyboardButton("➕ নতুন টাস্ক", callback_data="admin_new_task")]]
    text = "📋 <b>Tasks</b>\n\n"
    for r in rows:
        st = "✅" if r["is_active"] else "⏸"
        up = "👤" if r["is_user_post"] else ""
        text += f"{st}{up} #{r['id']} {r['title']} (+{r['reward_points']})\n"
        buttons.append(
            [
                InlineKeyboardButton(
                    f"{'⏸' if r['is_active'] else '▶️'} #{r['id']}",
                    callback_data=f"tgl_task_{r['id']}",
                ),
                InlineKeyboardButton(f"🗑 #{r['id']}", callback_data=f"del_task_{r['id']}"),
            ]
        )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def admin_new_task_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("টাস্ক টাইটেল:")
    return CREATE_TASK_TITLE


async def admin_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text("নির্দেশনা:")
    return CREATE_TASK_DESC


async def admin_task_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task_desc"] = update.message.text.strip()
    await update.message.reply_text("রিওয়ার্ড পয়েন্ট:")
    return CREATE_TASK_REWARD


async def admin_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["task_reward"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return CREATE_TASK_REWARD
    await update.message.reply_text("লিংক (/skip):")
    return CREATE_TASK_LINK


async def admin_task_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    link = None if t in ("/skip", "skip") else t
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO tasks (title,description,reward_points,task_link,created_by,created_at,is_active)
           VALUES (?,?,?,?,?,?,1)""",
        (
            context.user_data["task_title"],
            context.user_data["task_desc"],
            context.user_data["task_reward"],
            link,
            update.effective_user.id,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ টাস্ক তৈরি।",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def toggle_task_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    tid = int(q.data.split("_")[-1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET is_active = 1 - is_active WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    await q.edit_message_text(f"✅ টাস্ক #{tid} টগল।")


async def del_task_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    tid = int(q.data.split("_")[-1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE tasks SET is_active=0 WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    await q.edit_message_text(f"🗑 #{tid}")


# User posts review
async def admin_user_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, title, description, reward_points, created_by, created_at
           FROM tasks WHERE is_user_post=1 AND is_active=0 ORDER BY id ASC LIMIT 20"""
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("পেন্ডিং ইউজার পোস্ট নেই।")
        return
    for r in rows:
        buttons = [[
            InlineKeyboardButton("✅ Approve", callback_data=f"upok_{r['id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"upno_{r['id']}"),
        ]]
        await update.message.reply_text(
            f"📝 #{r['id']} by `{r['created_by']}`\n"
            f"<b>{r['title']}</b>\n{r['description'][:200]}\n"
            f"Reward: {r['reward_points']}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def up_ok_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    tid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=? AND is_user_post=1", (tid,))
    t = cur.fetchone()
    if not t:
        conn.close()
        await q.edit_message_text("নেই।")
        return
    cur.execute("UPDATE tasks SET is_active=1 WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    await q.edit_message_text(f"✅ Post #{tid} approved & live")
    try:
        await context.bot.send_message(
            t["created_by"],
            f"✅ আপনার টাস্ক অ্যাপ্রুভ হয়েছে!\n📋 {t['title']}",
        )
    except Exception:
        pass


async def up_no_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    tid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM tasks WHERE id=? AND is_user_post=1", (tid,))
    t = cur.fetchone()
    if not t:
        conn.close()
        await q.edit_message_text("নেই।")
        return
    # soft delete
    cur.execute("UPDATE tasks SET is_active=0, title=title || ' [REJECTED]' WHERE id=?", (tid,))
    # refund post cost
    cost = float(get_setting("post_task_cost", "50"))
    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (cost, t["created_by"]),
    )
    conn.commit()
    conn.close()
    add_history(t["created_by"], "post_refund", cost, f"task #{tid}")
    await q.edit_message_text(f"❌ Post #{tid} rejected + refund {cost}")
    try:
        await context.bot.send_message(
            t["created_by"],
            f"❌ আপনার টাস্ক রিজেক্ট। {cost} পয়েন্ট ফেরত।",
        )
    except Exception:
        pass


async def admin_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT s.*, t.title, t.reward_points FROM submissions s
           JOIN tasks t ON t.id=s.task_id
           WHERE s.status='pending' ORDER BY s.id ASC LIMIT 15"""
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("পেন্ডিং সাবমিশন নেই।")
        return
    for r in rows:
        buttons = [[
            InlineKeyboardButton("✅", callback_data=f"appr_{r['id']}"),
            InlineKeyboardButton("❌", callback_data=f"rej_{r['id']}"),
        ]]
        cap = f"🆔 {r['id']} | `{r['user_id']}`\n📋 {r['title']} | +{r['reward_points']}"
        try:
            if r["proof_photo"]:
                await context.bot.send_photo(
                    update.effective_chat.id, r["proof_photo"], caption=cap + "\n📷",
                    parse_mode=ParseMode.HTML,
                )
            if r["proof_video"]:
                await context.bot.send_video(
                    update.effective_chat.id, r["proof_video"],
                    caption=cap + "\n🎬",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
            elif r["proof_photo"]:
                await context.bot.send_message(
                    update.effective_chat.id, "↑ Approve/Reject",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        except Exception as e:
            await update.message.reply_text(f"Sub {r['id']}: {e}")


async def approve_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    sid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT s.*, t.reward_points, t.title FROM submissions s
           JOIN tasks t ON t.id=s.task_id WHERE s.id=? AND s.status='pending'""",
        (sid,),
    )
    s = cur.fetchone()
    if not s:
        conn.close()
        try:
            await q.edit_message_caption(caption="প্রসেসড।")
        except Exception:
            await q.edit_message_text("প্রসেসড।")
        return
    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (s["reward_points"], s["user_id"]),
    )
    cur.execute(
        "UPDATE submissions SET status='approved', reviewed_at=?, reviewed_by=? WHERE id=?",
        (datetime.now().isoformat(), q.from_user.id, sid),
    )
    conn.commit()
    conn.close()
    add_history(s["user_id"], "task_reward", s["reward_points"], s["title"])
    try:
        await q.edit_message_caption(caption=f"✅ +{s['reward_points']}")
    except Exception:
        await q.edit_message_text(f"✅ +{s['reward_points']}")
    try:
        await context.bot.send_message(
            s["user_id"], f"🎉 টাস্ক অ্যাপ্রুভ! +{s['reward_points']} পয়েন্ট"
        )
    except Exception:
        pass


async def reject_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    sid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE submissions SET status='rejected', reviewed_at=?, reviewed_by=? WHERE id=? AND status='pending'",
        (datetime.now().isoformat(), q.from_user.id, sid),
    )
    cur.execute("SELECT user_id FROM submissions WHERE id=?", (sid,))
    row = cur.fetchone()
    conn.commit()
    conn.close()
    try:
        await q.edit_message_caption(caption="❌ Rejected")
    except Exception:
        await q.edit_message_text("❌ Rejected")
    if row:
        try:
            await context.bot.send_message(row["user_id"], "❌ টাস্ক রিজেক্ট।")
        except Exception:
            pass


async def admin_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM withdraws WHERE status='pending' ORDER BY id ASC LIMIT 20")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("পেন্ডিং উইথড্র নেই।")
        return
    for r in rows:
        buttons = [[
            InlineKeyboardButton("✅ Done", callback_data=f"wdok_{r['id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"wdno_{r['id']}"),
        ]]
        await update.message.reply_text(
            f"💸 #{r['id']} `{r['user_id']}`\n{r['amount']} — {r['details']}",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def wd_ok_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    wid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM withdraws WHERE id=? AND status='pending'", (wid,))
    r = cur.fetchone()
    if not r:
        conn.close()
        await q.edit_message_text("প্রসেসড।")
        return
    cur.execute(
        "UPDATE withdraws SET status='done', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), wid),
    )
    conn.commit()
    conn.close()
    await q.edit_message_text(f"✅ WD #{wid}")
    try:
        await context.bot.send_message(r["user_id"], f"✅ উইথড্র #{wid} সম্পন্ন।")
    except Exception:
        pass


async def wd_no_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    wid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM withdraws WHERE id=? AND status='pending'", (wid,))
    r = cur.fetchone()
    if not r:
        conn.close()
        await q.edit_message_text("প্রসেসড।")
        return
    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (r["amount"], r["user_id"]),
    )
    cur.execute(
        "UPDATE withdraws SET status='rejected', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), wid),
    )
    conn.commit()
    conn.close()
    add_history(r["user_id"], "withdraw_refund", r["amount"], f"wd #{wid}")
    await q.edit_message_text(f"❌ WD #{wid} + refund")
    try:
        await context.bot.send_message(
            r["user_id"], f"❌ উইথড্র রিজেক্ট। {r['amount']} ফেরত।"
        )
    except Exception:
        pass


async def admin_deposits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM deposits WHERE status='pending' ORDER BY id ASC LIMIT 15")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("পেন্ডিং ডিপোজিট নেই।")
        return
    for r in rows:
        buttons = [[
            InlineKeyboardButton("✅", callback_data=f"depok_{r['id']}"),
            InlineKeyboardButton("❌", callback_data=f"depno_{r['id']}"),
        ]]
        try:
            await context.bot.send_photo(
                update.effective_chat.id,
                r["proof_file_id"],
                caption=f"💳 #{r['id']} `{r['user_id']}` {r['amount']}",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons),
            )
        except Exception as e:
            await update.message.reply_text(f"Dep {r['id']}: {e}")


async def dep_ok_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    did = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM deposits WHERE id=? AND status='pending'", (did,))
    r = cur.fetchone()
    if not r:
        conn.close()
        await q.edit_message_caption(caption="প্রসেসড।")
        return
    cur.execute(
        "UPDATE users SET points = points + ? WHERE user_id=?",
        (r["amount"], r["user_id"]),
    )
    cur.execute(
        "UPDATE deposits SET status='approved', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), did),
    )
    conn.commit()
    conn.close()
    add_history(r["user_id"], "deposit", r["amount"], f"dep #{did}")
    await q.edit_message_caption(caption=f"✅ +{r['amount']}")
    try:
        await context.bot.send_message(
            r["user_id"], f"✅ ডিপোজিট অ্যাপ্রুভ +{r['amount']}"
        )
    except Exception:
        pass


async def dep_no_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    did = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE deposits SET status='rejected', processed_at=? WHERE id=? AND status='pending'",
        (datetime.now().isoformat(), did),
    )
    cur.execute("SELECT user_id FROM deposits WHERE id=?", (did,))
    r = cur.fetchone()
    conn.commit()
    conn.close()
    await q.edit_message_caption(caption="❌ Rejected")
    if r:
        try:
            await context.bot.send_message(r["user_id"], "❌ ডিপোজিট রিজেক্ট।")
        except Exception:
            pass


# Channels
async def admin_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    channels = get_channels()
    text = "📢 <b>Force Channels</b>\n\n"
    buttons = [[InlineKeyboardButton("➕ Add", callback_data="add_ch")]]
    for ch in channels:
        text += f"• {ch['title']} (`{ch['chat_id']}`)\n"
        buttons.append(
            [InlineKeyboardButton(f"🗑 {ch['title']}", callback_data=f"rmch_{ch['id']}")]
        )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def add_ch_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Chat ID / @username পাঠান:")
    return ADD_CHANNEL


async def add_ch_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    raw = update.message.text.strip()
    try:
        chat = await context.bot.get_chat(raw)
        title = chat.title or str(chat.id)
        try:
            link = await context.bot.export_chat_invite_link(chat.id)
        except Exception:
            link = f"https://t.me/{chat.username}" if chat.username else None
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO forced_channels (chat_id,title,invite_link,added_at) VALUES (?,?,?,?)",
            (str(chat.id), title, link, datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
        await update.message.reply_text(
            f"✅ {title}",
            reply_markup=admin_keyboard(is_main(update.effective_user.id)),
        )
        return ConversationHandler.END
    except Exception as e:
        if raw.lstrip("-").isdigit():
            context.user_data["mch_id"] = raw
            await update.message.reply_text(f"ম্যানুয়াল। টাইটেল লিখুন:\n({e})")
            return ADD_CHANNEL_TITLE
        await update.message.reply_text(f"Error: {e}\n/cancel")
        return ADD_CHANNEL


async def add_ch_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mch_title"] = update.message.text.strip()
    await update.message.reply_text("Invite link (/skip):")
    return ADD_CHANNEL_LINK


async def add_ch_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    link = None if t in ("/skip", "skip") else t
    cid = context.user_data["mch_id"]
    title = context.user_data.get("mch_title", cid)
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO forced_channels (chat_id,title,invite_link,added_at) VALUES (?,?,?,?)",
        (str(cid), title, link, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ {title}",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def rmch_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    cid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM forced_channels WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    await q.edit_message_text("🗑 Removed")


# Payment methods (bKash, Nagad, etc.)
async def admin_pay_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payment_methods")
    rows = cur.fetchall()
    conn.close()
    text = "💳 <b>Payment Methods</b>\n(bKash, Nagad, Rocket, Binance...)\n\n"
    buttons = [[InlineKeyboardButton("➕ Add Method", callback_data="add_pay")]]
    for r in rows:
        text += f"• <b>{r['name']}</b>: {r['info']}\n"
        buttons.append(
            [InlineKeyboardButton(f"🗑 {r['name']}", callback_data=f"rmpay_{r['id']}")]
        )
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("নাম (bKash / Nagad / Rocket / Binance / অন্য):")
    return PAY_METHOD_NAME


async def add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pay_name"] = update.message.text.strip()
    await update.message.reply_text("ডিটেইলস (নম্বর/UID):")
    return PAY_METHOD_INFO


async def add_pay_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO payment_methods (name, info) VALUES (?,?)",
        (context.user_data["pay_name"], update.message.text.strip()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        "✅ Method added.",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def rmpay_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    pid = int(q.data.split("_")[1])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM payment_methods WHERE id=?", (pid,))
    conn.commit()
    conn.close()
    await q.edit_message_text("🗑 Removed")


# Settings
async def admin_ref_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        f"🎁 বর্তমান: {get_setting('referral_bonus')}\nনতুন বোনাস:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_REF_BONUS


async def set_ref_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("referral_bonus", str(v))
        await update.message.reply_text(
            f"✅ {v}",
            reply_markup=admin_keyboard(is_main(update.effective_user.id)),
        )
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return SET_REF_BONUS
    return ConversationHandler.END


async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        f"⚙️ <b>Settings</b>\n\n"
        f"Min WD: {get_setting('min_withdraw')}\n"
        f"Referral: {get_setting('referral_bonus')}\n"
        f"Post cost: {get_setting('post_task_cost')} pts\n"
        f"1 pt = {get_setting('point_value_bdt')} BDT\n"
        f"Support: @{get_setting('support_username') or '-'}\n"
        f"Maintenance: {get_setting('maintenance')}\n"
        f"Withdraw: {get_setting('withdraw_enabled')}\n"
        f"Device verify: {get_setting('verify_device')}\n"
        f"Phone verify: {get_setting('verify_phone')}\n"
        f"Captcha verify: {get_setting('verify_captcha')}"
    )
    buttons = [
        [InlineKeyboardButton("Min Withdraw", callback_data="set_min_wd")],
        [InlineKeyboardButton("Support Username", callback_data="set_support")],
        [InlineKeyboardButton("FAQ Text", callback_data="set_faq")],
        [InlineKeyboardButton("Update Note", callback_data="set_update_note")],
    ]
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def set_min_wd_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Min withdraw:")
    return SET_MIN_WD


async def set_min_wd_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("min_withdraw", str(v))
        await update.message.reply_text(
            f"✅ {v}",
            reply_markup=admin_keyboard(is_main(update.effective_user.id)),
        )
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return SET_MIN_WD
    return ConversationHandler.END


async def set_support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Support username:")
    return SET_SUPPORT


async def set_support_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("support_username", update.message.text.strip().lstrip("@"))
    await update.message.reply_text(
        "✅",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    return ConversationHandler.END


async def set_faq_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("নতুন FAQ টেক্সট (HTML OK):")
    return SET_FAQ


async def set_faq_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("faq_text", update.message.text)
    await update.message.reply_text(
        "✅ FAQ updated",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    return ConversationHandler.END


async def set_update_note_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Update note টেক্সট:")
    return SET_FAQ  # reuse state — will route via user_data flag


async def post_cost_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await update.message.reply_text(
        f"💰 Post cost: {get_setting('post_task_cost')} pts\n"
        f"1 pt = {get_setting('point_value_bdt')} BDT\n\n"
        f"নতুন <b>post task cost</b> (পয়েন্ট) লিখুন:",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_POST_COST


async def set_post_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("post_task_cost", str(v))
        await update.message.reply_text(
            f"✅ Post cost = {v}\nএখন 1 পয়েন্ট = কত BDT? (যেমন 0.10)"
        )
        return SET_POINT_BDT
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return SET_POST_COST


async def set_point_bdt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("point_value_bdt", str(v))
        await update.message.reply_text(
            f"✅ 1 pt = {v} BDT",
            reply_markup=admin_keyboard(is_main(update.effective_user.id)),
        )
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return SET_POINT_BDT
    return ConversationHandler.END


async def verify_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    d = get_setting("verify_device", "0")
    p = get_setting("verify_phone", "0")
    c = get_setting("verify_captcha", "0")
    m = get_setting("verify_captcha_math", "1")
    a = get_setting("verify_captcha_animal", "0")
    buttons = [
        [InlineKeyboardButton(f"📱 Device: {'ON' if d=='1' else 'OFF'}", callback_data="tog_vdev")],
        [InlineKeyboardButton(f"📞 Phone: {'ON' if p=='1' else 'OFF'}", callback_data="tog_vphone")],
        [InlineKeyboardButton(f"🔐 Captcha Master: {'ON' if c=='1' else 'OFF'}", callback_data="tog_vcaptcha")],
        [InlineKeyboardButton(f"🔢 Math Captcha: {'ON' if m=='1' else 'OFF'}", callback_data="tog_vmath")],
        [InlineKeyboardButton(f"🦁 Animal Captcha: {'ON' if a=='1' else 'OFF'}", callback_data="tog_vanimal")],
    ]
    await update.message.reply_text(
        "🔐 <b>Verify Settings</b>\nপ্রতিটি আলাদা ON/OFF:",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def tog_verify_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_admin(q.from_user.id):
        return
    key_map = {
        "tog_vdev": "verify_device",
        "tog_vphone": "verify_phone",
        "tog_vcaptcha": "verify_captcha",
        "tog_vmath": "verify_captcha_math",
        "tog_vanimal": "verify_captcha_animal",
    }
    key = key_map.get(q.data)
    if not key:
        return
    cur = get_setting(key, "0")
    new = "0" if cur == "1" else "1"
    set_setting(key, new)
    d = get_setting("verify_device", "0")
    p = get_setting("verify_phone", "0")
    c = get_setting("verify_captcha", "0")
    m = get_setting("verify_captcha_math", "1")
    a = get_setting("verify_captcha_animal", "0")
    buttons = [
        [InlineKeyboardButton(f"📱 Device: {'ON' if d=='1' else 'OFF'}", callback_data="tog_vdev")],
        [InlineKeyboardButton(f"📞 Phone: {'ON' if p=='1' else 'OFF'}", callback_data="tog_vphone")],
        [InlineKeyboardButton(f"🔐 Captcha Master: {'ON' if c=='1' else 'OFF'}", callback_data="tog_vcaptcha")],
        [InlineKeyboardButton(f"🔢 Math Captcha: {'ON' if m=='1' else 'OFF'}", callback_data="tog_vmath")],
        [InlineKeyboardButton(f"🦁 Animal Captcha: {'ON' if a=='1' else 'OFF'}", callback_data="tog_vanimal")],
    ]
    await q.edit_message_text(
        "🔐 Updated.",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cur = get_setting("maintenance", "0")
    new = "0" if cur == "1" else "1"
    set_setting("maintenance", new)
    await update.message.reply_text(
        f"🔧 Maintenance → {'ON' if new == '1' else 'OFF'}",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )


async def toggle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cur = get_setting("withdraw_enabled", "1")
    new = "0" if cur == "1" else "1"
    set_setting("withdraw_enabled", new)
    await update.message.reply_text(
        f"💸 Withdraw → {'ON' if new == '1' else 'OFF'}",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )


# Broadcast
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    await update.message.reply_text(
        "📢 ব্রডকাস্ট মেসেজ পাঠান (টেক্সট/ফটো/ভিডিও):\n/cancel",
        reply_markup=ReplyKeyboardRemove(),
    )
    return BROADCAST_MSG


async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_blocked=0")
    users = [r["user_id"] for r in cur.fetchall()]
    conn.close()
    ok = fail = 0
    msg = update.message
    for uid in users:
        try:
            if msg.text:
                await context.bot.send_message(uid, msg.text, parse_mode=ParseMode.HTML)
            elif msg.photo:
                await context.bot.send_photo(uid, msg.photo[-1].file_id, caption=msg.caption)
            elif msg.video:
                await context.bot.send_video(uid, msg.video.file_id, caption=msg.caption)
            else:
                await context.bot.copy_message(uid, msg.chat_id, msg.message_id)
            ok += 1
        except Exception:
            fail += 1
    await update.message.reply_text(
        f"✅ Broadcast\nOK: {ok} | Fail: {fail}",
        reply_markup=admin_keyboard(is_main(update.effective_user.id)),
    )
    return ConversationHandler.END


# Admin manage + ownership
async def admin_manage_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("❌ শুধু Main Admin।")
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id, role FROM admins")
    rows = cur.fetchall()
    conn.close()
    text = "👑 <b>Admins</b>\n\n"
    for r in rows:
        text += f"• `{r['user_id']}` — {r['role']}\n"
    buttons = [
        [InlineKeyboardButton("➕ Add Admin", callback_data="add_admin")],
        [InlineKeyboardButton("🗑 Remove Admin", callback_data="rm_admin")],
    ]
    await update.message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons)
    )


async def add_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_main(q.from_user.id):
        await q.edit_message_text("❌ Main only")
        return ConversationHandler.END
    await q.edit_message_text("নতুন অ্যাডমিন User ID:")
    return ADD_ADMIN_ID


async def add_admin_recv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID সংখ্যা।")
        return ADD_ADMIN_ID
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at) VALUES (?,?,?,?)",
        (uid, "admin", update.effective_user.id, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ `{uid}` admin",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(True),
    )
    try:
        await context.bot.send_message(uid, "আপনাকে অ্যাডমিন বানানো হয়েছে।")
    except Exception:
        pass
    return ConversationHandler.END


async def rm_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if not is_main(q.from_user.id):
        await q.edit_message_text("❌ Main only")
        return ConversationHandler.END
    await q.edit_message_text("রিমুভ করতে User ID:")
    return REMOVE_ADMIN_ID


async def rm_admin_recv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID সংখ্যা।")
        return REMOVE_ADMIN_ID
    if uid == MAIN_ADMIN_ID or is_main(uid):
        await update.message.reply_text(
            "❌ Main Admin কখনো রিমুভ করা যাবে না।",
            reply_markup=admin_keyboard(True),
        )
        return ConversationHandler.END
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM admins WHERE user_id=? AND role='admin'", (uid,))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ `{uid}` removed",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(True),
    )
    return ConversationHandler.END


async def transfer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_main(update.effective_user.id):
        await update.message.reply_text("❌ শুধু Main Admin।")
        return ConversationHandler.END
    await update.message.reply_text(
        "⚠️ Ownership Transfer\nনতুন Main Admin এর User ID:\n"
        "ট্রান্সফারের পর আপনি সাধারণ admin থাকবেন।",
        reply_markup=ReplyKeyboardRemove(),
    )
    return TRANSFER_OWNER_ID


async def transfer_recv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("ID সংখ্যা।")
        return TRANSFER_OWNER_ID
    old = update.effective_user.id
    if new_id == old:
        await update.message.reply_text("নিজেকে নয়।")
        return ConversationHandler.END
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO admins (user_id, role, added_by, added_at) VALUES (?,?,?,?)",
        (new_id, "main", old, datetime.now().isoformat()),
    )
    cur.execute("UPDATE admins SET role='admin' WHERE user_id=?", (old,))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ Ownership → `{new_id}`\nMain Admin আর সরানো যাবে না (নতুন main)।",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(False),
    )
    try:
        await context.bot.send_message(new_id, "🎉 আপনি এখন Main Admin!")
    except Exception:
        pass
    return ConversationHandler.END


# ================== ROUTER ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # captcha intercept
    if await on_captcha_text(update, context):
        return

    text = update.message.text or ""
    uid = update.effective_user.id

    if is_blocked(uid):
        await update.message.reply_text("ব্লক।")
        return
    if get_setting("maintenance", "0") == "1" and not is_admin(uid):
        await update.message.reply_text("🔧 Maintenance।")
        return

    if text == "💰 Balance":
        await cmd_balance(update, context)
    elif text == "📋 Tasks":
        await cmd_tasks(update, context)
    elif text == "👤 Profile":
        await cmd_profile(update, context)
    elif text == "👥 Referral":
        await cmd_referral(update, context)
    elif text == "💸 Withdraw":
        return await withdraw_start(update, context)
    elif text == "💳 Deposit":
        return await deposit_start(update, context)
    elif text == "➕ Post Task":
        return await post_task_start(update, context)
    elif text == "📜 History":
        await cmd_history(update, context)
    elif text == "🆘 Support":
        await cmd_support(update, context)
    elif text == "ℹ️ FAQ":
        await cmd_faq(update, context)
    elif text == "🔄 Update":
        await cmd_update(update, context)
    elif text == "👨‍💻 Developer":
        await cmd_developer(update, context)
    elif text == "🌐 Language":
        await cmd_language(update, context)
    elif text == "🔧 Admin Panel" and is_admin(uid):
        await admin_panel(update, context)
    elif context.user_data.get("awaiting_developer") and is_admin(uid):
        set_setting("developer_username", text.strip().lstrip("@"))
        context.user_data.pop("awaiting_developer", None)
        await update.message.reply_text(
            f"✅ Developer set: @{get_setting('developer_username')}",
            reply_markup=admin_keyboard(is_main(uid)),
        )
        return
    elif text == "👨‍💻 Set Developer" and is_admin(uid):
        context.user_data["awaiting_developer"] = True
        cur = get_setting("developer_username", "")
        await update.message.reply_text(
            f"বর্তমান: @{cur or '-'}\nনতুন username লিখুন (@ ছাড়া):",
            reply_markup=ReplyKeyboardRemove(),
        )
        return
    elif text == "🌐 Lang / FAQ" and is_admin(uid):
        await admin_settings(update, context)
        return
    elif text == "🏠 User Panel":
        await update.message.reply_text(
            "User Panel", reply_markup=user_keyboard(show_admin=is_admin(uid))
        )
    elif text == "👥 Users" and is_admin(uid):
        await admin_users(update, context)
    elif text == "📊 Statistics" and is_admin(uid):
        await admin_stats(update, context)
    elif text in ("➕ Add Balance", "➖ Remove Balance") and is_admin(uid):
        return await balance_start(update, context)
    elif text == "📋 Manage Tasks" and is_admin(uid):
        await admin_tasks_menu(update, context)
    elif text == "📥 Submissions" and is_admin(uid):
        await admin_submissions(update, context)
    elif text == "📝 User Posts" and is_admin(uid):
        await admin_user_posts(update, context)
    elif text == "📢 Broadcast" and is_admin(uid):
        return await broadcast_start(update, context)
    elif text == "💸 Withdrawals" and is_admin(uid):
        await admin_withdrawals(update, context)
    elif text == "💳 Deposits" and is_admin(uid):
        await admin_deposits(update, context)
    elif text == "📢 Channels" and is_admin(uid):
        await admin_channels(update, context)
    elif text == "💳 Payment Methods" and is_admin(uid):
        await admin_pay_methods(update, context)
    elif text == "🎁 Referral Settings" and is_admin(uid):
        return await admin_ref_settings(update, context)
    elif text == "⚙️ Settings" and is_admin(uid):
        await admin_settings(update, context)
    elif text == "🔐 Verify Settings" and is_admin(uid):
        await verify_settings(update, context)
    elif text == "💰 Post Cost / BDT" and is_admin(uid):
        return await post_cost_menu(update, context)
    elif text == "🔧 Maintenance ON/OFF" and is_admin(uid):
        await toggle_maintenance(update, context)
    elif text == "💸 Withdraw ON/OFF" and is_admin(uid):
        await toggle_withdraw(update, context)
    elif text == "👑 Add/Remove Admin" and is_main(uid):
        await admin_manage_menu(update, context)
    elif text == "🔄 Ownership Transfer" and is_main(uid):
        return await transfer_start(update, context)


def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).job_queue(JobQueue()).build()

    proof_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(proof_start_cb, pattern=r"^proof_\d+$")],
        states={
            WAIT_PHOTO: [MessageHandler(filters.PHOTO, proof_photo)],
            WAIT_VIDEO: [MessageHandler(filters.VIDEO, proof_video)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    wd_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💸 Withdraw$"), withdraw_start)],
        states={
            WD_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_amount)],
            WD_METHOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, withdraw_method)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dep_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 Deposit$"), deposit_start)],
        states={
            DEP_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)],
            DEP_PROOF: [MessageHandler(filters.PHOTO, deposit_proof)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    post_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Post Task$"), post_task_start)],
        states={
            POST_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_task_title)],
            POST_TASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_task_desc)],
            POST_TASK_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_task_reward)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    bal_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^➕ Add Balance$"), balance_start),
            MessageHandler(filters.Regex("^➖ Remove Balance$"), balance_start),
        ],
        states={
            BALANCE_UID: [MessageHandler(filters.TEXT & ~filters.COMMAND, balance_uid)],
            BALANCE_AMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, balance_amt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    task_create_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_new_task_cb, pattern="^admin_new_task$")],
        states={
            CREATE_TASK_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_title)],
            CREATE_TASK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_desc)],
            CREATE_TASK_REWARD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_reward)],
            CREATE_TASK_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_task_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    ch_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_ch_start, pattern="^add_ch$")],
        states={
            ADD_CHANNEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ch_receive)],
            ADD_CHANNEL_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ch_title)],
            ADD_CHANNEL_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_ch_link)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    pay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_pay_start, pattern="^add_pay$")],
        states={
            PAY_METHOD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_name)],
            PAY_METHOD_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_pay_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    ref_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 Referral Settings$"), admin_ref_settings)],
        states={SET_REF_BONUS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_ref_bonus)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    post_cost_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💰 Post Cost / BDT$"), post_cost_menu)],
        states={
            SET_POST_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_post_cost)],
            SET_POINT_BDT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_point_bdt)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    settings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(set_min_wd_cb, pattern="^set_min_wd$"),
            CallbackQueryHandler(set_support_cb, pattern="^set_support$"),
            CallbackQueryHandler(set_faq_cb, pattern="^set_faq$"),
        ],
        states={
            SET_MIN_WD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_min_wd_val)],
            SET_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_support_val)],
            SET_FAQ: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_faq_val)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 Broadcast$"), broadcast_start)],
        states={
            BROADCAST_MSG: [MessageHandler(filters.ALL & ~filters.COMMAND, broadcast_send)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    add_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_admin_start, pattern="^add_admin$")],
        states={ADD_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_recv)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    rm_admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(rm_admin_start, pattern="^rm_admin$")],
        states={REMOVE_ADMIN_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, rm_admin_recv)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    transfer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔄 Ownership Transfer$"), transfer_start)],
        states={TRANSFER_OWNER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, transfer_recv)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(MessageHandler(filters.CONTACT, on_contact))

    app.add_handler(CallbackQueryHandler(check_join_cb, pattern="^check_join$"))
    app.add_handler(CallbackQueryHandler(device_verify_cb, pattern=r"^devfy_"))
    app.add_handler(CallbackQueryHandler(animal_captcha_cb, pattern=r"^capani_"))
    app.add_handler(CallbackQueryHandler(lang_cb, pattern=r"^lang_"))
    app.add_handler(CallbackQueryHandler(task_detail_cb, pattern=r"^task_\d+$"))
    app.add_handler(CallbackQueryHandler(approve_cb, pattern=r"^appr_\d+$"))
    app.add_handler(CallbackQueryHandler(reject_cb, pattern=r"^rej_\d+$"))
    app.add_handler(CallbackQueryHandler(wd_ok_cb, pattern=r"^wdok_\d+$"))
    app.add_handler(CallbackQueryHandler(wd_no_cb, pattern=r"^wdno_\d+$"))
    app.add_handler(CallbackQueryHandler(dep_ok_cb, pattern=r"^depok_\d+$"))
    app.add_handler(CallbackQueryHandler(dep_no_cb, pattern=r"^depno_\d+$"))
    app.add_handler(CallbackQueryHandler(toggle_task_cb, pattern=r"^tgl_task_\d+$"))
    app.add_handler(CallbackQueryHandler(del_task_cb, pattern=r"^del_task_\d+$"))
    app.add_handler(CallbackQueryHandler(rmch_cb, pattern=r"^rmch_\d+$"))
    app.add_handler(CallbackQueryHandler(rmpay_cb, pattern=r"^rmpay_\d+$"))
    app.add_handler(CallbackQueryHandler(up_ok_cb, pattern=r"^upok_\d+$"))
    app.add_handler(CallbackQueryHandler(up_no_cb, pattern=r"^upno_\d+$"))
    app.add_handler(CallbackQueryHandler(tog_verify_cb, pattern=r"^tog_v"))

    for h in [
        proof_conv, wd_conv, dep_conv, post_conv, bal_conv, task_create_conv,
        ch_conv, pay_conv, ref_conv, post_cost_conv, settings_conv,
        broadcast_conv, add_admin_conv, rm_admin_conv, transfer_conv,
    ]:
        app.add_handler(h)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Earn Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
