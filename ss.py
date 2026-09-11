#!/usr/bin/env python3
"""
Earn Bot — UI matched to design screenshots
Main Admin: 8289191009

User Panel:
  Balance | Tasks | Profile | Referral | Withdraw | Deposit
  Post Task | History | Support

Admin Panel:
  Users | Statistics | Add/Remove Balance | Tasks | Submissions
  Withdrawals | Deposits | Channels | Payment Methods
  Referral Settings | Settings | Maintenance ON/OFF | Withdraw ON/OFF
  User Panel
"""

import logging
import sqlite3
import random
from datetime import datetime
from typing import Optional, List

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
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
from telegram.constants import ParseMode, ChatMemberStatus

# ================== CONFIG ==================
BOT_TOKEN = "8954125751:AAHAZ6HH2W6cZYf4e9Yr9ubvYGckWFVI0QI"
MAIN_ADMIN_ID = 8289191009
DB_NAME = "earn_bot.db"

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
    BALANCE_UID,
    BALANCE_AMT,
    BLOCK_UID,
    WD_AMOUNT,
    WD_METHOD,
    DEP_AMOUNT,
    DEP_PROOF,
    POST_TASK_TITLE,
    POST_TASK_DESC,
    POST_TASK_REWARD,
    PAY_METHOD_NAME,
    PAY_METHOD_INFO,
) = range(24)

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
            joined_at TEXT,
            last_active TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY,
            role TEXT DEFAULT 'admin',
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

    defaults = {
        "min_withdraw": "100",
        "referral_bonus": "10",
        "support_username": "",
        "maintenance": "0",
        "withdraw_enabled": "1",
        "welcome_text": "🎉 স্বাগতম! আমাদের প্রিমিয়াম বটে।\nনিচের বাটনগুলো ব্যবহার করুন।",
    }
    for k, v in defaults.items():
        cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

    cur.execute(
        "INSERT OR IGNORE INTO admins (user_id, role, added_at) VALUES (?, 'main', ?)",
        (MAIN_ADMIN_ID, datetime.now().isoformat()),
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
            cur.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (bonus, referrer_id))
            cur.execute(
                "INSERT INTO history (user_id, kind, amount, note, created_at) VALUES (?,?,?,?,?)",
                (referrer_id, "referral", bonus, f"ref from {uid}", datetime.now().isoformat()),
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


# ================== KEYBOARDS (design match) ==================
def user_keyboard(show_admin: bool = False):
    rows = [
        ["💰 Balance", "📋 Tasks"],
        ["👤 Profile", "👥 Referral"],
        ["💸 Withdraw", "💳 Deposit"],
        ["➕ Post Task", "📜 History"],
        ["🆘 Support"],
    ]
    if show_admin:
        rows.append(["🔧 Admin Panel"])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["👥 Users", "📊 Statistics"],
            ["➕ Add Balance", "➖ Remove Balance"],
            ["📋 Manage Tasks", "📥 Submissions"],
            ["💸 Withdrawals", "💳 Deposits"],
            ["📢 Channels", "💳 Payment Methods"],
            ["🎁 Referral Settings", "⚙️ Settings"],
            ["🔧 Maintenance ON/OFF", "💸 Withdraw ON/OFF"],
            ["🏠 User Panel"],
        ],
        resize_keyboard=True,
    )


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
            logger.warning(f"member check {cid}: {e}")
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
            buttons.append([InlineKeyboardButton(f"🔗 {ch['title'] or ch['chat_id']}", url=link)])
    buttons.append([InlineKeyboardButton("✅ আমি জয়েন করেছি", callback_data="check_join")])
    text = "⚠️ প্রথমে নিচের চ্যানেলগুলোতে জয়েন করুন, তারপর ✅ চাপুন।"
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
    await q.answer("চেক হচ্ছে...")
    user = q.from_user
    channels = get_channels()
    missing = []
    for ch in channels:
        if not await _member_ok(context.bot, ch["chat_id"], user.id):
            missing.append(ch)
    if missing:
        buttons = []
        for ch in missing:
            link = ch["invite_link"]
            if link:
                buttons.append([InlineKeyboardButton(f"🔗 {ch['title'] or ch['chat_id']}", url=link)])
        buttons.append([InlineKeyboardButton("✅ আমি জয়েন করেছি", callback_data="check_join")])
        await q.edit_message_text(
            "⚠️ এখনো সব চ্যানেলে জয়েন হয়নি। আবার চেষ্টা করুন।",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return
    try:
        await q.edit_message_text("✅ জয়েন ভেরিফাইড! এখন বট ব্যবহার করুন।")
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
        await update.message.reply_text("আপনি ব্লক করা আছেন।")
        return
    if get_setting("maintenance", "0") == "1" and not is_admin(user.id):
        await update.message.reply_text("🔧 বট Maintenance মোডে আছে। পরে আসুন।")
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

    await update.message.reply_text(
        get_setting("welcome_text", "🎉 স্বাগতম!"),
        reply_markup=user_keyboard(show_admin=is_admin(user.id)),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    uid = update.effective_user.id
    kb = admin_keyboard() if context.user_data.get("in_admin") else user_keyboard(is_admin(uid))
    # default user panel
    await update.message.reply_text(
        "বাতিল।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    return ConversationHandler.END


# ================== USER: BALANCE / PROFILE ==================
async def cmd_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    pts = u["points"] if u else 0
    await update.message.reply_text(f"💰 <b>Balance:</b> {pts} পয়েন্ট", parse_mode=ParseMode.HTML)


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
        f"👥 Referral: {refs} জন\n"
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
        f"👥 <b>Referral</b>\n\n"
        f"লিংক:\n<code>{link}</code>\n\n"
        f"বোনাস: {bonus} পয়েন্ট / রেফার\n"
        f"মোট রেফার: {cnt} জন",
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
        await update.message.reply_text("সাপোর্ট এখনো সেট নেই।")
        return
    await update.message.reply_text(
        "🆘 Support",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("💬 মেসেজ করুন", url=f"https://t.me/{un}")]]
        ),
    )


# ================== TASKS ==================
async def cmd_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_blocked(uid):
        return
    if not await check_force_join(update, context):
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
        await update.message.reply_text("📋 এখন নতুন টাস্ক নেই।")
        return
    buttons = [
        [InlineKeyboardButton(f"📋 {t['title']} (+{t['reward_points']})", callback_data=f"task_{t['id']}")]
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
        f"রিওয়ার্ড: <b>+{t['reward_points']}</b> পয়েন্ট\n\n"
        f"নির্দেশনা:\n{t['description']}\n\n"
        f"কাজ শেষে স্ক্রিনশট + ভিডিও প্রুফ লাগবে।"
    )
    buttons = []
    if t["task_link"]:
        buttons.append([InlineKeyboardButton("🔗 লিংকে যান", url=t["task_link"])])
    buttons.append([InlineKeyboardButton("✅ কাজ করেছি · প্রুফ দিন", callback_data=f"proof_{tid}")])
    await q.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


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
        await q.edit_message_text("এই টাস্ক আগেই সাবমিট করা হয়েছে।")
        return ConversationHandler.END
    conn.close()
    context.user_data["task_id"] = tid
    await q.edit_message_text("📷 স্ক্রিনশট পাঠান (একটি ছবি)।")
    return WAIT_PHOTO


async def proof_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("শুধু ছবি পাঠান।")
        return WAIT_PHOTO
    context.user_data["photo"] = update.message.photo[-1].file_id
    await update.message.reply_text("✅ স্ক্রিনশট OK।\nএখন ভিডিও প্রুফ পাঠান।")
    return WAIT_VIDEO


async def proof_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.video:
        await update.message.reply_text("শুধু ভিডিও পাঠান।")
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
        "✅ প্রুফ সাবমিট হয়েছে! অ্যাডমিন রিভিউ করে পয়েন্ট দিবে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ================== WITHDRAW / DEPOSIT ==================
async def withdraw_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if get_setting("withdraw_enabled", "1") != "1":
        await update.message.reply_text("💸 উইথড্র এখন বন্ধ আছে।")
        return ConversationHandler.END
    u = get_user(update.effective_user.id)
    min_w = float(get_setting("min_withdraw", "100"))
    pts = u["points"] if u else 0
    if pts < min_w:
        await update.message.reply_text(f"কমপক্ষে {min_w} পয়েন্ট লাগবে। আপনার: {pts}")
        return ConversationHandler.END
    await update.message.reply_text(
        f"আপনার ব্যালেন্স: {pts}\nকত উইথড্র করবেন? (মিন {min_w})",
        reply_markup=ReplyKeyboardRemove(),
    )
    return WD_AMOUNT


async def withdraw_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সঠিক সংখ্যা লিখুন।")
        return WD_AMOUNT
    u = get_user(update.effective_user.id)
    min_w = float(get_setting("min_withdraw", "100"))
    if amt < min_w or amt > u["points"]:
        await update.message.reply_text("অবৈধ পরিমাণ।")
        return WD_AMOUNT
    context.user_data["wd_amt"] = amt
    await update.message.reply_text(
        "পেমেন্ট মেথড ও ডিটেইলস লিখুন:\n"
        "উদাহরণ: Binance UID 123456\nবা bKash 01XXXXXXXXX"
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
        "✅ উইথড্র রিকোয়েস্ট পাঠানো হয়েছে। অ্যাডমিন প্রসেস করবে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    try:
        await context.bot.send_message(
            MAIN_ADMIN_ID,
            f"💸 Withdraw\nUser: `{uid}`\nAmount: {amt}\n{details}",
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
        text += "পেমেন্ট মেথড:\n"
        for m in methods:
            text += f"• <b>{m['name']}</b>\n{m['info']}\n\n"
    else:
        text += "পেমেন্ট মেথড সেট নেই। অ্যাডমিনকে বলুন।\n\n"
    text += "ডিপোজিটের পরিমাণ লিখুন (সংখ্যা):"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardRemove())
    return DEP_AMOUNT


async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amt = float(update.message.text.strip())
        if amt <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("সঠিক পরিমাণ লিখুন।")
        return DEP_AMOUNT
    context.user_data["dep_amt"] = amt
    await update.message.reply_text("পেমেন্ট প্রুফ (স্ক্রিনশট) পাঠান:")
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
        """INSERT INTO deposits (user_id,amount,proof_file_id,created_at)
           VALUES (?,?,?,?)""",
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
            caption=f"💳 Deposit\nUser: `{uid}`\nAmount: {amt}",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    context.user_data.clear()
    return ConversationHandler.END


# ================== USER POST TASK ==================
async def post_task_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "➕ Post Task\nটাস্কের টাইটেল লিখুন:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return POST_TASK_TITLE


async def post_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pt_title"] = update.message.text.strip()
    await update.message.reply_text("বিস্তারিত নির্দেশনা লিখুন:")
    return POST_TASK_DESC


async def post_task_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pt_desc"] = update.message.text.strip()
    await update.message.reply_text("রিওয়ার্ড পয়েন্ট (সংখ্যা):")
    return POST_TASK_REWARD


async def post_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        reward = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সঠিক সংখ্যা।")
        return POST_TASK_REWARD
    uid = update.effective_user.id
    # user posts go pending as inactive until admin activates — or active with is_user_post
    conn = get_db()
    cur = conn.cursor()
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
    await update.message.reply_text(
        "✅ টাস্ক সাবমিট হয়েছে। অ্যাডমিন অ্যাপ্রুভ করলে লাইভে যাবে।",
        reply_markup=user_keyboard(show_admin=is_admin(uid)),
    )
    try:
        await context.bot.send_message(
            MAIN_ADMIN_ID,
            f"➕ User Post Task\nFrom: `{uid}`\n{context.user_data['pt_title']}\nReward: {reward}",
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
    await update.message.reply_text("🔧 Admin Panel", reply_markup=admin_keyboard())


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
    text = f"👥 <b>Users</b> (total {total})\n\n"
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
    cur.execute("SELECT COALESCE(SUM(points),0) s FROM users")
    pts = cur.fetchone()["s"]
    conn.close()
    await update.message.reply_text(
        f"📊 <b>Statistics</b>\n\n"
        f"👥 Users: {users}\n"
        f"📋 Active Tasks: {tasks}\n"
        f"📥 Pending Submissions: {subs}\n"
        f"💸 Pending Withdrawals: {wds}\n"
        f"💳 Pending Deposits: {deps}\n"
        f"💰 Total Points in system: {pts}",
        parse_mode=ParseMode.HTML,
    )


async def balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return ConversationHandler.END
    op = "add" if "Add" in (update.message.text or "") else "remove"
    context.user_data["bal_op"] = op
    await update.message.reply_text(
        "User ID পাঠান:", reply_markup=ReplyKeyboardRemove()
    )
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
    await update.message.reply_text(f"বর্তমান: {u['points']}\nপরিমাণ লিখুন:")
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
    conn = get_db()
    cur = conn.cursor()
    if op == "remove":
        cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
        p = cur.fetchone()["points"]
        if p < amt:
            conn.close()
            await update.message.reply_text(f"পর্যাপ্ত নেই। আছে: {p}", reply_markup=admin_keyboard())
            context.user_data.clear()
            return ConversationHandler.END
        cur.execute("UPDATE users SET points = points - ? WHERE user_id=?", (amt, uid))
        # no notify on remove
        add_history(uid, "admin_remove", -amt, "admin")
        msg = f"✅ {amt} কাটা হয়েছে।"
    else:
        cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amt, uid))
        add_history(uid, "admin_add", amt, "admin")
        msg = f"✅ {amt} অ্যাড হয়েছে।"
        try:
            await context.bot.send_message(uid, f"🎉 অ্যাডমিন {amt} পয়েন্ট দিয়েছেন।")
        except Exception:
            pass
    cur.execute("SELECT points FROM users WHERE user_id=?", (uid,))
    new_p = cur.fetchone()["points"]
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"{msg}\nUser `{uid}` → {new_p}",
        parse_mode=ParseMode.HTML,
        reply_markup=admin_keyboard(),
    )
    context.user_data.clear()
    return ConversationHandler.END


async def admin_tasks_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, title, reward_points, is_active, is_user_post FROM tasks ORDER BY id DESC LIMIT 20")
    rows = cur.fetchall()
    conn.close()
    buttons = [[InlineKeyboardButton("➕ নতুন টাস্ক", callback_data="admin_new_task")]]
    text = "📋 <b>Tasks</b>\n\n"
    for r in rows:
        st = "✅" if r["is_active"] else "⏸"
        up = "👤" if r["is_user_post"] else ""
        text += f"{st}{up} #{r['id']} {r['title']} (+{r['reward_points']})\n"
        buttons.append([
            InlineKeyboardButton(f"{'⏸' if r['is_active'] else '▶️'} #{r['id']}", callback_data=f"tgl_task_{r['id']}"),
            InlineKeyboardButton(f"🗑 #{r['id']}", callback_data=f"del_task_{r['id']}"),
        ])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def admin_new_task_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("টাস্ক টাইটেল লিখুন:")
    return CREATE_TASK_TITLE


async def admin_task_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task_title"] = update.message.text.strip()
    await update.message.reply_text("নির্দেশনা লিখুন (কাস্টমাইজ):")
    return CREATE_TASK_DESC


async def admin_task_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["task_desc"] = update.message.text.strip()
    await update.message.reply_text("রিওয়ার্ড পয়েন্ট:")
    return CREATE_TASK_REWARD


async def admin_task_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["task_reward"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("সংখ্যা লিখুন।")
        return CREATE_TASK_REWARD
    await update.message.reply_text("লিংক (না থাকলে /skip):")
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
    await update.message.reply_text("✅ টাস্ক তৈরি হয়েছে।", reply_markup=admin_keyboard())
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
    await q.edit_message_text(f"✅ টাস্ক #{tid} টগল হয়েছে।")


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
    await q.edit_message_text(f"🗑 টাস্ক #{tid} ডিলিট।")


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
        await update.message.reply_text("কোনো পেন্ডিং সাবমিশন নেই।")
        return
    for r in rows:
        cap = (
            f"🆔 {r['id']} | User `{r['user_id']}`\n"
            f"📋 {r['title']} | +{r['reward_points']}"
        )
        buttons = [[
            InlineKeyboardButton("✅", callback_data=f"appr_{r['id']}"),
            InlineKeyboardButton("❌", callback_data=f"rej_{r['id']}"),
        ]]
        try:
            if r["proof_photo"]:
                await context.bot.send_photo(
                    update.effective_chat.id, r["proof_photo"], caption=cap + "\n📷",
                    parse_mode=ParseMode.HTML,
                )
            if r["proof_video"]:
                await context.bot.send_video(
                    update.effective_chat.id, r["proof_video"], caption=cap + "\n🎬",
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=ParseMode.HTML,
                )
            elif r["proof_photo"]:
                await context.bot.send_message(
                    update.effective_chat.id, "↑ Approve/Reject:",
                    reply_markup=InlineKeyboardMarkup(buttons),
                )
        except Exception as e:
            await update.message.reply_text(f"Sub {r['id']} error: {e}")


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
        await q.edit_message_caption(caption="ইতিমধ্যে প্রসেসড।")
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
        await q.edit_message_caption(caption=f"✅ Approved +{s['reward_points']}")
    except Exception:
        await q.edit_message_text(f"✅ Approved +{s['reward_points']}")
    try:
        await context.bot.send_message(
            s["user_id"],
            f"🎉 টাস্ক অ্যাপ্রুভ! +{s['reward_points']} পয়েন্ট",
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
            await context.bot.send_message(row["user_id"], "টাস্ক রিজেক্ট হয়েছে।")
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
            f"💸 #{r['id']} User `{r['user_id']}`\n{r['amount']} — {r['details']}",
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
        await q.edit_message_text("ইতিমধ্যে প্রসেসড।")
        return
    cur.execute(
        "UPDATE withdraws SET status='done', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), wid),
    )
    conn.commit()
    conn.close()
    await q.edit_message_text(f"✅ Withdraw #{wid} done")
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
        await q.edit_message_text("ইতিমধ্যে প্রসেসড।")
        return
    cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (r["amount"], r["user_id"]))
    cur.execute(
        "UPDATE withdraws SET status='rejected', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), wid),
    )
    conn.commit()
    conn.close()
    add_history(r["user_id"], "withdraw_refund", r["amount"], f"wd #{wid}")
    await q.edit_message_text(f"❌ Withdraw #{wid} rejected + refund")
    try:
        await context.bot.send_message(r["user_id"], f"❌ উইথড্র রিজেক্ট। {r['amount']} ফেরত।")
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
            InlineKeyboardButton("✅ Approve", callback_data=f"depok_{r['id']}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"depno_{r['id']}"),
        ]]
        try:
            await context.bot.send_photo(
                update.effective_chat.id,
                r["proof_file_id"],
                caption=f"💳 #{r['id']} User `{r['user_id']}` Amount: {r['amount']}",
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
    cur.execute("UPDATE users SET points = points + ? WHERE user_id=?", (r["amount"], r["user_id"]))
    cur.execute(
        "UPDATE deposits SET status='approved', processed_at=? WHERE id=?",
        (datetime.now().isoformat(), did),
    )
    conn.commit()
    conn.close()
    add_history(r["user_id"], "deposit", r["amount"], f"dep #{did}")
    await q.edit_message_caption(caption=f"✅ Deposit approved +{r['amount']}")
    try:
        await context.bot.send_message(r["user_id"], f"✅ ডিপোজিট অ্যাপ্রুভ +{r['amount']}")
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
    await q.edit_message_caption(caption="❌ Deposit rejected")
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
        buttons.append([InlineKeyboardButton(f"🗑 {ch['title']}", callback_data=f"rmch_{ch['id']}")])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def add_ch_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text(
        "Chat ID বা @username পাঠান।\nপ্রাইভেট: -100...\nবটকে Admin বানান।"
    )
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
        await update.message.reply_text(f"✅ {title}", reply_markup=admin_keyboard())
        return ConversationHandler.END
    except Exception as e:
        if raw.lstrip("-").isdigit():
            context.user_data["mch_id"] = raw
            await update.message.reply_text(f"অটো পায়নি। টাইটেল লিখুন:\n({e})")
            return ADD_CHANNEL_TITLE
        await update.message.reply_text(f"Error: {e}\n/cancel")
        return ADD_CHANNEL


async def add_ch_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mch_title"] = update.message.text.strip()
    await update.message.reply_text("Invite link (/skip যদি না থাকে):")
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
    await update.message.reply_text(f"✅ Manual add: {title}", reply_markup=admin_keyboard())
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


# Payment methods
async def admin_pay_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM payment_methods")
    rows = cur.fetchall()
    conn.close()
    text = "💳 <b>Payment Methods</b>\n\n"
    buttons = [[InlineKeyboardButton("➕ Add", callback_data="add_pay")]]
    for r in rows:
        text += f"• {r['name']}: {r['info']}\n"
        buttons.append([InlineKeyboardButton(f"🗑 {r['name']}", callback_data=f"rmpay_{r['id']}")])
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def add_pay_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("মেথডের নাম (যেমন: bKash / Binance):")
    return PAY_METHOD_NAME


async def add_pay_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pay_name"] = update.message.text.strip()
    await update.message.reply_text("ডিটেইলস (নম্বর/UID ইত্যাদি):")
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
    await update.message.reply_text("✅ Payment method added.", reply_markup=admin_keyboard())
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


async def admin_ref_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cur_b = get_setting("referral_bonus", "10")
    await update.message.reply_text(
        f"🎁 বর্তমান রেফারেল বোনাস: {cur_b}\nনতুন মান লিখুন:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return SET_REF_BONUS


async def set_ref_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("referral_bonus", str(v))
        await update.message.reply_text(f"✅ Referral bonus = {v}", reply_markup=admin_keyboard())
    except ValueError:
        await update.message.reply_text("সংখ্যা লিখুন।")
        return SET_REF_BONUS
    return ConversationHandler.END


async def admin_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    text = (
        f"⚙️ <b>Settings</b>\n\n"
        f"Min withdraw: {get_setting('min_withdraw')}\n"
        f"Referral: {get_setting('referral_bonus')}\n"
        f"Support: @{get_setting('support_username') or '-'}\n"
        f"Maintenance: {get_setting('maintenance')}\n"
        f"Withdraw enabled: {get_setting('withdraw_enabled')}"
    )
    buttons = [
        [InlineKeyboardButton("Min Withdraw", callback_data="set_min_wd")],
        [InlineKeyboardButton("Support Username", callback_data="set_support")],
    ]
    await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))


async def set_min_wd_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("নতুন min withdraw লিখুন:")
    return SET_MIN_WD


async def set_min_wd_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        v = float(update.message.text.strip())
        set_setting("min_withdraw", str(v))
        await update.message.reply_text(f"✅ Min withdraw = {v}", reply_markup=admin_keyboard())
    except ValueError:
        await update.message.reply_text("সংখ্যা।")
        return SET_MIN_WD
    return ConversationHandler.END


async def set_support_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    await q.edit_message_text("Support username (@ ছাড়া):")
    return SET_SUPPORT


async def set_support_val(update: Update, context: ContextTypes.DEFAULT_TYPE):
    set_setting("support_username", update.message.text.strip().lstrip("@"))
    await update.message.reply_text("✅ Support set.", reply_markup=admin_keyboard())
    return ConversationHandler.END


async def toggle_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cur = get_setting("maintenance", "0")
    new = "0" if cur == "1" else "1"
    set_setting("maintenance", new)
    await update.message.reply_text(
        f"🔧 Maintenance → {'ON' if new == '1' else 'OFF'}",
        reply_markup=admin_keyboard(),
    )


async def toggle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    cur = get_setting("withdraw_enabled", "1")
    new = "0" if cur == "1" else "1"
    set_setting("withdraw_enabled", new)
    await update.message.reply_text(
        f"💸 Withdraw → {'ON' if new == '1' else 'OFF'}",
        reply_markup=admin_keyboard(),
    )


# ================== TEXT ROUTER ==================
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    uid = update.effective_user.id

    if is_blocked(uid):
        await update.message.reply_text("ব্লক করা আছেন।")
        return
    if get_setting("maintenance", "0") == "1" and not is_admin(uid):
        await update.message.reply_text("🔧 Maintenance মোড।")
        return

    # User
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
    elif text == "🔧 Admin Panel" and is_admin(uid):
        await admin_panel(update, context)
    elif text == "🏠 User Panel":
        await update.message.reply_text(
            "User Panel", reply_markup=user_keyboard(show_admin=is_admin(uid))
        )

    # Admin
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
    elif text == "🔧 Maintenance ON/OFF" and is_admin(uid):
        await toggle_maintenance(update, context)
    elif text == "💸 Withdraw ON/OFF" and is_admin(uid):
        await toggle_withdraw(update, context)


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

    settings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(set_min_wd_cb, pattern="^set_min_wd$"),
            CallbackQueryHandler(set_support_cb, pattern="^set_support$"),
        ],
        states={
            SET_MIN_WD: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_min_wd_val)],
            SET_SUPPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_support_val)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("cancel", cancel))

    app.add_handler(CallbackQueryHandler(check_join_cb, pattern="^check_join$"))
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

    app.add_handler(proof_conv)
    app.add_handler(wd_conv)
    app.add_handler(dep_conv)
    app.add_handler(post_conv)
    app.add_handler(bal_conv)
    app.add_handler(task_create_conv)
    app.add_handler(ch_conv)
    app.add_handler(pay_conv)
    app.add_handler(ref_conv)
    app.add_handler(settings_conv)

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Earn Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
