import telebot
from telebot import types
import random
import time
import json
import os
import sys

# ==============================================================================
# [1] ГЛОБАЛЬНЫЕ НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ
# ==============================================================================

# Ваш уникальный токен бота
TOKEN = "8886116833:AAEDyyrYKXH3WtY2BBFCOe4lZcaqlYBEaXY"

# Список администраторов (Для безопасности рекомендуется заменить на ID, например: [12345678, 87654321])
ADMINS = ["verybigsunr", "Ravgant"] 

bot = telebot.TeleBot(TOKEN)

DB_FILES = {
    'cards': 'cards.json',         
    'colls': 'collections.json',   
    'squads': 'squads.json',       
    'users': 'users_data.json',     
    'bans': 'bans.json',           
    'promos': 'promos.json'        
}

# ==============================================================================
# [2] ИГРОВЫЕ ПАРАМЕТРЫ (КОНФИГУРАЦИЯ БАЛАНСА)
# ==============================================================================

RARITY_STATS = {
    1: {"chance": 35, "score": 1000, "atk": 100, "label": "Обычная"},
    2: {"chance": 30, "score": 3000, "atk": 450, "label": "Необычная"},
    3: {"chance": 20, "score": 7500, "atk": 1000, "label": "Редкая"},
    4: {"chance": 10, "score": 15000, "atk": 2500, "label": "Эпическая"},
    5: {"chance": 5, "score": 30000, "atk": 5000, "label": "Легендарная"}
}

POSITIONS_RU = {
    "ГК": "Вратарь", "ЛЗ": "Левый Защитник", "ПЗ": "Правый Защитник",
    "ЦП": "Центральный Полузащитник", "ЛВ": "Левый Вингер", "ПВ": "Правый Вингер", "КФ": "Нападающий"
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

# ==============================================================================
# [3] МОДУЛЬ РАБОТЫ С ДАННЫМИ (JSON ENGINE)
# ==============================================================================

def load_data(key):
    file_path = DB_FILES.get(key)
    if not os.path.exists(file_path):
        default_structure = [] if key in ['cards', 'bans'] else {}
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(default_structure, file_out, ensure_ascii=False, indent=4)
        return default_structure
    
    with open(file_path, 'r', encoding='utf-8') as file_in:
        try:
            content = file_in.read()
            if not content:
                return [] if key in ['cards', 'bans'] else {}
            return json.loads(content)
        except Exception as error:
            print(f"Ошибка чтения базы {key}: {error}")
            return [] if key in ['cards', 'bans'] else {}

def save_data(data_object, key):
    file_path = DB_FILES.get(key)
    try:
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(data_object, file_out, ensure_ascii=False, indent=4)
        return True
    except Exception as error:
        print(f"Критическая ошибка при сохранении {key}: {error}")
        return False

# ==============================================================================
# [4] СИСТЕМНЫЕ ПРОВЕРКИ И ЛОГИРОВАНИЕ
# ==============================================================================

def check_admin_permission(user_obj):
    if user_obj.username is None:
        return False
    current_username = user_obj.username.lower()
    for admin_name in ADMINS:
        if admin_name.lower() == current_username:
            return True
    return False

def check_ban_status(user_obj):
    ban_list = load_data('bans')
    user_id_string = str(user_obj.id)
    user_name_string = user_obj.username.lower() if user_obj.username else "no_nick"
    return user_id_string in ban_list or user_name_string in ban_list

def calculate_total_power(user_id):
    squad_data = load_data('squads')
    my_squad = squad_data.get(str(user_id), [None] * 7)
    power_sum = 0
    for card_item in my_squad:
        if card_item is not None:
            stars = card_item.get('stars', 1)
            power_sum += RARITY_STATS[stars]['atk']
    return power_sum

def log_action(user_id, action_name):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] USER_ID: {user_id} | ACTION: {action_name}")

# ==============================================================================
# [5] ГЕНЕРАТОРЫ ИНТЕРФЕЙСА (KEYBOARDS)
# ==============================================================================

def create_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_roll = types.KeyboardButton("🎰 Крутить карту")
    btn_collection = types.KeyboardButton("🗂 Коллекция")
    btn_squad = types.KeyboardButton("📋 Состав")
    btn_profile = types.KeyboardButton("👤 Профиль")
    btn_top = types.KeyboardButton("🏆 Топ очков")
    btn_pvp = types.KeyboardButton("🏟 ПВП Арена")
    btn_promo = types.KeyboardButton("🎟 Промокод")
    btn_referrals = types.KeyboardButton("👥 Рефералы")
    
    markup.add(btn_roll, btn_collection, btn_squad, btn_profile)
    markup.add(btn_top, btn_pvp, btn_promo, btn_referrals)
    
    try:
        chat_info = bot.get_chat(user_id)
        if check_admin_permission(chat_info):
            btn_admin = types.KeyboardButton("🛠 Админ-панель")
            markup.add(btn_admin)
    except:
        pass
        
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

# ==============================================================================
# [6] ОБРАБОТКА КОМАНД И РЕФЕРАЛОВ
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_message_handler(message):
    if check_ban_status(message.from_user):
        bot.send_message(message.chat.id, "🚫 Вы заблокированы. Доступ к боту закрыт.")
        return

    users_database = load_data('users')
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, "START_COMMAND")

    inviter_id = None
    parts = message.text.split()
    if len(parts) > 1:
        inviter_id = parts[1]

    if user_id_key not in users_database:
        user_display_name = f"@{message.from_user.username}" if message.from_user.username else f"id{user_id_key}"
        users_database[user_id_key] = {
            "nick": message.from_user.first_name,
            "username": user_display_name,
            "score": 0,
            "free_rolls": 0,
            "bonus_luck": 1.0,
            "refs": 0,
            "used_promos": []
        }
        
        if inviter_id and inviter_id in users_database and inviter_id != user_id_key:
            users_database[inviter_id]["score"] += 5000
            users_database[inviter_id]["free_rolls"] = users_database[inviter_id].get("free_rolls", 0) + 3
            users_database[inviter_id]["refs"] += 1
            
            try:
                msg_to_inviter = "👥 **НОВЫЙ ИГРОК!**\n\nПо вашей ссылке зарегистрировался новый пользователь.\n🎁 Вам начислено:\n— **5,000 очков**\n— **3 бесплатных прокрута**"
                bot.send_message(int(inviter_id), msg_to_inviter, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить уведомление рефереру: {e}")

    save_data(users_database, 'users')
    
    welcome_text = "⚽️ **Приветствую, {}!**\n\nВы попали в симулятор футбольных карточек.\nИспользуйте меню ниже для игры!".format(message.from_user.first_name)
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_menu(message.from_user.id), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_stats_handler(message):
    if check_ban_status(message.from_user): return
    user_id = message.from_user.id
    users_db = load_data('users')
    bot_info = bot.get_me()
    
    invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
    ref_count = users_db.get(str(user_id), {}).get("refs", 0)
    
    referral_text = f"👥 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\nПриглашайте друзей!\n🎁 **Награда:**\n— **5,000 очков**\n— **3 прокрута**\n\nПриглашено: **{ref_count}**\nСсылка:\n`{invite_link}`"
    bot.send_message(message.chat.id, referral_text, parse_mode="Markdown")

# ==============================================================================
# [7] МОДУЛЬ ПРОМОКОДОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input_start(message):
    if check_ban_status(message.from_user): return
    sent_msg = bot.send_message(message.chat.id, "🎟 Введите промокод:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(sent_msg, process_promo_logic)

def process_promo_logic(message):
    user_id_key = str(message.from_user.id)
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_main_menu(message.from_user.id))
        return
        
    input_code = message.text.strip().upper()
    users_db = load_data('users')
    promos_db = load_data('promos')
    
    if input_code not in promos_db:
        bot.send_message(message.chat.id, "❌ Неверный код.", reply_markup=create_main_menu(message.from_user.id))
        return

    if input_code in users_db[user_id_key].get('used_promos', []):
        bot.send_message(message.chat.id, "❌ Уже активирован.", reply_markup=create_main_menu(message.from_user.id))
        return

    code_info = promos_db[input_code]
    reward_type = code_info['type']
    reward_val = code_info['value']
    
    if reward_type == 'rolls':
        users_db[user_id_key]['free_rolls'] = users_db[user_id_key].get('free_rolls', 0) + int(reward_val)
        success_msg = f"✅ +{reward_val} прокрутов!"
    elif reward_type == 'luck':
        users_db[user_id_key]['bonus_luck'] = float(reward_val)
        success_msg = f"✅ Удача х{reward_val}!"
    else:
        users_db[user_id_key]['score'] += int(reward_val)
        success_msg = f"✅ +{int(reward_val):,} очков!"

    if 'used_promos' not in users_db[user_id_key]:
        users_db[user_id_key]['used_promos'] = []
    users_db[user_id_key]['used_promos'].append(input_code)
    
    save_data(users_db, 'users')
    bot.send_message(message.chat.id, success_msg, reply_markup=create_main_menu(message.from_user.id), parse_mode="Markdown")

# ==============================================================================
# [8] СИСТЕМА ПРОКРУТОВ (ROLL)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎰 Крутить карту")
def roll_card_handler(message):
    if check_ban_status(message.from_user): return
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    all_cards = load_data('cards')
    
    if not all_cards:
        bot.send_message(message.chat.id, "❌ Карт еще нет в базе.")
        return
        
    current_time_stamp = time.time()
    bonus_rolls = users_db[user_id_key].get('free_rolls', 0)
    
    if not check_admin_permission(message.from_user) and bonus_rolls <= 0:
        if user_id_key in roll_cooldowns and current_time_stamp - roll_cooldowns[user_id_key] < 10800:
            rem = int(10800 - (current_time_stamp - roll_cooldowns[user_id_key]))
            bot.send_message(message.chat.id, f"⏳ Кулдаун! Доступно через {rem // 3600}ч {(rem % 3600) // 60}м.")
            return

    luck = users_db[user_id_key].get('bonus_luck', 1.0)
    rarity_indices = sorted(RARITY_STATS.keys())
    weights = [RARITY_STATS[r]['chance'] * (luck if r >= 4 else 1.0) for r in rarity_indices]

    final_rarity = random.choices(rarity_indices, weights=weights)[0]
    pool = [c for c in all_cards if c['stars'] == final_rarity] or all_cards
    won_card = random.choice(pool)
    
    if bonus_rolls > 0:
        users_db[user_id_key]['free_rolls'] -= 1
        attempt_info = "🎫 Использован бонус-ролл."
    else:
        roll_cooldowns[user_id_key] = current_time_stamp
        attempt_info = "⏳ Следующий бесплатный ролл через 3 часа."

    users_db[user_id_key]['bonus_luck'] = 1.0
    collections_db = load_data('colls')
    if user_id_key not in collections_db: collections_db[user_id_key] = []
    
    is_duplicate = any(x['name'] == won_card['name'] for x in collections_db[user_id_key])
    if is_duplicate:
        points = int(RARITY_STATS[won_card['stars']]['score'] * 0.3)
        res_msg = "🔄 Повтор! Получено 30% компенсации."
    else:
        points = RARITY_STATS[won_card['stars']]['score']
        res_msg = "✨ Новая карта в коллекции!"
        collections_db[user_id_key].append(won_card)
        save_data(collections_db, 'colls')

    users_db[user_id_key]['score'] += points
    save_data(users_db, 'users')

    caption = f"⚽️ **{won_card['name']}**\nРедкость: {'⭐'*won_card['stars']}\n{res_msg}\n Баланс: {users_db[user_id_key]['score']:,}\n{attempt_info}"
    try:
        bot.send_photo(message.chat.id, won_card['photo'], caption=caption, parse_mode="Markdown")
    except:
        bot.send_message(message.chat.id, f"🏆 Вы выиграли карту: {won_card['name']}\n{caption}", parse_mode="Markdown")

# ==============================================================================
# [9] МОДУЛЬ ПВП (БОИ С ДРУГИМИ ИГРОКАМИ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🏟 ПВП Арена")
def pvp_hub_handler(message):
    if check_ban_status(message.from_user): return
    user_id_key = str(message.from_user.id)
    
    if not check_admin_permission(message.from_user) and user_id_key in pvp_cooldowns:
        if time.time() - pvp_cooldowns[user_id_key] < 900:
            bot.send_message(message.chat.id, "⏳ Футболисты устали. Матч доступен раз в 15 минут.")
            return

    pvp_markup = types.InlineKeyboardMarkup(row_width=1)
    pvp_markup.add(types.InlineKeyboardButton("🎲 Случайный соперник", callback_data="pvp_action_random"),
                   types.InlineKeyboardButton("👤 Найти по нику", callback_data="pvp_action_by_user"))
    
    bot.send_message(message.chat.id, f"🏟 Мощь вашего состава: {calculate_total_power(user_id_key)}\nИщите соперника:", reply_markup=pvp_markup)

@bot.callback_query_handler(func=lambda call: call.data == "pvp_action_random")
def pvp_random_matchmaking(call):
    users_db = load_data('users')
    p1 = str(call.from_user.id)
    if calculate_total_power(p1) <= 0:
        bot.answer_callback_query(call.id, "❌ Ваш состав пуст!", show_alert=True)
        return

    opponents = [uid for uid in users_db.keys() if uid != p1 and calculate_total_power(uid) > 0]
    if not opponents:
        bot.answer_callback_query(call.id, "❌ Соперники не найдены.", show_alert=True)
        return
        
    run_match_logic(call.message.chat.id, p1, random.choice(opponents))

@bot.callback_query_handler(func=lambda call: call.data == "pvp_action_by_user")
def pvp_search_by_username_start(call):
    sent_msg = bot.send_message(call.message.chat.id, "👤 Введите username или ID игрока:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(sent_msg, process_pvp_search_by_input)

def process_pvp_search_by_input(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_main_menu(message.from_user.id))
        return
    query = message.text.replace("@", "").lower().strip()
    users_db = load_data('users')
    p1 = str(message.from_user.id)
    p2 = None
    
    for uid, info in users_db.items():
        if uid == query or info.get('username', '').replace("@", "").lower() == query:
            p2 = uid
            break
            
    if not p2 or p2 == p1 or calculate_total_power(p2) <= 0:
        bot.send_message(message.chat.id, "❌ Игрок не найден или у него пустой состав.", reply_markup=create_main_menu(p1))
        return
        
    run_match_logic(message.chat.id, p1, p2)

def run_match_logic(chat_id, p1, p2):
    users_db = load_data('users')
    w1 = float(calculate_total_power(p1)) ** 1.35
    w2 = float(calculate_total_power(p2)) ** 1.35
    
    winner = random.choices([p1, p2], weights=[w1 or 1, w2 or 1])[0]
    users_db[winner]['score'] += 1000
    save_data(users_db, 'users')
    pvp_cooldowns[p1] = time.time()
    
    bot.send_message(chat_id, f"🏆 Победитель: {users_db[winner]['username']} (+1,000 очков)", reply_markup=create_main_menu(p1))

# ==============================================================================
# [10] ПРОФИЛЬ, ТОП И ПРОСМОТР АЛЬБОМОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_view_handler(message):
    if check_ban_status(message.from_user): return
    uid = str(message.from_user.id)
    u_info = load_data('users').get(uid, {})
    cards_cnt = len(load_data('colls').get(uid, []))
    
    text = f"👤 **ПРОФИЛЬ**\n\nБаланс: {u_info.get('score', 0):,} очков\nКарт: {cards_cnt}\nМощь: {calculate_total_power(uid)}"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ очков")
def global_top_handler(message):
    if check_ban_status(message.from_user): return
    users = sorted(load_data('users').items(), key=lambda x: x[1]['score'], reverse=True)[:10]
    text = "🏆 **ТОП-10 ИГРОКОВ**\n\n"
    for i, (uid, info) in enumerate(users, 1):
        text += f"{i}. {info['username']} — {info['score']:,} очков\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection_menu_handler(message):
    bot.send_message(message.chat.id, "🗂 Раздел коллекции находится в разработке.", reply_markup=create_main_menu(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📋 Состав")
def squad_menu_handler(message):
    bot.send_message(message.chat.id, "📋 Раздел управления составом находится в разработке.", reply_markup=create_main_menu(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_handler(message):
    if check_admin_permission(message.from_user):
        bot.send_message(message.chat.id, "🛠 Панель администратора:", reply_markup=create_admin_menu())

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_to_menu_handler(message):
    bot.send_message(message.chat.id, "🏠 Вы вернулись в главное меню", reply_markup=create_main_menu(message.from_user.id))

if __name__ == '__main__':
    print("Бот успешно запущен!")
    bot.infinity_polling()
