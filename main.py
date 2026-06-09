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
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("FootballBotCore")

# ==============================================================================
# [2] ГЛОБАЛЬНЫЕ НАСТРОЙКИ И ИНИЦИАЛИЗАЦИЯ БОТА
# ==============================================================================

# Уникальный токен вашего Telegram бота
TOKEN = "8834454809:AAGwW6gfVziVZ1u-gplIwI1DLt1ZJBBMVeE"

# Список администраторов (цифровые Telegram ID)
ADMINS = [7908057052, 1674945230]

bot = telebot.TeleBot(TOKEN)

# Конфигурация путей к файлам базы данных JSON
DB_FILES = {
    'cards': 'cards.json',         # База данных всех существующих карточек
    'colls': 'collections.json',   # Коллекции карточек игроков
    'squads': 'squads.json',       # Текущие футбольные составы пользователей
    'users': 'users_data.json',     # Профили пользователей, балансы, статистика
    'bans': 'bans.json',           # Черный список (заблокированные ID и юзернеймы)
    'promos': 'promos.json'        # Доступные промокоды и их параметры
}

# ==============================================================================
# [3] ИГРОВЫЕ ПАРАМЕТРЫ И КОНФИГУРАЦИЯ БАЛАНСА
# ==============================================================================

# Характеристики редкостей карт, шансы выпадения и сила атаки
RARITY_STATS = {
    1: {"chance": 35, "score": 1000, "atk": 100, "label": "Обычная"},
    2: {"chance": 30, "score": 3000, "atk": 450, "label": "Необычная"},
    3: {"chance": 20, "score": 7500, "atk": 1000, "label": "Редкая"},
    4: {"chance": 10, "score": 15000, "atk": 2500, "label": "Эпическая"},
    5: {"chance": 5, "score": 30000, "atk": 5000, "label": "Легендарная"}
}

# Декодирование футбольных позиций на русский язык
POSITIONS_RU = {
    "ГК": "Вратарь", 
    "ЛЗ": "Левый Защитник", 
    "ПЗ": "Правый Защитник",
    "ЦП": "Центральный Полузащитник", 
    "ЛВ": "Левый Вингер", 
    "ПВ": "Правый Вингер", 
    "КФ": "Нападающий"
}

# Конфигурация слотов игрового состава (7 позиций)
SQUAD_SLOTS = {
    0: {"label": "🧤 ГК (Вратарь)", "code": "ГК"},
    1: {"label": "🛡 ЛЗ (Защитник)", "code": "ЛЗ"},
    2: {"label": "🛡 ПЗ (Защитник)", "code": "ПЗ"},
    3: {"label": "👟 ЦП (Полузащитник)", "code": "ЦП"},
    4: {"label": "⚡️ ЛВ (Вингер)", "code": "ЛВ"},
    5: {"label": "⚡️ ПВ (Вингер)", "code": "ПВ"},
    6: {"label": "🎯 КФ (Нападающий)", "code": "КФ"}
}

# Глобальные словари для отслеживания времени перезарядки действий (Cooldowns)
roll_cooldowns = {}
pvp_cooldowns = {}

# Очередь поиска онлайн-матчей (хранит ID игроков, ожидающих игру)
online_matchmaking_queue = []

# ==============================================================================
# [4] УПРАВЛЕНИЕ ДАННЫМИ (JSON STORAGE ENGINE С АВТО-БЭКАПОМ)
# ==============================================================================

def initialize_database_files():
    """Проверяет наличие всех файлов БД и создает пустые структуры, если файлы отсутствуют."""
    logger.info("Проверка целостности файлов базы данных...")
    for key, file_name in DB_FILES.items():
        if not os.path.exists(file_name):
            default_structure = [] if key in ['cards', 'bans'] else {}
            try:
                with open(file_name, 'w', encoding='utf-8') as f:
                    json.dump(default_structure, f, ensure_ascii=False, indent=4)
                logger.info(f"Создан новый пустой файл базы данных: {file_name}")
            except IOError as e:
                logger.critical(f"Не удалось инициализировать файл {file_name}: {e}")

# Запуск первичной инициализации при импорте модуля
initialize_database_files()


def load_data(key):
    file_path = DB_FILES.get(key)
    if not file_path:
        return [] if key in ['cards', 'bans'] else {}

    if not os.path.exists(file_path):
        backup_path = file_path + ".bak"
        if os.path.exists(backup_path):
            try:
                with open(backup_path, 'r', encoding='utf-8') as b_file:
                    backup_content = b_file.read()
                with open(file_path, 'w', encoding='utf-8') as f_file:
                    f_file.write(backup_content)
            except IOError:
                pass
        else:
            return [] if key in ['cards', 'bans'] else {}

    with open(file_path, 'r', encoding='utf-8') as file_in:
        try:
            content = file_in.read()
            if not content.strip():
                return [] if key in ['cards', 'bans'] else {}
            return json.loads(content)
        except json.JSONDecodeError:
            backup_path = file_path + ".bak"
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, 'r', encoding='utf-8') as backup_in:
                        return json.loads(backup_in.read())
                except Exception:
                    pass
            return [] if key in ['cards', 'bans'] else {}
        except Exception:
            return [] if key in ['cards', 'bans'] else {}


def save_data(data_object, key):
    file_path = DB_FILES.get(key)
    if not file_path:
        return False

    if os.path.exists(file_path):
        try:
            backup_path = file_path + ".bak"
            if os.path.exists(backup_path):
                os.remove(backup_path)
            os.rename(file_path, backup_path)
        except Exception:
            pass

    try:
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(data_object, file_out, ensure_ascii=False, indent=4)
        return True
    except IOError:
        backup_path = file_path + ".bak"
        if os.path.exists(backup_path):
            try:
                os.rename(backup_path, file_path)
            except Exception:
                pass
        return False
    except Exception:
        return False

# ==============================================================================
# [5] СИСТЕМНЫЕ ПРОВЕРКИ, БЕЗОПАСНОСТЬ И ВЫЧИСЛЕНИЯ
# ==============================================================================

def check_admin_permission(user_obj):
    if user_obj is None:
        return False
    return user_obj.id in ADMINS


def check_ban_status(user_obj):
    if user_obj is None:
        return False
    ban_list = load_data('bans')
    user_id_string = str(user_obj.id)
    user_name_string = user_obj.username.lower() if user_obj.username else "no_username_set"
    if user_id_string in ban_list or user_name_string in ban_list:
        return True
    return False


def calculate_total_power(user_id):
    squad_data = load_data('squads')
    my_squad = squad_data.get(str(user_id), [None] * 7)
    power_sum = 0
    for card_item in my_squad:
        if card_item is not None and isinstance(card_item, dict):
            stars = card_item.get('stars', 1)
            if stars not in RARITY_STATS:
                stars = 1
            power_sum += RARITY_STATS[stars]['atk']
    return power_sum


def log_action(user_id, action_name):
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"ИГРОК: {user_id} | ДЕЙСТВИЕ: {action_name} | ВРЕМЯ: {current_time}")

# ==============================================================================
# [6] ИНТЕРФЕЙСНЫЙ ДВИЖОК (ГЕНЕРАЦИЯ КЛАВИАТУР СИСТЕМЫ)
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
    
    markup.add(btn_roll, btn_collection)
    markup.add(btn_squad, btn_profile)
    markup.add(btn_top, btn_pvp)
    markup.add(btn_promo, btn_referrals)
    
    class LocalUserObject:
        def __init__(self, uid):
            self.id = uid

    if check_admin_permission(LocalUserObject(user_id)):
        btn_admin = types.KeyboardButton("🛠 Админ-панель")
        markup.add(btn_admin)
        
    return markup


def create_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn_add_card = types.KeyboardButton("➕ Добавить карту")
    btn_del_card = types.KeyboardButton("🗑 Удалить карту")
    btn_add_promo = types.KeyboardButton("🎟 +Промокод")
    btn_del_promo = types.KeyboardButton("🗑 Удалить промокод")
    btn_ban = types.KeyboardButton("🚫 Забанить")
    btn_unban = types.KeyboardButton("✅ Разбанить")
    btn_reset = types.KeyboardButton("🧨 Обнулить бота")
    btn_back = types.KeyboardButton("🏠 Назад в меню")
    
    markup.add(btn_add_card, btn_del_card)
    markup.add(btn_add_promo, btn_del_promo)
    markup.add(btn_ban, btn_unban)
    markup.add(btn_reset, btn_back)
    return markup


def create_cancel_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup


def create_pvp_menu():
    """Инлайн-меню для выбора режима ПВП матча."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_bot_match = types.InlineKeyboardButton("🤖 Быстрый матч (с ботом)", callback_data="pvp_mode_bot")
    btn_online_match = types.InlineKeyboardButton("🔎 Искать онлайн-матч (живой игрок)", callback_data="pvp_mode_online")
    markup.add(btn_bot_match, btn_online_match)
    return markup

# ==============================================================================
# [7] ОБРАБОТЧИКИ СИСТЕМНЫХ КОМАНД И РЕФЕРАЛЬНОЙ СИСТЕМЫ
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_message_handler(message):
    if check_ban_status(message.from_user):
        bot.send_message(message.chat.id, "🚫 Вы заблокированы. Доступ к функциям симулятора закрыт.")
        return

    users_database = load_data('users')
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, f"START_COMMAND_TRIGGERED")

    inviter_id = None
    command_parts = message.text.split()
    if len(command_parts) > 1:
        inviter_id = command_parts[1].strip()

    if user_id_key not in users_database:
        user_display_name = f"@{message.from_user.username}" if message.from_user.username else f"id_{user_id_key}"
        users_database[user_id_key] = {
            "nick": message.from_user.first_name if message.from_user.first_name else "Футболист",
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
            users_database[inviter_id]["refs"] = users_database[inviter_id].get("refs", 0) + 1
            try:
                msg_to_inviter = (
                    "👥 **НОВЫЙ ИГРОК ПОДКЛЮЧЕН!**\n\n"
                    "По вашей реферальной ссылке зарегистрировался новый менеджер.\n"
                    "🎁 **Вам начислено вознаграждение:**\n"
                    "— 💰 **+5,000 очков на баланс**\n"
                    "— 🎫 **+3 бесплатных прокрута карточек**"
                )
                bot.send_message(int(inviter_id), msg_to_inviter, parse_mode="Markdown")
            except Exception:
                pass
        save_data(users_database, 'users')

    welcome_text = (
        "⚽️ **Приветствую, {}!**\n\n"
        "Вы попали в симулятор футбольных карточек.\n"
        "Собирайте уникальные составы, прокачивайте команду, активируйте секретные промокоды "
        "и побеждайте других менеджеров в реальном времени на ПВП Арене!\n\n"
        "Используйте встроенное графическое меню для управления."
    ).format(message.from_user.first_name)
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_menu(message.from_user.id), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_stats_handler(message):
    if check_ban_status(message.from_user):
        return
    user_id = message.from_user.id
    users_db = load_data('users')
    try:
        bot_info = bot.get_me()
        bot_username = bot_info.username
    except Exception:
        bot_username = "FootballCardSimulatorBot"
    
    invite_link = f"https://t.me/{bot_username}?start={user_id}"
    user_profile_data = users_db.get(str(user_id), {})
    ref_count = user_profile_data.get("refs", 0)
    
    referral_text = (
        "👥 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        "Развивайте футбольное сообщество бота и получайте ценные призы!\n\n"
        "🎁 **Награда за каждого приглашенного друга:**\n"
        "— 💰 **5,000 очков на счет**\n"
        "— 🎫 **3 бонусных прокрута карт**\n\n"
        "📊 Ваша личная статистика:\n"
        "— Всего приглашено игроков: **{}**\n\n"
        "🔗 Ваша уникальная ссылка для приглашений (нажмите для копирования):\n"
        "`{}`"
    ).format(ref_count, invite_link)
    bot.send_message(message.chat.id, referral_text, parse_mode="Markdown")

# ==============================================================================
# [8] МОДУЛЬ ПРОМОКОДОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input_start(message):
    if check_ban_status(message.from_user):
        return
    sent_msg = bot.send_message(
        message.chat.id, 
        "🎟 **АКТИВАЦИЯ ПРОМОКОДА**\n\nВведите ваш секретный промокод:", 
        reply_markup=create_cancel_menu(),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(sent_msg, process_promo_logic)


def process_promo_logic(message):
    user_id_key = str(message.from_user.id)
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "🔄 Ввод промокода отменен.", reply_markup=create_main_menu(message.from_user.id))
        return
        
    input_code = message.text.strip().upper()
    users_db = load_data('users')
    promos_db = load_data('promos')
    
    if user_id_key not in users_db:
        bot.send_message(message.chat.id, "❌ Системная ошибка. Перезапустите бота через /start", reply_markup=create_main_menu(message.from_user.id))
        return

    if input_code not in promos_db:
        bot.send_message(message.chat.id, "❌ Такого промокода не существует.", reply_markup=create_main_menu(message.from_user.id))
        return

    if 'used_promos' not in users_db[user_id_key]:
        users_db[user_id_key]['used_promos'] = []
        
    if input_code in users_db[user_id_key]['used_promos']:
        bot.send_message(message.chat.id, "❌ Вы уже активировали этот промокод.", reply_markup=create_main_menu(message.from_user.id))
        return

    code_info = promos_db[input_code]
    reward_type = code_info.get('type', 'score')
    reward_val = code_info.get('value', 0)
    
    if reward_type == 'rolls':
        users_db[user_id_key]['free_rolls'] = users_db[user_id_key].get('free_rolls', 0) + int(reward_val)
        success_msg = f"🎉 **АКТИВИРОВАН!**\n🎁 Награда: **+{int(reward_val)} бонусных прокрутов**!"
    elif reward_type == 'luck':
        users_db[user_id_key]['bonus_luck'] = float(reward_val)
        success_msg = f"🎉 **АКТИВИРОВАН!**\n🎁 Награда: **Множитель удачи х{float(reward_val)}**!"
    else:
        users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + int(reward_val)
        success_msg = f"🎉 **АКТИВИРОВАН!**\n🎁 Награда: **+{int(reward_val):,} очков**!"

    users_db[user_id_key]['used_promos'].append(input_code)
    save_data(users_db, 'users')
    bot.send_message(message.chat.id, success_msg, reply_markup=create_main_menu(message.from_user.id), parse_mode="Markdown")

# ==============================================================================
# [9] СИСТЕМА ПРОКРУТОВ КАРТ (КД 2 ЧАСА)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎰 Крутить карту")
def roll_card_handler(message):
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    all_cards = load_data('cards')
    
    if not all_cards or len(all_cards) == 0:
        bot.send_message(message.chat.id, "❌ В игре пока нет доступных футбольных карточек.")
        return
        
    current_time_stamp = time.time()
    bonus_rolls = users_db.get(user_id_key, {}).get('free_rolls', 0)
    
    # Кулдаун 2 часа
    if not check_admin_permission(message.from_user) and bonus_rolls <= 0:
        if user_id_key in roll_cooldowns:
            elapsed_time = current_time_stamp - roll_cooldowns[user_id_key]
            if elapsed_time < 7200:
                remaining_seconds = int(7200 - elapsed_time)
                hours = remaining_seconds // 3600
                minutes = (remaining_seconds % 3600) // 60
                bot.send_message(message.chat.id, f"⏳ **Кулдаун ролла!** Вы сможете прокрутить рулетку снова через **{hours}ч {minutes}м**.", parse_mode="Markdown")
                return

    user_luck_multiplier = users_db.get(user_id_key, {}).get('bonus_luck', 1.0)
    rarity_indices = sorted(RARITY_STATS.keys())
    
    calculated_weights = []
    for r_level in rarity_indices:
        base_chance = RARITY_STATS[r_level]['chance']
        if r_level >= 4:
            calculated_weights.append(base_chance * user_luck_multiplier)
        else:
            calculated_weights.append(base_chance)

    chosen_rarity_level = random.choices(rarity_indices, weights=calculated_weights)[0]
    filtered_card_pool = [card for card in all_cards if card.get('stars', 1) == chosen_rarity_level]
    
    if not filtered_card_pool:
        won_card_object = random.choice(all_cards)
        chosen_rarity_level = won_card_object.get('stars', 1)
    else:
        won_card_object = random.choice(filtered_card_pool)
        
    if bonus_rolls > 0:
        users_db[user_id_key]['free_rolls'] -= 1
        attempt_info_text = f"🎫 Осталось бонусных прокрутов: **{users_db[user_id_key]['free_rolls']}** шт."
    else:
        roll_cooldowns[user_id_key] = current_time_stamp
        attempt_info_text = "⏳ Следующий бесплатный ролл доступен через **2 часа**."

    users_db[user_id_key]['bonus_luck'] = 1.0
    collections_db = load_data('colls')
    if user_id_key not in collections_db:
        collections_db[user_id_key] = []
        
    has_duplicate = any(existing_card.get('name') == won_card_object.get('name') for existing_card in collections_db[user_id_key])
    
    if has_duplicate:
        earned_points = int(RARITY_STATS[chosen_rarity_level]['score'] * 0.3)
        result_status_label = f"🔄 **ДУБЛИКАТ!** Получена компенсация: `+{earned_points:,}`"
    else:
        earned_points = RARITY_STATS[chosen_rarity_level]['score']
        result_status_label = f"✨ **НОВАЯ КАРТА!** Добавлена в коллекцию: `+{earned_points:,}`"
        collections_db[user_id_key].append(won_card_object)
        save_data(collections_db, 'colls')

    users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + earned_points
    save_data(users_db, 'users')
    
    stars_visual_representation = "⭐" * chosen_rarity_level
    caption_message = (
        f"🏆 **СПИН РУЛЕТКИ ЗАВЕРШЕН!**\n\n"
        f"🏃‍♂️ Игрок: **{won_card_object.get('name')}**\n"
        f"🛡 Позиция: `{POSITIONS_RU.get(won_card_object.get('position', 'ЦП'))}`\n"
        f"🏢 Клуб: _{won_card_object.get('club', 'Свободный агент')}_\n"
        f"📊 Редкость: {stars_visual_representation}\n"
        f"⚡ АТК: **{RARITY_STATS[chosen_rarity_level]['atk']}**\n\n"
        f"{result_status_label}\n"
        f"💰 Баланс: **{users_db[user_id_key]['score']:,}** очков.\n\n"
        f"{attempt_info_text}"
    )

    try:
        bot.send_photo(message.chat.id, won_card_object.get('photo'), caption=caption_message, parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, caption_message, parse_mode="Markdown")

# ==============================================================================
# [10] ГАЛЕРЕЯ КОЛЛЕКЦИИ И СОСТАВЫ ИГРОКОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection_menu_handler(message):
    if check_ban_status(message.from_user):
        return
    user_id_key = str(message.from_user.id)
    collections_db = load_data('colls')
    my_cards_list = collections_db.get(user_id_key, [])
    
    if not my_cards_list:
        bot.send_message(message.chat.id, "🗂 У вас пока нет ни одной карточки. Крутите рулетку!", parse_mode="Markdown")
        return

    stats_by_rarity = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for card in my_cards_list:
        stars = card.get('stars', 1)
        if stars in stats_by_rarity:
            stats_by_rarity[stars] += 1

    summary_text = (
        f"🗂 **ВАША КОЛЛЕКЦИЯ ({len(my_cards_list)} шт.)**\n\n"
        f"⚪️ Обычные: **{stats_by_rarity[1]}**\n"
        f"🟢 Необычные: **{stats_by_rarity[2]}**\n"
        f"🔵 Редкие: **{stats_by_rarity[3]}**\n"
        f"🟡 Эпические: **{stats_by_rarity[4]}**\n"
        f"🔴 Легендарные: **{stats_by_rarity[5]}**\n"
    )
    inline_markup = types.InlineKeyboardMarkup(row_width=2)
    inline_markup.add(types.InlineKeyboardButton("⭐ Обычные", callback_data="view_rarity_1"), types.InlineKeyboardButton("⭐⭐ Необычные", callback_data="view_rarity_2"))
    inline_markup.add(types.InlineKeyboardButton("⭐⭐⭐ Редкие", callback_data="view_rarity_3"), types.InlineKeyboardButton("⭐⭐⭐⭐ Эпики", callback_data="view_rarity_4"))
    inline_markup.add(types.InlineKeyboardButton("👑 Легенды", callback_data="view_rarity_5"))
    bot.send_message(message.chat.id, summary_text, reply_markup=inline_markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("view_rarity_"))
def process_view_rarity_callback(call):
    user_id_key = str(call.from_user.id)
    rarity_level_to_filter = int(call.data.replace("view_rarity_", ""))
    collections_db = load_data('colls')
    filtered_cards = [c for c in collections_db.get(user_id_key, []) if c.get('stars', 1) == rarity_level_to_filter]

    if not filtered_cards:
        bot.answer_callback_query(call.id, "У вас нет карт этой редкости!", show_alert=True)
        return

    bot.answer_callback_query(call.id, "Загрузка...")
    response_page_text = f"🗂 **СПИСОК КАРТ [{RARITY_STATS[rarity_level_to_filter]['label']}]**\n\n"
    for index, card in enumerate(filtered_cards, 1):
        response_page_text += f"{index}. **{card.get('name')}** (`{card.get('position')}`) — АТК: **{RARITY_STATS[rarity_level_to_filter]['atk']}**\n"
    bot.send_message(call.message.chat.id, response_page_text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📋 Состав")
def squad_menu_handler(message):
    if check_ban_status(message.from_user):
        return
    user_id_key = str(message.from_user.id)
    squads_db = load_data('squads')
    
    if user_id_key not in squads_db:
        squads_db[user_id_key] = [None] * 7
        save_data(squads_db, 'squads')
        
    current_user_squad = squads_db[user_id_key]
    squad_view_text = f"📋 **ВАШ СОСТАВ СБОРНОЙ**\n\n⚔️ Общая мощь (АТК): **{calculate_total_power(message.from_user.id)}**\n\n"
    inline_squad_markup = types.InlineKeyboardMarkup(row_width=1)
    
    for slot_id, slot_meta in SQUAD_SLOTS.items():
        assigned_card = current_user_squad[slot_id] if slot_id < len(current_user_squad) else None
        if assigned_card:
            slot_status_string = f"{slot_meta['label']}: {assigned_card.get('name')} (⭐{assigned_card.get('stars', 1)})"
        else:
            slot_status_string = f"{slot_meta['label']}: ❌ Пусто"
        squad_view_text += f"• {slot_status_string}\n"
        inline_squad_markup.add(types.InlineKeyboardButton(f"⚙️ Настроить {slot_meta['code']}", callback_data=f"manage_slot_{slot_id}"))
        
    bot.send_message(message.chat.id, squad_view_text, reply_markup=inline_squad_markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("manage_slot_"))
def process_manage_slot_callback(call):
    user_id_key = str(call.from_user.id)
    slot_id_to_change = int(call.data.replace("manage_slot_", ""))
    required_position_code = SQUAD_SLOTS[slot_id_to_change]['code']
    collections_db = load_data('colls')
    eligible_cards = [c for c in collections_db.get(user_id_key, []) if c.get('position') == required_position_code]
    
    if not eligible_cards:
        bot.answer_callback_query(call.id, f"В коллекции нет игроков позиции {required_position_code}!", show_alert=True)
        return
        
    selection_markup = types.InlineKeyboardMarkup(row_width=1)
    for index, card in enumerate(eligible_cards):
        button_text = f"{card.get('name')} (АТК: {RARITY_STATS[card.get('stars', 1)]['atk']})"
        selection_markup.add(types.InlineKeyboardButton(button_text, callback_data=f"setcard_{slot_id_to_change}_{index}"))
    selection_markup.add(types.InlineKeyboardButton("🗑 Очистить слот", callback_data=f"clear_slot_{slot_id_to_change}"))
    
    bot.send_message(call.message.chat.id, "🏃‍♂️ **ВЫБОР ИГРОКА:**", reply_markup=selection_markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("setcard_") or call.data.startswith("clear_slot_"))
def finalize_slot_assignment_callback(call):
    user_id_key = str(call.from_user.id)
    squads_db = load_data('squads')
    if user_id_key not in squads_db: squads_db[user_id_key] = [None] * 7

    if call.data.startswith("clear_slot_"):
        slot_id = int(call.data.replace("clear_slot_", ""))
        squads_db[user_id_key][slot_id] = None
        save_data(squads_db, 'squads')
        bot.edit_message_text("✅ Игрок убран из тактического состава.", chat_id=call.message.chat.id, message_id=call.message.message_id)
        return

    data_parts = call.data.split("_")
    slot_id, card_index_in_pool = int(data_parts[1]), int(data_parts[2])
    collections_db = load_data('colls')
    eligible_cards = [c for c in collections_db.get(user_id_key, []) if c.get('position') == SQUAD_SLOTS[slot_id]['code']]
    
    squads_db[user_id_key][slot_id] = eligible_cards[card_index_in_pool]
    save_data(squads_db, 'squads')
    bot.edit_message_text(f"✅ Утвержден на позицию: **{eligible_cards[card_index_in_pool].get('name')}**", chat_id=call.message.chat.id, message_id=call.message.message_id, parse_mode="Markdown")

# ==============================================================================
# [11] ПРОФИЛЬ И РЕЙТИНГИ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def user_profile_handler(message):
    if check_ban_status(message.from_user):
        return
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    collections_db = load_data('colls')
    user_profile = users_db.get(user_id_key, {})
    
    profile_text = (
        f"👤 **ЛИЧНЫЙ КАБИНЕТ МЕНЕДЖЕРА**\n\n"
        f"📝 Никнейм: **{user_profile.get('nick', 'Не указан')}**\n"
        f"💰 Баланс: **{user_profile.get('score', 0):,}** очков\n"
        f"🎫 Прокруты: **{user_profile.get('free_rolls', 0)}** шт.\n"
        f"🗂 Всего карт: **{len(collections_db.get(user_id_key, []))}** шт.\n"
        f"⚔️ Мощность состава: **{calculate_total_power(message.from_user.id)}** АТК\n"
    )
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🏆 Топ очков")
def leaderboard_handler(message):
    if check_ban_status(message.from_user):
        return
    users_db = load_data('users')
    sorted_users = sorted(users_db.items(), key=lambda item: item[1].get('score', 0), reverse=True)[:10]
    
    leaderboard_text = "🏆 **ТОП-10 ФУТБОЛЬНЫХ МЕНЕДЖЕРОВ**\n\n"
    for rank, (uid, p_data) in enumerate(sorted_users, 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        leaderboard_text += f"{medal} {p_data.get('nick')} ({p_data.get('username')}) — **{p_data.get('score', 0):,}** очков\n"
    bot.send_message(message.chat.id, leaderboard_text, parse_mode="Markdown")

# ==============================================================================
# [12] ПВП АРЕНА (ДВИЖОК С ВЫБОРОМ: БОТ ИЛИ ОНЛАЙН С ЖИВЫМ ИГРОКОМ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🏟 ПВП Арена")
def pvp_arena_entry_handler(message):
    """Главная точка входа на Арену. Запрашивает выбор режима матча."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    current_time_stamp = time.time()
    
    # Кулдаун 1 час на поединки (для не-админов)
    if not check_admin_permission(message.from_user):
        if user_id_key in pvp_cooldowns:
            elapsed_time = current_time_stamp - pvp_cooldowns[user_id_key]
            if elapsed_time < 3600:
                remaining_seconds = int(3600 - elapsed_time)
                bot.send_message(message.chat.id, f"⏳ **Команда на восстановлении!** Следующий ПВП-матч доступен через **{remaining_seconds // 60} мин. {remaining_seconds % 60} сек.**")
                return

    squads_db = load_data('squads')
    my_squad = squads_db.get(user_id_key, [])
    if not my_squad or all(slot is None for slot in my_squad):
        bot.send_message(message.chat.id, "🏟 **Арена:** Вы не можете играть с пустым составом! Зайдите в меню **📋 Состав**.", parse_mode="Markdown")
        return

    bot.send_message(
        message.chat.id,
        "🏟 **ДОБРО ПОЖАЛОВАТЬ НА ПВП АРЕНУ!**\n\n"
        "Выберите тип футбольного противостояния:\n"
        "1️⃣ **Быстрый матч с ботом** — игра против случайного зарегистрированного состава из базы.\n"
        "2️⃣ **Онлайн-матч** — бот поместит вас в комнату ожидания и подберет живого соперника, запустившего поиск параллельно!",
        reply_markup=create_pvp_menu(),
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("pvp_mode_"))
def process_pvp_mode_selection(call):
    """Обработчик выбора режима матча."""
    user_id_key = str(call.from_user.id)
    mode = call.data.replace("pvp_mode_", "")
    
    current_time_stamp = time.time()
    if not check_admin_permission(call.from_user) and user_id_key in pvp_cooldowns and (current_time_stamp - pvp_cooldowns[user_id_key]) < 3600:
        bot.answer_callback_query(call.id, "Вы еще не восстановились!")
        return

    bot.answer_callback_query(call.id, "Режим выбран")
    
    # --- РЕЖИМ 1: МАТЧ С БОТОМ ---
    if mode == "bot":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        squads_db = load_data('squads')
        users_db = load_data('users')
        
        potential_opponents = [uid for uid in squads_db.keys() if uid != user_id_key and any(slot is not None for slot in squads_db[uid])]
        
        if not potential_opponents:
            bot.send_message(call.message.chat.id, "🤖 К сожалению, в базе еще нет других команд для симуляции ИИ-матча. Выставлен дефолтный ИИ-соперник.")
            opp_name = "ИИ-Бот Академии"
            opp_power = random.randint(1000, 5000)
        else:
            chosen_opp_id = random.choice(potential_opponents)
            opp_name = users_db.get(chosen_opp_id, {}).get('nick', 'Случайный Менеджер')
            opp_power = calculate_total_power(chosen_opp_id)
            if opp_power == 0: opp_power = random.randint(1000, 3000)
            
        my_power = calculate_total_power(user_id_key)
        
        bot.send_message(call.message.chat.id, "🎬 **Матч начался! Рефери дает стартовый свисток...**")
        time.sleep(1.5)
        
        # Генерация счета на основе мощностей
        my_score = 0
        opp_score = 0
        for _ in range(3):  # 3 опасных момента
            if random.randint(0, my_power + opp_power) < my_power:
                my_score += 1
            if random.randint(0, my_power + opp_power) < opp_power:
                opp_score += 1
                
        pvp_cooldowns[user_id_key] = current_time_stamp
        
        result_text = f"🏟 **ФИНАЛЬНЫЙ СВИСТОК!**\n\nВаша команда: **{my_power} АТК**\nКоманда {opp_name}: **{opp_power} АТК**\n\n🔢 Счёт матча: 🟥 **{my_score} : {opp_score}** 🟨\n\n"
        
        if my_score > opp_score:
            reward = 3500
            users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + reward
            result_text += f"🎉 **ПОБЕДА!** Вы продемонстрировали выдающийся тактический футбол. Награда: **+{reward} очков**!"
        elif my_score < opp_score:
            result_text += "❌ **ПОРАЖЕНИЕ.** Ваш состав не устоял под прессингом оппонента. Проведите ротацию состава и попробуйте снова!"
        else:
            reward = 1000
            users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + reward
            result_text += f"🤝 **НИЧЬЯ!** Напряженная борьба на каждом сантиметре поля. Бонус: **+{reward} очков**."
            
        save_data(users_db, 'users')
        bot.send_message(call.message.chat.id, result_text, parse_mode="Markdown")

    # --- РЕЖИМ 2: ОНЛАЙН-МАТЧ С ЖИВЫМ ИГРОКОМ ---
    elif mode == "online":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if int(user_id_key) in online_matchmaking_queue:
            bot.send_message(call.message.chat.id, "🔎 Вы уже находитесь в очереди поиска онлайн-игры.")
            return
            
        if online_matchmaking_queue:
            opponent_id_key = str(online_matchmaking_queue.pop(0))
            if opponent_id_key == user_id_key:
                bot.send_message(call.message.chat.id, "🔎 Поиск возобновлен. Ожидайте оппонента...")
                online_matchmaking_queue.append(int(user_id_key))
                return
                
            # Старт матча между user_id_key и opponent_id_key
            users_db = load_data('users')
            p1_name = users_db.get(user_id_key, {}).get('nick', 'Игрок 1')
            p2_name = users_db.get(opponent_id_key, {}).get('nick', 'Игрок 2')
            
            p1_power = calculate_total_power(user_id_key)
            p2_power = calculate_total_power(opponent_id_key)
            
            # Оповещение обоих игроков
            match_start_announcement = "⚡ **СОПЕРНИК НАЙДЕН!**\n\n⚔ Противостояние начинается прямо сейчас!"
            try:
                bot.send_message(int(user_id_key), match_start_announcement)
                bot.send_message(int(opponent_id_key), match_start_announcement)
            except Exception:
                pass
                
            p1_goals = 0
            p2_goals = 0
            for _ in range(3):
                if random.randint(0, p1_power + p2_power) < p1_power: p1_goals += 1
                if random.randint(0, p1_power + p2_power) < p2_power: p2_goals += 1
                
            pvp_cooldowns[user_id_key] = current_time_stamp
            pvp_cooldowns[opponent_id_key] = current_time_stamp
            
            # Подсчет итогов для Игрока 1
            res_p1 = f"🏟 **ИТОГИ ОНЛАЙН МАТЧА**\n\nВы: **{p1_power} АТК** ({p1_name})\nСоперник: **{p2_power} АТК** ({p2_name})\n\n🔢 Итоговый счёт: `{p1_goals} : {p2_goals}`\n\n"
            if p1_goals > p2_goals:
                users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + 5000
                res_p1 += "🎉 **ВЫ ПОБЕДИЛИ!** Награда: **+5,000 очков!**"
            elif p1_goals < p2_goals:
                res_p1 += "❌ **ВЫ ПРОИГРАЛИ.** Оппонент оказался сильнее в этот раз."
            else:
                users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + 1500
                res_p1 += "🤝 **НИЧЬЯ!** Бонус: **+1,500 очков.**"
                
            # Подсчет итогов для Игрока 2
            res_p2 = f"🏟 **ИТОГИ ОНЛАЙН МАТЧА**\n\nВы: **{p2_power} АТК** ({p2_name})\nСоперник: **{p1_power} АТК** ({p1_name})\n\n🔢 Итоговый счёт: `{p2_goals} : {p1_goals}`\n\n"
            if p2_goals > p1_goals:
                users_db[opponent_id_key]['score'] = users_db[opponent_id_key].get('score', 0) + 5000
                res_p2 += "🎉 **ВЫ ПОБЕДИЛИ!** Награда: **+5,000 очков!**"
            elif p2_goals < p1_goals:
                res_p2 += "❌ **ВЫ ПРОИГРАЛИ.** Оппонент оказался сильнее в этот раз."
            else:
                users_db[opponent_id_key]['score'] = users_db[opponent_id_key].get('score', 0) + 1500
                res_p2 += "🤝 **НИЧЬЯ!** Бонус: **+1,500 очков.**"
                
            save_data(users_db, 'users')
            
            try:
                bot.send_message(int(user_id_key), res_p1, parse_mode="Markdown")
                bot.send_message(int(opponent_id_key), res_p2, parse_mode="Markdown")
            except Exception:
                pass
        else:
            online_matchmaking_queue.append(int(user_id_key))
            bot.send_message(call.message.chat.id, "🔎 **Вы добавлены в комнату ожидания...**\nБот ищет живого оппонента. Пожалуйста, подождите. Как только второй игрок нажмет поиск, матч начнется автоматически!")

# ==============================================================================
# [13] АДМИНИСТРАТИВНЫЙ ФУНКЦИОНАЛ (УПРАВЛЕНИЕ СИСТЕМОЙ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_root_handler(message):
    if not check_admin_permission(message.from_user):
        return
    bot.send_message(message.chat.id, "🛠 **ГЛАВНОЕ МЕНЮ АДМИНИСТРАТОРА**\n\nВыберите команду управления:", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def admin_back_to_main_menu(message):
    bot.send_message(message.chat.id, "🔄 Возврат в пользовательское меню.", reply_markup=create_main_menu(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def admin_add_card_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите данные новой карты в формате:\n`Имя | Позиция (ГК, ЛЗ, ПЗ, ЦП, ЛВ, ПВ, КФ) | Клуб | Редкость (1-5) | URL-Фото`", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_add_card_step2)

def admin_add_card_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    try:
        parts = message.text.split("|")
        name = parts[0].strip()
        pos = parts[1].strip().upper()
        club = parts[2].strip()
        stars = int(parts[3].strip())
        photo = parts[4].strip()
        
        cards = load_data('cards')
        cards.append({"name": name, "position": pos, "club": club, "stars": stars, "photo": photo})
        save_data(cards, 'cards')
        bot.send_message(message.chat.id, f"✅ Карта **{name}** успешно добавлена в общую базу роллов!", reply_markup=create_admin_menu(), parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, "❌ Ошибка синтаксиса. Проверьте разделители и формат данных.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту")
def admin_delete_card_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите ТОЧНОЕ имя футболиста для удаления карты из системы:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_delete_card_step2)

def admin_delete_card_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    cards = load_data('cards')
    target = message.text.strip()
    new_cards = [c for c in cards if c.get('name', '').lower() != target.lower()]
    
    if len(cards) == len(new_cards):
        bot.send_message(message.chat.id, "❌ Карта с таким именем не найдена.", reply_markup=create_admin_menu())
    else:
        save_data(new_cards, 'cards')
        bot.send_message(message.chat.id, f"✅ Карта **{target}** успешно удалена из базы.", reply_markup=create_admin_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎟 +Промокод")
def admin_add_promo_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите параметры промокода в формате:\n`КОД | Тип (score / rolls / luck) | Значение`", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_add_promo_step2)

def admin_add_promo_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    try:
        parts = message.text.split("|")
        code = parts[0].strip().upper()
        p_type = parts[1].strip().lower()
        val = float(parts[2].strip()) if p_type == 'luck' else int(parts[2].strip())
        
        promos = load_data('promos')
        promos[code] = {"type": p_type, "value": val}
        save_data(promos, 'promos')
        bot.send_message(message.chat.id, f"✅ Промокод `{code}` успешно создан!", reply_markup=create_admin_menu(), parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, "❌ Неверный формат данных.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🗑 Удалить промокод")
def admin_del_promo_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите кодовое слово промокода для удаления:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_del_promo_step2)

def admin_del_promo_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    promos = load_data('promos')
    target = message.text.strip().upper()
    if target in promos:
        del promos[target]
        save_data(promos, 'promos')
        bot.send_message(message.chat.id, f"✅ Промокод `{target}` уничтожен.", reply_markup=create_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Промокод не найден.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🚫 Забанить")
def admin_ban_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите Telegram ID или юзернейм (без @) нарушителя:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_ban_step2)

def admin_ban_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    bans = load_data('bans')
    target = message.text.strip().lower()
    if target not in bans:
        bans.append(target)
        save_data(bans, 'bans')
        bot.send_message(message.chat.id, f"✅ Пользователь `{target}` добавлен в черный список.", reply_markup=create_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Пользователь уже находится в бане.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "✅ Разбанить")
def admin_unban_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Введите ID или юзернейм для разблокировки:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_unban_step2)

def admin_unban_step2(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Действие отменено", reply_markup=create_admin_menu())
        return
    bans = load_data('bans')
    target = message.text.strip().lower()
    if target in bans:
        bans.remove(target)
        save_data(bans, 'bans')
        bot.send_message(message.chat.id, f"✅ Пользователь `{target}` амнистирован.", reply_markup=create_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Данный пользователь отсутствует в черном списке.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🧨 Обнулить бота")
def admin_reset_system_step1(message):
    if not check_admin_permission(message.from_user): return
    msg = bot.send_message(message.chat.id, "Вы уверены, что хотите полностью стереть профили, составы и коллекции ВСЕХ пользователей? Напишите `ДА, Я УВЕРЕН` для подтверждения.", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(msg, admin_reset_system_step2)

def admin_reset_system_step2(message):
    if message.text == "ДА, Я УВЕРЕН":
        save_data({}, 'users')
        save_data({}, 'colls')
        save_data({}, 'squads')
        bot.send_message(message.chat.id, "🧨 **ИГРОВАЯ БАЗА ДАННЫХ УСПЕШНО СБРОШЕНА ДО НУЛЯ!**", reply_markup=create_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Действие отменено или подтверждение введено неверно.", reply_markup=create_admin_menu())

# ==============================================================================
# [14] ТОЧКА ВХОДА И НЕПРЕРЫВНЫЙ ОПРОС (POLLING)
# ==============================================================================

if __name__ == '__main__':
    logger.info("Футбольный менеджер-симулятор успешно запущен и готов к обработке пакетов.")
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
