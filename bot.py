import os
import json
import asyncio
import aiohttp
import time
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# ============================================
# CONFIG
# ============================================

BOT_TOKEN = "7859523030:AAGXSdbSYd2W9FXIc4KsW3FDtIRY9tb8O44"  # <-- Yangi token qo'ying!
ADMIN_IDS = [7607916773]
DB_FILE = "database.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ============================================
# JSON DATABASE
# ============================================

def load_db():
    if not os.path.exists(DB_FILE):
        data = {"stats": [], "admins": ADMIN_IDS}
        with open(DB_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return data
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_query_stat(user_id, server):
    db = load_db()
    db["stats"].append({
        "user_id": user_id,
        "server": server,
        "ts": int(datetime.now().timestamp())
    })
    save_db(db)

def get_basic_stats():
    db = load_db()
    users = len(set([x["user_id"] for x in db["stats"]]))
    servers = len(set([x["server"] for x in db["stats"]]))
    queries = len(db["stats"])
    return {"users": users, "servers": servers, "queries": queries}

# ============================================
# SERVER INFO API
# ============================================

async def fetch_server_info(ip: str):
    url = f"https://api.mcsrvstat.us/2/{ip}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
        except:
            return None

# ============================================
# GROUP REPLY FUNCTION
# ============================================

async def reply(message: types.Message, text: str, **kwargs):
    if message.chat.type in ["group", "supergroup"]:
        return await message.reply(text, **kwargs)
    else:
        return await message.answer(text, **kwargs)

# ============================================
# COMMAND: /start
# ============================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    username = message.from_user.username or message.from_user.first_name
    text = (
        f"👋 Assalomu alaykum, {username}!\n\n"
        "✅ Siz ushbu bot orqali Minecraft server statistikasi haqida bilib olishingiz mumkin!\n\n"
        "🚀 Server statistikasini bilish uchun shunchaki botga server manzilini yuboring!\n\n"
        "⁉️ Bot haqida ko'proq bilish uchun /help buyrug'ini yuboring!"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🤝 Guruhga qo‘shish", url="https://t.me/MCISUZBOT?startgroup=on")]]
    )
    await reply(message, text, reply_markup=kb)

# ============================================
# COMMAND: /help
# ============================================

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "🟩 Minecraft Server Status yordam:\n\n"
        "🔹 /s <ip> — to‘liq status\n"
        "🔹 /p <ip> — o‘yinchilar ro‘yxati\n"
        "🔹 /v <ip> — server versiyasi\n"
        "🔹 /top — eng ko‘p tekshirilgan serverlar TOP 10\n"
        "🔹 /stats — bot statistikasi\n"
        "🔹 Shunchaki server IP yuboring — avtomatik status chiqadi"
    )
    await reply(message, text)

# ============================================
# COMMAND: /stats
# ============================================

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    s = get_basic_stats()
    now = datetime.now()
    text = (
        f"📊 Bot statistikasi:\n"
        f"👥 Foydalanuvchilar: {s['users']}\n"
        f"🖥 Serverlar: {s['servers']}\n"
        f"🔍 Tekshiruvlar: {s['queries']}\n"
        f"📆 Sana: {now.strftime('%d/%m/%Y %H:%M:%S')}"
    )
    await reply(message, text)

# ============================================
# SERVER STATUS RESPONSE
# ============================================

async def send_server_status(message: types.Message, ip: str, mode: str):
    data = await fetch_server_info(ip)
    add_query_stat(message.from_user.id, ip)

    if not data or not data.get("online", False):
        await reply(message, f"❌ {ip} offline yoki topilmadi!")
        return

    online_count = data.get("players", {}).get("online", 0)
    max_players = data.get("players", {}).get("max", "?")
    version = data.get("version", "Noma'lum")
    motd = "\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum"
    ping = data.get("debug", {}).get("ping", "-")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📄Ko'proq Ma'lumot", callback_data=f"more::{ip}")]]
    )

    if mode == "s":
        await reply(message,
            f"📊 {ip} statusi:\n"
            f"🟢 Online\n"
            f"👥 O'yinchilar: {online_count}/{max_players}\n"
            f"⚙️ Versiya: {version}\n"
            f"💬 MOTD:\n{motd}\n"
            f"⏱️ Ping: {ping}",
            reply_markup=kb
        )

    elif mode == "v":
        await reply(message, f"⚙️ Versiya: {version}\n⏱️ Ping: {ping}", reply_markup=kb)

    elif mode == "p":
        players = data.get("players", {}).get("list", [])
        await reply(message,
            f"👥 O'yinchilar: {online_count}/{max_players}\n"
            f"📄 Ro‘yxat: {', '.join(players) if players else 'Yo‘q'}",
            reply_markup=kb
        )

# ============================================
# COMMANDS WITH FIXED SAFE SPLIT
# ============================================

def get_ip_safe(message: types.Message):
    parts = message.text.split(" ", 1)
    return parts[1].strip() if len(parts) > 1 else None

@dp.message(Command("s"))
async def cmd_s(message: types.Message):
    ip = get_ip_safe(message)
    if not ip:
        return await reply(message, "❗️ Format: /s <server ip>")
    await send_server_status(message, ip, "s")

@dp.message(Command("v"))
async def cmd_v(message: types.Message):
    ip = get_ip_safe(message)
    if not ip:
        return await reply(message, "❗️ Format: /v <server ip>")
    await send_server_status(message, ip, "v")

@dp.message(Command("p"))
async def cmd_p(message: types.Message):
    ip = get_ip_safe(message)
    if not ip:
        return await reply(message, "❗️ Format: /p <server ip>")
    await send_server_status(message, ip, "p")

# ============================================
# COMMAND: /top
# ============================================

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    db = load_db()
    servers = [x["server"] for x in db["stats"]]
    servers = [s for s in servers if not s.startswith("/")]

    if not servers:
        await reply(message, "❌ Hozircha serverlar yo'q")
        return

    server_counts = {}
    for s in servers:
        server_counts[s] = server_counts.get(s, 0) + 1

    top_servers = sorted(server_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    medals = ["🥇", "🥈", "🥉"] + ["🎖"] * 7

    text = "🏆 Eng ko'p ishlatilgan serverlar (TOP 10):\n\n"
    for idx, (srv, cnt) in enumerate(top_servers):
        text += f"{medals[idx]} │ {srv} | {cnt} marta\n"

    text += "\n🤖 Bot: Minecraft Server Status Uz (https://t.me/MCISUZBOT)"
    await reply(message, text)

# ============================================
# CALLBACK DATA: MORE INFO
# ============================================
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Markdown uchun qo'lda escape funksiyasi
def escape_markdown(text: str) -> str:
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in escape_chars else c for c in text)

@dp.callback_query(F.data.startswith("more::"))
async def show_more(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    data = await fetch_server_info(ip)

    if not data:
        return await call.answer("Xato.")

    motd = escape_markdown("\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum")
    players = data.get("players", {}).get("list", [])
    plugins_list = data.get("plugins", {}).get("names", [])
    port = data.get("port", "Noma'lum")
    version = data.get("version", "Noma'lum")
    online_count = data.get("players", {}).get("online", 0)
    max_players = data.get("players", {}).get("max", "?")
    ping = data.get("debug", {}).get("ping", "-")

    players_text = escape_markdown(", ".join(players) if players else "Yo‘q")
    plugins_text = escape_markdown("\n".join(plugins_list) if plugins_list else "Yo‘q")

    text = (
        f"📝 *Qo‘shimcha ma’lumot:*\n"
        f"📌 *Server:* {ip}:{port}\n"
        f"⚙️ *Versiya:* {version}\n"
        f"🟢 *Online:* {online_count}/{max_players}\n"
        f"⏱️ *Ping:* {ping}\n\n"
        f"💬 *MOTD:*\n{motd}\n\n"
        f"🧩 *Pluginlar:*\n{plugins_text}\n\n"
        f"👥 *O'yinchilar:* {players_text}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"more::{ip}")]]
    )

    # Avvalgi xabarni yangilash
    await call.message.edit_text(text, parse_mode="Markdown", reply_markup=kb)
    await call.answer()


# ============================================
# DEFAULT TEXT → SERVER IP
# ============================================

@dp.message(F.text)
async def handle_ip(message: types.Message):
    text = message.text.strip()

    if text.startswith("/"):
        return

    if "." not in text or " " in text:
        return  # Oddiy gap → javob bermaydi

    await send_server_status(message, text, "s")

# ============================================
# START BOT
# ============================================

async def main():
    print("BOT ISHLAYAPTI...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
