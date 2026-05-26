import telebot
from telebot import types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import random
import json
import os

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8711407704:AAGZWhw8jXSjoofD2w7MlFJy-6_guVXYU0E"
ADMINS = [1674945230, 7908057052] 

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

FILES = {
    'cards': 'cards_data.json', 
    'colls': 'collections_data.json', 
    'users': 'users_stats.json',
    'squads': 'squads_data.json'
}

STATS = {
    1: {"score": 1000},
    2: {"score": 2000},
    3: {"score": 4000},
    4: {"score": 6000},
    5: {"score": 10000}
}

# ТЕПЕРЬ С GK!
POSITIONS = ["LF", "CF", "RF", "CM", "LB", "RB", "GK"]

# --- [2] СОСТОЯНИЯ (FSM) ---
class AddCardState(StatesGroup):
    name = State()
    ovr = State()
    event = State()
    pos = State()
    rarity = State()
    stars = State()
    photo = State()

# --- [3] БД ФУНКЦИИ ---
def load_db(key):
    if not os.path.exists(FILES[key]):
        res = {} if key != 'cards' else []
        save_db(res, key)
        return res
    with open(FILES[key], 'r', encoding='utf-8') as f:
        try: return json.load(f)
        except: return {} if key != 'cards' else []

def save_db(data, key):
    with open(FILES[key], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_stars(count):
    try: return "⭐️" * int(count)
    except: return "⭐️"

def is_admin(m):
    return m.from_user.id in ADMINS

# --- [4] КЛАВИАТУРЫ ---
def main_kb(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Получить карту", "📋 Мой Состав")
    markup.row("🗂 Коллекция", "👤 Профиль")
    markup.row("🏆 Топ игроков", "💎 Премиум")
    if is_admin(user):
        markup.add("🛠 Админ-панель")
    return markup

def admin_kb():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("➕ Добавить карту", "🗑 Удалить карту")
    markup.row("📊 Статистика базы", "🏠 Назад в меню")
    return markup

# --- [5] ЛОГИКА ИГРЫ ---

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}
        save_db(users, 'users')
    bot.send_message(m.chat.id, "👋 Привет! Это бот СЛС карточек с функцией менеджмента состава.", 
                     reply_markup=main_kb(m.from_user), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll_start(m):
    cards = load_db('cards')
    if not cards: 
        return bot.send_message(m.chat.id, "❌ В игре пока нет карточек! Добавьте их через админ-панель.")

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎁 Открыть", callback_data="open_pack"))
    markup.row(types.InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_pack"))

    pack_img = '465d12ab-8fc3-4bc1-853e-dd4c3a10de12.png'
    try:
        with open(pack_img, 'rb') as photo:
            bot.send_photo(m.chat.id, photo, caption="🎁 **Бесплатный пак готов!**", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(m.chat.id, "🎁 **Бесплатный пак готов!**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["open_pack", "cancel_pack"])
def pack_callback(call):
    uid = str(call.from_user.id)
    if call.data == "cancel_pack":
        bot.answer_callback_query(call.id, "Открыто позже")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        return

    bot.answer_callback_query(call.id, "✨ Открываем пак...")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

    cards = load_db('cards')
    users = load_db('users')
    colls = load_db('colls')

    if not cards:
        return bot.send_message(call.message.chat.id, "❌ Ошибка: база карт пуста.")

    won = random.choice(cards)
    if uid not in colls: colls[uid] = []
    
    is_new = not any(c['name'] == won['name'] for c in colls[uid])
    base_pts = STATS.get(int(won.get('stars', 1)), {"score": 500})["score"]
    added_pts = base_pts if is_new else int(base_pts * 0.3)
    
    if uid not in users:
        users[uid] = {"score": 0, "username": call.from_user.username or f"user_{uid}"}

    users[uid]['score'] += int(added_pts)
    if is_new:
        colls[uid].append(won)
        save_db(colls, 'colls')
    save_db(users, 'users')
    
    status = "🆕 Новая карта!" if is_new else "♻️ Повторка"
    caption = (
        f"⚽️ **{won['name']}** ({status})\n"
        f"║ 📊 OVR: `{won.get('ovr', '—')}`\n"
        f"║ 🛡 {won.get('event', 'Обычная')}\n"
        f"║ ⚽️ POSITION: `{won.get('pos', '—')}`\n"
        f"║ ✨ {won.get('rarity', 'COMMON').upper()}\n"
        f" — — — — — — — — — —\n"
        f"📊 Рейтинг: {get_stars(won.get('stars', 1))}\n"
        f"💠 Очки: +{int(added_pts)} | Всего: {users[uid]['score']:,}"
    )
    try:
        bot.send_photo(call.message.chat.id, won['photo'], caption=caption, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"🏃‍♂️ **Карточка успешно выбита!**\n\n{caption}", parse_mode="Markdown")

# --- [6] СИСТЕМА СОСТАВА (О
