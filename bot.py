import os
import json
import time
import asyncio
import aiohttp
import re
import threading
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, MEMBER, LEFT, KICKED
from collections import defaultdict

# ================= CONFIG =================
# Token avval muhit o'zgaruvchisidan olinadi (xavfsizroq), topilmasa eskisi ishlatiladi
BOT_TOKEN = os.getenv("BOT_TOKEN", "8581720787:AAGuPwSrySl-mQgSbOu4R9Ghx6opmSQOrdM")
ADMIN_IDS = [7607916773]  # Ko'p admin qo'shish mumkin
PREMIUM_CONTACT = "https://t.me/QahramonovK"
BOT_USERNAME = "mcveryBot"
CREATOR = "@QahramonovK"

# ---- Yangi: kesh, spam-himoya sozlamalari ----
SERVER_CACHE = {}           # {ip: {"data":..., "time": unix_ts}}
CACHE_TTL_SECONDS = 20       # shu vaqt ichida bir xil IP qayta so'ralmaydi
USER_COOLDOWN = {}           # {user_id: last_request_unix_ts}
COOLDOWN_SECONDS = 3          # bitta foydalanuvchi ketma-ket so'rov oralig'i
MAX_STATS_ENTRIES = 3000     # "stats" jurnali cheksiz o'smasligi uchun chegara
DB_LOCK = threading.Lock()   # db.json fayli bir vaqtda buzilmasligi uchun

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

DB_FILE = "db.json"

# Telegram Premium Emoji IDs
EMOJI = {
    "diamond": "⭐",      # Premium emoji placeholder
    "online": "🟢",
    "offline": "🔴",
    "crown": "👑",
    "fire": "🔥",
    "star": "⭐",
    "zap": "⚡",
    "shield": "🛡",
    "server": "🖥",
    "players": "👥",
    "ping": "📡",
    "version": "⚙️",
    "motd": "💬",
    "plugin": "🧩",
    "software": "🧪",
    "hosting": "🌐",
    "map": "🗺",
    "chart": "📊",
    "trophy": "🏆",
    "gem": "💎",
    "rocket": "🚀",
}

# ================= TRANSLATIONS =================
TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum, <b>{name}</b>!\n\n"
            "🖥 <b>Minecraft Server Monitor Bot</b>\n\n"
            "📡 Istalgan Minecraft serverining to'liq statistikasini real vaqtda bilib oling!\n\n"
            "🔍 <b>Qanday foydalanish:</b>\n"
            "▫️ Server domen yoki IP manzilini yuboring\n"
            "▫️ Masalan: <code>play.hypixel.net</code>\n\n"
            "💎 <b>Premium</b> bilan ko'proq ma'lumot!\n"
            "❓ Yordam: /help\n"
            "👨‍💻 Muallif: @QahramonovK"
        ),
        "help": (
            "❓ <b>Bot bo'yicha to'liq qo'llanma</b>\n\n"
            "🖥 <b>Server tekshirish:</b>\n"
            "▫️ Domen yoki IP yuboring: <code>play.hypixel.net</code>\n"
            "▫️ Port bilan: <code>server.com:25565</code>\n\n"
            "🆓 <b>Bepul imkoniyatlar:</b>\n"
            "▫️ Online/Offline holat\n"
            "▫️ O'yinchilar soni\n"
            "▫️ Server versiyasi\n"
            "▫️ MOTD (server nomi)\n\n"
            "💎 <b>Premium imkoniyatlar:</b>\n"
            "▫️ O'yinchilar ro'yxati\n"
            "▫️ Pluginlar va software\n"
            "▫️ Hosting ma'lumoti\n"
            "▫️ Ping tekshirish\n"
            "▫️ Server joylashuvi\n"
            "▫️ Kunlik statistika\n\n"
            "📌 <b>Buyruqlar:</b>\n"
            "/start — Bosh sahifa\n"
            "/help — Yordam\n"
            "/top — Top serverlar\n"
            "/stats — Bot statistikasi\n"
            "/lang — Til o'zgartirish\n"
            "/premium — Premium bo'lim\n\n"
            "👨‍💻 Muallif: @QahramonovK"
        ),
        "info": (
            "ℹ️ <b>Bot haqida</b>\n\n"
            "🤖 <b>Minecraft Server Monitor</b>\n"
            "📊 Serverlar holati, o'yinchilar, ping va ko'proq\n"
            "🌍 3 tilda ishlaydi: O'zbek | Русский | English\n"
            "⚡️ Real vaqt ma'lumotlari\n"
            "💎 Premium obuna bilan to'liq imkoniyatlar\n\n"
            "🔧 <b>Versiya:</b> 2.0.0\n"
            "👨‍💻 <b>Muallif:</b> @QahramonovK\n"
            "📅 <b>Yangilangan:</b> 2025"
        ),
        "top_empty": "❌ Hozircha hech qanday server tekshirilmagan",
        "top_title": "🏆 <b>Top 10 — Eng ko'p tekshirilgan serverlar:</b>\n\n",
        "premium_title": (
            "💎 <b>Premium Bo'lim</b>\n\n"
            "🌟 Sizning tarifingiz: <b>{tarif}</b>\n"
            "💰 Narxi: <b>25 000 so'm / 1 oy</b>\n\n"
            "✨ <b>Premium imkoniyatlari:</b>\n"
            "▫️ 👥 O'yinchilar ro'yxati\n"
            "▫️ 🧩 Pluginlar ro'yxati\n"
            "▫️ 💻 Hosting ma'lumoti\n"
            "▫️ 🔌 IP & Port\n"
            "▫️ 🧪 Server software\n"
            "▫️ 📡 Ping tekshirish\n"
            "▫️ 🗺 Server joylashuvi\n"
            "▫️ 📊 Kunlik statistika\n\n"
            "📩 Obuna olish: @QahramonovK"
        ),
        "lang_choose": "🌐 <b>Tilni tanlang</b>\nChoose language\nВыберите язык",
        "lang_saved": "✅ Til saqlandi!",
        "not_premium": (
            "💎 <b>Premium kerak!</b>\n\n"
            "Bu xususiyat faqat Premium foydalanuvchilar uchun.\n"
            "Obuna olish: @QahramonovK"
        ),
        "server_offline": "❌ <b>{ip}</b> — offline yoki topilmadi!\n\n⏱ Keyinroq qayta urinib ko'ring.",
        "server_invalid": (
            "❌ <b>Noto'g'ri format!</b>\n\n"
            "Faqat haqiqiy domen yoki IP manzil yuboring.\n\n"
            "✅ <b>To'g'ri misollar:</b>\n"
            "▫️ <code>play.hypixel.net</code>\n"
            "▫️ <code>mc.example.com:25565</code>\n"
            "▫️ <code>123.45.67.89</code>"
        ),
        "status_online": "🟢 Online",
        "status_offline": "🔴 Offline",
        "tarif_premium": "💎 Premium",
        "tarif_free": "🆓 Free",
        "server_stat": (
            "🖥 <b>{ip}</b>\n"
            "{'━' * 25}\n"
            "🔌 Holat: {status}\n"
            "👥 O'yinchilar: <b>{online}</b> / <b>{max}</b>\n"
            "⚙️ Versiya: <b>{version}</b>\n"
            "💬 MOTD: <i>{motd}</i>\n"
            "📊 Tekshiruv: <b>{check_count}</b> marta\n"
            "🌟 Tarif: {tarif}\n"
            "⏱ Yangilangan: {time}"
        ),
        "server_stat_premium": (
            "\n\n💎 <b>Premium ma'lumotlar:</b>\n"
            "🧩 Pluginlar: <b>{plugins}</b>\n"
            "🧪 Software: <b>{software}</b>\n"
            "💻 Hosting IP: <b>{hosting}</b>"
        ),
        "more_info": "📄 Batafsil",
        "refresh": "🔄 Yangilash",
        "back": "⬅️ Orqaga",
        "more_title": "📌 <b>{ip} — Batafsil ma'lumot</b>\n{'━' * 25}\n\n",
        "players_label": "👥 O'yinchilar",
        "version_label": "⚙️ Versiya",
        "ping_label": "📡 Ping",
        "motd_label": "💬 MOTD",
        "status_label": "🔌 Holat",
        "tarif_label": "🌟 Tarif",
        "plugins_label": "🧩 Pluginlar",
        "software_label": "🧪 Software",
        "hosting_label": "💻 Hosting",
        "no_data": "Noma'lum",
        "no_players": "Hozir yo'q",
        "fetching": "⏳ Ma'lumot yuklanmoqda...",
        "admin_welcome": (
            "⚙️ <b>Admin Panel</b>\n"
            "{'━' * 25}\n"
            "👤 Admin: <b>{name}</b>\n\n"
            "📊 <b>Statistika:</b>\n"
            "👥 Foydalanuvchilar: <b>{users}</b>\n"
            "💎 Premium: <b>{premium}</b>\n"
            "🚫 Banlangan: <b>{banned}</b>\n"
            "🏘 Guruhlar: <b>{groups}</b>\n"
            "📋 So'rovlar: <b>{queries}</b>\n"
            "📢 Broadcast: <b>{broadcasts}</b> marta"
        ),
        "admin_not": "❌ Siz admin emassiz!",
        "broadcast_ask": "📢 Barcha foydalanuvchilarga yuboriladigan xabarni yozing:\n\n(Bekor qilish uchun /cancel)",
        "broadcast_group_ask": "🏘 Barcha guruhlarga yuboriladigan xabarni yozing:\n\n(Bekor qilish uchun /cancel)",
        "broadcast_done": "✅ Xabar yuborish tugadi!\n\n✅ Yuborildi: <b>{ok}</b>\n❌ Xato: <b>{fail}</b>",
        "premium_given": "✅ {name} ({uid}) — Premium berildi!",
        "premium_removed": "❌ {name} ({uid}) — Premium bekor qilindi",
        "ban_ask": "🚫 Ban qilmoqchi bo'lgan foydalanuvchi ID sini kiriting:\n\n(Bekor qilish: /cancel)",
        "unban_ask": "✅ Unban qilmoqchi bo'lgan foydalanuvchi ID sini kiriting:\n\n(Bekor qilish: /cancel)",
        "banned": "✅ {name} ({uid}) ban qilindi",
        "unbanned": "✅ {uid} unban qilindi",
        "banned_user": "🚫 Siz ushbu botdan foydalana olmaysiz!\n\nMurojaat: @QahramonovK",
        "stats_title": "📊 <b>Bot Statistikasi</b>\n{'━' * 25}\n\n",
        "admin_add_ask": "👑 Yangi admin ID sini kiriting:\n\n(Bekor qilish: /cancel)",
        "admin_added": "✅ {uid} — Admin qo'shildi!",
        "admin_removed": "✅ {uid} — Admin o'chirildi",
        "cancelled": "❌ Bekor qilindi",
        "new_member_group": "👋 Salom! Men <b>Minecraft Server Monitor</b> botiman!\n\n🖥 Menga server manzilini yuboring, men uning statistikasini ko'rsataman!\n\n💎 To'liq ma'lumot uchun: @{bot}",
        "btn_admin_panel": "⚙️ Admin Panel",
        "btn_top": "🏆 Top Serverlar",
        "btn_about": "ℹ️ Bot haqida",
        "btn_help": "❓ Yordam",
        "btn_lang": "🌐 Til",
        "btn_premium_get": "💎 Premium olish",
        "btn_premium_active": "💎 Premium ✅",
        "btn_stats": "📊 Statistika",
        "btn_add_group": "🤝 Guruhga qo'shish",
        "btn_subscribe": "💎 Obuna sotib olish →",
        "pf_players": "👥 O'yinchilar ro'yxati",
        "pf_plugins": "🧩 Pluginlar ro'yxati",
        "pf_hosting": "💻 Hosting ma'lumoti",
        "pf_ipport": "🔌 IP & Port",
        "pf_software": "🧪 Server software",
        "pf_ping": "📡 Ping tekshirish",
        "pf_location": "🗺 Server joylashuvi",
        "pf_daily": "📊 Kunlik statistika",
    },
    "ru": {
        "start": (
            "👋 Привет, <b>{name}</b>!\n\n"
            "🖥 <b>Minecraft Server Monitor Bot</b>\n\n"
            "📡 Получайте полную статистику любого Minecraft сервера в реальном времени!\n\n"
            "🔍 <b>Как пользоваться:</b>\n"
            "▫️ Отправьте домен или IP адрес сервера\n"
            "▫️ Например: <code>play.hypixel.net</code>\n\n"
            "💎 <b>Premium</b> открывает больше данных!\n"
            "❓ Справка: /help\n"
            "👨‍💻 Автор: @QahramonovK"
        ),
        "help": (
            "❓ <b>Полное руководство по боту</b>\n\n"
            "🖥 <b>Проверка сервера:</b>\n"
            "▫️ Отправьте домен или IP: <code>play.hypixel.net</code>\n"
            "▫️ С портом: <code>server.com:25565</code>\n\n"
            "🆓 <b>Бесплатные функции:</b>\n"
            "▫️ Статус Online/Offline\n"
            "▫️ Количество игроков\n"
            "▫️ Версия сервера\n"
            "▫️ MOTD (название сервера)\n\n"
            "💎 <b>Premium функции:</b>\n"
            "▫️ Список игроков\n"
            "▫️ Плагины и software\n"
            "▫️ Информация о хостинге\n"
            "▫️ Проверка пинга\n"
            "▫️ Местоположение сервера\n"
            "▫️ Ежедневная статистика\n\n"
            "📌 <b>Команды:</b>\n"
            "/start — Главная\n"
            "/help — Справка\n"
            "/top — Топ серверов\n"
            "/stats — Статистика бота\n"
            "/lang — Сменить язык\n"
            "/premium — Premium раздел\n\n"
            "👨‍💻 Автор: @QahramonovK"
        ),
        "info": (
            "ℹ️ <b>О боте</b>\n\n"
            "🤖 <b>Minecraft Server Monitor</b>\n"
            "📊 Статус серверов, игроки, пинг и многое другое\n"
            "🌍 3 языка: O'zbek | Русский | English\n"
            "⚡️ Данные в реальном времени\n"
            "💎 Полный функционал с Premium\n\n"
            "🔧 <b>Версия:</b> 2.0.0\n"
            "👨‍💻 <b>Автор:</b> @QahramonovK\n"
            "📅 <b>Обновлён:</b> 2025"
        ),
        "top_empty": "❌ Пока что ни один сервер не проверялся",
        "top_title": "🏆 <b>Топ 10 — Самые проверяемые серверы:</b>\n\n",
        "premium_title": (
            "💎 <b>Premium Раздел</b>\n\n"
            "🌟 Ваш тариф: <b>{tarif}</b>\n"
            "💰 Цена: <b>25 000 сум / мес</b>\n\n"
            "✨ <b>Возможности Premium:</b>\n"
            "▫️ 👥 Список игроков\n"
            "▫️ 🧩 Список плагинов\n"
            "▫️ 💻 Информация о хостинге\n"
            "▫️ 🔌 IP & Port\n"
            "▫️ 🧪 Server software\n"
            "▫️ 📡 Проверка пинга\n"
            "▫️ 🗺 Геолокация сервера\n"
            "▫️ 📊 Ежедневная статистика\n\n"
            "📩 Купить: @QahramonovK"
        ),
        "lang_choose": "🌐 <b>Выберите язык</b>\nChoose language\nTilni tanlang",
        "lang_saved": "✅ Язык сохранён!",
        "not_premium": (
            "💎 <b>Нужен Premium!</b>\n\n"
            "Эта функция только для Premium пользователей.\n"
            "Купить: @QahramonovK"
        ),
        "server_offline": "❌ <b>{ip}</b> — оффлайн или не найден!\n\n⏱ Попробуйте позже.",
        "server_invalid": (
            "❌ <b>Неверный формат!</b>\n\n"
            "Отправьте корректный домен или IP адрес.\n\n"
            "✅ <b>Примеры:</b>\n"
            "▫️ <code>play.hypixel.net</code>\n"
            "▫️ <code>mc.example.com:25565</code>\n"
            "▫️ <code>123.45.67.89</code>"
        ),
        "status_online": "🟢 Онлайн",
        "status_offline": "🔴 Офлайн",
        "tarif_premium": "💎 Premium",
        "tarif_free": "🆓 Free",
        "server_stat": (
            "🖥 <b>{ip}</b>\n"
            "{'━' * 25}\n"
            "🔌 Статус: {status}\n"
            "👥 Игроков: <b>{online}</b> / <b>{max}</b>\n"
            "⚙️ Версия: <b>{version}</b>\n"
            "💬 MOTD: <i>{motd}</i>\n"
            "📊 Проверок: <b>{check_count}</b> раз\n"
            "🌟 Тариф: {tarif}\n"
            "⏱ Обновлено: {time}"
        ),
        "server_stat_premium": (
            "\n\n💎 <b>Premium данные:</b>\n"
            "🧩 Плагины: <b>{plugins}</b>\n"
            "🧪 ПО: <b>{software}</b>\n"
            "💻 Хостинг IP: <b>{hosting}</b>"
        ),
        "more_info": "📄 Подробнее",
        "refresh": "🔄 Обновить",
        "back": "⬅️ Назад",
        "more_title": "📌 <b>{ip} — Подробная информация</b>\n{'━' * 25}\n\n",
        "players_label": "👥 Игроки",
        "version_label": "⚙️ Версия",
        "ping_label": "📡 Пинг",
        "motd_label": "💬 MOTD",
        "status_label": "🔌 Статус",
        "tarif_label": "🌟 Тариф",
        "plugins_label": "🧩 Плагины",
        "software_label": "🧪 ПО",
        "hosting_label": "💻 Хостинг",
        "no_data": "Неизвестно",
        "no_players": "Нет сейчас",
        "fetching": "⏳ Загрузка данных...",
        "admin_welcome": (
            "⚙️ <b>Админ Панель</b>\n"
            "{'━' * 25}\n"
            "👤 Админ: <b>{name}</b>\n\n"
            "📊 <b>Статистика:</b>\n"
            "👥 Пользователей: <b>{users}</b>\n"
            "💎 Premium: <b>{premium}</b>\n"
            "🚫 Заблокировано: <b>{banned}</b>\n"
            "🏘 Групп: <b>{groups}</b>\n"
            "📋 Запросов: <b>{queries}</b>\n"
            "📢 Рассылок: <b>{broadcasts}</b>"
        ),
        "admin_not": "❌ Вы не являетесь администратором!",
        "broadcast_ask": "📢 Напишите сообщение для рассылки всем пользователям:\n\n(Отмена: /cancel)",
        "broadcast_group_ask": "🏘 Напишите сообщение для рассылки по группам:\n\n(Отмена: /cancel)",
        "broadcast_done": "✅ Рассылка завершена!\n\n✅ Отправлено: <b>{ok}</b>\n❌ Ошибок: <b>{fail}</b>",
        "premium_given": "✅ {name} ({uid}) — Premium выдан!",
        "premium_removed": "❌ {name} ({uid}) — Premium снят",
        "ban_ask": "🚫 Введите ID пользователя для бана:\n\n(Отмена: /cancel)",
        "unban_ask": "✅ Введите ID для разбана:\n\n(Отмена: /cancel)",
        "banned": "✅ {name} ({uid}) забанен",
        "unbanned": "✅ {uid} разбанен",
        "banned_user": "🚫 Вы заблокированы!\n\nПо вопросам: @QahramonovK",
        "stats_title": "📊 <b>Статистика бота</b>\n{'━' * 25}\n\n",
        "admin_add_ask": "👑 Введите ID нового администратора:\n\n(Отмена: /cancel)",
        "admin_added": "✅ {uid} — Добавлен как админ!",
        "admin_removed": "✅ {uid} — Удалён из администраторов",
        "cancelled": "❌ Отменено",
        "new_member_group": "👋 Привет! Я <b>Minecraft Server Monitor</b>!\n\n🖥 Отправьте мне адрес сервера и я покажу статистику!\n\n💎 Подробнее: @{bot}",
        "btn_admin_panel": "⚙️ Админ Панель",
        "btn_top": "🏆 Топ серверов",
        "btn_about": "ℹ️ О боте",
        "btn_help": "❓ Справка",
        "btn_lang": "🌐 Язык",
        "btn_premium_get": "💎 Получить Premium",
        "btn_premium_active": "💎 Premium ✅",
        "btn_stats": "📊 Статистика",
        "btn_add_group": "🤝 Добавить в группу",
        "btn_subscribe": "💎 Купить подписку →",
        "pf_players": "👥 Список игроков",
        "pf_plugins": "🧩 Список плагинов",
        "pf_hosting": "💻 Информация о хостинге",
        "pf_ipport": "🔌 IP & Порт",
        "pf_software": "🧪 Software сервера",
        "pf_ping": "📡 Проверка пинга",
        "pf_location": "🗺 Местоположение сервера",
        "pf_daily": "📊 Ежедневная статистика",
    },
    "en": {
        "start": (
            "👋 Hello, <b>{name}</b>!\n\n"
            "🖥 <b>Minecraft Server Monitor Bot</b>\n\n"
            "📡 Get full statistics of any Minecraft server in real time!\n\n"
            "🔍 <b>How to use:</b>\n"
            "▫️ Send a server domain or IP address\n"
            "▫️ Example: <code>play.hypixel.net</code>\n\n"
            "💎 <b>Premium</b> unlocks more data!\n"
            "❓ Help: /help\n"
            "👨‍💻 Creator: @QahramonovK"
        ),
        "help": (
            "❓ <b>Complete Bot Guide</b>\n\n"
            "🖥 <b>Check a server:</b>\n"
            "▫️ Send domain or IP: <code>play.hypixel.net</code>\n"
            "▫️ With port: <code>server.com:25565</code>\n\n"
            "🆓 <b>Free features:</b>\n"
            "▫️ Online/Offline status\n"
            "▫️ Player count\n"
            "▫️ Server version\n"
            "▫️ MOTD (server name)\n\n"
            "💎 <b>Premium features:</b>\n"
            "▫️ Player list\n"
            "▫️ Plugins and software\n"
            "▫️ Hosting information\n"
            "▫️ Ping check\n"
            "▫️ Server location\n"
            "▫️ Daily statistics\n\n"
            "📌 <b>Commands:</b>\n"
            "/start — Home\n"
            "/help — Help\n"
            "/top — Top servers\n"
            "/stats — Bot statistics\n"
            "/lang — Change language\n"
            "/premium — Premium section\n\n"
            "👨‍💻 Creator: @QahramonovK"
        ),
        "info": (
            "ℹ️ <b>About Bot</b>\n\n"
            "🤖 <b>Minecraft Server Monitor</b>\n"
            "📊 Server status, players, ping and more\n"
            "🌍 3 languages: O'zbek | Русский | English\n"
            "⚡️ Real-time data\n"
            "💎 Full features with Premium\n\n"
            "🔧 <b>Version:</b> 2.0.0\n"
            "👨‍💻 <b>Creator:</b> @QahramonovK\n"
            "📅 <b>Updated:</b> 2025"
        ),
        "top_empty": "❌ No servers have been checked yet",
        "top_title": "🏆 <b>Top 10 — Most checked servers:</b>\n\n",
        "premium_title": (
            "💎 <b>Premium Section</b>\n\n"
            "🌟 Your plan: <b>{tarif}</b>\n"
            "💰 Price: <b>25 000 UZS / month</b>\n\n"
            "✨ <b>Premium features:</b>\n"
            "▫️ 👥 Player list\n"
            "▫️ 🧩 Plugin list\n"
            "▫️ 💻 Hosting info\n"
            "▫️ 🔌 IP & Port\n"
            "▫️ 🧪 Server software\n"
            "▫️ 📡 Ping check\n"
            "▫️ 🗺 Server geolocation\n"
            "▫️ 📊 Daily statistics\n\n"
            "📩 Subscribe: @QahramonovK"
        ),
        "lang_choose": "🌐 <b>Choose language</b>\nTilni tanlang\nВыберите язык",
        "lang_saved": "✅ Language saved!",
        "not_premium": (
            "💎 <b>Premium required!</b>\n\n"
            "This feature is for Premium users only.\n"
            "Subscribe: @QahramonovK"
        ),
        "server_offline": "❌ <b>{ip}</b> — offline or not found!\n\n⏱ Try again later.",
        "server_invalid": (
            "❌ <b>Invalid format!</b>\n\n"
            "Send a valid domain or IP address.\n\n"
            "✅ <b>Examples:</b>\n"
            "▫️ <code>play.hypixel.net</code>\n"
            "▫️ <code>mc.example.com:25565</code>\n"
            "▫️ <code>123.45.67.89</code>"
        ),
        "status_online": "🟢 Online",
        "status_offline": "🔴 Offline",
        "tarif_premium": "💎 Premium",
        "tarif_free": "🆓 Free",
        "server_stat": (
            "🖥 <b>{ip}</b>\n"
            "{'━' * 25}\n"
            "🔌 Status: {status}\n"
            "👥 Players: <b>{online}</b> / <b>{max}</b>\n"
            "⚙️ Version: <b>{version}</b>\n"
            "💬 MOTD: <i>{motd}</i>\n"
            "📊 Checked: <b>{check_count}</b> times\n"
            "🌟 Plan: {tarif}\n"
            "⏱ Updated: {time}"
        ),
        "server_stat_premium": (
            "\n\n💎 <b>Premium data:</b>\n"
            "🧩 Plugins: <b>{plugins}</b>\n"
            "🧪 Software: <b>{software}</b>\n"
            "💻 Hosting IP: <b>{hosting}</b>"
        ),
        "more_info": "📄 More Info",
        "refresh": "🔄 Refresh",
        "back": "⬅️ Back",
        "more_title": "📌 <b>{ip} — Detailed Info</b>\n{'━' * 25}\n\n",
        "players_label": "👥 Players",
        "version_label": "⚙️ Version",
        "ping_label": "📡 Ping",
        "motd_label": "💬 MOTD",
        "status_label": "🔌 Status",
        "tarif_label": "🌟 Plan",
        "plugins_label": "🧩 Plugins",
        "software_label": "🧪 Software",
        "hosting_label": "💻 Hosting",
        "no_data": "Unknown",
        "no_players": "None right now",
        "fetching": "⏳ Fetching data...",
        "admin_welcome": (
            "⚙️ <b>Admin Panel</b>\n"
            "{'━' * 25}\n"
            "👤 Admin: <b>{name}</b>\n\n"
            "📊 <b>Statistics:</b>\n"
            "👥 Users: <b>{users}</b>\n"
            "💎 Premium: <b>{premium}</b>\n"
            "🚫 Banned: <b>{banned}</b>\n"
            "🏘 Groups: <b>{groups}</b>\n"
            "📋 Queries: <b>{queries}</b>\n"
            "📢 Broadcasts: <b>{broadcasts}</b>"
        ),
        "admin_not": "❌ You are not an admin!",
        "broadcast_ask": "📢 Write a message to send to all users:\n\n(Cancel: /cancel)",
        "broadcast_group_ask": "🏘 Write a message to send to all groups:\n\n(Cancel: /cancel)",
        "broadcast_done": "✅ Broadcast finished!\n\n✅ Sent: <b>{ok}</b>\n❌ Failed: <b>{fail}</b>",
        "premium_given": "✅ {name} ({uid}) — Premium granted!",
        "premium_removed": "❌ {name} ({uid}) — Premium removed",
        "ban_ask": "🚫 Enter user ID to ban:\n\n(Cancel: /cancel)",
        "unban_ask": "✅ Enter user ID to unban:\n\n(Cancel: /cancel)",
        "banned": "✅ {name} ({uid}) banned",
        "unbanned": "✅ {uid} unbanned",
        "banned_user": "🚫 You are banned!\n\nContact: @QahramonovK",
        "stats_title": "📊 <b>Bot Statistics</b>\n{'━' * 25}\n\n",
        "admin_add_ask": "👑 Enter new admin ID:\n\n(Cancel: /cancel)",
        "admin_added": "✅ {uid} — Added as admin!",
        "admin_removed": "✅ {uid} — Removed from admins",
        "cancelled": "❌ Cancelled",
        "new_member_group": "👋 Hello! I'm <b>Minecraft Server Monitor</b>!\n\n🖥 Send me a server address and I'll show statistics!\n\n💎 More: @{bot}",
        "btn_admin_panel": "⚙️ Admin Panel",
        "btn_top": "🏆 Top Servers",
        "btn_about": "ℹ️ About Bot",
        "btn_help": "❓ Help",
        "btn_lang": "🌐 Language",
        "btn_premium_get": "💎 Get Premium",
        "btn_premium_active": "💎 Premium ✅",
        "btn_stats": "📊 Statistics",
        "btn_add_group": "🤝 Add to group",
        "btn_subscribe": "💎 Buy subscription →",
        "pf_players": "👥 Player list",
        "pf_plugins": "🧩 Plugin list",
        "pf_hosting": "💻 Hosting info",
        "pf_ipport": "🔌 IP & Port",
        "pf_software": "🧪 Server software",
        "pf_ping": "📡 Ping check",
        "pf_location": "🗺 Server location",
        "pf_daily": "📊 Daily statistics",
    }
}

def t(lang: str, key: str, **kwargs) -> str:
    lang = lang if lang in TEXTS else "uz"
    text = TEXTS[lang].get(key, TEXTS["uz"].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except Exception:
            pass
    return text

# ================= DATABASE =================
def load_db():
    with DB_LOCK:
        if not os.path.exists(DB_FILE):
            data = {
                "users": {},
                "premium_users": [],
                "banned_users": [],
                "admin_ids": [7607916773],
                "stats": [],
                "groups": {},
                "broadcast_count": 0,
                "server_checks": {}
            }
            _save_db_locked(data)
            return data
        try:
            with open(DB_FILE, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            # Fayl vaqtincha buzilgan/bo'sh bo'lsa, dastur qulamasligi uchun
            return {
                "users": {}, "premium_users": [], "banned_users": [],
                "admin_ids": [7607916773], "stats": [], "groups": {},
                "broadcast_count": 0, "server_checks": {}
            }

def _save_db_locked(data):
    # "stats" jurnali cheksiz o'sib ketmasligi uchun eng oxirgi yozuvlarni saqlaymiz
    stats = data.get("stats")
    if isinstance(stats, list) and len(stats) > MAX_STATS_ENTRIES:
        data["stats"] = stats[-MAX_STATS_ENTRIES:]
    tmp_file = DB_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(tmp_file, DB_FILE)  # atomik almashtirish - fayl hech qachon yarim yozilgan holda qolmaydi

def save_db(data):
    with DB_LOCK:
        _save_db_locked(data)

def get_user_lang(user_id: str) -> str:
    db = load_db()
    return db.get("users", {}).get(str(user_id), {}).get("lang", "uz")

def register_user(user_id: str, name: str = "", lang: str = "uz", username: str = ""):
    db = load_db()
    db.setdefault("users", {})
    uid = str(user_id)
    if uid not in db["users"]:
        db["users"][uid] = {
            "lang": lang, 
            "name": name, 
            "username": username,
            "joined": datetime.now().isoformat(),
            "query_count": 0
        }
    else:
        # Update name/username if changed
        db["users"][uid]["name"] = name
        if username:
            db["users"][uid]["username"] = username
    save_db(db)

def register_group(chat_id: str, title: str):
    db = load_db()
    db.setdefault("groups", {})
    db["groups"][str(chat_id)] = {
        "title": title,
        "joined": datetime.now().isoformat()
    }
    save_db(db)

def remove_group(chat_id: str):
    db = load_db()
    db.setdefault("groups", {})
    db["groups"].pop(str(chat_id), None)
    save_db(db)

def add_query_stat(user_id: str, server: str):
    db = load_db()
    db.setdefault("stats", [])
    db.setdefault("server_checks", {})
    db["stats"].append({"user": user_id, "server": server, "time": datetime.now().isoformat()})
    # Count per server
    db["server_checks"][server] = db["server_checks"].get(server, 0) + 1
    # Count per user
    uid = str(user_id)
    if uid in db.get("users", {}):
        db["users"][uid]["query_count"] = db["users"][uid].get("query_count", 0) + 1
    save_db(db)

def get_server_check_count(server: str) -> int:
    db = load_db()
    return db.get("server_checks", {}).get(server, 0)

def get_top_servers(n=10):
    db = load_db()
    counts = db.get("server_checks", {})
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]

def is_premium(user_id) -> bool:
    db = load_db()
    return str(user_id) in map(str, db.get("premium_users", []))

def is_banned(user_id) -> bool:
    db = load_db()
    return str(user_id) in map(str, db.get("banned_users", []))

def is_admin(user_id) -> bool:
    db = load_db()
    all_admins = db.get("admin_ids", [7607916773])
    return int(user_id) in [int(x) for x in all_admins]

# ================= FSM STATES =================
class AdminState(StatesGroup):
    broadcast = State()
    broadcast_group = State()
    ban_user = State()
    unban_user = State()
    add_admin = State()
    remove_admin = State()
    manual_premium_uid = State()
    manual_remove_premium_uid = State()

# ================= KEYBOARDS =================
def main_keyboard(user_id):
    lang = get_user_lang(str(user_id))
    premium = is_premium(str(user_id))
    premium_label = t(lang, "btn_premium_active") if premium else t(lang, "btn_premium_get")
    kb = [
        [
            InlineKeyboardButton(text=t(lang, "btn_top"), callback_data="top"),
            InlineKeyboardButton(text=t(lang, "btn_about"), callback_data="info"),
        ],
        [
            InlineKeyboardButton(text=t(lang, "btn_help"), callback_data="help"),
            InlineKeyboardButton(text=t(lang, "btn_lang"), callback_data="lang"),
        ],
        [InlineKeyboardButton(text=premium_label, callback_data="premium")],
        [InlineKeyboardButton(text=t(lang, "btn_stats"), callback_data="user_stats")],
        [InlineKeyboardButton(text=t(lang, "btn_add_group"), url=f"https://t.me/{BOT_USERNAME}?startgroup=on")],
    ]
    if is_admin(user_id):
        kb.insert(0, [InlineKeyboardButton(text=t(lang, "btn_admin_panel"), callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def lang_keyboard(lang="uz"):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="lang_uz")],
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data="back_main")],
    ])

def premium_features_keyboard(user_id):
    lang = get_user_lang(str(user_id))
    premium = is_premium(str(user_id))
    lock = "" if premium else " 🔒"
    buttons = [
        [InlineKeyboardButton(text=f"{t(lang, 'pf_players')}{lock}", callback_data="pf_players")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_plugins')}{lock}", callback_data="pf_plugins")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_hosting')}{lock}", callback_data="pf_hosting")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_ipport')}{lock}", callback_data="pf_ipport")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_software')}{lock}", callback_data="pf_software")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_ping')}{lock}", callback_data="pf_ping")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_location')}{lock}", callback_data="pf_location")],
        [InlineKeyboardButton(text=f"{t(lang, 'pf_daily')}{lock}", callback_data="pf_daily")],
    ]
    if not premium:
        buttons.append([InlineKeyboardButton(text=t(lang, "btn_subscribe"), url=PREMIUM_CONTACT)])
    buttons.append([InlineKeyboardButton(text=t(lang, "back"), callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm_users"),
            InlineKeyboardButton(text="🏘 Guruhlar", callback_data="adm_groups"),
        ],
        [
            InlineKeyboardButton(text="💎 Premium berish", callback_data="adm_give_premium"),
            InlineKeyboardButton(text="💎 Premium olish", callback_data="adm_remove_premium"),
        ],
        [
            InlineKeyboardButton(text="🚫 Ban", callback_data="adm_ban"),
            InlineKeyboardButton(text="✅ Unban", callback_data="adm_unban"),
        ],
        [
            InlineKeyboardButton(text="📢 Users Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton(text="🏘 Groups Broadcast", callback_data="adm_broadcast_groups"),
        ],
        [
            InlineKeyboardButton(text="👑 Admin qo'shish", callback_data="adm_add_admin"),
            InlineKeyboardButton(text="👑 Admin o'chirish", callback_data="adm_remove_admin"),
        ],
        [InlineKeyboardButton(text="📊 To'liq statistika", callback_data="adm_stats")],
        [
            InlineKeyboardButton(text="💎 Premium ro'yxat", callback_data="adm_premium_list"),
            InlineKeyboardButton(text="🚫 Ban ro'yxat", callback_data="adm_ban_list"),
        ],
        [
            InlineKeyboardButton(text="👑 Adminlar", callback_data="adm_admin_list"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="adm_refresh"),
        ],
        [InlineKeyboardButton(text="⬅️ Bosh sahifa", callback_data="back_main")],
    ])

def server_keyboard(ip: str, lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t(lang, "more_info"), callback_data=f"more::{ip}"),
            InlineKeyboardButton(text="🔄", callback_data=f"recheck::{ip}"),
        ],
    ])

def more_keyboard(ip: str, lang: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "refresh"), callback_data=f"refresh::{ip}")],
        [InlineKeyboardButton(text=t(lang, "back"), callback_data=f"back::{ip}")],
    ])

# ================= SERVER API =================
DOMAIN_REGEX = re.compile(r"^(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}(?::\d+)?$")
IP_REGEX = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?$")

async def fetch_server_info(ip: str, force: bool = False):
    """Server ma'lumotini oladi. Kesh orqali bir xil so'rovlarni tezlashtiradi."""
    key = ip.lower().strip()
    now = time.time()

    if not force:
        cached = SERVER_CACHE.get(key)
        if cached and (now - cached["time"]) < CACHE_TTL_SECONDS:
            return cached["data"]

    url = f"https://api.mcsrvstat.us/3/{ip}"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    SERVER_CACHE[key] = {"data": data, "time": now}
                    return data
                return None
        except Exception:
            return None

def format_time():
    return datetime.now().strftime("%H:%M:%S")

def progress_bar(current, maximum, length=10):
    """O'yinchilar sonini vizual chiziq (bar) ko'rinishida ko'rsatadi"""
    try:
        current = int(current)
        maximum = int(maximum)
        if maximum <= 0:
            return "▱" * length
        ratio = min(current / maximum, 1.0)
    except (TypeError, ValueError):
        return "▱" * length
    filled = round(ratio * length)
    return "▰" * filled + "▱" * (length - filled)

_CARD_LABELS = {
    "uz": {"players": "O'yinchilar", "version": "Versiya", "checked": "marta tekshirilgan",
           "plugins": "Pluginlar", "software": "Software", "hosting": "Hosting IP"},
    "ru": {"players": "Игроков", "version": "Версия", "checked": "раз проверено",
           "plugins": "Плагины", "software": "ПО", "hosting": "Хостинг IP"},
    "en": {"players": "Players", "version": "Version", "checked": "times checked",
           "plugins": "Plugins", "software": "Software", "hosting": "Hosting IP"},
}

def build_server_text(ip: str, data: dict, uid: str, lang: str) -> str:
    online = data.get("online", False)
    players = data.get("players", {})
    online_count = players.get("online", 0)
    max_players = players.get("max", 0)

    version_info = data.get("version", t(lang, "no_data"))
    if isinstance(version_info, dict):
        version = version_info.get("name", t(lang, "no_data"))
    else:
        version = version_info or t(lang, "no_data")

    motd_data = data.get("motd", {})
    if isinstance(motd_data, dict):
        motd = " | ".join(motd_data.get("clean", [])) or t(lang, "no_data")
    else:
        motd = str(motd_data) or t(lang, "no_data")

    motd = " ".join(motd.split())
    if len(motd) > 55:
        motd = motd[:52] + "..."

    status_str = t(lang, "status_online") if online else t(lang, "status_offline")
    tarif_str = t(lang, "tarif_premium") if is_premium(uid) else t(lang, "tarif_free")
    check_count = get_server_check_count(ip)
    bar = progress_bar(online_count, max_players if max_players else 0)
    L = _CARD_LABELS.get(lang, _CARD_LABELS["uz"])
    premium = is_premium(uid)

    text = (
        f"{status_str}\n"
        f"🖥 <b>{ip}</b>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"👥 <b>{online_count}</b>/<b>{max_players}</b>  {L['players']}\n"
        f"<code>{bar}</code>\n\n"
        f"⚙️ {version}\n"
        f"💬 <i>{motd}</i>\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{tarif_str}  ·  🕐 {format_time()}  ·  📊 {check_count} {L['checked']}"
    )

    if premium:
        plugins = ", ".join(data.get("plugins", {}).get("names", [])[:8]) or t(lang, "no_data")
        software = data.get("software", t(lang, "no_data"))
        hosting = data.get("ip", t(lang, "no_data"))
        text += (
            f"\n\n💎 <b>{L['plugins']}:</b> {plugins}\n"
            f"🧪 {software}  ·  💻 {hosting}"
        )

    return text

def build_more_text(ip: str, data: dict, uid: str, lang: str) -> str:
    motd_data = data.get("motd", {})
    if isinstance(motd_data, dict):
        motd = " | ".join(motd_data.get("clean", [])) or t(lang, "no_data")
    else:
        motd = str(motd_data) or t(lang, "no_data")

    players = data.get("players", {})
    players_list = players.get("list", [])
    if isinstance(players_list, list) and len(players_list) > 0:
        if isinstance(players_list[0], dict):
            players_names = [p.get("name", "?") for p in players_list[:20]]
        else:
            players_names = players_list[:20]
    else:
        players_names = []

    online_count = players.get("online", 0)
    max_players = players.get("max", "?")

    version_info = data.get("version", t(lang, "no_data"))
    if isinstance(version_info, dict):
        version = version_info.get("name", t(lang, "no_data"))
        protocol = version_info.get("protocol", "")
    else:
        version = version_info or t(lang, "no_data")
        protocol = ""

    ping = data.get("debug", {}).get("ping", False)
    ping_str = "✅ Javob beryapti" if ping else "❌ Javob yo'q"
    online = data.get("online", False)
    premium = is_premium(uid)
    tarif_str = t(lang, "tarif_premium") if premium else t(lang, "tarif_free")

    hostname = data.get("hostname", ip)
    port = data.get("port", "25565")
    eula_blocked = data.get("eula_blocked", False)

    if players_names:
        players_str = ", ".join(players_names)
        if len(players_list) > 20:
            players_str += f" (+{len(players_list)-20})"
    else:
        players_str = t(lang, "no_players")

    bar = progress_bar(online_count, max_players if max_players else 0)
    status_line = "🟢 <b>Online</b>" if online else "🔴 <b>Offline</b>"

    # ── Umumiy ma'lumot ──
    text = (
        f"📌 <b>{ip}</b> — batafsil\n"
        f"{status_line}\n"
        f"┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n\n"
        f"💬 <i>{motd}</i>\n\n"
        f"🌐 <b>Manzil:</b> <code>{hostname}:{port}</code>\n"
    )

    # ── O'yinchilar ──
    text += (
        f"\n👥 <b>O'yinchilar:</b> {online_count}/{max_players}\n"
        f"<code>{bar}</code>\n"
        f"   ↳ {players_str}\n"
    )

    # ── Texnik ma'lumot ──
    text += f"\n⚙️ <b>Versiya:</b> {version}"
    if protocol:
        text += f" <i>(protocol {protocol})</i>"
    text += f"\n📡 <b>Ping:</b> {ping_str}"

    if eula_blocked:
        text += f"\n⚠️ <b>Diqqat:</b> server Mojang EULA bo'yicha bloklangan"

    text += (
        f"\n┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈┈\n"
        f"{tarif_str}  ·  🕐 {format_time()}"
    )

    # ── Premium bo'limi ──
    if premium:
        plugins = ", ".join(data.get("plugins", {}).get("names", [])[:15]) or t(lang, "no_data")
        software = data.get("software", t(lang, "no_data"))
        hosting = data.get("ip", t(lang, "no_data"))
        icon = data.get("icon", "")
        map_name = data.get("map", {})
        if isinstance(map_name, dict):
            map_name = map_name.get("clean") or map_name.get("raw") or t(lang, "no_data")
        map_name = map_name or t(lang, "no_data")

        text += (
            f"\n\n💎 <b>Premium ma'lumotlar</b>\n"
            f"🧩 <b>Pluginlar:</b> {plugins}\n"
            f"🧪 <b>Software:</b> {software}\n"
            f"💻 <b>Hosting IP:</b> {hosting}\n"
            f"🗺 <b>Xarita:</b> {map_name}"
        )
        if icon:
            text += "\n🖼 <b>Icon:</b> mavjud ✅"

    return text

# ================= START =================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    uid = str(message.from_user.id)

    if is_banned(uid):
        await message.answer(t("uz", "banned_user"))
        return

    name = message.from_user.full_name or message.from_user.username or "Foydalanuvchi"
    username = message.from_user.username or ""
    register_user(uid, name, username=username)
    lang = get_user_lang(uid)

    await message.answer(
        t(lang, "start", name=name),
        reply_markup=main_keyboard(uid),
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    uid = str(message.from_user.id)
    if is_banned(uid): return
    lang = get_user_lang(uid)
    await message.answer(t(lang, "help"), parse_mode="HTML", reply_markup=main_keyboard(uid))

@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    uid = str(message.from_user.id)
    if is_banned(uid): return
    lang = get_user_lang(uid)
    await _send_top(message, uid, lang)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    uid = str(message.from_user.id)
    if is_banned(uid): return
    lang = get_user_lang(uid)
    db = load_db()
    user_data = db.get("users", {}).get(uid, {})
    q_count = user_data.get("query_count", 0)
    joined = user_data.get("joined", "")[:10] if user_data.get("joined") else "?"
    
    sep = "━" * 20
    text = (
        f"📊 <b>Sizning statistikangiz</b>\n"
        f"<code>{sep}</code>\n\n"
        f"👤 Ism: <b>{user_data.get('name', '?')}</b>\n"
        f"🌐 Til: <b>{user_data.get('lang', 'uz').upper()}</b>\n"
        f"🌟 Tarif: <b>{'💎 Premium' if is_premium(uid) else '🆓 Free'}</b>\n"
        f"📋 So'rovlar: <b>{q_count}</b>\n"
        f"📅 Ro'yxatdan o'tgan: <b>{joined}</b>\n\n"
        f"🔥 <b>Top serverlar (barcha):</b>\n"
    )
    top = get_top_servers(5)
    if top:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (srv, cnt) in enumerate(top):
            text += f"{medals[i]} <code>{srv}</code> — <b>{cnt}</b>\n"
    else:
        text += "Hali yo'q\n"
    
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard(uid))

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    uid = str(message.from_user.id)
    lang = get_user_lang(uid)
    await message.answer(t(lang, "lang_choose"), reply_markup=lang_keyboard(lang), parse_mode="HTML")

@dp.message(Command("premium"))
async def cmd_premium(message: types.Message):
    uid = str(message.from_user.id)
    lang = get_user_lang(uid)
    premium = is_premium(uid)
    tarif = t(lang, "tarif_premium") if premium else t(lang, "tarif_free")
    await message.answer(
        t(lang, "premium_title", tarif=tarif),
        reply_markup=premium_features_keyboard(uid),
        parse_mode="HTML"
    )

@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    current = await state.get_state()
    if current:
        await state.clear()
        lang = get_user_lang(str(message.from_user.id))
        await message.answer(t(lang, "cancelled"))

# ================= MAIN CALLBACKS =================
@dp.callback_query(F.data == "back_main")
async def cb_back_main(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    name = call.from_user.full_name or "Foydalanuvchi"
    try:
        await call.message.edit_text(
            t(lang, "start", name=name),
            reply_markup=main_keyboard(uid),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data == "help")
async def cb_help(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    try:
        await call.message.edit_text(t(lang, "help"), reply_markup=main_keyboard(uid), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data == "info")
async def cb_info(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    text = t(lang, "info")
    if is_admin(uid):
        db = load_db()
        text += f"\n\n⚙️ <b>Admin:</b> Users: {len(db.get('users',{}))}, Premium: {len(db.get('premium_users',[]))}"
    try:
        await call.message.edit_text(text, reply_markup=main_keyboard(uid), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data == "top")
async def cb_top(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    await _send_top_edit(call, uid, lang)

async def _send_top(message, uid, lang):
    top = get_top_servers(10)
    if not top:
        text = t(lang, "top_empty")
    else:
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        text = t(lang, "top_title")
        for i, (srv, cnt) in enumerate(top):
            bar = "█" * min(cnt, 10) + "░" * max(0, 10 - cnt)
            text += f"{medals[i]} <code>{srv}</code>\n   ↳ {bar} <b>{cnt}</b>\n"
    await message.answer(text, reply_markup=main_keyboard(uid), parse_mode="HTML")

async def _send_top_edit(call, uid, lang):
    top = get_top_servers(10)
    if not top:
        text = t(lang, "top_empty")
    else:
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        text = t(lang, "top_title")
        for i, (srv, cnt) in enumerate(top):
            text += f"{medals[i]} <code>{srv}</code> — <b>{cnt}</b>\n"
    try:
        await call.message.edit_text(text, reply_markup=main_keyboard(uid), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data == "user_stats")
async def cb_user_stats(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    db = load_db()
    user_data = db.get("users", {}).get(uid, {})
    q_count = user_data.get("query_count", 0)
    joined = user_data.get("joined", "")[:10] if user_data.get("joined") else "?"
    sep = "━" * 20
    text = (
        f"📊 <b>Profilingiz</b>\n"
        f"<code>{sep}</code>\n\n"
        f"👤 Ism: <b>{user_data.get('name','?')}</b>\n"
        f"🆔 ID: <code>{uid}</code>\n"
        f"🌐 Til: <b>{user_data.get('lang','uz').upper()}</b>\n"
        f"🌟 Tarif: <b>{'💎 Premium' if is_premium(uid) else '🆓 Free'}</b>\n"
        f"📋 So'rovlar: <b>{q_count}</b>\n"
        f"📅 A'zo bo'lgan: <b>{joined}</b>"
    )
    try:
        await call.message.edit_text(text, reply_markup=main_keyboard(uid), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data == "lang")
async def cb_lang(call: types.CallbackQuery):
    lang = get_user_lang(str(call.from_user.id))
    try:
        await call.message.edit_text(t(lang, "lang_choose"), reply_markup=lang_keyboard(lang), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("lang_"))
async def cb_set_lang(call: types.CallbackQuery):
    lang = call.data.split("_")[1]
    uid = str(call.from_user.id)
    db = load_db()
    db.setdefault("users", {}).setdefault(uid, {})["lang"] = lang
    save_db(db)
    name = call.from_user.full_name or "Foydalanuvchi"
    await call.answer(t(lang, "lang_saved"), show_alert=True)
    try:
        await call.message.edit_text(
            t(lang, "start", name=name),
            reply_markup=main_keyboard(uid),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data == "premium")
async def cb_premium(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    premium = is_premium(uid)
    tarif = t(lang, "tarif_premium") if premium else t(lang, "tarif_free")
    try:
        await call.message.edit_text(
            t(lang, "premium_title", tarif=tarif),
            reply_markup=premium_features_keyboard(uid),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("pf_"))
async def cb_premium_feature(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    if not is_premium(uid):
        await call.answer(t(lang, "not_premium"), show_alert=True)
        return
    feature_texts = {
        "players": "👥 O'yinchilar ro'yxatini ko'rish uchun server manzilini yuboring",
        "plugins": "🧩 Pluginlar ro'yxatini ko'rish uchun server manzilini yuboring",
        "hosting": "💻 Hosting ma'lumotini ko'rish uchun server manzilini yuboring",
        "ipport": "🔌 IP & Port ma'lumotini ko'rish uchun server manzilini yuboring",
        "software": "🧪 Software ma'lumotini ko'rish uchun server manzilini yuboring",
        "ping": "📡 Ping tekshirish uchun server manzilini yuboring",
        "location": "🗺 Joylashuv ma'lumotini ko'rish uchun server manzilini yuboring",
        "daily": "📊 Kunlik statistika uchun server manzilini yuboring",
    }
    feature = call.data[3:]
    await call.message.answer(feature_texts.get(feature, "Server manzilini yuboring:"))
    await call.answer()

# ================= ADMIN PANEL CALLBACK =================
@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if not is_admin(uid):
        await call.answer("❌ Admin emassiz!", show_alert=True)
        return
    db = load_db()
    sep = "━" * 20
    text = (
        f"⚙️ <b>Admin Panel</b>\n"
        f"<code>{sep}</code>\n"
        f"👤 Admin: <b>{call.from_user.full_name}</b>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"👥 Foydalanuvchilar: <b>{len(db.get('users', {}))}</b>\n"
        f"💎 Premium: <b>{len(db.get('premium_users', []))}</b>\n"
        f"🚫 Banlangan: <b>{len(db.get('banned_users', []))}</b>\n"
        f"🏘 Guruhlar: <b>{len(db.get('groups', {}))}</b>\n"
        f"📋 So'rovlar: <b>{len(db.get('stats', []))}</b>\n"
        f"📢 Broadcast: <b>{db.get('broadcast_count', 0)}</b>"
    )
    try:
        await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("adm_"))
async def cb_admin(call: types.CallbackQuery, state: FSMContext):
    uid = str(call.from_user.id)
    if not is_admin(uid):
        await call.answer("❌ Admin emassiz!", show_alert=True)
        return

    data = call.data
    db = load_db()

    if data == "adm_refresh":
        sep = "━" * 20
        text = (
            f"⚙️ <b>Admin Panel</b>\n"
            f"<code>{sep}</code>\n"
            f"👤 Admin: <b>{call.from_user.full_name}</b>\n\n"
            f"📊 <b>Statistika:</b>\n"
            f"👥 Foydalanuvchilar: <b>{len(db.get('users', {}))}</b>\n"
            f"💎 Premium: <b>{len(db.get('premium_users', []))}</b>\n"
            f"🚫 Banlangan: <b>{len(db.get('banned_users', []))}</b>\n"
            f"🏘 Guruhlar: <b>{len(db.get('groups', {}))}</b>\n"
            f"📋 So'rovlar: <b>{len(db.get('stats', []))}</b>"
        )
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer("✅ Yangilandi")

    elif data == "adm_users":
        users = db.get("users", {})
        premium_users = db.get("premium_users", [])
        banned_users = db.get("banned_users", [])
        if not users:
            text = "👥 <b>Foydalanuvchilar yo'q</b>"
        else:
            text = f"👥 <b>Foydalanuvchilar ({len(users)} ta):</b>\n\n"
            for i, (u_id, info) in enumerate(list(users.items())[:25], 1):
                badges = ""
                if str(u_id) in map(str, premium_users): badges += " 💎"
                if str(u_id) in map(str, banned_users): badges += " 🚫"
                name = info.get("name", "—")
                uname = f"@{info.get('username')}" if info.get("username") else ""
                lang_flag = {"uz": "🇺🇿", "ru": "🇷🇺", "en": "🇬🇧"}.get(info.get("lang", "uz"), "🌐")
                text += f"{i}. {lang_flag} <code>{u_id}</code> — {name} {uname}{badges}\n"
            if len(users) > 25:
                text += f"\n... va yana <b>{len(users) - 25}</b> ta"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_groups":
        groups = db.get("groups", {})
        if not groups:
            text = "🏘 <b>Guruhlar yo'q</b>"
        else:
            text = f"🏘 <b>Guruhlar ({len(groups)} ta):</b>\n\n"
            for i, (g_id, info) in enumerate(list(groups.items())[:20], 1):
                title = info.get("title", "—")
                joined = info.get("joined", "")[:10]
                text += f"{i}. <code>{g_id}</code> — <b>{title}</b> ({joined})\n"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_stats":
        stats = db.get("stats", [])
        users_count = len(db.get("users", {}))
        premium_count = len(db.get("premium_users", []))
        banned_count = len(db.get("banned_users", []))
        groups_count = len(db.get("groups", {}))
        top = get_top_servers(5)
        sep = "━" * 20
        text = f"📊 <b>Bot To'liq Statistikasi</b>\n<code>{sep}</code>\n\n"
        text += f"👥 Foydalanuvchilar: <b>{users_count}</b>\n"
        text += f"💎 Premium: <b>{premium_count}</b>\n"
        text += f"🚫 Banlangan: <b>{banned_count}</b>\n"
        text += f"🏘 Guruhlar: <b>{groups_count}</b>\n"
        text += f"📋 Jami so'rovlar: <b>{len(stats)}</b>\n"
        text += f"📢 Broadcast: <b>{db.get('broadcast_count', 0)}</b>\n\n"
        if top:
            text += "🏆 <b>Top 5 serverlar:</b>\n"
            medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
            for i, (srv, cnt) in enumerate(top):
                text += f"{medals[i]} <code>{srv}</code> — <b>{cnt}</b>\n"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_premium_list":
        premium_users = db.get("premium_users", [])
        users = db.get("users", {})
        if not premium_users:
            text = "💎 <b>Premium foydalanuvchilar yo'q</b>"
        else:
            text = f"💎 <b>Premium ({len(premium_users)} ta):</b>\n\n"
            for i, u_id in enumerate(premium_users, 1):
                name = users.get(str(u_id), {}).get("name", "—")
                text += f"{i}. <code>{u_id}</code> — {name}\n"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_ban_list":
        banned_users = db.get("banned_users", [])
        users = db.get("users", {})
        if not banned_users:
            text = "🚫 <b>Banlangan foydalanuvchilar yo'q</b>"
        else:
            text = f"🚫 <b>Banlangan ({len(banned_users)} ta):</b>\n\n"
            for i, u_id in enumerate(banned_users, 1):
                name = users.get(str(u_id), {}).get("name", "—")
                text += f"{i}. <code>{u_id}</code> — {name}\n"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_admin_list":
        all_admins = db.get("admin_ids", [7607916773])
        users = db.get("users", {})
        text = f"👑 <b>Adminlar ({len(all_admins)} ta):</b>\n\n"
        for i, a_id in enumerate(all_admins, 1):
            name = users.get(str(a_id), {}).get("name", "—")
            text += f"{i}. 👑 <code>{a_id}</code> — {name}\n"
        try:
            await call.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_broadcast":
        await call.message.answer(t("uz", "broadcast_ask"))
        await state.set_state(AdminState.broadcast)
        await call.answer()

    elif data == "adm_broadcast_groups":
        groups = db.get("groups", {})
        if not groups:
            await call.answer("❌ Hech qanday guruh yo'q!", show_alert=True)
            return
        await call.message.answer(t("uz", "broadcast_group_ask"))
        await state.set_state(AdminState.broadcast_group)
        await call.answer()

    elif data == "adm_give_premium":
        users = db.get("users", {})
        premium_users = db.get("premium_users", [])
        free_users = {u_id: info for u_id, info in users.items() if str(u_id) not in map(str, premium_users)}
        if not free_users:
            await call.answer("✅ Barcha foydalanuvchilar Premium!", show_alert=True)
            return
        buttons = []
        for u_id, info in list(free_users.items())[:20]:
            name = info.get("name", u_id)[:20]
            buttons.append([InlineKeyboardButton(text=f"➕ {name} ({u_id})", callback_data=f"give_pr::{u_id}")])
        buttons.append([InlineKeyboardButton(text="✏️ ID kiritish", callback_data="give_pr_manual")])
        buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_refresh")])
        try:
            await call.message.edit_text(
                "💎 <b>Premium berish:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_remove_premium":
        premium_users = db.get("premium_users", [])
        users = db.get("users", {})
        if not premium_users:
            await call.answer("❌ Premium foydalanuvchi yo'q!", show_alert=True)
            return
        buttons = []
        for u_id in premium_users[:20]:
            name = users.get(str(u_id), {}).get("name", str(u_id))[:20]
            buttons.append([InlineKeyboardButton(text=f"➖ {name} ({u_id})", callback_data=f"remove_pr::{u_id}")])
        buttons.append([InlineKeyboardButton(text="✏️ ID kiritish", callback_data="remove_pr_manual")])
        buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_refresh")])
        try:
            await call.message.edit_text(
                "💎 <b>Premium olish:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await call.answer()

    elif data == "adm_ban":
        await call.message.answer(t("uz", "ban_ask"))
        await state.set_state(AdminState.ban_user)
        await call.answer()

    elif data == "adm_unban":
        await call.message.answer(t("uz", "unban_ask"))
        await state.set_state(AdminState.unban_user)
        await call.answer()

    elif data == "adm_add_admin":
        await call.message.answer(t("uz", "admin_add_ask"))
        await state.set_state(AdminState.add_admin)
        await call.answer()

    elif data == "adm_remove_admin":
        all_admins = db.get("admin_ids", [7607916773])
        users = db.get("users", {})
        buttons = []
        for a_id in all_admins:
            if int(a_id) == 7607916773:
                continue  # Asosiy adminni o'chirib bo'lmaydi
            name = users.get(str(a_id), {}).get("name", str(a_id))[:20]
            buttons.append([InlineKeyboardButton(text=f"❌ {name} ({a_id})", callback_data=f"del_admin::{a_id}")])
        if not buttons:
            await call.answer("❌ O'chirish mumkin bo'lgan admin yo'q!", show_alert=True)
            return
        buttons.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_refresh")])
        try:
            await call.message.edit_text(
                "👑 <b>Admin o'chirish:</b>",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                parse_mode="HTML"
            )
        except TelegramBadRequest:
            pass
        await call.answer()

# ================= PREMIUM TOGGLE =================
@dp.callback_query(F.data.startswith("give_pr::"))
async def cb_give_premium(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    u_id = call.data.split("::")[1]
    db = load_db()
    name = db.get("users", {}).get(str(u_id), {}).get("name", u_id)
    if str(u_id) not in map(str, db.get("premium_users", [])):
        db.setdefault("premium_users", []).append(str(u_id))
        save_db(db)
        await call.answer(t("uz", "premium_given", uid=u_id, name=name), show_alert=True)
        try:
            await bot.send_message(int(u_id),
                "🎉 Tabriklaymiz! Sizga 💎 <b>Premium</b> berildi!\n\nEndi barcha imkoniyatlardan foydalaning!",
                parse_mode="HTML")
        except Exception:
            pass
    else:
        await call.answer("✅ Allaqachon Premium!", show_alert=True)

@dp.callback_query(F.data == "give_pr_manual")
async def cb_give_pr_manual(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    await call.message.answer("💎 Premium bermoqchi bo'lgan foydalanuvchi ID sini kiriting:")
    await state.set_state(AdminState.manual_premium_uid)
    await call.answer()

@dp.callback_query(F.data == "remove_pr_manual")
async def cb_remove_pr_manual(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    await call.message.answer("💎 Premium bekor qilmoqchi bo'lgan foydalanuvchi ID sini kiriting:")
    await state.set_state(AdminState.manual_remove_premium_uid)
    await call.answer()

@dp.callback_query(F.data.startswith("remove_pr::"))
async def cb_remove_premium(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    u_id = call.data.split("::")[1]
    db = load_db()
    name = db.get("users", {}).get(str(u_id), {}).get("name", u_id)
    db["premium_users"] = [x for x in db.get("premium_users", []) if str(x) != str(u_id)]
    save_db(db)
    await call.answer(t("uz", "premium_removed", uid=u_id, name=name), show_alert=True)
    try:
        await bot.send_message(int(u_id), "ℹ️ Sizning 💎 Premium obunangiz tugadi.\n\nQayta olish: @QahramonovK", parse_mode="HTML")
    except Exception:
        pass

@dp.callback_query(F.data.startswith("del_admin::"))
async def cb_del_admin(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("❌", show_alert=True)
        return
    a_id = call.data.split("::")[1]
    if int(a_id) == 7607916773:
        await call.answer("❌ Asosiy adminni o'chirib bo'lmaydi!", show_alert=True)
        return
    db = load_db()
    db["admin_ids"] = [x for x in db.get("admin_ids", []) if int(x) != int(a_id)]
    save_db(db)
    await call.answer(t("uz", "admin_removed", uid=a_id), show_alert=True)

# ================= ADMIN FSM HANDLERS =================
@dp.message(AdminState.broadcast)
async def fsm_broadcast(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    db = load_db()
    users = db.get("users", {})
    ok = fail = 0
    status_msg = await message.reply("📤 Yuborilmoqda... 0%")
    total = len(users)
    for idx, u_id in enumerate(users.keys()):
        try:
            await bot.send_message(
                int(u_id),
                f"📢 <b>Admindan xabar:</b>\n\n{message.html_text}",
                parse_mode="HTML"
            )
            ok += 1
        except Exception:
            fail += 1
        if (ok + fail) % 10 == 0:
            pct = int((ok + fail) / total * 100) if total else 100
            try:
                await status_msg.edit_text(f"📤 Yuborilmoqda... {pct}%\n✅ {ok} ❌ {fail}")
            except Exception:
                pass
        await asyncio.sleep(0.05)
    
    db["broadcast_count"] = db.get("broadcast_count", 0) + 1
    save_db(db)
    await status_msg.edit_text(t("uz", "broadcast_done", ok=ok, fail=fail), parse_mode="HTML")
    await state.clear()

@dp.message(AdminState.broadcast_group)
async def fsm_broadcast_group(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    db = load_db()
    groups = db.get("groups", {})
    ok = fail = 0
    status_msg = await message.reply(f"📤 Guruhlaarga yuborilmoqda... (0/{len(groups)})")
    for g_id in groups.keys():
        try:
            await bot.send_message(
                int(g_id),
                f"📢 <b>Admindan xabar:</b>\n\n{message.html_text}",
                parse_mode="HTML"
            )
            ok += 1
        except Exception:
            fail += 1
            # Remove invalid group
            if fail:
                remove_group(g_id)
        await asyncio.sleep(0.1)
    await status_msg.edit_text(
        f"🏘 Guruh broadcast tugadi!\n\n✅ Yuborildi: <b>{ok}</b>\n❌ Xato: <b>{fail}</b>",
        parse_mode="HTML"
    )
    await state.clear()

@dp.message(AdminState.ban_user)
async def fsm_ban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    u_id = message.text.strip()
    if not u_id.isdigit():
        await message.reply("❌ Faqat raqamli ID kiriting!")
        return
    db = load_db()
    name = db.get("users", {}).get(u_id, {}).get("name", u_id)
    if u_id not in map(str, db.get("banned_users", [])):
        db.setdefault("banned_users", []).append(u_id)
        save_db(db)
        await message.reply(t("uz", "banned", uid=u_id, name=name))
        try:
            await bot.send_message(int(u_id), t("uz", "banned_user"))
        except Exception:
            pass
    else:
        await message.reply(f"⚠️ {u_id} allaqachon banlangan")
    await state.clear()

@dp.message(AdminState.unban_user)
async def fsm_unban(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    u_id = message.text.strip()
    db = load_db()
    db["banned_users"] = [x for x in db.get("banned_users", []) if str(x) != str(u_id)]
    save_db(db)
    await message.reply(t("uz", "unbanned", uid=u_id))
    await state.clear()

@dp.message(AdminState.add_admin)
async def fsm_add_admin(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    u_id = message.text.strip()
    if not u_id.isdigit():
        await message.reply("❌ Faqat raqamli ID kiriting!")
        return
    db = load_db()
    if int(u_id) not in [int(x) for x in db.get("admin_ids", [])]:
        db.setdefault("admin_ids", []).append(int(u_id))
        save_db(db)
        await message.reply(t("uz", "admin_added", uid=u_id))
        try:
            await bot.send_message(int(u_id), "👑 Siz admin qildingiz! /admin")
        except Exception:
            pass
    else:
        await message.reply(f"⚠️ {u_id} allaqachon admin")
    await state.clear()

@dp.message(AdminState.manual_premium_uid)
async def fsm_manual_premium(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    u_id = message.text.strip()
    if not u_id.isdigit():
        await message.reply("❌ Faqat raqamli ID kiriting!")
        await state.clear()
        return
    db = load_db()
    name = db.get("users", {}).get(u_id, {}).get("name", u_id)
    if u_id not in map(str, db.get("premium_users", [])):
        db.setdefault("premium_users", []).append(u_id)
        save_db(db)
        await message.reply(t("uz", "premium_given", uid=u_id, name=name))
        try:
            await bot.send_message(int(u_id),
                "🎉 Sizga 💎 <b>Premium</b> berildi! @mcveryBot", parse_mode="HTML")
        except Exception:
            pass
    else:
        await message.reply(f"✅ {u_id} allaqachon Premium!")
    await state.clear()

@dp.message(AdminState.manual_remove_premium_uid)
async def fsm_manual_remove_premium(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    u_id = message.text.strip()
    db = load_db()
    name = db.get("users", {}).get(u_id, {}).get("name", u_id)
    db["premium_users"] = [x for x in db.get("premium_users", []) if str(x) != u_id]
    save_db(db)
    await message.reply(t("uz", "premium_removed", uid=u_id, name=name))
    await state.clear()

# ================= SERVER STATUS =================
async def send_server_status(message: types.Message, ip: str):
    uid = str(message.from_user.id)
    lang = get_user_lang(uid)

    loading = await message.reply(t(lang, "fetching"), parse_mode="HTML")
    data = await fetch_server_info(ip)
    add_query_stat(uid, ip)

    if not data or not data.get("online") and not data.get("motd") and not data.get("players"):
        # Try to build offline response
        text = (
            f"🔴 Offline  🖥 <b>{ip}</b>\n\n"
            f"⚠️ Server javob bermadi yoki topilmadi.\n"
            f"🕐 {format_time()}"
        )
        try:
            await loading.edit_text(text, parse_mode="HTML")
        except TelegramBadRequest:
            await message.reply(text, parse_mode="HTML")
        return

    text = build_server_text(ip, data, uid, lang)
    try:
        await loading.edit_text(text, reply_markup=server_keyboard(ip, lang), parse_mode="HTML")
    except TelegramBadRequest:
        await message.reply(text, reply_markup=server_keyboard(ip, lang), parse_mode="HTML")

@dp.callback_query(F.data.startswith("more::"))
async def cb_more(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    data = await fetch_server_info(ip)
    if not data:
        await call.answer("❌ Server topilmadi", show_alert=True)
        return
    text = build_more_text(ip, data, uid, lang)
    try:
        await call.message.edit_text(text, reply_markup=more_keyboard(ip, lang), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

@dp.callback_query(F.data.startswith("recheck::"))
async def cb_recheck(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    await call.answer("⏳ Tekshirilmoqda...")
    data = await fetch_server_info(ip, force=True)
    add_query_stat(uid, ip)
    if not data:
        await call.answer("❌ Server javob bermadi", show_alert=True)
        return
    text = build_server_text(ip, data, uid, lang)
    try:
        await call.message.edit_text(text, reply_markup=server_keyboard(ip, lang), parse_mode="HTML")
    except TelegramBadRequest:
        pass

@dp.callback_query(F.data.startswith("refresh::"))
async def cb_refresh(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    data = await fetch_server_info(ip, force=True)
    if not data:
        await call.answer("❌ Server topilmadi", show_alert=True)
        return
    text = build_more_text(ip, data, uid, lang)
    try:
        await call.message.edit_text(text, reply_markup=more_keyboard(ip, lang), parse_mode="HTML")
        await call.answer("✅ Yangilandi!")
    except TelegramBadRequest:
        await call.answer("✅ Yangilandi")

@dp.callback_query(F.data.startswith("back::"))
async def cb_back_server(call: types.CallbackQuery):
    ip = call.data.split("::")[1]
    uid = str(call.from_user.id)
    lang = get_user_lang(uid)
    data = await fetch_server_info(ip)
    if not data:
        await call.answer("❌ Server topilmadi", show_alert=True)
        return
    text = build_server_text(ip, data, uid, lang)
    try:
        await call.message.edit_text(text, reply_markup=server_keyboard(ip, lang), parse_mode="HTML")
    except TelegramBadRequest:
        pass
    await call.answer()

# ================= GROUP HANDLING =================
@dp.my_chat_member()
async def on_my_chat_member(event: ChatMemberUpdated):
    """Bot guruhga qo'shilganda yoki chiqarilganda"""
    chat = event.chat
    if chat.type in ("group", "supergroup"):
        new_status = event.new_chat_member.status
        if new_status == "member" or new_status == "administrator":
            register_group(str(chat.id), chat.title or "Unknown")
            try:
                await bot.send_message(
                    chat.id,
                    f"👋 Assalomu alaykum!\n\n🖥 <b>Minecraft Server Monitor</b> botiga xush kelibsiz!\n\nServer manzilini yuboring va statistikani ko'ring!\n\n💎 Premium: @QahramonovK",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        elif new_status in ("left", "kicked", "banned"):
            remove_group(str(chat.id))

# ================= ADMIN COMMAND =================
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    uid = str(message.from_user.id)
    if not is_admin(uid):
        lang = get_user_lang(uid)
        await message.reply(t(lang, "admin_not"))
        return
    db = load_db()
    sep = "━" * 20
    text = (
        f"⚙️ <b>Admin Panel</b>\n"
        f"<code>{sep}</code>\n"
        f"👤 Admin: <b>{message.from_user.full_name}</b>\n\n"
        f"📊 <b>Statistika:</b>\n"
        f"👥 Foydalanuvchilar: <b>{len(db.get('users', {}))}</b>\n"
        f"💎 Premium: <b>{len(db.get('premium_users', []))}</b>\n"
        f"🚫 Banlangan: <b>{len(db.get('banned_users', []))}</b>\n"
        f"🏘 Guruhlar: <b>{len(db.get('groups', {}))}</b>\n"
        f"📋 So'rovlar: <b>{len(db.get('stats', []))}</b>\n"
        f"📢 Broadcast: <b>{db.get('broadcast_count', 0)}</b>"
    )
    await message.reply(text, reply_markup=admin_keyboard(), parse_mode="HTML")

# ================= TEXT HANDLER =================
@dp.message(F.text)
async def handle_text(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    uid = str(message.from_user.id)

    if is_banned(uid):
        lang = get_user_lang(uid)
        await message.reply(t(lang, "banned_user"))
        return

    text = message.text.strip()

    if text.startswith("/"):
        return

    # Group chat: only respond to valid server addresses
    if message.chat.type in ("group", "supergroup"):
        if not (DOMAIN_REGEX.match(text) or IP_REGEX.match(text)):
            return  # Guruhlarda xato xabar ko'rsatmaymiz

    if DOMAIN_REGEX.match(text) or IP_REGEX.match(text):
        # Spam-himoya: bir foydalanuvchi juda tez-tez so'rov yubormasin
        now = time.time()
        last = USER_COOLDOWN.get(uid, 0)
        if not is_admin(uid) and (now - last) < COOLDOWN_SECONDS:
            wait = round(COOLDOWN_SECONDS - (now - last), 1)
            await message.reply(f"⏳ Iltimos, {wait} soniya kuting...")
            return
        USER_COOLDOWN[uid] = now

        # Register user if not registered
        name = message.from_user.full_name or "Foydalanuvchi"
        username = message.from_user.username or ""
        register_user(uid, name, username=username)
        await send_server_status(message, text)
    else:
        # Oddiy gaplarga (salom, matn va h.k.) umuman javob bermaymiz.
        # Faqat "domen/IP yozishga urinib, xato qilgan" holatlarda yordam ko'rsatamiz
        # (masalan nuqta bor, lekin format noto'g'ri: "play. hypixel .net")
        looks_like_attempt = "." in text and " " not in text and len(text) >= 4
        if looks_like_attempt:
            lang = get_user_lang(uid)
            await message.reply(t(lang, "server_invalid"), parse_mode="HTML")
        # aks holda - hech narsa demaymiz, xuddi guruhdagidek

# ================= RENDER UCHUN MINIMAL WEB SERVER =================
# Render "Web Service" turi portni tinglab turishni talab qiladi.
# Bu funksiya faqat shu talabni qondirish uchun - botning asosiy ishiga (polling) tegmaydi.
from aiohttp import web as _aioweb

async def _handle_ping(request):
    return _aioweb.Response(text="Minecraft Stats Bot ishlab turibdi ✅")

async def start_keepalive_server():
    app = _aioweb.Application()
    app.router.add_get("/", _handle_ping)
    runner = _aioweb.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = _aioweb.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"✅ Keep-alive server {port}-portda ishga tushdi")

# ================= RUN =================
async def main():
    print("✅ Minecraft Stats Bot v2.0 ishga tushdi!")
    # Avval o'rnatilgan webhook bo'lsa (polling bilan to'qnashadi), uni tozalaymiz
    await bot.delete_webhook(drop_pending_updates=True)
    await start_keepalive_server()
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
