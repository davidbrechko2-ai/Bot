import telebot
from telebot import types, custom_filters
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import random
import json
import os
import logging

# --- [0] НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8610869446:AAHlOyFAteMgPXZe8Ehizb-QCpP1VpCmfhU"
ADMINS = [1674945230, 7908057052]  # ID администраторов (числа int)

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

# Доступные позиции (включая Вратаря)
POSITIONS = ["LF", "CF", "RF", "CM", "LB", "RB", "GK"]

# --- [2] СОСТОЯНИЯ ДЛЯ АДМИН-ПАНЕЛИ (FSM) ---
class AddCardState(StatesGroup):
    name = State()
    ovr = State()
    event = State()
    pos = State()
    rarity = State()
    stars = State()
    photo = State()

# --- [3] БАЗА ДАННЫХ И ХЕЛПЕРЫ ---
def load_db(key):
    if not os.path.exists(FILES[key]):
        res = {} if key != 'cards' else []
        save_db(res, key)
        return res
    with open(FILES[key], 'r', encoding='utf-8') as f:
        try: 
            return json.load(f)
        except Exception: 
            res = {} if key != 'cards' else []
            save_db(res, key)
            return res

def save_db(data, key):
    with open(FILES[key], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_stars(count):
    try: 
        return "⭐️" * int(count)
    except Exception: 
        return "⭐️"

def is_admin(m):
    return m.from_user.id in ADMINS

def async_with_state(m, key, value):
    with bot.retrieve_data(m.from_user.id, m.chat.id) as data:
        data[key] = value

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

# --- [5] АВАРІЙНЫЙ СБРОС СОСТОЯНИЙ ---
@bot.message_handler(commands=['clear', 'сброс', 'stop'], state="*")
def cancel_any_state(m):
    bot.delete_state(m.from_user.id, m.chat.id)
    bot.send_message(m.chat.id, "🔄 Все зависшие процессы и состояния успешно сброшены!", reply_markup=main_kb(m.from_user))

# --- [6] ЛОГИКА ИГРЫ ---

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}
        save_db(users, 'users')
    bot.send_message(m.chat.id, "👋 Привет! Это бот СЛС карточек с функцией менеджмента состава.\n\n"
                                "Если бот когда-либо перестанет отвечать на кнопки, отправьте команду /clear", 
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
    except Exception:
        bot.send_message(m.chat.id, "🎁 **Бесплатный пак готов!** (Изображение пака не найдено)", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["open_pack", "cancel_pack"])
def pack_callback(call):
    uid = str(call.from_user.id)
    if call.data == "cancel_pack":
        bot.answer_callback_query(call.id, "Открыто позже")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception: pass
        return

    bot.answer_callback_query(call.id, "✨ Открываем пак...")
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass

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
    except Exception:
        bot.send_message(call.message.chat.id, f"🏃‍♂️ **Карточка успешно выбита!**\n\n{caption}", parse_mode="Markdown")

# --- [7] СИСТЕМА СОСТАВА (GK ВКЛЮЧЕН) ---
def get_squad_text(uid):
    squads = load_db('squads')
    my_squad = squads.get(uid, {p: None for p in POSITIONS})
    
    lf = my_squad.get("LF") or "[Пусто]"
    cf = my_squad.get("CF") or "[Пусто]"
    rf = my_squad.get("RF") or "[Пусто]"
    cm = my_squad.get("CM") or "[Пусто]"
    lb = my_squad.get("LB") or "[Пусто]"
    rb = my_squad.get("RB") or "[Пусто]"
    gk = my_squad.get("GK") or "[Пусто]"
    
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    total_ovr = 0
    players_count = 0
    
    for pos in POSITIONS:
        p_name = my_squad.get(pos)
        if p_name:
            card = next((c for c in my_cards if c['name'] == p_name), None)
            if card and str(card.get('ovr', '')).isdigit():
                total_ovr += int(card['ovr'])
                players_count += 1
                
    avg_ovr = round(total_ovr / players_count) if players_count > 0 else 0

    return (
        f"📋 **ВАШ ТЕКУЩИЙ СОСТАВ**\n"
        f"📊 Общий OVR состава: `{avg_ovr}`\n"
        f" — — — — — — — — — — — —\n\n"
        f"🔥 **АТАКА:**\n LF: `{lf}` | CF: `{cf}` | RF: `{rf}`\n\n"
        f"⚡️ **ПОЛУЗАЩИТА:**\n CM: `{cm}`\n\n"
        f"🛡 **ЗАЩИТА:**\n LB: `{lb}` | RB: `{rb}`\n\n"
        f"🧤 **ВРАТАРЬ:**\n GK: `{gk}`\n\n"
        f" — — — — — — — — — — — —\n"
        f" Нажмите на кнопку ниже, чтобы изменить позицию:"
    )

@bot.message_handler(func=lambda m: m.text == "📋 Мой Состав")
def view_squad(m):
    uid = str(m.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(*[types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS])
    bot.send_message(m.chat.id, get_squad_text(uid), reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pos_"))
def choose_player_for_pos(call):
    uid = str(call.from_user.id)
    target_pos = call.data.replace("pos_", "")
    colls = load_db('colls')
    eligible_cards = [c for c in colls.get(uid, []) if str(c.get('pos', '')).upper() == target_pos.upper()]
    
    if not eligible_cards:
        bot.answer_callback_query(call.id, f"⚠️ У вас нет игроков на позицию {target_pos}!", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for card in eligible_cards:
        markup.add(types.InlineKeyboardButton(f"🏃‍♂️ {card['name']} (OVR: {card.get('ovr', '—')})", callback_data=f"set_{target_pos}_{card['name']}"))
    markup.add(types.InlineKeyboardButton("⬅️ Назад к составу", callback_data="back_to_squad"))
    
    bot.edit_message_text(f"🎯 **Выберите игрока на позицию {target_pos}:**", 
                          call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("set_"))
def set_player_final(call):
    uid = str(call.from_user.id)
    data_parts = call.data.split("_")
    pos = data_parts[1]
    player_name = "_".join(data_parts[2:])
    
    squads = load_db('squads')
    if uid not in squads: squads[uid] = {p: None for p in POSITIONS}
    squads[uid][pos] = player_name
    save_db(squads, 'squads')
    
    bot.answer_callback_query(call.id, f"✅ Поставлен на {pos}!")
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(*[types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS])
    bot.edit_message_text(get_squad_text(uid), call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_squad")
def back_squad_callback(call):
    uid = str(call.from_user.id)
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(*[types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS])
    bot.edit_message_text(get_squad_text(uid), call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- [8] АДМИН-ПАНЕЛЬ ---

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель" and is_admin(m))
def admin_panel(m):
    bot.send_message(m.chat.id, "🛠 **Панель администратора**\nВыберите действие:", 
                     reply_markup=admin_kb(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📊 Статистика базы" and is_admin(m))
def admin_stats(m):
    cards = load_db('cards')
    users = load_db('users')
    text = (f"📈 **Статистика Бот-системы:**\n"
            f"└ Карточек создано в базе: `{len(cards)}`\n"
            f"└ Всего уникальных игроков: `{len(users)}`")
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

# Шаг 1: Имя
@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту" and is_admin(m))
def start_add_card(m):
    bot.set_state(m.from_user.id, AddCardState.name, m.chat.id)
    bot.send_message(m.chat.id, "1️⃣ Введите **ИМЯ** игрока:", parse_mode="Markdown", 
                     reply_markup=types.ReplyKeyboardRemove())

# Шаг 2: OVR
@bot.message_handler(state=AddCardState.name)
def process_name(m):
    async_with_state(m, 'name', m.text)
    bot.set_state(m.from_user.id, AddCardState.ovr, m.chat.id)
    bot.send_message(m.chat.id, f"2️⃣ Введите общий рейтинг **OVR** (число) для {m.text}:", parse_mode="Markdown")

# Шаг 3: Событие
@bot.message_handler(state=AddCardState.ovr)
def process_ovr(m):
    if not m.text.isdigit():
        return bot.send_message(m.chat.id, "❌ Ошибка! Введите корректное число (например: 89):")
    async_with_state(m, 'ovr', m.text)
    bot.set_state(m.from_user.id, AddCardState.event, m.chat.id)
    bot.send_message(m.chat.id, "3️⃣ Введите **НАЗВАНИЕ СОБЫТИЯ** (например: Редкая, TOTS, СЛС):", parse_mode="Markdown")

# Шаг 4: Позиция
@bot.message_handler(state=AddCardState.event)
def process_event(m):
    async_with_state(m, 'event', m.text)
    bot.set_state(m.from_user.id, AddCardState.pos, m.chat.id)
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.add(*POSITIONS)
    bot.send_message(m.chat.id, "4️⃣ Выберите одну из **ПОЗИЦИЙ**:", reply_markup=markup, parse_mode="Markdown")

# Шаг 5: Редкость
@bot.message_handler(state=AddCardState.pos)
def process_pos(m):
    if m.text.upper() not in POSITIONS:
        return bot.send_message(m.chat.id, "❌ Воспользуйтесь кнопками на клавиатуре для выбора позиции!")
    async_with_state(m, 'pos', m.text.upper())
    bot.set_state(m.from_user.id, AddCardState.rarity, m.chat.id)
    bot.send_message(m.chat.id, "5️⃣ Введите **РЕДКОСТЬ** текста (например: EPIC, LEGENDARY):", reply_markup=types.ReplyKeyboardRemove(), parse_mode="Markdown")

# Шаг 6: Звезды
@bot.message_handler(state=AddCardState.rarity)
def process_rarity(m):
    async_with_state(m, 'rarity', m.text.upper())
    bot.set_state(m.from_user.id, AddCardState.stars, m.chat.id)
    bot.send_message(m.chat.id, "6️⃣ Введите **КОЛИЧЕСТВО ЗВЕЗД** (число от 1 до 5):", parse_mode="Markdown")

# Шаг 7: Фотография
@bot.message_handler(state=AddCardState.stars)
def process_stars(m):
    if not m.text.isdigit() or not (1 <= int(m.text) <= 5):
        return bot.send_message(m.chat.id, "❌ Ошибка! Нужно ввести число строго от 1 до 5!")
    async_with_state(m, 'stars', int(m.text))
    bot.set_state(m.from_user.id, AddCardState.photo, m.chat.id)
    bot.send_message(m.chat.id, "7️⃣ Отправьте **ФОТО** для карточки:", parse_mode="Markdown")

# Сохранение карты
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
    bot.send_message(m.chat.id, f"✅ Новая карточка игрока **{new_card['name']}** успешно добавлена!", 
                     reply_markup=admin_kb(), parse_mode="Markdown")

# Удаление карт
@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту" and is_admin(m))
def delete_card_menu(m):
    cards = load_db('cards')
    if not cards: return bot.send_message(m.chat.id, "❌ База данных карточек пуста.")
    
    markup = types.InlineKeyboardMarkup()
    for c in cards[-15:]:
        markup.add(types.InlineKeyboardButton(f"❌ {c['name']} ({c['pos']} | OVR: {c['ovr']})", callback_data=f"del_{c['name']}"))
    bot.send_message(m.chat.id, "Выберите карточку для удаления (последние 15):", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def process_delete(call):
    name_to_delete = call.data.replace("del_", "")
    cards = load_db('cards')
    save_db([c for c in cards if c['name'] != name_to_delete], 'cards')
    bot.edit_message_text(f"✅ Карточка **{name_to_delete}** успешно удалена из базы.", call.message.chat.id, call.message.message_id)

# --- [9] СТАНДАРТНЫЕ КОМАНДЫ ПОЛЬЗОВАТЕЛЕЙ ---

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def top_players(m):
    users = load_db('users')
    sorted_users = sorted(users.items(), key=lambda x: x[1]['score'], reverse=True)
    text = "🏆 **ТОП-10 ИГРОКОВ:**\n\n"
    for i, (uid, data) in enumerate(sorted_users[:10], 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} @{data['username']} — {data['score']:,} очков\n"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def my_collection(m):
    uid = str(m.from_user.id)
    my_cards = load_db('colls').get(uid, [])
    if not my_cards: 
        return bot.send_message(m.chat.id, "🗂 Ваша личная коллекция пока пуста!")
    
    text = f"🗂 **ВАША КОЛЛЕКЦИЯ ({len(my_cards)} шт.):**\n\n"
    for card in my_cards:
        c_name = card.get('name', 'Без имени')
        c_pos = card.get('pos', '—')
        c_ovr = card.get('ovr', '—')
        c_stars = get_stars(card.get('stars', 1))
        text += f"• {c_name} | Поз: {c_pos} | OVR: {c_ovr} ({c_stars})\n"
        
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    uid = str(m.from_user.id)
    u = load_db('users').get(uid, {"score": 0, "username": m.from_user.username or f"user_{uid}"})
    c = len(load_db('colls').get(uid, []))
    text = f"👤 **ВАШ ПРОФИЛЬ**\n — — — — — — — —\n🆔 ID: `{uid}`\n💠 Очки: `{u['score']:,}`\n🗂 Коллекция: {c} шт.\n — — — — — — — —"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def prem(m):
    bot.send_message(m.chat.id, "💎 **Премиум статус**\n\n• Крутки без КД\n✉️ Купить: @verybigsun", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_home(m):
    bot.send_message(m.chat.id, "Вы вернулись в главное меню:", reply_markup=main_kb(m.from_user))

# Регистрация системных фильтров
bot.add_custom_filter(custom_filters.StateFilter(bot))

# --- [10] ЗАПУСК БОТА ---
if __name__ == '__main__':
    print("Бот успешно инициализирован и слушает новый токен...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Критическое исключение при старте пуллинга: {e}")
