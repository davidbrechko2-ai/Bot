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

# Предустановленный список футбольных клубов для лора или кастомизации карт
FOOTBALL_CLUBS_POOL = [
    "Интер Милан",
    "Арсенал Лондон",
    "Барселона",
    "Наполи",
    "Реал Мадрид",
    "Манчестер Сити",
    "Бавария Мюнхен"
]

# Глобальные словари для отслеживания времени перезарядки действий (Cooldowns)
roll_cooldowns = {}
pvp_cooldowns = {}

# ==============================================================================
# [4] УПРАВЛЕНИЕ ДАННЫМИ (JSON STORAGE ENGINE ПРЯМОЙ ЗАПИСИ)
# ==============================================================================

def initialize_database_files():
    """Проверяет наличие всех файлов БД и создает пустые структуры, если файлы отсутствуют."""
    logger.info("Проверка целостности файлов базы данных...")
    for key, file_name in DB_FILES.items():
        if not os.path.exists(file_name) or os.path.getsize(file_name) == 0:
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
    """Безопасно загружает данные из JSON файла по ключу таблицы."""
    file_path = DB_FILES.get(key)
    if not file_path:
        return [] if key in ['cards', 'bans'] else {}

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        default_structure = [] if key in ['cards', 'bans'] else {}
        return default_structure

    with open(file_path, 'r', encoding='utf-8') as file_in:
        try:
            content = file_in.read()
            if not content.strip():
                return [] if key in ['cards', 'bans'] else {}
            return json.loads(content)
        except json.JSONDecodeError:
            return [] if key in ['cards', 'bans'] else {}
        except Exception:
            return [] if key in ['cards', 'bans'] else {}


def save_data(data_object, key):
    """Сохраняет переданный объект данных прямо в нужный JSON файл без конфликтов блокировки."""
    file_path = DB_FILES.get(key)
    if not file_path:
        return False

    try:
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(data_object, file_out, ensure_ascii=False, indent=4)
        return True
    except Exception as general_error:
        logger.critical(f"Критическая ошибка сохранения данных {key}: {general_error}")
        return False

# ==============================================================================
# [5] СИСТЕМНЫЕ ПРОВЕРКИ, БЕЗОПАСНОСТЬ И ВЫЧИСЛЕНИЯ
# ==============================================================================

def check_admin_permission(user_obj):
    """Проверяет, имеет ли пользователь административные права."""
    if user_obj is None:
        return False
    return user_obj.id in ADMINS


def check_ban_status(user_obj):
    """Проверяет, заблокирован ли пользователь в боте."""
    if user_obj is None:
        return False
        
    ban_list = load_data('bans')
    user_id_string = str(user_obj.id)
    user_name_string = user_obj.username.lower() if user_obj.username else "no_username_set"
    
    if user_id_string in ban_list:
        return True
    if user_name_string in ban_list:
        return True
        
    return False


def calculate_total_power(user_id):
    """Рассчитывает суммарную силу атаки (мощность) текущего футбольного состава игрока."""
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
    """Фиксирует действия пользователей в консоли для мониторинга активности."""
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"ИГРОК: {user_id} | ДЕЙСТВИЕ: {action_name} | ВРЕМЯ: {current_time}")

# ==============================================================================
# [6] ИНТЕРФЕЙСНЫЙ ДВИЖОК (ГЕНЕРАЦИЯ КЛАВИАТУР СИСТЕМЫ)
# ==============================================================================

def create_main_menu(user_id):
    """Формирует главное меню управления для пользователей и админов."""
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
    """Создает специализированное меню управления для администраторов бота."""
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
    """Создает универсальную кнопку отмены для выхода из интерактивных диалогов ввода."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup

# ==============================================================================
# [7] ОБРАБОТЧИКИ СИСТЕМНЫХ КОМАНД И РЕФЕРАЛЬНОЙ СИСТЕМЫ
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_message_handler(message):
    """Обработчик команды /start с регистрацией и реферальной системой."""
    if check_ban_status(message.from_user):
        bot.send_message(message.chat.id, "🚫 Вы заблокированы. Доступ к функциям симулятора закрыт.")
        return

    users_database = load_data('users')
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, f"START_COMMAND_TRIGGERED (Text: {message.text})")

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
            except Exception as referral_error:
                logger.error(f"Не удалось отправить пуш-уведомление рефереру {inviter_id}: {referral_error}")

        save_data(users_database, 'users')

    welcome_text = (
        "⚽️ **Приветствую, {}!**\n\n"
        "Вы попали в продвинутый симулятор футбольных карточек.\n"
        "Собирайте уникальные составы, прокачивайте команду, активируйте секретные промокоды "
        "и побеждайте других менеджеров на ПВП Арене!\n\n"
        "Используйте встроенное графическое меню для управления своей футбольной империей."
    ).format(message.from_user.first_name)
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=create_main_menu(message.from_user.id), 
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_stats_handler(message):
    """Генерирует индивидуальную реферальную ссылку и выводит статистику приглашенных друзей."""
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
# [8] МОДУЛЬ ПРОМОКОДОВ (ИНТЕРАКТИВНЫЙ ВВОД, ВАЛИДАЦИЯ И НАГРАДЫ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input_start(message):
    """Инициализирует процесс ввода промокода."""
    if check_ban_status(message.from_user):
        return
        
    user_id = message.from_user.id
    log_action(user_id, "OPENED_PROMO_MENU")
    
    sent_msg = bot.send_message(
        message.chat.id, 
        "🎟 **АКТИВАЦИЯ ПРОМОКОДА**\n\nВведите ваш секретный промокод (регистр букв не имеет значения):", 
        reply_markup=create_cancel_menu(),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(sent_msg, process_promo_logic)


def process_promo_logic(message):
    """Основной движок валидации введенного промокода и начисления внутриигровых бонусов."""
    user_id_key = str(message.from_user.id)
    
    if message.text == "❌ Отмена":
        bot.send_message(
            message.chat.id, 
            "🔄 Ввод промокода отменен. Вы вернулись в меню.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return
        
    input_code = message.text.strip().upper()
    users_db = load_data('users')
    promos_db = load_data('promos')
    
    if user_id_key not in users_db:
        bot.send_message(
            message.chat.id, 
            "❌ Системная ошибка: ваш профиль не найден. Перезапустите бота через /start", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return

    if input_code not in promos_db:
        bot.send_message(
            message.chat.id, 
            "❌ К сожалению, такого промокода не существует или его срок действия истёк.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return

    if 'used_promos' not in users_db[user_id_key]:
        users_db[user_id_key]['used_promos'] = []
        
    if input_code in users_db[user_id_key]['used_promos']:
        bot.send_message(
            message.chat.id, 
            "❌ Вы уже активировали этот промокод ранее! Повторная активация невозможна.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return

    code_info = promos_db[input_code]
    reward_type = code_info.get('type', 'score')
    reward_val = code_info.get('value', 0)
    
    success_msg = ""
    
    if reward_type == 'rolls':
        users_db[user_id_key]['free_rolls'] = users_db[user_id_key].get('free_rolls', 0) + int(reward_val)
        success_msg = f"🎉 **УСПЕШНО!**\n\nВы активировали промокод `{input_code}`!\n🎁 Награда: **+{int(reward_val)} бонусных прокрутов** карт!"
    elif reward_type == 'luck':
        users_db[user_id_key]['bonus_luck'] = float(reward_val)
        success_msg = f"🎉 **УСПЕШНО!**\n\nВы активировали промокод `{input_code}`!\n🎁 Награда: **Множитель удачи х{float(reward_val)}** на следующий бесплатный ролл!"
    elif reward_type == 'score':
        users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + int(reward_val)
        success_msg = f"🎉 **УСПЕШНО!**\n\nВы активировали промокод `{input_code}`!\n🎁 Награда: **+{int(reward_val):,} очков** на ваш баланс!"
    else:
        users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + 1000
        success_msg = f"🎉 **УСПЕШНО!**\n\nПромокод активирован. Начислен стандартный бонус: **+1,000 очков**."

    users_db[user_id_key]['used_promos'].append(input_code)
    
    if save_data(users_db, 'users'):
        log_action(user_id_key, f"ACTIVATED_PROMO_{input_code}")
        bot.send_message(message.chat.id, success_msg, reply_markup=create_main_menu(message.from_user.id), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Произошла ошибка при сохранении данных базы. Попробуйте позже.", reply_markup=create_main_menu(message.from_user.id))

# ==============================================================================
# [9] СИСТЕМА ПРОКРУТОВ С РАНДОМИЗАЦИЕЙ ВЕСОВЫХ КОЭФФИЦИЕНТОВ (ROLL ENGINE)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎰 Крутить карту")
def roll_card_handler(message):
    """Генерирует случайную футбольную карту, учитывая кулдаун 1 час."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    all_cards = load_data('cards')
    
    if not all_cards or len(all_cards) == 0:
        bot.send_message(message.chat.id, "❌ В игре пока нет доступных футбольных карточек. Администрация скоро их добавит!")
        return
        
    current_time_stamp = time.time()
    bonus_rolls = users_db.get(user_id_key, {}).get('free_rolls', 0)
    
    if not check_admin_permission(message.from_user) and bonus_rolls <= 0:
        if user_id_key in roll_cooldowns:
            elapsed_time = current_time_stamp - roll_cooldowns[user_id_key]
            if elapsed_time < 3600:
                remaining_seconds = int(3600 - elapsed_time)
                minutes = remaining_seconds // 60
                seconds = remaining_seconds % 60
                bot.send_message(
                    message.chat.id, 
                    f"⏳ **Кулдаун на бесплатный ролл!**\n\nВы сможете запустить рулетку снова через **{minutes}м {seconds}с**.\n"
                    f"💡 Копите бонусные прокруты за приглашение друзей (меню 👥 Рефералы) или вводите промокоды!",
                    parse_mode="Markdown"
                )
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
        attempt_info_text = f"🎫 Использован 1 бонусный прокрут. Осталось: **{users_db[user_id_key]['free_rolls']}** шт."
    else:
        roll_cooldowns[user_id_key] = current_time_stamp
        attempt_info_text = "⏳ Следующий бесплатный запуск рулетки доступен через **1 час**."

    users_db[user_id_key]['bonus_luck'] = 1.0
    
    collections_db = load_data('colls')
    if user_id_key not in collections_db:
        collections_db[user_id_key] = []
        
    has_duplicate = any(existing_card.get('name') == won_card_object.get('name') for existing_card in collections_db[user_id_key])
    
    if has_duplicate:
        earned_points = int(RARITY_STATS[chosen_rarity_level]['score'] * 0.3)
        result_status_label = f"🔄 **ДУБЛИКАТ!** Вы получили компенсацию **30%** очков: `+{earned_points:,}`"
    else:
        earned_points = RARITY_STATS[chosen_rarity_level]['score']
        result_status_label = f"✨ **НОВАЯ КАРТА!** Она добавлена в коллекцию: `+{earned_points:,}` очков."
        collections_db[user_id_key].append(won_card_object)
        save_data(collections_db, 'colls')

    users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + earned_points
    save_data(users_db, 'users')
    
    stars_visual_representation = "⭐" * chosen_rarity_level
    rarity_text_label = RARITY_STATS[chosen_rarity_level]['label']
    card_position_ru = POSITIONS_RU.get(won_card_object.get('position', 'ЦП'), 'Полузащитник')
    card_club = won_card_object.get('club', 'Свободный агент')
    
    caption_message = (
        f"🏆 **СПИН РУЛЕТКИ ЗАВЕРШЕН!**\n\n"
        f"🏃‍♂️ Игрок: **{won_card_object.get('name')}**\n"
        f"🛡 Позиция: `{card_position_ru}`\n"
        f"🏢 Клуб: _{card_club}_\n"
        f"📊 Редкость: {stars_visual_representation} ({rarity_text_label})\n"
        f"⚡ Сила атаки (АТК): **{RARITY_STATS[chosen_rarity_level]['atk']}**\n\n"
        f"{result_status_label}\n"
        f"💰 Ваш новый баланс: **{users_db[user_id_key]['score']:,}** очков.\n\n"
        f"{attempt_info_text}"
    )

    try:
        bot.send_photo(message.chat.id, won_card_object.get('photo'), caption=caption_message, parse_mode="Markdown")
    except Exception:
        bot.send_message(message.chat.id, f"🖼 *(Изображение недоступно)*\n\n{caption_message}", parse_mode="Markdown")

# ==============================================================================
# [10] ИНТЕРАКТИВНАЯ ГАЛЕРЕЯ И СОРТИРОВКА КОЛЛЕКЦИИ (COLLECTION ENGINE)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection_menu_handler(message):
    """Отображает общую сводную статистику альбома карточек игрока."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    collections_db = load_data('colls')
    my_cards_list = collections_db.get(user_id_key, [])
    
    if not my_cards_list:
        bot.send_message(
            message.chat.id, 
            "🗂 **ВАША КОЛЛЕКЦИЯ**\n\nУ вас пока нет ни одной футбольной карточки.\n"
            "Запустите рулетку в меню: **🎰 Крутить карту**, чтобы собрать свой первый состав!", 
            parse_mode="Markdown"
        )
        return

    stats_by_rarity = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for card in my_cards_list:
        stars = card.get('stars', 1)
        if stars in stats_by_rarity:
            stats_by_rarity[stars] += 1

    summary_text = (
        f"🗂 **ГЛАВНЫЙ АЛЬБОМ КОЛЛЕКЦИИ**\n\n"
        f"Всего карточек во владении: **{len(my_cards_list)}** шт.\n\n"
        f"⚪️ Обычные (⭐): **{stats_by_rarity[1]}** шт.\n"
        f"🟢 Необычные (⭐⭐): **{stats_by_rarity[2]}** шт.\n"
        f"🔵 Редкие (⭐⭐⭐): **{stats_by_rarity[3]}** шт.\n"
        f"🟡 Эпические (⭐⭐⭐⭐): **{stats_by_rarity[4]}** шт.\n"
        f"🔴 Легендарные (⭐⭐⭐⭐⭐): **{stats_by_rarity[5]}** шт.\n\n"
        f"Выберите интересующую категорию редкости для просмотра подробного списка карт:"
    )

    inline_markup = types.InlineKeyboardMarkup(row_width=2)
    btn_r1 = types.InlineKeyboardButton("⭐ Обычные", callback_data="view_rarity_1")
    btn_r2 = types.InlineKeyboardButton("⭐⭐ Необычные", callback_data="view_rarity_2")
    btn_r3 = types.InlineKeyboardButton("⭐⭐⭐ Редкие", callback_data="view_rarity_3")
    btn_r4 = types.InlineKeyboardButton("⭐⭐⭐⭐ Эпики", callback_data="view_rarity_4")
    btn_r5 = types.InlineKeyboardButton("👑 Легенды", callback_data="view_rarity_5")
    
    inline_markup.add(btn_r1, btn_r2)
    inline_markup.add(btn_r3, btn_r4)
    inline_markup.add(btn_r5)

    bot.send_message(message.chat.id, summary_text, reply_markup=inline_markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("view_rarity_"))
def process_view_rarity_callback(call):
    """Динамический обработчик инлайн-кнопок категорий коллекции."""
    user_id_key = str(call.from_user.id)
    rarity_level_to_filter = int(call.data.replace("view_rarity_", ""))
    
    collections_db = load_data('colls')
    my_cards_list = collections_db.get(user_id_key, [])
    
    filtered_cards = [c for c in my_cards_list if c.get('stars', 1) == rarity_level_to_filter]
    label_text = RARITY_STATS[rarity_level_to_filter]['label']
    stars_str = "⭐" * rarity_level_to_filter

    if not filtered_cards:
        bot.answer_callback_query(call.id, f"У вас нет карт редкости {label_text}!", show_alert=True)
        return

    bot.answer_callback_query(call.id, f"Загрузка категории: {label_text}")

    response_page_text = f"🗂 **СПИСОК КАРТ [{label_text.upper()} {stars_str}]**\n\n"
    for index, card in enumerate(filtered_cards, 1):
        pos = POSITIONS_RU.get(card.get('position', 'ЦП'), 'Полузащитник')
        club = card.get('club', 'Свободный агент')
        power = RARITY_STATS[rarity_level_to_filter]['atk']
        response_page_text += f"{index}. **{card.get('name')}** (`{pos}`) — Клуб: _{club}_ | АТК: **{power}**\n"

    bot.send_message(call.message.chat.id, response_page_text, parse_mode="Markdown")

# ==============================================================================
# [11] УПРАВЛЕНИЕ СВОИМ ТАКТИЧЕСКИМ СОСТАВОМ (SQUAD ENGINE)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "📋 Состав")
def squad_menu_handler(message):
    """Отображает текущий футбольный ростер из 7 позиций."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    squads_db = load_data('squads')
    
    if user_id_key not in squads_db:
        squads_db[user_id_key] = [None] * 7
        save_data(squads_db, 'squads')
        
    current_user_squad = squads_db[user_id_key]
    total_calculated_power = calculate_total_power(message.from_user.id)
    
    squad_view_text = (
        f"📋 **ВАШ ТАКТИЧЕСКИЙ СОСТАВ КОМАНДЫ**\n\n"
        f"Здесь отображаются футболисты, защищающие честь вашего клуба на ПВП Аренах.\n\n"
        f"⚔️ Суммарная мощь состава (АТК): **{total_calculated_power}**\n\n"
        f"=== ТЕКУЩИЙ РОСТЕР ПОЗИЦИЙ ===\n"
    )
    
    inline_squad_markup = types.InlineKeyboardMarkup(row_width=1)
    for slot_id, slot_meta in SQUAD_SLOTS.items():
        assigned_card = None
        if slot_id < len(current_user_squad):
            assigned_card = current_user_squad[slot_id]
            
        if assigned_card:
            card_rarity_stars = "⭐" * assigned_card.get('stars', 1)
            slot_status_string = f"{slot_meta['label']}: {assigned_card.get('name')} ({card_rarity_stars})"
        else:
            slot_status_string = f"{slot_meta['label']}: ❌ Позиция пуста"
            
        squad_view_text += f"• {slot_status_string}\n"
        
        button_callback_data = f"manage_slot_{slot_id}"
        inline_squad_markup.add(types.InlineKeyboardButton(f"⚙️ Настроить {slot_meta['code']}", callback_data=button_callback_data))
        
    squad_view_text += "\nНажмите на кнопку соответствующей позиции ниже, чтобы выставить игрока."
    bot.send_message(message.chat.id, squad_view_text, reply_markup=inline_squad_markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("manage_slot_"))
def process_manage_slot_callback(call):
    """Выводит список доступных карт из коллекции для размещения в выбранный слот."""
    user_id_key = str(call.from_user.id)
    slot_id_to_change = int(call.data.replace("manage_slot_", ""))
    
    slot_configuration = SQUAD_SLOTS.get(slot_id_to_change)
    if not slot_configuration:
        return
        
    required_position_code = slot_configuration['code']
    collections_db = load_data('colls')
    my_cards_list = collections_db.get(user_id_key, [])
    
    eligible_cards = [c for c in my_cards_list if c.get('position') == required_position_code]
    
    if not eligible_cards:
        bot.answer_callback_query(
            call.id, 
            f"В вашей коллекции нет игроков позиции {required_position_code}!\nКрутите рулетку, чтобы выбить их.", 
            show_alert=True
        )
        return
        
    bot.answer_callback_query(call.id, "Загрузка доступных футболистов...")
    
    selection_markup = types.InlineKeyboardMarkup(row_width=1)
    for index, card in enumerate(eligible_cards):
        stars_visual = "⭐" * card.get('stars', 1)
        button_text = f"{card.get('name')} [{stars_visual}] (АТК: {RARITY_STATS[card.get('stars', 1)]['atk']})"
        cb_data = f"setcard_{slot_id_to_change}_{index}"
        selection_markup.add(types.InlineKeyboardButton(button_text, callback_data=cb_data))
        
    selection_markup.add(types.InlineKeyboardButton("🗑 Очистить слот", callback_data=f"clear_slot_{slot_id_to_change}"))
    
    bot.send_message(
        call.message.chat.id, 
        f"🏃‍♂️ **ВЫБОР ИГРОКА НА ПОЗИЦИЮ {slot_configuration['label']}**\n\n"
        f"Нажмите на нужного игрока, чтобы заявить его в стартовый лист:", 
        reply_markup=selection_markup,
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("clear_slot_"))
def process_clear_slot_callback(call):
    """Полностью очищает выбранный слот тактического состава игрока."""
    user_id_key = str(call.from_user.id)
    slot_id_to_clear = int(call.data.replace("clear_slot_", ""))
    
    squads_db = load_data('squads')
    if user_id_key in squads_db and slot_id_to_clear < len(squads_db[user_id_key]):
        squads_db[user_id_key][slot_id_to_clear] = None
        save_data(squads_db, 'squads')
        
    bot.answer_callback_query(call.id, "Позиция успешно освобождена!", show_alert=False)
    bot.send_message(
        call.message.chat.id, 
        f"✅ Позиция команды была успешно очищена от игрока.", 
        reply_markup=create_main_menu(call.from_user.id)
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("setcard_"))
def process_set_card_callback(call):
    """Размещает выбранного футболиста в соответствующий слот игрового ростера."""
    user_id_key = str(call.from_user.id)
    parameters_list = call.data.split('_')
    target_slot_id = int(parameters_list[1])
    chosen_card_index = int(parameters_list[2])
    
    slot_meta_data = SQUAD_SLOTS.get(target_slot_id)
    collections_db = load_data('colls')
    my_cards_list = collections_db.get(user_id_key, [])
    
    eligible_cards = [c for c in my_cards_list if c.get('position') == slot_meta_data['code']]
    
    if chosen_card_index >= len(eligible_cards):
        bot.answer_callback_query(call.id, "Выбранная карта больше недоступна.", show_alert=True)
        return
        
    selected_card_object = eligible_cards[chosen_card_index]
    squads_db = load_data('squads')
    
    if user_id_key not in squads_db:
        squads_db[user_id_key] = [None] * 7
        
    squads_db[user_id_key][target_slot_id] = selected_card_object
    save_data(squads_db, 'squads')
    
    bot.answer_callback_query(call.id, f"Установлен: {selected_card_object.get('name')}", show_alert=False)
    
    success_text = (
        f"✅ **ИГРОК ВЫСТАВЛЕН В СТАРТ!**\n\n"
        f"Футболист **{selected_card_object.get('name')}** успешно занял позицию `{slot_meta_data['label']}`."
    )
    bot.send_message(call.message.chat.id, success_text, reply_markup=create_main_menu(call.from_user.id), parse_mode="Markdown")

# ==============================================================================
# [12] МОДУЛЬ ПВП АРЕНЫ И РЕЙТИНГОВ (PVP ENGINE С КУЛДАУНОМ 2 ЧАСА НА ВСЕ МАТЧИ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🏟 ПВП Арена")
def pvp_arena_menu_handler(message):
    """Главный хаб ПВП Арены. Единый кулдаун в 2 часа на любые матчи."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    current_time_stamp = time.time()
    
    if not check_admin_permission(message.from_user):
        if user_id_key in pvp_cooldowns:
            elapsed_time = current_time_stamp - pvp_cooldowns[user_id_key]
            if elapsed_time < 7200:
                remaining_seconds = int(7200 - elapsed_time)
                hours = remaining_seconds // 3600
                minutes = (remaining_seconds % 3600) // 60
                bot.send_message(
                    message.chat.id, 
                    f"⏳ **Ваши футболисты восстанавливают силы после прошлого матча!**\n\n"
                    f"Следующий выход на поле будет доступен через **{hours}ч {minutes}м**.",
                    parse_mode="Markdown"
                )
                return

    total_power = calculate_total_power(message.from_user.id)
    if total_power <= 0:
        bot.send_message(
            message.chat.id, 
            "🏟 **ПВП АРЕНА БЛОКИРОВАНА**\n\nВаш текущий состав пуст (Мощь: 0 АТК).\n"
            "Выставьте игроков в меню **📋 Состав**!",
            parse_mode="Markdown"
        )
        return

    arena_text = (
        f"🏟 **ДОБРО ПОЖАЛОВАТЬ НА СТАДИОН ПВП АРЕНЫ!**\n\n"
        f"Ваша текущая атакующая сила состава: 💪 **{total_power} АТК**\n\n"
        f"Выберите тип матча:"
    )
    
    inline_arena_markup = types.InlineKeyboardMarkup(row_width=1)
    inline_arena_markup.add(
        types.InlineKeyboardButton("🤖 Обычный матч (Против ИИ)", callback_data="pvp_play_bot"),
        types.InlineKeyboardButton("🌍 Онлайн матч (Против Игрока)", callback_data="pvp_play_online")
    )
    
    bot.send_message(message.chat.id, arena_text, reply_markup=inline_arena_markup, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "pvp_play_bot")
def process_pvp_against_bot_callback(call):
    """Симулирует поединок против виртуального соперника (ИИ)."""
    user_id_key = str(call.from_user.id)
    current_time_stamp = time.time()
    
    if not check_admin_permission(call.from_user):
        if user_id_key in pvp_cooldowns and (current_time_stamp - pvp_cooldowns[user_id_key] < 7200):
            bot.answer_callback_query(call.id, "Ваши футболисты еще не восстановились!", show_alert=True)
            return

    bot.answer_callback_query(call.id, "Матч начинается! Идет симуляция...")
    
    users_db = load_data('users')
    my_calculated_power = calculate_total_power(call.from_user.id)
    bot_club_name = random.choice(FOOTBALL_CLUBS_POOL)
    bot_generated_power = random.randint(200, 12000)
    
    total_aggregate_power = my_calculated_power + bot_generated_power
    my_win_chance_percent = int((my_calculated_power / total_aggregate_power) * 100) if total_aggregate_power > 0 else 50
    
    if my_win_chance_percent > 92: my_win_chance_percent = 92
    if my_win_chance_percent < 8: my_win_chance_percent = 8
    
    random_dice_roll = random.randint(1, 100)
    my_goals = 0
    enemy_goals = 0
    
    if random_dice_roll <= my_win_chance_percent:
        my_goals = random.choices([1, 2, 3, 4, 5], weights=[40, 35, 15, 8, 2])[0]
        enemy_goals = random.randint(0, my_goals - 1)
        match_outcome_label = "🏆 **ВЕЛИКОЛЕПНАЯ ПОБЕДА!**"
        points_bonus_reward = 3500
    elif random_dice_roll <= (my_win_chance_percent + 15):
        my_goals = random.randint(0, 3)
        enemy_goals = my_goals
        match_outcome_label = "🤝 **НАПРЯЖЕННАЯ НИЧЬЯ!**"
        points_bonus_reward = 1000
    else:
        enemy_goals = random.choices([1, 2, 3, 4, 5], weights=[40, 35, 15, 8, 2])[0]
        my_goals = random.randint(0, enemy_goals - 1)
        match_outcome_label = "❌ **ДОСАДНОЕ ПОРАЖЕНИЕ!**"
        points_bonus_reward = 150

    users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + points_bonus_reward
    
    if not check_admin_permission(call.from_user):
        pvp_cooldowns[user_id_key] = current_time_stamp
        
    save_data(users_db, 'users')

    report_card_message = (
        f"{match_outcome_label}\n\n"
        f"⚽️ **Финальный счет поединка:**\n"
        f"🛡 Ваша команда (**{my_calculated_power}** АТК) — **{my_goals}**\n"
        f"🤖 ФК {bot_club_name} (**{bot_generated_power}** АТК) — **{enemy_goals}**\n\n"
        f"🎁 Награда за итог встречи: **+{points_bonus_reward:,} очков**.\n\n"
        f"⏳ Следующий матч будет доступен через **2 часа**."
    )
    
    bot.send_message(call.message.chat.id, report_card_message, reply_markup=create_main_menu(call.from_user.id), parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "pvp_play_online")
def process_pvp_online_callback(call):
    """Имитирует поиск соперников по сети и запускает онлайн-матч."""
    user_id_key = str(call.from_user.id)
    current_time_stamp = time.time()
    
    if not check_admin_permission(call.from_user):
        if user_id_key in pvp_cooldowns and (current_time_stamp - pvp_cooldowns[user_id_key] < 7200):
            bot.answer_callback_query(call.id, "Ваши футболисты еще не восстановились!", show_alert=True)
            return

    bot.answer_callback_query(call.id, "Поиск свободного соперника в сети...")
    
    users_db = load_data('users')
    my_calculated_power = calculate_total_power(call.from_user.id)
    
    online_opponents_pool = ["@Neo_Manager", "@Sofa_Scout", "@Giggs_Fan", "@CR7_God", "@Leo_King", "@Zeus_Tactic", "@Alonso_Way"]
    chosen_opponent_nick = random.choice(online_opponents_pool)
    
    deviation = int(my_calculated_power * 0.4) if my_calculated_power > 1000 else 500
    online_opponent_power = max(150, my_calculated_power + random.randint(-deviation, deviation))
    
    total_aggregate_power = my_calculated_power + online_opponent_power
    my_win_chance_percent = int((my_calculated_power / total_aggregate_power) * 100) if total_aggregate_power > 0 else 50
    
    if my_win_chance_percent > 90: my_win_chance_percent = 90
    if my_win_chance_percent < 10: my_win_chance_percent = 10
    
    random_dice_roll = random.randint(1, 100)
    my_goals = 0
    enemy_goals = 0
    
    if random_dice_roll <= my_win_chance_percent:
        my_goals = random.choices([1, 2, 3, 4, 5], weights=[35, 40, 15, 8, 2])[0]
        enemy_goals = random.randint(0, my_goals - 1)
        match_outcome_label = "⚡️ **ГРАНДИОЗНАЯ ОНЛАЙН ПОБЕДА!**"
        points_bonus_reward = 5000
    elif random_dice_roll <= (my_win_chance_percent + 12):
        my_goals = random.randint(0, 2)
        enemy_goals = my_goals
        match_outcome_label = "🤝 **БОЕВАЯ ОНЛАЙН НИЧЬЯ!**"
        points_bonus_reward = 1500
    else:
        enemy_goals = random.choices([1, 2, 3, 4, 5], weights=[35, 40, 15, 8, 2])[0]
        my_goals = random.randint(0, enemy_goals - 1)
        match_outcome_label = "❌ **ПОРАЖЕНИЕ В ОНЛАЙН МАТЧЕ!**"
        points_bonus_reward = 300

    users_db[user_id_key]['score'] = users_db[user_id_key].get('score', 0) + points_bonus_reward
    
    if not check_admin_permission(call.from_user):
        pvp_cooldowns[user_id_key] = current_time_stamp
        
    save_data(users_db, 'users')

    report_card_message = (
        f"{match_outcome_label}\n\n"
        f"🌍 **Сетевой поединок завершен:**\n"
        f"🛡 Вы (**{my_calculated_power}** АТК) — **{my_goals}**\n"
        f"👥 Менеджер {chosen_opponent_nick} (**{online_opponent_power}** АТК) — **{enemy_goals}**\n\n"
        f"🎁 Награда за онлайн-рейтинг: **+{points_bonus_reward:,} очков**.\n\n"
        f"⏳ Следующий матч будет доступен через **2 часа**."
    )
    
    bot.send_message(call.message.chat.id, report_card_message, reply_markup=create_main_menu(call.from_user.id), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def user_profile_handler(message):
    """Выводит детальную карточку профиля менеджера."""
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    collections_db = load_data('colls')
    
    user_profile = users_db.get(user_id_key, {})
    my_cards = collections_db.get(user_id_key, [])
    total_power = calculate_total_power(message.from_user.id)
    
    profile_text = (
        f"👤 **ЛИЧНЫЙ ПРОФИЛЬ ФУТБОЛЬНОГО МЕНЕДЖЕРА**\n\n"
        f"🆔 Ваш Telegram ID: `{user_id_key}`\n"
        f"👤 Никнейм: **{user_profile.get('nick', 'Футболист')}**\n"
        f"🏷 Тег: {user_profile.get('username', '@нет')}\n\n"
        f"💰 Баланс клуба: **{user_profile.get('score', 0):,}** игровых очков\n"
        f"🎫 Бонусные прокруты (роллы): **{user_profile.get('free_rolls', 0)}** шт.\n"
        f"🍀 Множитель удачи: **х{user_profile.get('bonus_luck', 1.0)}**\n\n"
        f"🗂 Всего карт в альбоме: **{len(my_cards)}** шт.\n"
        f"⚔️ Атакующая мощь состава: 💪 **{total_power} АТК**\n"
        f"👥 Приглашено друзей: **{user_profile.get('refs', 0)}**"
    )
    
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🏆 Топ очков")
def leaderboard_handler(message):
    """Формирует и выводит таблицу лидеров среди топ-10 лучших менеджеров бота."""
    if check_ban_status(message.from_user):
        return
        
    users_db = load_data('users')
    sorted_users = sorted(users_db.items(), key=lambda item: item[1].get('score', 0), reverse=True)
    top_10_slice = sorted_users[:10]
    
    leaderboard_text = "🏆 **ТАБЛИЦА ЛИДЕРОВ (ТОП-10 МЕНЕДЖЕРОВ)**\n\n"
    for rank, (uid, udata) in enumerate(top_10_slice, 1):
        medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"*{rank}.*"
        leaderboard_text += f"{medal} {udata.get('nick', 'Футболист')} ({udata.get('username', 'id')}) — **{udata.get('score', 0):,}** очков\n"
        
    bot.send_message(message.chat.id, leaderboard_text, parse_mode="Markdown")

# ==============================================================================
# [13] АДМИНИСТРАТИВНАЯ ПАНЕЛЬ УПРАВЛЕНИЯ (БЕЗОПАСНЫЙ BACK-END ENGINE)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_root_handler(message):
    """Открывает скрытое меню инструментов для подтвержденных администраторов."""
    if check_ban_status(message.from_user):
        return
    if not check_admin_permission(message.from_user):
        return
        
    bot.send_message(
        message.chat.id, 
        "🛠 **ГЛАВНЫЙ СЕРВЕРНЫЙ МОДУЛЬ УПРАВЛЕНИЯ**\n\nДобро пожаловать в админ-панель. Доступ разрешен.", 
        reply_markup=create_admin_menu(),
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back_to_main_menu_handler(message):
    """Возвращает администратора из спец-панели обратно в пользовательский интерфейс."""
    if check_ban_status(message.from_user):
        return
        
    bot.send_message(
        message.chat.id, 
        "🏠 Вы вернулись в стандартное интерактивное меню игрока.", 
        reply_markup=create_main_menu(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "🚫 Забанить")
def admin_ban_start(message):
    if not check_admin_permission(message.from_user): return
    m_sent = bot.send_message(message.chat.id, "🚫 Введите **Telegram ID** или **username** (без @) для блокировки:", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_ban_execute)

def admin_ban_execute(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Блокировка отменена.", reply_markup=create_admin_menu())
        return
    target = message.text.strip().lower()
    ban_list = load_data('bans')
    if target not in ban_list:
        ban_list.append(target)
        save_data(ban_list, 'bans')
    bot.send_message(message.chat.id, f"✅ Объект `{target}` успешно заблокирован.", reply_markup=create_admin_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "✅ Разбанить")
def admin_unban_start(message):
    if not check_admin_permission(message.from_user): return
    m_sent = bot.send_message(message.chat.id, "✅ Введите **Telegram ID** или **username** для амнистии:", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_unban_execute)

def admin_unban_execute(message):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Амнистия отменена.", reply_markup=create_admin_menu())
        return
    target = message.text.strip().lower()
    ban_list = load_data('bans')
    if target in ban_list:
        ban_list.remove(target)
        save_data(ban_list, 'bans')
        bot.send_message(message.chat.id, f"✅ С объекта `{target}` успешно сняты ограничения.", reply_markup=create_admin_menu(), parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "❌ Данный объект не числился в списках заблокированных.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def admin_add_card_start(message):
    """Пошаговый мастер создания новой футбольной карты в базу данных."""
    if not check_admin_permission(message.from_user): return
    m_sent = bot.send_message(message.chat.id, "🏃‍♂️ **ШАГ 1:** Введите ФИО нового футболиста:", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_add_card_step2, {})

def admin_add_card_step2(message, card_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    card_obj['name'] = message.text.strip()
    m_sent = bot.send_message(message.chat.id, "🛡 **ШАГ 2:** Введите позицию (ГК, ЛЗ, ПЗ, ЦП, ЛВ, ПВ, КФ):", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_add_card_step3, card_obj)

def admin_add_card_step3(message, card_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    pos = message.text.strip().upper()
    if pos not in POSITIONS_RU:
        m_sent = bot.send_message(message.chat.id, "❌ Неверная позиция! Попробуйте снова (ГК, ЛЗ, ПЗ, ЦП, ЛВ, ПВ, КФ):")
        bot.register_next_step_handler(m_sent, admin_add_card_step3, card_obj)
        return
    card_obj['position'] = pos
    m_sent = bot.send_message(message.chat.id, "🏢 **ШАГ 3:** Введите название футбольного клуба:", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_add_card_step4, card_obj)

def admin_add_card_step4(message, card_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    card_obj['club'] = message.text.strip()
    m_sent = bot.send_message(message.chat.id, "⭐ **ШАГ 4:** Укажите звездность / редкость (от 1 до 5):", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_add_card_step5, card_obj)

def admin_add_card_step5(message, card_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    try:
        stars = int(message.text.strip())
        if stars < 1 or stars > 5: raise ValueError
    except ValueError:
        m_sent = bot.send_message(message.chat.id, "❌ Число должно быть строго от 1 до 5! Повторите ввод:")
        bot.register_next_step_handler(m_sent, admin_add_card_step5, card_obj)
        return
    card_obj['stars'] = stars
    m_sent = bot.send_message(message.chat.id, "🖼 **ШАГ 5:** Вставьте URL ссылку на фотографию игрока:", reply_markup=create_cancel_menu(), parse_mode="Markdown")
    bot.register_next_step_handler(m_sent, admin_add_card_finalize, card_obj)

def admin_add_card_finalize(message, card_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    card_obj['photo'] = message.text.strip()
    
    cards_list = load_data('cards')
    cards_list.append(card_obj)
    
    if save_data(cards_list, 'cards'):
        bot.send_message(
            message.chat.id, 
            f"🎉 **КАРТОЧКА УСПЕШНО ЗАПИСАНА В БАЗУ!**\n\nФутболист {card_obj['name']} доступен в рулетке.", 
            reply_markup=create_admin_menu(), 
            parse_mode="Markdown"
        )
    else:
        bot.send_message(message.chat.id, "❌ Ошибка сохранения базы данных.", reply_markup=create_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🎟 +Промокод")
def admin_add_promo_start(message):
    if not check_admin_permission(message.from_user): return
    m_sent = bot.send_message(message.chat.id, "🎟 Введите имя промокода (в верхнем регистре):", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(m_sent, admin_add_promo_step2, {})

def admin_add_promo_step2(message, promo_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    promo_name = message.text.strip().upper()
    m_sent = bot.send_message(message.chat.id, "⚙️ Введите тип награды (score / rolls / luck):", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(m_sent, admin_add_promo_step3, {"name": promo_name})

def admin_add_promo_step3(message, promo_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    p_type = message.text.strip().lower()
    if p_type not in ['score', 'rolls', 'luck']:
        m_sent = bot.send_message(message.chat.id, "❌ Неверный тип! Введите корректный (score / rolls / luck):")
        bot.register_next_step_handler(m_sent, admin_add_promo_step3, promo_obj)
        return
    promo_obj['type'] = p_type
    m_sent = bot.send_message(message.chat.id, "💰 Введите номинальное цифровое значение награды:", reply_markup=create_cancel_menu())
    bot.register_next_step_handler(m_sent, admin_add_promo_finalize, promo_obj)

def admin_add_promo_finalize(message, promo_obj):
    if message.text == "❌ Отмена":
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_admin_menu())
        return
    try:
        val = float(message.text.strip())
    except ValueError:
        m_sent = bot.send_message(message.chat.id, "❌ Должно быть числом! Попробуйте снова:")
        bot.register_next_step_handler(m_sent, admin_add_promo_finalize, promo_obj)
        return
        
    promos_db = load_data('promos')
    promos_db[promo_obj['name']] = {
        "type": promo_obj['type'],
        "value": val
    }
    save_data(promos_db, 'promos')
    bot.send_message(message.chat.id, f"🎟 Промокод `{promo_obj['name']}` успешно добавлен.", reply_markup=create_admin_menu(), parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🧨 Обнулить бота")
def admin_wipe_database_warning(message):
    if not check_admin_permission(message.from_user): return
    m_sent = bot.send_message(
        message.chat.id, 
        "⚠️ **ВНИМАНИЕ! КРИТИЧЕСКАЯ ОПЕРАЦИЯ!**\n\nВы собираетесь полностью обнулить все профили пользователей.\n"
        "Для подтверждения введите секретную фразу: `СБРОСИРОВАТЬ ВСЕ`", 
        reply_markup=create_cancel_menu(),
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(m_sent, admin_wipe_database_execute)

def admin_wipe_database_execute(message):
    if message.text == "СБРОСИРОВАТЬ ВСЕ":
        for k in ['colls', 'squads', 'users']:
            save_data({}, k)
        bot.send_message(message.chat.id, "🧨 Все базы данных пользователей успешно стёрты.", reply_markup=create_admin_menu())
    else:
        bot.send_message(message.chat.id, "❌ Команда отменена.", reply_markup=create_admin_menu())

# ==============================================================================
# [14] ПРЕДОХРАНИТЕЛЬНЫЙ ДЕФОЛТНЫЙ ОБРАБОТЧИК НЕИЗВЕСТНОГО ТЕКСТА
# ==============================================================================

@bot.message_handler(func=lambda message: True)
def default_fallback_text_handler(message):
    if check_ban_status(message.from_user):
        return
    bot.send_message(
        message.chat.id,
        "❓ **Неизвестная команда.**\n\nПожалуйста, используйте встроенные интерактивные кнопки меню.",
        reply_markup=create_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

# ==============================================================================
# [15] БЕЗКОНЕЧНЫЙ ЦИКЛ ОПРОСА СЕРВЕРОВ TELEGRAM (POLLING START)
# ==============================================================================

if __name__ == '__main__':
    logger.info("==================================================")
    logger.info(" СИСТЕМА УСПЕШНО ИНИЦИАЛИЗИРОВАНА И СКОМПИЛИРОВАНА")
    logger.info(" БОТ ФУТБОЛЬНЫХ КАРТОЧЕК РАБОТАЕТ В ШТАТНОМ РЕЖИМЕ")
    logger.info("==================================================")
    bot.infinity_polling()
