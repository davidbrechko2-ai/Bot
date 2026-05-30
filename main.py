import telebot
from telebot import types
import random
import time
import json
import os
import sys
import loggin

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
TOKEN = "8359038333:AAGJsCswTmItZ77qcdPbCaEBV8safgGei9A"

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
    btn_edit_card = types.KeyboardButton("📝 Изменить карту")
    btn_del_card = types.KeyboardButton("🗑 Удалить карту")
    btn_add_promo = types.KeyboardButton("🎟 +Промокод")
    btn_del_promo = types.KeyboardButton("🗑 Удалить промокод")
    btn_ban = types.KeyboardButton("🚫 Забанить")
    btn_unban = types.KeyboardButton("✅ Разбанить")
    btn_reset = types.KeyboardButton("🧨 Обнулить бота")
    btn_back = types.KeyboardButton("🏠 Назад в меню")
    
    markup.add(btn_add_card, btn_edit_card, btn_del_card)
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
    
    # Повторная базовая проверка на КД
    current_time_stamp = time.time()
    if not check_admin_permission(call.from_user) and user_id_key in pvp_cooldowns and (current_time_stamp - pvp_cooldowns[user_id_key]) < 3600:
        bot.answer_callback_query(call.id, "Вы еще не восстановились!")
        return

    bot.answer_callback_query(call.id, "Режим выбран")
    
    # --- РЕЖИМ 1: МАТЧ С БОТОМ ---
    if mode == "bot":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        squads_db = load_data('squads')
        potential_opponents = [uid for uid in squads_db.keys() if uid != user_id_key and any(slot is not None for slot in squads_db[uid])]
        
        if not potential_opponents:
            bot.send_message(call.message.chat.id, "🏟 Полноценных ботов-составов не найдено. Попробуйте Онлайн-матч!")
            return
            
        chosen_opponent_id = random.choice(potential_opponents)
        users_db = load_data('users')
        
        my_total_atk = calculate_total_power(call.from_user.id)
        opponent_total_atk = calculate_total_power(int(chosen_opponent_id))
        
        pvp_cooldowns[user_id_key] = current_time_stamp
        
        bot.send_message(call.message.chat.id, f"🏟 **МАТЧ С БОТОМ НАЧАТ!**\n\n⚔️ Ваша сила: **{my_total_atk} АТК**\n🛡 Сила соперника: **{opponent_total_atk} АТК**\n\n*Арбитр симулирует игру...*", parse_mode="Markdown")
        time.sleep(2)
        
        # Симуляция исхода
        total_pool = my_total_atk + opponent_total_atk if (my_total_atk + opponent_total_atk) > 0 else 1
        if random.uniform(0, 100) <= (my_total_atk / total_pool * 100):
            prize = random.randint(3000, 7000)
            users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + prize
            res_msg = f"🎉 **ПОБЕДА!** Награда: **+{prize:,} очков**!"
        else:
            consolation = random.randint(500, 1500)
            users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + consolation
            res_msg = f"😭 **ПОРАЖЕНИЕ!** Утешительный бонус: **+{consolation:,} очков**."
            
        save_data(users_db, 'users')
        bot.send_message(call.message.chat.id, res_msg, parse_mode="Markdown")

    # --- РЕЖИМ 2: ОНЛАЙН-МАТЧ (МАТЧМЕЙКИНГ РЕАЛЬНОГО ВРЕМЕНИ) ---
    elif mode == "online":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        if user_id_key in online_matchmaking_queue:
            bot.send_message(call.message.chat.id, "🔎 Вы уже находитесь в очереди поиска онлайн-матча.")
            return

        # Если в очереди никого нет — становимся первыми
        if not online_matchmaking_queue:
            online_matchmaking_queue.append(user_id_key)
            bot.send_message(
                call.message.chat.id, 
                "🔎 **ПОИСК ЖИВОГО СОПЕРНИКА...**\n\n"
                "Вы успешно добавлены в комнату ожидания.\n"
                "Как только другой менеджер нажмет поиск, матч начнется автоматически! Вы получите уведомление.",
                parse_mode="Markdown"
            )
            log_action(user_id_key, "ENTERED_ONLINE_QUEUE")
        else:
            # Вытягиваем соперника из очереди
            opponent_id_key = online_matchmaking_queue.pop(0)
            
            # Защита от игры с самим собой (если баг очереди)
            if opponent_id_key == user_id_key:
                online_matchmaking_queue.append(user_id_key)
                bot.send_message(call.message.chat.id, "🔎 Поиск продолжается...")
                return
                
            users_db = load_data('users')
            
            # Фиксация кулдауна обоим игрокам
            pvp_cooldowns[user_id_key] = current_time_stamp
            pvp_cooldowns[opponent_id_key] = current_time_stamp
            
            # Расчет сил сторон
            p1_atk = calculate_total_power(int(user_id_key))
            p2_atk = calculate_total_power(int(opponent_id_key))
            
            p1_nick = users_db.get(user_id_key, {}).get('nick', 'Игрок 1')
            p2_nick = users_db.get(opponent_id_key, {}).get('nick', 'Игрок 2')
            
            # Математика триумфа
            total_atk_pool = p1_atk + p2_atk if (p1_atk + p2_atk) > 0 else 1
            p1_win_chance = (p1_atk / total_atk_pool) * 100
            
            dice_roll = random.uniform(0, 100)
            
            if dice_roll <= p1_win_chance:
                # Победил Игрок 1 (тот, кто только что нажал кнопку)
                p1_prize = random.randint(5000, 10000)  # В онлайне награды выше!
                p2_consolation = random.randint(1000, 2000)
                
                users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + p1_prize
                users_db[opponent_id_key]['score'] = users_db[opponent_id_key].get('score', 0) + p2_consolation
                
                # Уведомление первому
                msg_p1 = f"🏟 **ОНЛАЙН-МАТЧ НАЙДЕН И ЗАВЕРШЕН!**\n\n⚔️ Соперник: **{p2_nick}**\n\n🎉 **ВЫ ПОБЕДИЛИ!** На поле была тотальная доминация.\n🎁 Награда: **+{p1_prize:,} очков**!"
                # Уведомление второму (кто ждал в очереди)
                msg_p2 = f"🏟 **ОНЛАЙН-МАТЧ НАЙДЕН И ЗАВЕРШЕН!**\n\n⚔️ Соперник: **{p1_nick}**\n\n😭 **ВЫ ПРОИГРАЛИ!** Соперник обошел вас тактически.\n🎁 Утешительный бонус: **+{p2_consolation:,} очков**."
            else:
                # Победил Игрок 2 (тот, кто покорно ждал в очереди)
                p2_prize = random.randint(5000, 10000)
                p1_consolation = random.randint(1000, 2000)
                
                users_db[opponent_id_key]['score'] = users_db[opponent_id_key].get('score', 0) + p2_prize
                users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + p1_consolation
                
                msg_p1 = f"🏟 **ОНЛАЙН-МАТЧ НАЙДЕН И ЗАВЕРШЕН!**\n\n⚔️ Соперник: **{p2_nick}**\n\n😭 **ВЫ ПРОИГРАЛИ!** Оппонент контратаковал безупречно.\n🎁 Утешительный бонус: **+{p1_consolation:,} очков**."
                msg_p2 = f"🏟 **ОНЛАЙН-МАТЧ НАЙДЕН И ЗАВЕРШЕН!**\n\n⚔️ Соперник: **{p1_nick}**\n\n🎉 **ВЫ ПОБЕДИЛИ!** Команда из зала ожидания разгромила врага!\n🎁 Награда: **+{p2_prize:,} очков**!"

            save_data(users_db, 'users')
            
            # Безопасная рассылка итогов
            try: bot.send_message(int(user_id_key), msg_p1, parse_mode="Markdown")
            except Exception: pass
            
            try: bot.send_message(int(opponent_id_key), msg_p2, parse_mode="Markdown")
            except Exception: pass
            
            log_action(user_id_key, f"ONLINE_MATCH_RESOLVED_WITH_{opponent_id_key}")

# ==============================================================================
# [13] МОДУЛЬ АДМИНИСТРИРОВАНИЯ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_root_handler(message):
    if not check_admin_permission(message.from_user): return
    bot.send_message(message.chat.id, "🛠 **ИНЖЕНЕРНАЯ АДМИН-ПАНЕЛЬ БОТА**", reply_markup=create_admin_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def admin_back_to_main_menu(message):
    if not check_admin_permission(message.from_user): return
    bot.send_message(message.chat.id, "🔄 Вы вышли из режима администрирования.", reply_markup=create_main_menu(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def admin_add_card_start(message):
    if not check_admin_permission(message.from_user): return
    sent = bot.send_message(message.chat.id, "➕ **Имя футболиста:**", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(sent, admin_add_card_step_2)


def admin_add_card_step_2(message):
    if message.text == "❌ Отмена": return
    card_name = message.text.strip()
    sent = bot.send_message(message.chat.id, f"➕ Позиция (**ГК, ЛЗ, ПЗ, ЦП, ЛВ, ПВ, КФ**):")
    bot.register_next_step_handler(sent, admin_add_card_step_3, card_name)


def admin_add_card_step_3(message, card_name):
    pos = message.text.strip().upper()
    if pos not in POSITIONS_RU: return
    sent = bot.send_message(message.chat.id, f"➕ Звездность (**1-5**):")
    bot.register_next_step_handler(sent, admin_add_card_step_4, card_name, pos)


def admin_add_card_step_4(message, card_name, pos):
    stars = int(message.text.strip())
    sent = bot.send_message(message.chat.id, f"➕ Название клуба:")
    bot.register_next_step_handler(sent, admin_add_card_step_5, card_name, pos, stars)


def admin_add_card_step_5(message, card_name, pos, stars):
    club = message.text.strip()
    sent = bot.send_message(message.chat.id, f"➕ Прямая URL-ссылка на фото:")
    bot.register_next_step_handler(sent, admin_add_card_finalize, card_name, pos, stars, club)


def admin_add_card_finalize(message, card_name, pos, stars, club):
    photo_url = message.text.strip()
    cards_list = load_data('cards')
    cards_list.append({"name": card_name, "position": pos, "stars": stars, "club": club, "photo": photo_url})
    save_data(cards_list, 'cards')
    bot.send_message(message.chat.id, "✅ Карточка успешно добавлена!", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🎟 +Промокод")
def admin_add_promo_start(message):
    if not check_admin_permission(message.from_user): return
    sent = bot.send_message(message.chat.id, "🎟 **Кодовое слово:**", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(sent, admin_add_promo_step_2)


def admin_add_promo_step_2(message):
    promo_code = message.text.strip().upper()
    sent = bot.send_message(message.chat.id, "🎟 Тип наград (**score, rolls, luck**):")
    bot.register_next_step_handler(sent, admin_add_promo_step_3, promo_code)


def admin_add_promo_step_3(message, promo_code):
    p_type = message.text.strip().lower()
    sent = bot.send_message(message.chat.id, "🎟 Значение бонуса:")
    bot.register_next_step_handler(sent, admin_add_promo_finalize, promo_code, p_type)


def admin_add_promo_finalize(message, promo_code, p_type):
    val = float(message.text.strip()) if p_type == 'luck' else int(message.text.strip())
    promos_db = load_data('promos')
    promos_db[promo_code] = {"type": p_type, "value": val}
    save_data(promos_db, 'promos')
    bot.send_message(message.chat.id, "✅ Промокод создан!", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🚫 Забанить")
def admin_ban_user_start(message):
    if not check_admin_permission(message.from_user): return
    sent = bot.send_message(message.chat.id, "🚫 Введите ID или Username для бана:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(sent, admin_ban_user_finalize)


def admin_ban_user_finalize(message):
    target = message.text.strip().lower()
    ban_list = load_data('bans')
    ban_list.append(target)
    save_data(ban_list, 'bans')
    bot.send_message(message.chat.id, "✅ Бан успешно зафиксирован.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🧨 Обнулить бота")
def admin_hard_reset_system(message):
    if not check_admin_permission(message.from_user): return
    save_data({}, 'users')
    save_data({}, 'colls')
    save_data({}, 'squads')
    roll_cooldowns.clear()
    pvp_cooldowns.clear()
    online_matchmaking_queue.clear()
    bot.send_message(message.chat.id, "🧨 Полный сброс выполнен!", reply_markup=create_admin_menu())

# ==============================================================================
# [14] ПРЕДОХРАНИТЕЛЬНЫЙ ДЕФОЛТНЫЙ ОБРАБОТЧИК
# ==============================================================================

@bot.message_handler(func=lambda message: True)
def default_fallback_text_handler(message):
    if check_ban_status(message.from_user): return
    bot.send_message(message.chat.id, "❓ Используйте кнопки графического меню.", reply_markup=create_main_menu(message.from_user.id))

# ==============================================================================
# [15] ЗАПУСК БОТА (POLLING)
# ==============================================================================

if __name__ == '__main__':
    logger.info("Бот футбольных карточек запущен на портах Telegram...")
    bot.infinity_polling(skip_pending=True)
