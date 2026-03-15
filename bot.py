import os
import json
import asyncio
import aiohttp
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest



BOT_TOKEN = "8581720787:AAGuPwSrySl-mQgSbOu4R9Ghx6opmSQOrdM"
ADMIN_ID = 7607916773

bot = Bot(token=BOT_TOKEN)

# ================= FSM STORAGE =================
storage = MemoryStorage()  # bu kerak
dp = Dispatcher(storage=storage)

DB_FILE = "db.json"

# ================= DATABASE =================
def load_db():
    if not os.path.exists(DB_FILE):
        data = {"users": {}, "premium_users": [], "stats": [], "groups": []}
        save_db(data)
        return data
    with open(DB_FILE) as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

def add_query_stat(user_id, server):
    db = load_db()
    db.setdefault("stats", [])
    db["stats"].append({"user": user_id, "server": server})
    save_db(db)

def get_top_servers():
    db = load_db()
    servers = [x["server"] for x in db["stats"]]
    counts = {}
    for s in servers:
        counts[s] = counts.get(s, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]

def is_premium(user_id):
    db = load_db()
    return str(user_id) in map(str, db.get("premium_users", []))

# ================= BROADCAST STATE =================
class BroadcastState(StatesGroup):
    waiting_for_message = State()

# ================= ADMIN PANEL =================
def admin_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yhati", callback_data="admin_users")],
            [InlineKeyboardButton(text="💎 Premium berish/olish", callback_data="admin_premium")],
            [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
            [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin_broadcast")],
        ]
    )

@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Siz admin emassiz!")
        return
    await message.reply("⚙️ Admin panelga xush kelibsiz:", reply_markup=admin_keyboard())

@dp.callback_query(F.data.startswith("admin_"))
async def handle_admin(call: types.CallbackQuery, state: FSMContext):
    db = load_db()
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    text = ""
    kb = admin_keyboard()

    if call.data == "admin_users":
        users = db.get("users", {})
        text = "👥 Foydalanuvchilar:\n" + "\n".join(
            [f"{i+1}. ID: {uid}, Til: {info.get('lang','uz')}" for i, (uid, info) in enumerate(users.items())]
        ) or "Foydalanuvchi yo‘q"

    elif call.data == "admin_premium":
        users = db.get("users", {})
        buttons = [
            [InlineKeyboardButton(
                text=f"{uid} - Premium ✅" if str(uid) in map(str, db.get("premium_users", [])) else f"{uid} - Free ❌",
                callback_data=f"toggle_premium::{uid}"
            )]
            for uid in users.keys()
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        text = "💎 Foydalanuvchilarga Premium berish/olish"

    elif call.data == "admin_stats":
        stats = db.get("stats", [])
        text = f"📊 Statistikalar:\nUmumiy so‘rovlar: {len(stats)}"

    elif call.data == "admin_broadcast":
        text = "📢 Iltimos, barcha foydalanuvchilarga yuboriladigan xabarni kiriting:"
        await call.message.edit_text(text, reply_markup=kb)
        # FSMga o'tish
        await state.set_state(BroadcastState.waiting_for_message)
        await call.answer()

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("✅ Yangilash muvaffaqiyatli")
        else:
            raise

# ================= BROADCAST HANDLER =================
@dp.message(BroadcastState.waiting_for_message)
async def handle_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Siz admin emassiz!")
        await state.clear()
        return

    db = load_db()
    users = db.get("users", {})
    groups = db.get("groups", [])

    success_users = failed_users = success_groups = failed_groups = 0

    # Foydalanuvchilarga yuborish
    for uid in users.keys():
        try:
            await bot.send_message(uid, f"📢 Admindan xabar:\n\n{message.text}")
            success_users += 1
        except:
            failed_users += 1

    # Guruhlarga yuborish
    for gid in groups:
        try:
            await bot.send_message(gid, f"📢 Admindan xabar:\n\n{message.text}")
            success_groups += 1
        except:
            failed_groups += 1

    await message.reply(
        f"✅ Foydalanuvchilarga yuborildi: {success_users}\n"
        f"❌ Foydalanuvchilarga yuborilmadi: {failed_users}\n"
        f"✅ Guruhlarga yuborildi: {success_groups}\n"
        f"❌ Guruhlarga yuborilmadi: {failed_groups}"
    )

    await state.clear()  # FSMni tozalash


    
# ================= PREMIUM TOGGLE =================
@dp.callback_query(F.data.startswith("toggle_premium::"))
async def toggle_premium(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        await call.answer("❌ Siz admin emassiz!", show_alert=True)
        return

    uid = call.data.split("::")[1]
    db = load_db()
    premium_users = db.get("premium_users", [])

    if uid in map(str, premium_users):
        premium_users = [x for x in premium_users if str(x) != str(uid)]
        await call.answer(f"❌ {uid} Premium bekor qilindi")
    else:
        premium_users.append(uid)
        await call.answer(f"✅ {uid} Premium berildi")

    db["premium_users"] = premium_users
    save_db(db)

    # Tugmalar yangilanishi
    users = db.get("users", {})
    buttons = [
        [InlineKeyboardButton(
            text=f"{u} - Premium ✅" if str(u) in map(str, premium_users) else f"{u} - Free ❌",
            callback_data=f"toggle_premium::{u}"
        )] for u in users.keys()
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("✅ Tugmalar yangilandi")
        else:
            raise




# ================= INLINE KEYBOARDS =================
def start_keyboard(user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 Top", callback_data="top"),
                InlineKeyboardButton(text="ℹ️ Info", callback_data="info")
            ],
            [
                InlineKeyboardButton(text="❓ Help", callback_data="help"),
                InlineKeyboardButton(text="🌐 Lang", callback_data="lang")
            ],
            [InlineKeyboardButton(text="💎 Premium", callback_data="premium")],
            [InlineKeyboardButton(text="🤝 Guruhga qo‘shish", url="https://t.me/mcveryBot?startgroup=on")]
        ]
    )

def lang_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🇺🇿 Uzbek", callback_data="lang_uz")],
            [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
            [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
        ]
    )

def premium_keyboard(user_id):
    tarif = "Premium" if is_premium(user_id) else "Free"
    narx = "25 000 so'm / 1 oy" if tarif == "Premium" else "25 000 so'm / 1 oy"
    buttons = [
        [InlineKeyboardButton(text="👥 Playerlarni ko‘rish", callback_data="premium_players")],
        [InlineKeyboardButton(text="💻 Server hosting nomi", callback_data="premium_hosting")],
        [InlineKeyboardButton(text="🔌 IP & Port", callback_data="premium_ip")],
        [InlineKeyboardButton(text="⚙️ Server imkoniyatlari", callback_data="premium_features")],
        [InlineKeyboardButton(text="🗺 Hosting sifati", callback_data="premium_quality")],
        [InlineKeyboardButton(text="📢 Rasmiy kanal", callback_data="premium_channel")],
        [InlineKeyboardButton(text="🌐 Sayt", callback_data="premium_site")],
        [InlineKeyboardButton(text="🚀 Bot tezligi x2", callback_data="premium_speed")],
        [InlineKeyboardButton(text="🔧 Qo‘shimcha 10+ imkoniyatlar", callback_data="premium_more")]
    ]
    if tarif == "Free":
        buttons.append([InlineKeyboardButton(text="💎 Obuna sotib olish", url="https://t.me/QahramonovK")])
    return InlineKeyboardMarkup(inline_keyboard=buttons), tarif, narx

@dp.callback_query(F.data.startswith("premium_"))
async def handle_premium_buttons(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if not is_premium(uid):
        await call.answer("❌ Bu xususiyat faqat Premium foydalanuvchilar uchun. Obuna sotib oling!", show_alert=True)
        return

    data = call.data
    await call.message.answer("💬 Server IP manzilini kiriting:")

    # Bu handler keyingi xabarni kutadi va IP ga qarab javob beradi
    @dp.message(F.text)
    async def handle_server_ip(message: types.Message):
        server_ip = message.text.strip()
        info = await fetch_server_info(server_ip)
        if not info:
            await message.reply("❌ Server topilmadi yoki offline!")
            return

        if data == "premium_players":
            players = info.get("players", {})
            online_count = players.get("online", 0)
            max_players = players.get("max", "?")
            players_list = players.get("list", [])
            text = f"👥 O'yinchilar: {online_count}/{max_players}\n"
            text += "Ro'yhat: " + (", ".join(players_list) if players_list else "Yo‘q")
            await message.reply(text)

        elif data == "premium_features":
            hosting = info.get("host", "Noma'lum")
            ram = info.get("ram", "Noma'lum")      # API da bo'lsa
            cpu = info.get("cpu", "Noma'lum")      # API da bo'lsa
            disk = info.get("disk", "Noma'lum")    # API da bo'lsa
            uptime = info.get("uptime", "Noma'lum")
            text = f"💻 Server imkoniyatlari:\nHosting: {hosting}\nRAM: {ram}\nCPU: {cpu}\nDisk: {disk}\nUptime: {uptime}"
            await message.reply(text)

        elif data == "premium_site":
            site = info.get("website", "Yo‘q")
            await message.reply(f"🌐 Rasmiy sayt: {site}")

        elif data == "premium_channel":
            channel = info.get("official_channel", "Yo‘q")
            await message.reply(f"📢 Rasmiy kanal: {channel}")

        elif data == "premium_ip":
            ip = info.get("ip", server_ip)
            port = info.get("port", "Unknown")
            await message.reply(f"🔌 IP & Port: {ip}:{port}")

        elif data == "premium_hosting":
            hosting = info.get("host", "Noma'lum")
            await message.reply(f"💻 Server hosting: {hosting}")

        elif data == "premium_speed":
            await message.reply("🚀 Bot tezligi x2 ishlaydi!")  # misol uchun

        elif data == "premium_more":
            # Qo‘shimcha 10+ xususiyatlarni o‘yladim
            text = (
                "🔧 Qo‘shimcha xususiyatlar:\n"
                "1. Max o'yinchi soni\n"
                "2. Server location\n"
                "3. Server mods\n"
                "4. World size\n"
                "5. Online time\n"
                "6. Backup status\n"
                "7. Server software\n"
                "8. Plugin list\n"
                "9. Server latency\n"
                "10. Active events\n"
                "11. Maintenance info\n"
                "12. Server owner\n"
            )
            await message.reply(text)

    await call.answer()



# ================= START =================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = str(message.from_user.id)
    db = load_db()
    db.setdefault("users", {})
    if uid not in db["users"]:
        db["users"][uid] = {"lang": "uz"}
        save_db(db)
    username = message.from_user.username or message.from_user.first_name
    text = f"👋 Assalomu alaykum, {username}!\n\n✅ Siz ushbu bot orqali Minecraft server statistikasi va yangiliklarni bilib olishingiz mumkin!\n\n🚀 Server statistikasini bilish uchun botga server manzilini yuboring!\n\n⁉️ Ko‘proq bilish uchun tugmalardan foydalaning!"
    await message.answer(text, reply_markup=start_keyboard(uid))

# ================= CALLBACKS =================
@dp.callback_query(F.data=="help")
async def help_menu(call: types.CallbackQuery):
    text = "❓ Bot qo'llanma\n\nServer domen/IP yuboring va statistikani ko‘ring.\nTo‘liq imkoniyatlar uchun Premium obuna oling."
    await call.message.edit_text(text, reply_markup=start_keyboard(call.from_user.id))

@dp.callback_query(F.data=="info")
async def info_menu(call: types.CallbackQuery):
    text = "ℹ️ Minecraft server monitoring bot.\nServer online, players, ping va boshqa ma’lumotlarni tekshiradi."
    if call.from_user.id == ADMIN_ID:
        text += "\n⚙️ Beta versiya"
    await call.message.edit_text(text, reply_markup=start_keyboard(call.from_user.id))

@dp.callback_query(F.data=="top")
async def top_menu(call: types.CallbackQuery):
    top = get_top_servers()
    if not top:
        text = "❌ Hozircha serverlar yo'q"
    else:
        text = "🏆 Eng ko'p tekshirilgan serverlar:\n" + "\n".join(f"{i+1}. {srv} — {cnt} marta" for i, (srv, cnt) in enumerate(top))
    await call.message.edit_text(text, reply_markup=start_keyboard(call.from_user.id))

@dp.callback_query(F.data=="premium")
async def premium_menu(call: types.CallbackQuery):
    kb, tarif, narx = premium_keyboard(call.from_user.id)
    await call.message.edit_text(f"💎 Premium bo‘lim\n\nSizning tarifingiz: {tarif}\nNarxi: {narx}", reply_markup=kb)

@dp.callback_query(F.data=="lang")
async def choose_lang(call: types.CallbackQuery):
    await call.message.edit_text("🌐 Tilni tanlang", reply_markup=lang_keyboard())

@dp.callback_query(F.data.startswith("lang_"))
async def set_lang(call: types.CallbackQuery):
    lang = call.data.split("_")[1]
    db = load_db()
    uid = str(call.from_user.id)
    db.setdefault("users", {})
    db["users"].setdefault(uid, {})["lang"] = lang
    save_db(db)
    await call.answer("Til o'zgartirildi ✅")
    await call.message.edit_text("✅ Til saqlandi", reply_markup=start_keyboard(call.from_user.id))


# ================= DOMEN / IP CHECK =================
DOMAIN_REGEX = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")  # misol: minestax.uz
IP_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")  # misol: 123.45.67.89




# ================= SERVER =================
async def fetch_server_info(ip: str):
    url = f"https://api.mcsrvstat.us/2/{ip}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                return await resp.json()
        except:
            return None

async def send_server_status(message: types.Message, ip: str, mode: str):
    if "." not in ip:
        await message.reply("❌ Faqat domen qabul qilinadi!")
        return

    data = await fetch_server_info(ip)
    add_query_stat(str(message.from_user.id), ip)

    if not data:
        await message.reply(f"❌ {ip} offline yoki topilmadi!")
        return

    online = data.get("online", False)
    players = data.get("players", {})
    online_count = players.get("online", 0)
    max_players = players.get("max", "?")
    version = data.get("version", "Noma'lum")
    motd = "\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum"
    uid = str(message.from_user.id)
    tarif = "Premium" if is_premium(uid) else "Free"

    text = f"📊 {ip} server statistikasi:\n🟢 Status: {'Online ✅' if online else 'Offline ❌'}\n👥 O'yinchilar: {online_count}/{max_players}\n⚙️ Versiya: {version}\n💬 MOTD: {motd}\n🌟 Tarif: {tarif}"

    if is_premium(uid):
        plugins = ", ".join(data.get("plugins", {}).get("names", [])) or "Yo‘q"
        software = data.get("software", "Noma'lum")
        hosting = data.get("host", "Noma'lum")
        text += f"\n🧩 Pluginlar: {plugins}\n🧪 Software: {software}\n💻 Hosting: {hosting}"

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📄 Qo'shimcha ma'lumot", callback_data=f"more::{ip}")]])
    await message.reply(text, reply_markup=kb)
# ================= CALLBACK MORE =================
@dp.callback_query(F.data.startswith("more::"))
async def more_info(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    data = await fetch_server_info(ip)
    if not data:
        await call.answer("❌ Server topilmadi")
        return

    uid = str(call.from_user.id)
    premium = is_premium(uid)

    # Asosiy ma'lumotlar
    motd = "\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum"
    players_list = data.get("players", {}).get("list", [])
    online_count = data.get("players", {}).get("online", 0)
    max_players = data.get("players", {}).get("max", "?")
    version = data.get("version", "Noma'lum")
    ping = data.get("ping", "Noma'lum")
    online_time = data.get("online", False)
    tarif = "Premium" if premium else "Free"

    # Qo‘shimcha ma'lumot matni
    text = (
        f"📌 {ip} qo‘shimcha ma'lumot:\n"
        f"💬 MOTD:\n{motd}\n"
        f"👥 O'yinchilar: {online_count}/{max_players} ({', '.join(players_list) if players_list else 'Yo‘q'})\n"
        f"⚙️ Versiya: {version}\n"
        f"🔘 Ping: {ping} ms\n"
        f"🗂 Status: {'Online ✅' if online_time else 'Offline ❌'}\n"
        f"🌟 Tarif: {tarif}"
    )

    if premium:
        plugins = ", ".join(data.get("plugins", {}).get("names", [])) or "Yo‘q"
        software = data.get("software", "Noma'lum")
        hosting = data.get("host", "Noma'lum")
        text += f"\n🧩 Pluginlar: {plugins}\n🧪 Software: {software}\n💻 Hosting: {hosting}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"refresh::{ip}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back::{ip}")]
        ]
    )

    # Telegram “message not modified” xatosini oldini olish
    if call.message.text != text or call.message.reply_markup != kb:
        await call.message.edit_text(text, reply_markup=kb)
    else:
        await call.answer("✅ Yangilash muvaffaqiyatli")
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= CALLBACK MORE =================
@dp.callback_query(F.data.startswith("more::"))
async def more_info(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    data = await fetch_server_info(ip)
    if not data:
        await call.answer("❌ Server topilmadi")
        return

    uid = str(call.from_user.id)
    premium = is_premium(uid)

    motd = "\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum"
    players_list = data.get("players", {}).get("list", [])
    online_count = data.get("players", {}).get("online", 0)
    max_players = data.get("players", {}).get("max", "?")
    version = data.get("version", "Noma'lum")
    ping = data.get("ping", "Noma'lum")
    online_time = data.get("online", False)
    tarif = "Premium" if premium else "Free"

    text = (
        f"📌 {ip} qo‘shimcha ma'lumot:\n"
        f"💬 MOTD:\n{motd}\n"
        f"👥 O'yinchilar: {online_count}/{max_players} ({', '.join(players_list) if players_list else 'Yo‘q'})\n"
        f"⚙️ Versiya: {version}\n"
        f"🔘 Ping: {ping} ms\n"
        f"🗂 Status: {'Online ✅' if online_time else 'Offline ❌'}\n"
        f"🌟 Tarif: {tarif}"
    )

    if premium:
        plugins = ", ".join(data.get("plugins", {}).get("names", [])) or "Yo‘q"
        software = data.get("software", "Noma'lum")
        hosting = data.get("host", "Noma'lum")
        text += f"\n🧩 Pluginlar: {plugins}\n🧪 Software: {software}\n💻 Hosting: {hosting}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Yangilash", callback_data=f"refresh::{ip}")],
            [InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back::{ip}")]
        ]
    )

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("✅ Yangilash muvaffaqiyatli")
        else:
            raise

# ================= CALLBACK BACK =================
@dp.callback_query(F.data.startswith("back::"))
async def back_to_stats(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    data = await fetch_server_info(ip)
    if not data:
        await call.answer("❌ Server topilmadi")
        return

    uid = str(call.from_user.id)
    tarif = "Premium" if is_premium(uid) else "Free"

    online = data.get("online", False)
    players = data.get("players", {})
    online_count = players.get("online", 0)
    max_players = players.get("max", "?")
    version = data.get("version", "Noma'lum")
    motd = "\n".join(data.get("motd", {}).get("clean", [])) or "Noma'lum"

    text = (
        f"📊 {ip} server statistikasi:\n"
        f"🟢 Status: {'Online ✅' if online else 'Offline ❌'}\n"
        f"👥 O'yinchilar: {online_count}/{max_players}\n"
        f"⚙️ Versiya: {version}\n"
        f"💬 MOTD: {motd}\n"
        f"🌟 Tarif: {tarif}"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📄 Qo'shimcha ma'lumot", callback_data=f"more::{ip}")]]
    )

    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer("✅ Yangilash muvaffaqiyatli")
        else:
            raise

# ================= CALLBACK REFRESH =================
@dp.callback_query(F.data.startswith("refresh::"))
async def refresh_info(call: types.CallbackQuery):
    await more_info(call)


# ================= DEFAULT HANDLER =================
@dp.message(F.text)
async def handle_text(message: types.Message):
    text = message.text.strip()
    
    # Buyruqlarni o'tkazib yuborish
    if text.startswith("/") or text.lower() in ["help","start","top","info","premium","lang"]:
        return
    
    # Faqat haqiqiy domen yoki IP bo‘lsa serverni tekshiradi
    if DOMAIN_REGEX.match(text) or IP_REGEX.match(text):
        await send_server_status(message, text)
    else:
        # Noto'g'ri domen yoki oddiy matn bo‘lsa hech narsa yubormaydi

        return

# ================= RUN BOT =================
async def main():
    print("BOT STARTED")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
