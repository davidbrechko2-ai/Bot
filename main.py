import telebot
from telebot import types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import random
import json
import os

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8711407704:AAGZWhw8jXSjoofD2w7MlFJy-6_guVXYU0E"
ADMINS = [1674945230, 7908057052] # Используйте числа (int)

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

FILES = {
    'cards': 'cards_data.json', 
    'colls': 'collections_data.json', 
    'users': 'users_stats.json',
    'squads': 'squads_data.json'
}

POSITIONS = ["LF", "CF", "RF", "CM", "LB", "RB"]

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

# --- [5] АДМИН ПАНЕЛЬ (НОВАЯ ЛОГИКА) ---

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель" and is_admin(m))
def admin_panel(m):
    bot.send_message(m.chat.id, "🛠 **Панель администратора**\nВыберите действие:", 
                     reply_markup=admin_kb(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика базы" and is_admin(m))
def admin_stats(m):
    cards = load_db('cards')
    users = load_db('users')
    text = (f"📈 **Статистика:**\n"
            f"└ Карточек в базе: `{len(cards)}`\n"
            f"└ Всего игроков: `{len(users)}`")
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

# --- ПРОЦЕСС ДОБАВЛЕНИЯ КАРТЫ (FSM) ---

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту" and is_admin(m))
def start_add_card(m):
    bot.set_state(m.from_user.id, AddCardState.name, m.chat.id)
    bot.send_message(m.chat.id, "1️⃣ Введите **ИМЯ** игрока:", parse_mode="Markdown", 
                     reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(state=AddCardState.name)
def process_name(m):
    async_with_state(m, 'name', m.text)
    bot.set_state(m.from_user.id, AddCardState.ovr, m.chat.id)
    bot.send_message(m.chat.id, f"2️⃣ Введите **OVR** (число) для {m.text}:")

@bot.message_handler(state=AddCardState.ovr)
def process_ovr(m):
    if not m.text.isdigit():
        return bot.send_message(m.chat.id, "❌ Ошибка! Введите число (например: 89)")
    async_with_state(m, 'ovr', m.text)
    bot.set_state(m.from_user.id, AddCardState.event, m.chat.id)
    bot.send_message(m.chat.id, "3️⃣ Введите **НАЗВАНИЕ СОБЫТИЯ** (например: TOTW):")

@bot.message_handler(state=AddCardState.event)
def process_event(m):
    async_with_state(m, 'event', m.text)
    bot.set_state(m.from_user.id, AddCardState.pos, m.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(*POSITIONS)
    bot.send_message(m.chat.id, "4️⃣ Выберите **ПОЗИЦИЮ**:", reply_markup=markup)

@bot.message_handler(state=AddCardState.pos)
def process_pos(m):
    if m.text.upper() not in POSITIONS:
        return bot.send_message(m.chat.id, "❌ Выберите позицию из кнопок!")
    async_with_state(m, 'pos', m.text.upper())
    bot.set_state(m.from_user.id, AddCardState.rarity, m.chat.id)
    bot.send_message(m.chat.id, "5️⃣ Введите **РЕДКОСТЬ** (например: EPIC):", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(state=AddCardState.rarity)
def process_rarity(m):
    async_with_state(m, 'rarity', m.text.upper())
    bot.set_state(m.from_user.id, AddCardState.stars, m.chat.id)
    bot.send_message(m.chat.id, "6️⃣ Введите **КОЛ-ВО ЗВЕЗД** (1-5):")

@bot.message_handler(state=AddCardState.stars)
def process_stars(m):
    if not m.text.isdigit() or not (1 <= int(m.text) <= 5):
        return bot.send_message(m.chat.id, "❌ Введите число от 1 до 5!")
    async_with_state(m, 'stars', int(m.text))
    bot.set_state(m.from_user.id, AddCardState.photo, m.chat.id)
    bot.send_message(m.chat.id, "7️⃣ Отправьте **ФОТО** карточки:")

@bot.message_handler(state=AddCardState.photo, content_types=['photo'])
def process_final_photo(m):
    with bot.retrieve_data(m.from_user.id, m.chat.id) as data:
        new_card = {
            "name": data['name'],
            "ovr": data['ovr'],
            "event": data['event'],
            "pos": data['pos'],
            "rarity": data['rarity'],
            "stars": data['stars'],
            "photo": m.photo[-1].file_id
        }
    
    cards = load_db('cards')
    cards.append(new_card)
    save_db(cards, 'cards')
    
    bot.delete_state(m.from_user.id, m.chat.id)
    bot.send_message(m.chat.id, f"✅ Карта **{new_card['name']}** успешно добавлена!", 
                     reply_markup=admin_kb(), parse_mode="Markdown")

# --- Хелпер для FSM ---
def async_with_state(m, key, value):
    with bot.retrieve_data(m.from_user.id, m.chat.id) as data:
        data[key] = value

# --- УДАЛЕНИЕ ---
@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту" and is_admin(m))
def delete_card_menu(m):
    cards = load_db('cards')
    if not cards: return bot.send_message(m.chat.id, "❌ В базе нет карт.")
    
    markup = types.InlineKeyboardMarkup()
    # Показываем последние 15 карт, чтобы не перегружать инлайн
    for c in cards[-15:]:
        markup.add(types.InlineKeyboardButton(f"❌ {c['name']} ({c['ovr']})", callback_data=f"del_{c['name']}"))
    bot.send_message(m.chat.id, "Выберите карту для удаления (показаны последние 15):", reply_markup=markup)

# --- [6] ОСТАЛЬНАЯ ЛОГИКА (Ваша без изменений) ---

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_home(m):
    bot.send_message(m.chat.id, "Вы вернулись в меню:", reply_markup=main_kb(m))

# Не забудьте добавить фильтры в конце!
bot.add_custom_filter(custom_filters.StateFilter(bot))
bot.add_custom_filter(custom_filters.IsDigitFilter())

if __name__ == '__main__':
    print("Бот успешно запущен!")
    bot.infinity_polling()
