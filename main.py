import telebot
from telebot import types
import random
import time
import json
import os

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8711407704:AAGZWhw8jXSjoofD2w7MlFJy-6_guVXYU0E"
ADMINS = ["1674945230", "7908057052"] 
bot = telebot.TeleBot(TOKEN)

# Настройка КД (в секундах). 3600 сек = 1 час.
COOLDOWN_TIME = 3600 

FILES = {
    'cards': 'cards_data.json', 
    'colls': 'collections_data.json', 
    'users': 'users_stats.json',
    'squads': 'squads_data.json'
}

# Очки за рейтинг звезд
STATS = {
    1: {"score": 1000},
    2: {"score": 2000},
    3: {"score": 4000},
    4: {"score": 6000},
    5: {"score": 10000}
}

POSITIONS = ["LF", "CF", "RF", "CM", "LB", "RB"]

last_roll = {}

# --- [2] БД ФУНКЦИИ ---
def load_db(key):
    if not os.path.exists(FILES[key]):
        res = {} if key in ['users', 'colls', 'squads'] else []
        save_db(res, key)
        return res
    with open(FILES[key], 'r', encoding='utf-8') as f:
        try: 
            return json.load(f)
        except: 
            return {} if key in ['users', 'colls', 'squads'] else []

def save_db(data, key):
    with open(FILES[key], 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def get_stars(count):
    try:
        return "⭐️" * int(count)
    except:
        return "⭐️"

def is_admin_user(user):
    return str(user.id) in ADMINS

# --- [3] КЛАВИАТУРЫ ---
def main_kb(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Получить карту", "📋 Мой Состав")
    markup.row("🗂 Коллекция", "👤 Профиль")
    markup.row("🏆 Топ игроков", "💎 Премиум")
    if is_admin_user(user):
        markup.add("🛠 Админ-панель")
    return markup

# --- [4] ЛОГИКА ИГРЫ ---

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}
        save_db(users, 'users')
    
    bot.send_message(m.chat.id, "👋 Привет! Это бот СЛС карточек с функцией менеджмента состава.", 
                     reply_markup=main_kb(m.from_user), parse_mode="Markdown")

# МОМЕНТАЛЬНАЯ ВЫДАЧА КАРТЫ ПО КНОПКЕ
@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll_card_instantly(m):
    uid = str(m.from_user.id)
    is_admin = is_admin_user(m.from_user)

    # Проверка КД
    if not is_admin:
        now = time.time()
        if uid in last_roll:
            elapsed = now - last_roll[uid]
            if elapsed < COOLDOWN_TIME:
                remains = int(COOLDOWN_TIME - elapsed)
                mins = remains // 60
                secs = remains % 60
                return bot.send_message(m.chat.id, f"⏳ Нужно подождать еще {mins} мин. {secs} сек.", parse_mode="Markdown")
        last_roll[uid] = now

    cards = load_db('cards')
    users = load_db('users')
    colls = load_db('colls')

    if not cards: 
        return bot.send_message(m.chat.id, "❌ В игре пока нет карточек! Сначала добавьте их через Админ-панель.")

    # Выбираем случайную карту
    won = random.choice(cards)
    if uid not in colls: 
        colls[uid] = []
    
    is_new = not any(c['name'] == won['name'] for c in colls[uid])
    base_pts = STATS.get(int(won.get('stars', 1)), {"score": 500})["score"]
    added_pts = base_pts if is_new else int(base_pts * 0.3)
    
    if uid not in users:
        users[uid] = {"score": 0, "username": m.from_user.username or f"user_{uid}"}

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
        f"💠 Очки: +{int(added_pts):,} | Всего: {users[uid]['score']:,}"
    )
    
    try:
        # Пробуем отправить с фото
        bot.send_photo(m.chat.id, won['photo'], caption=caption, parse_mode="Markdown")
    except Exception as e:
        # Железный запасной вариант: если фото устарело/сломалось, бот пришлет текст и не упадет
        bot.send_message(m.chat.id, f"🏃‍♂️ **Карточка успешно выбита!** (Фото недоступно, передобавьте карту в админке)\n\n{caption}", parse_mode="Markdown")

# --- [5] СИСТЕМА СОСТАВА ---

def get_squad_text(uid):
    squads = load_db('squads')
    my_squad = squads.get(uid, {p: None for p in POSITIONS})
    
    lf = my_squad.get("LF") or "[Пусто]"
    cf = my_squad.get("CF") or "[Пусто]"
    rf = my_squad.get("RF") or "[Пусто]"
    cm = my_squad.get("CM") or "[Пусто]"
    lb = my_squad.get("LB") or "[Пусто]"
    rb = my_squad.get("RB") or "[Пусто]"
    
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

    text = (
        f"📋 **ВАШ ТЕКУЩИЙ СОСТАВ**\n"
        f"📊 Общий OVR состава: `{avg_ovr}`\n"
        f" — — — — — — — — — — — —\n\n"
        f"🔥 **АТАКА:**\n"
        f" LF: `{lf}`\n"
        f" CF: `{cf}`\n"
        f" RF: `{rf}`\n\n"
        f"⚡️ **ПОЛУЗАЩИТА:**\n"
        f" CM: `{cm}`\n\n"
        f"🛡 **ЗАЩИТА:**\n"
        f" LB: `{lb}`\n"
        f" RB: `{rb}`\n\n"
        f" — — — — — — — — — — — —\n"
        f" Нажмите на кнопку ниже, чтобы изменить позицию:"
    )
    return text

@bot.message_handler(func=lambda m: m.text == "📋 Мой Состав")
def view_squad(m):
    uid = str(m.from_user.id)
    text = get_squad_text(uid)
    
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS]
    markup.add(*btns)
    
    bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("pos_"))
def choose_player_for_pos(call):
    uid = str(call.from_user.id)
    target_pos = call.data.replace("pos_", "")
    
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    eligible_cards = [c for c in my_cards if c.get('pos', '').upper() == target_pos.upper()]
    
    if not eligible_cards:
        bot.answer_callback_query(call.id, f"⚠️ У вас в коллекции нет игроков с позицией {target_pos}!", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    for card in eligible_cards:
        ovr = card.get('ovr', '—')
        markup.add(types.InlineKeyboardButton(f"🏃‍♂️ {card['name']} (OVR: {ovr})", callback_data=f"set_{target_pos}_{card['name']}"))
        
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
    if uid not in squads:
        squads[uid] = {p: None for p in POSITIONS}
        
    squads[uid][pos] = player_name
    save_db(squads, 'squads')
    
    bot.answer_callback_query(call.id, f"✅ {player_name} поставлен на {pos}!")
    
    text = get_squad_text(uid)
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS]
    markup.add(*btns)
    
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_to_squad")
def back_squad_callback(call):
    uid = str(call.from_user.id)
    text = get_squad_text(uid)
    markup = types.InlineKeyboardMarkup(row_width=3)
    btns = [types.InlineKeyboardButton(f"⚙️ {p}", callback_data=f"pos_{p}") for p in POSITIONS]
    markup.add(*btns)
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- [6] ОСТАЛЬНЫЕ КОМАНДЫ ---

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
    colls = load_db('colls')
    my_cards = colls.get(uid, [])
    
    if not my_cards:
        return bot.send_message(m.chat.id, "🗂 Ваша коллекция пока пуста!")
    
    text = f"🗂 **ВАША КОЛЛЕКЦИЯ ({len(my_cards)} шт.):**\n\n"
    for card in my_cards:
        text += f"• {card['name']} | Поз: {card.get('pos', '—')} | OVR: {card.get('ovr', '—')} ({get_stars(card.get('stars', 1))})\n"
    
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    uid = str(m.from_user.id)
    u = load_db('users').get(uid, {"score": 0, "username": m.from_user.username or f"user_{uid}"})
    c = len(load_db('colls').get(uid, []))
    
    text = (
        f"👤 **ВАШ ПРОФИЛЬ**\n"
        f" — — — — — — — —\n"
        f"🆔 ID: `{uid}`\n"
        f"💠 Очки: `{u['score']:,}`\n"
        f"🗂 Коллекция: {c} шт.\n"
        f" — — — — — — — —"
    )
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def prem(m):
    bot.send_message(m.chat.id, "💎 **Премиум статус**\n\n• Крутки без КД\n✉️ Купить: @verybigsun", parse_mode="Markdown")

# --- АДМИН-ПАНЕЛЬ ---

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def adm(m):
    if is_admin_user(m.from_user):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("➕ Добавить карту", "🗑 Удалить карту")
        markup.row("🏠 Назад в меню")
        bot.send_message(m.chat.id, "🛠 Панель управления администратора:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту")
def delete_menu(m):
    if is_admin_user(m.from_user):
        cards = load_db('cards')
        if not cards: return bot.send_message(m.chat.id, "❌ База карт пуста.")
        
        markup = types.InlineKeyboardMarkup()
        for c in cards:
            markup.add(types.InlineKeyboardButton(f"❌ Удалить {c['name']}", callback_data=f"del_{c['name']}"))
        bot.send_message(m.chat.id, "Выберите карту для удаления:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def process_delete(call):
    name_to_delete = call.data.replace("del_", "")
    cards = load_db('cards')
    new_cards = [c for c in cards if c['name'] != name_to_delete]
    save_db(new_cards, 'cards')
    bot.edit_message_text(f"✅ Карта **{name_to_delete}** удалена.", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def add_start(m):
    if is_admin_user(m.from_user):
        msg = bot.send_message(m.chat.id, "1️⃣ Введите ИМЯ игрока:")
        bot.register_next_step_handler(msg, add_step_ovr)

def add_step_ovr(m):
    name = m.text
    msg = bot.send_message(m.chat.id, f"2️⃣ Введите общий рейтинг OVR (например: 85) для {name}:")
    bot.register_next_step_handler(msg, add_step_event, name)

def add_step_event(m, name):
    ovr = m.text
    msg = bot.send_message(m.chat.id, f"3️⃣ Введите НАЗВАНИЕ СОБЫТИЯ (например: TOTY 26):")
    bot.register_next_step_handler(msg, add_step_pos, name, ovr)

def add_step_pos(m, name, ovr):
    event = m.text
    msg = bot.send_message(m.chat.id, f"4️⃣ Введите ОСНОВНУЮ ПОЗИЦИЮ (строго одну из: LF, CF, RF, CM, LB, RB):")
    bot.register_next_step_handler(msg, add_step_rarity, name, ovr, event)

def add_step_rarity(m, name, ovr, event):
    pos = m.text.upper()
    msg = bot.send_message(m.chat.id, f"5️⃣ Введите РЕДКОСТЬ (например: EPIC, LEGENDARY):")
    bot.register_next_step_handler(msg, add_step_stars, name, ovr, event, pos)

def add_step_stars(m, name, ovr, event, pos):
    rarity = m.text
    msg = bot.send_message(m.chat.id, f"6️⃣ Введите РЕЙТИНГ В ЗВЕЗДАХ для расчета очков (1-5):")
    bot.register_next_step_handler(msg, add_step_photo, name, ovr, event, pos, rarity)

def add_step_photo(m, name, ovr, event, pos, rarity):
    stars = m.text
    msg = bot.send_message(m.chat.id, f"7️⃣ Теперь отправьте ФОТО карточки:")
    bot.register_next_step_handler(msg, add_final, name, ovr, event, pos, rarity, stars)

def add_final(m, name, ovr, event, pos, rarity, stars):
    if not m.photo:
        return bot.send_message(m.chat.id, "❌ Ошибка! Вы не отправили фото. Начните добавление заново.")
    
    cards = load_db('cards')
    cards.append({
        "name": name,
        "ovr": ovr,
        "event": event,
        "pos": pos,
        "rarity": rarity,
        "stars": int(stars) if stars.isdigit() else 1,
        "photo": m.photo[-1].file_id
    })
    save_db(cards, 'cards')
    bot.send_message(m.chat.id, f"✅ Карта *{name}* успешно создана!", reply_markup=main_kb(m.from_user), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back(m):
    bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb(m.from_user))

if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    bot.infinity_polling()
