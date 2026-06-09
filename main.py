import telebot
from telebot import types
import random
import time
import json
import os
import sys
import logging

# ==============================================================================
# [1] НАСТРОЙКА СИСТЕМНОГО ЛОГИРОВАНИЯ
# ==============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(name)s - %(message)s',
    handlers=[sys.stdout]
)
logger = logging.getLogger("FootballBotCore")

# ==============================================================================
# [2] ГЛОБАЛЬНЫЕ НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ БОТА
# ==============================================================================

TOKEN = "8834454809:AAGwW6gfVziVZ1u-gplIwI1DLt1ZJBBMVeE"
ADMINS = [7908057052, 1674945230]

bot = telebot.TeleBot(TOKEN)

DB_FILES = {
    'cards': 'cards.json',
    'colls': 'collections.json',
    'squads': 'squads.json',
    'users': 'users_data.json',
    'bans': 'bans.json',
    'promos': 'promos.json'
}

RARITY_STATS = {
    1: {"chance": 35, "score": 1000, "atk": 100, "label": "Обычная"},
    2: {"chance": 30, "score": 3000, "atk": 450, "label": "Необычная"},
    3: {"chance": 20, "score": 7500, "atk": 1000, "label": "Редкая"},
    4: {"chance": 10, "score": 15000, "atk": 2500, "label": "Эпическая"},
    5: {"chance": 5, "score": 30000, "atk": 5000, "label": "Легендарная"}
}

POSITIONS_RU = {
    "ГК": "Вратарь", "ЛЗ": "Левый Защитник", "ПЗ": "Правый Защитник",
    "ЦП": "Центральный Полузащитник", "ЛВ": "Левый Вингер", "ПВ": "Правый Вингер", 
    "КФ": "Нападающий"
}

SQUAD_SLOTS = {
    0: {"label": "🧤 ГК (Вратарь)", "code": "ГК"},
    1: {"label": "🛡 ЛЗ (Защитник)", "code": "ЛЗ"},
    2: {"label": "🛡 ПЗ (Защитник)", "code": "ПЗ"},
    3: {"label": "👟 ЦП (Полузащитник)", "code": "ЦП"},
    4: {"label": "⚡️ ЛВ (Вингер)", "code": "ЛВ"},
    5: {"label": "⚡️ ПВ (Вингер)", "code": "ПВ"},
    6: {"label": "🎯 КФ (Нападающий)", "code": "КФ"}
}

roll_cooldowns = {}
pvp_cooldowns = {}
online_matchmaking_queue = []

# ==============================================================================
# [4] УПРАВЛЕНИЕ ДАННЫМИ (JSON STORAGE ENGINE)
# ==============================================================================

def initialize_database_files():
    for key, file_name in DB_FILES.items():
        if not os.path.exists(file_name):
            default_structure = [] if key in ['cards', 'bans'] else {}
            with open(file_name, 'w', encoding='utf-8') as f:
                json.dump(default_structure, f, ensure_ascii=False, indent=4)

initialize_database_files()

def load_data(key):
    file_path = DB_FILES.get(key)
    if not os.path.exists(file_path): return [] if key in ['cards', 'bans'] else {}
    with open(file_path, 'r', encoding='utf-8') as file_in:
        try:
            content = file_in.read()
            return json.loads(content) if content.strip() else ([] if key in ['cards', 'bans'] else {})
        except Exception:
            return [] if key in ['cards', 'bans'] else {}

def save_data(data_object, key):
    file_path = DB_FILES.get(key)
    try:
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(data_object, file_out, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

def check_admin_permission(user_obj):
    return user_obj and user_obj.id in ADMINS

def check_ban_status(user_obj):
    if not user_obj: return False
    ban_list = load_data('bans')
    return str(user_obj.id) in ban_list or (user_obj.username and user_obj.username.lower() in ban_list)

def calculate_total_power(user_id):
    squad_data = load_data('squads')
    my_squad = squad_data.get(str(user_id), [None] * 7)
    power_sum = 0
    for card in my_squad:
        if card and isinstance(card, dict):
            stars = card.get('stars', 1)
            power_sum += RARITY_STATS.get(stars, {"atk": 100})['atk']
    return power_sum

# ==============================================================================
# [6] ИНТЕРФЕЙСНЫЙ ДВИЖОК
# ==============================================================================

def create_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("🎰 Крутить карту"), types.KeyboardButton("🗂 Коллекция"))
    markup.add(types.KeyboardButton("📋 Состав"), types.KeyboardButton("👤 Профиль"))
    markup.add(types.KeyboardButton("🏆 Топ очков"), types.KeyboardButton("🏟 ПВП Арена"))
    markup.add(types.KeyboardButton("🎟 Промокод"), types.KeyboardButton("👥 Рефералы"))
    if check_admin_permission(types.User(user_id, '', False)):
        markup.add(types.KeyboardButton("🛠 Админ-панель"))
    return markup

def create_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(types.KeyboardButton("➕ Добавить карту"), types.KeyboardButton("📝 Изменить карту"), types.KeyboardButton("🗑 Удалить карту"))
    markup.add(types.KeyboardButton("🎟 +Промокод"), types.KeyboardButton("🗑 Удалить промокод"))
    markup.add(types.KeyboardButton("🚫 Забанить"), types.KeyboardButton("✅ Разбанить"))
    markup.add(types.KeyboardButton("🧨 Обнулить бота"), types.KeyboardButton("🏠 Назад в меню"))
    return markup

def create_cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup

def create_pvp_menu():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🤖 Быстрый матч (с ботом)", callback_data="pvp_mode_bot"),
        types.InlineKeyboardButton("🔎 Искать онлайн-матч", callback_data="pvp_mode_online")
    )
    return markup

# ==============================================================================
# [7-12] СТАНДАРТНЫЕ ИГРОВЫЕ ОБРАБОТЧИКИ
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_message_handler(message):
    if check_ban_status(message.from_user):
        bot.send_message(message.chat.id, "🚫 Вы заблокированы.")
        return

    users_database = load_data('users')
    user_id_key = str(message.from_user.id)

    inviter_id = message.text.split()[1].strip() if len(message.text.split()) > 1 else None

    if user_id_key not in users_database:
        user_display_name = f"@{message.from_user.username}" if message.from_user.username else f"id_{user_id_key}"
        users_database[user_id_key] = {
            "nick": message.from_user.first_name or "Футболист",
            "username": user_display_name, "score": 0, "free_rolls": 0, "bonus_luck": 1.0, "refs": 0, "used_promos": []
        }
        if inviter_id and inviter_id in users_database and inviter_id != user_id_key:
            users_database[inviter_id]["score"] += 5000
            users_database[inviter_id]["free_rolls"] = users_database[inviter_id].get("free_rolls", 0) + 3
            users_database[inviter_id]["refs"] = users_database[inviter_id].get("refs", 0) + 1
            try:
                bot.send_message(int(inviter_id), "👥 <b>Новый реферал!</b> Вам начислено +5,000 очков и +3 прокрута!", parse_mode="HTML")
            except: pass
        save_data(users_database, 'users')

    bot.send_message(message.chat.id, f"⚽️ <b>Привет, {message.from_user.first_name}!</b> Добро пожаловать в симулятор.", reply_markup=create_main_menu(message.from_user.id), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_stats_handler(message):
    if check_ban_status(message.from_user): return
    bot_username = bot.get_me().username
    invite_link = f"https://t.me/{bot_username}?start={message.from_user.id}"
    ref_count = load_data('users').get(str(message.from_user.id), {}).get("refs", 0)
    bot.send_message(message.chat.id, f"👥 <b>Рефералы:</b> {ref_count}\n🔗 Ссылка: <code>{invite_link}</code>", parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input_start(message):
    if check_ban_status(message.from_user): return
    sent_msg = bot.send_message(message.chat.id, "🎟 Введите промокод:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(sent_msg, process_promo_logic)

def process_promo_logic(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "🔄 Отменено.", reply_markup=create_main_menu(message.from_user.id))
        return
    code = message.text.strip().upper()
    users_db = load_data('users')
    promos_db = load_data('promos')
    uid = str(message.from_user.id)

    if code not in promos_db:
        bot.send_message(message.chat.id, "❌ Нет такого кода.", reply_markup=create_main_menu(message.from_user.id))
        return
    if code in users_db.get(uid, {}).get('used_promos', []):
        bot.send_message(message.chat.id, "❌ Уже активирован.", reply_markup=create_main_menu(message.from_user.id))
        return

    reward = promos_db[code]
    if reward.get('type') == 'rolls':
        users_db[uid]['free_rolls'] = users_db[uid].get('free_rolls', 0) + int(reward['value'])
    else:
        users_db[uid]['score'] = users_db[uid].get('score', 0) + int(reward['value'])

    if 'used_promos' not in users_db[uid]: users_db[uid]['used_promos'] = []
    users_db[uid]['used_promos'].append(code)
    save_data(users_db, 'users')
    bot.send_message(message.chat.id, "🎉 Успешно активирован!", reply_markup=create_main_menu(message.from_user.id))

# ==============================================================================
# [9] КРУТИТЬ КАРТУ (РУЛЕТКА)
# ==============================================================================
@bot.message_handler(func=lambda m: m.text == "🎰 Крутить карту")
def roll_card_handler(message):
    if check_ban_status(message.from_user): return
    uid = str(message.from_user.id)
    users_db = load_data('users')
    all_cards = load_data('cards')

    if not all_cards:
        bot.send_message(message.chat.id, "❌ В базе нет карточек!")
        return

    # Кулдаун 2 часа
    now = time.time()
    if not check_admin_permission(message.from_user) and users_db.get(uid, {}).get('free_rolls', 0) <= 0:
        if uid in roll_cooldowns and now - roll_cooldowns[uid] < 7200:
            rem = int(7200 - (now - roll_cooldowns[uid]))
            bot.send_message(message.chat.id, f"⏳ Кулдаун ролла! Ждите {rem//3600}ч {(rem%3600)//60}м.")
            return

    # Выбор карты по шансам
    rarities = [1, 2, 3, 4, 5]
    weights = [RARITY_STATS[r]['chance'] for r in rarities]
    chosen_r = random.choices(rarities, weights=weights)[0]
    
    pool = [c for c in all_cards if c.get('stars', 1) == chosen_r]
    won_card = random.choice(pool if pool else all_cards)
    chosen_r = won_card.get('stars', 1)

    if users_db.get(uid, {}).get('free_rolls', 0) > 0:
        users_db[uid]['free_rolls'] -= 1
        txt = f"🎫 Осталось бонусных прокрутов: {users_db[uid]['free_rolls']}"
    else:
        roll_cooldowns[uid] = now
        txt = "⏳ Следующий ролл через 2 часа."

    colls_db = load_data('colls')
    if uid not in colls_db: colls_db[uid] = []
    
    dup = any(x.get('name') == won_card.get('name') for x in colls_db[uid])
    pts = int(RARITY_STATS[chosen_r]['score'] * (0.3 if dup else 1.0))
    
    if not dup: colls_db[uid].append(won_card)
    users_db[uid]['score'] = users_db[uid].get('score', 0) + pts
    
    save_data(users_db, 'users')
    save_data(colls_db, 'colls')

    caption = (
        f"🏆 <b>КАРТА ВЫПАЛА!</b>\n\n"
        f"🏃‍♂️ {won_card.get('name')}\n"
        f"🛡 Позиция: {won_card.get('position')} ({POSITIONS_RU.get(won_card.get('position'), 'ЦП')})\n"
        f"🏢 Клуб: {won_card.get('club')}\n"
        f"📊 Редкость: {'⭐'*chosen_r}\n"
        f"⚡ АТК: {RARITY_STATS[chosen_r]['atk']}\n\n"
        f"{'🔄 ДУБЛИКАТ! (Компенсация 30%)' if dup else '✨ НОВАЯ КАРТА!'}\n"
        f"💰 Баланс: {users_db[uid]['score']:,} очков.\n\n{txt}"
    )

    if won_card.get('photo'):
        try: bot.send_photo(message.chat.id, won_card['photo'], caption=caption, parse_mode="HTML")
        except: bot.send_message(message.chat.id, caption, parse_mode="HTML")
    else:
        bot.send_message(message.chat.id, caption, parse_mode="HTML")

# ==============================================================================
# [10-11] ПРОФИЛИ, КОЛЛЕКЦИИ, СОСТАВЫ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection_menu_handler(message):
    if check_ban_status(message.from_user): return
    my_cards = load_data('colls').get(str(message.from_user.id), [])
    if not my_cards:
        bot.send_message(message.chat.id, "🗂 У вас пока нет ни одной карточки.")
        return
    txt = f"🗂 <b>Ваша коллекция ({len(my_cards)} шт):</b>\n\n"
    for i, c in enumerate(my_cards, 1):
        txt += f"{i}. {c.get('name')} ({c.get('position')}) - {'⭐'*c.get('stars',1)}\n"
    bot.send_message(message.chat.id, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "📋 Состав")
def squad_menu_handler(message):
    if check_ban_status(message.from_user): return
    uid = str(message.from_user.id)
    squads_db = load_data('squads')
    if uid not in squads_db: squads_db[uid] = [None] * 7 ; save_data(squads_db, 'squads')
    
    txt = f"📋 <b>Ваш состав сборной</b>\nМощь: {calculate_total_power(message.from_user.id)} АТК\n\n"
    markup = types.InlineKeyboardMarkup(row_width=1)
    for slot_id, slot in SQUAD_SLOTS.items():
        card = squads_db[uid][slot_id]
        txt += f"• {slot['label']}: {card.get('name') if card else '❌ Пусто'}\n"
        markup.add(types.InlineKeyboardButton(f"⚙️ Настроить {slot['code']}", callback_data=f"manage_slot_{slot_id}"))
    bot.send_message(message.chat.id, txt, reply_markup=markup, parse_mode="HTML")

@bot.callback_query_handler(func=lambda call: call.data.startswith("manage_slot_"))
def process_manage_slot_callback(call):
    uid = str(call.from_user.id)
    slot_id = int(call.data.replace("manage_slot_", ""))
    code = SQUAD_SLOTS[slot_id]['code']
    eligible = [c for c in load_data('colls').get(uid, []) if c.get('position') == code]
    
    if not eligible:
        bot.answer_callback_query(call.id, f"В коллекции нет игроков позиции {code}!", show_alert=True)
        return
    markup = types.InlineKeyboardMarkup(row_width=1)
    for i, card in enumerate(eligible):
        markup.add(types.InlineKeyboardButton(f"{card['name']} (⭐{card['stars']})", callback_data=f"setcard_{slot_id}_{i}"))
    markup.add(types.InlineKeyboardButton("🗑 Очистить слот", callback_data=f"clear_slot_{slot_id}"))
    bot.send_message(call.message.chat.id, "🏃‍♂️ Выберите игрока:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("setcard_") or call.data.startswith("clear_slot_"))
def finalize_slot_assignment_callback(call):
    uid = str(call.from_user.id)
    squads_db = load_data('squads')
    if call.data.startswith("clear_slot_"):
        slot_id = int(call.data.replace("clear_slot_", ""))
        squads_db[uid][slot_id] = None
        save_data(squads_db, 'squads')
        bot.edit_message_text("✅ Слот очищен.", call.message.chat.id, call.message.message_id)
        return
    parts = call.data.split("_")
    slot_id, idx = int(parts[1]), int(parts[2])
    eligible = [c for c in load_data('colls').get(uid, []) if c.get('position') == SQUAD_SLOTS[slot_id]['code']]
    squads_db[uid][slot_id] = eligible[idx]
    save_data(squads_db, 'squads')
    bot.edit_message_text(f"✅ Установлен: {eligible[idx]['name']}", call.message.chat.id, call.message.message_id)

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def user_profile_handler(message):
    if check_ban_status(message.from_user): return
    prof = load_data('users').get(str(message.from_user.id), {})
    txt = f"👤 <b>Профиль менеджера:</b>\n💰 Баланс: {prof.get('score',0):,} очков\n🎫 Прокруты: {prof.get('free_rolls',0)} шт.\n⚔️ Мощь: {calculate_total_power(message.from_user.id)} АТК"
    bot.send_message(message.chat.id, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ очков")
def leaderboard_handler(message):
    if check_ban_status(message.from_user): return
    sorted_u = sorted(load_data('users').items(), key=lambda x: x[1].get('score', 0), reverse=True)[:10]
    txt = "🏆 <b>ТОП-10 МЕНЕДЖЕРА</b>\n\n"
    for r, (uid, d) in enumerate(sorted_u, 1):
        txt += f"{r}. {d.get('nick')} — <b>{d.get('score',0):,}</b> очков\n"
    bot.send_message(message.chat.id, txt, parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏟 ПВП Арена")
def pvp_arena_entry_handler(message):
    if check_ban_status(message.from_user): return
    bot.send_message(message.chat.id, "🏟 Режимы ПВП Арены:", reply_markup=create_pvp_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith("pvp_mode_"))
def process_pvp_mode_selection(call):
    bot.answer_callback_query(call.id, "В разработке...")

# ==============================================================================
# [13] МОДУЛЬ АДМИНИСТРИРОВАНИЯ (УЛЬТРА-БЫСТРОЕ ДОБАВЛЕНИЕ В 1 КЛИК)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_text_handler(message):
    if not check_admin_permission(message.from_user): return
    bot.send_message(message.chat.id, "🛠 <b>Панель управления</b>", reply_markup=create_admin_menu(), parse_mode="HTML")

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_to_main_menu_handler(message):
    bot.send_message(message.chat.id, "🏠 Главное меню", reply_markup=create_main_menu(message.from_user.id))

# --- НОВАЯ СУПЕР ЛОГИКА: ФОТО + ТЕКСТ В ОДНОМ СЛОВЕ ---

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def fast_add_card_start(message):
    if not check_admin_permission(message.from_user): return
    
    inst = (
        "📥 **ДОБАВЛЕНИЕ КАРТОЧКИ В 1 ШАГ**\n\n"
        "Просто пришли мне **ФОТОГРАФИЮ КАРТОЧКИ** и в описании к ней (подписи) напиши данные через палочку `|`.\n\n"
        "**Формат подписи:**\n"
        "`Имя игрока | Позиция | Клуб | Редкость от 1 до 5`\n\n"
        "**Пример:**\n"
        "`Kylian Mbappé | КФ | Real Madrid | 5`\n\n"
        "_(Если фотка не нужна, можешь просто отправить этот текст сообщением без фото)_"
    )
    sent_msg = bot.send_message(message.chat.id, inst, reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(sent_msg, fast_add_card_save)


def fast_add_card_save(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "🔄 Отменено.", reply_markup=create_admin_menu())
        return

    # 1. Проверяем, есть ли в сообщении фото или это обычный текст
    photo_file_id = ""
    raw_text = ""

    if message.photo:
        photo_file_id = message.photo[-1].file_id  # Берем максимальное качество
        raw_text = message.caption
    else:
        raw_text = message.text

    if not raw_text:
        sent_msg = bot.send_message(message.chat.id, "⚠️ Ошибка! Ты забыл написать текст/подпись к фото. Попробуй еще раз:")
        bot.register_next_step_handler(sent_msg, fast_add_card_save)
        return

    # 2. Парсим строчку через разделитель "|"
    try:
        parts = [p.strip() for p in raw_text.split("|")]
        if len(parts) < 4: raise ValueError
        
        name = parts[0]
        pos = parts[1].upper()
        club = parts[2]
        stars = int(parts[3])
        
        if pos not in POSITIONS_RU: raise KeyError
        if stars not in RARITY_STATS: raise IndexError
        
    except (ValueError, KeyError, IndexError):
        sent_msg = bot.send_message(
            message.chat.id, 
            "❌ **Ошибка разбора строки!** Неверный формат.\n"
            "Убедись, что написал всё через палочку: `Имя | Позиция | Клуб | Число_от_1_до_5`\n"
            "Пример: `Cristiano Ronaldo | КФ | Al-Nassr | 5`"
        )
        bot.register_next_step_handler(sent_msg, fast_add_card_save)
        return

    # 3. Сохраняем готовую карту
    new_card = {
        "name": name,
        "position": pos,
        "club": club,
        "stars": stars,
        "photo": photo_file_id  # Теперь сохраняется прямой ID фотки из Telegram!
    }

    all_cards = load_data('cards')
    all_cards.append(new_card)
    save_data(all_cards, 'cards')

    success = (
        "✅ **КАРТОЧКА УСПЕШНО ДОБАВЛЕНА!**\n\n"
        f"🏃‍♂️ Игрок: **{name}**\n"
        f"🛡 Позиция: `{pos}` ({POSITIONS_RU[pos]})\n"
        f"🏢 Клуб: *{club}*\n"
        f"📊 Редкость: {'⭐'*stars} ({RARITY_STATS[stars]['label']})"
    )
    
    bot.send_message(message.chat.id, success, reply_markup=create_admin_menu(), parse_mode="Markdown")


# Остальные стабы
@bot.message_handler(func=lambda m: m.text in ["📝 Изменить карту", "🗑 Удалить карту", "🎟 +Промокод", "🗑 Удалить промокод", "🚫 Забанить", "✅ Разбанить", "🧨 Обнулить бота"])
def admin_actions_stub_handler(message):
    if not check_admin_permission(message.from_user): return
    bot.send_message(message.chat.id, f"⚙️ Функция «{message.text}» в разработке.")

if __name__ == '__main__':
    logger.info("Бот успешно запущен!")
    bot.infinity_polling(skip_pending=True)
