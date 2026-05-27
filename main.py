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
TOKEN = "8711407704:AAGZWhw8jXSjoofD2w7MlFJy-6_guVXYU0E"

# Список администраторов, имеющих доступ к панели управления (username БЕЗ @)
ADMINS = ["verybigsunr", "Ravgant"] 

# Инициализация объекта бота
bot = telebot.TeleBot(TOKEN)

# Словарь путей к файлам базы данных. Используем JSON для простоты и наглядности.
DB_FILES = {
    'cards': 'cards.json',         # База данных всех существующих футболистов
    'colls': 'collections.json',   # База владения (какие карты у каких юзеров)
    'squads': 'squads.json',       # Текущие активные составы игроков (7 позиций)
    'users': 'users_data.json',     # Основные данные: баланс, рефералы, удача
    'bans': 'bans.json',           # Список заблокированных пользователей
    'promos': 'promos.json'        # Доступные промокоды и их параметры
}

# ==============================================================================
# [2] ИГРОВЫЕ ПАРАМЕТРЫ (КОНФИГУРАЦИЯ БАЛАНСА)
# ==============================================================================

# Характеристики каждой редкости: шансы, вознаграждение и боевая мощь
RARITY_STATS = {
    1: {
        "chance": 35, 
        "score": 1000, 
        "atk": 100,
        "label": "Обычная"
    },
    2: {
        "chance": 30, 
        "score": 3000, 
        "atk": 450,
        "label": "Необычная"
    },
    3: {
        "chance": 20, 
        "score": 7500, 
        "atk": 1000,
        "label": "Редкая"
    },
    4: {
        "chance": 10, 
        "score": 15000, 
        "atk": 2500,
        "label": "Эпическая"
    },
    5: {
        "chance": 5,  
        "score": 30000, 
        "atk": 5000,
        "label": "Легендарная"
    }
}

# Словарь для расшифровки сокращений позиций на русский язык
POSITIONS_RU = {
    "ГК": "Вратарь", 
    "ЛЗ": "Левый Защитник", 
    "ПЗ": "Правый Защитник",
    "ЦП": "Центральный Полузащитник", 
    "ЛВ": "Левый Вингер", 
    "ПВ": "Правый Вингер", 
    "КФ": "Нападающий"
}

# Определение слотов для формирования команды (ровно 7 позиций)
SQUAD_SLOTS = {
    0: {"label": "🧤 ГК (Вратарь)", "code": "ГК"},
    1: {"label": "🛡 ЛЗ (Защитник)", "code": "ЛЗ"},
    2: {"label": "🛡 ПЗ (Защитник)", "code": "ПЗ"},
    3: {"label": "👟 ЦП (Полузащитник)", "code": "ЦП"},
    4: {"label": "⚡️ ЛВ (Вингер)", "code": "ЛВ"},
    5: {"label": "⚡️ ПВ (Вингер)", "code": "ПВ"},
    6: {"label": "🎯 КФ (Нападающий)", "code": "КФ"}
}

# Переменные для хранения временных ограничений в памяти (Cooldowns)
roll_cooldowns = {}
pvp_cooldowns = {}

# ==============================================================================
# [3] МОДУЛЬ РАБОТЫ С ДАННЫМИ (JSON ENGINE)
# ==============================================================================

def load_data(key):
    """
    Функция загружает информацию из JSON файла.
    Если файла не существует, она создает его с пустой структурой.
    """
    file_path = DB_FILES.get(key)
    
    # Проверка: существует ли файл вообще
    if not os.path.exists(file_path):
        # Определение типа структуры по умолчанию
        if key in ['cards', 'bans']:
            default_structure = []
        else:
            default_structure = {}
            
        with open(file_path, 'w', encoding='utf-8') as file_out:
            json.dump(default_structure, file_out, ensure_ascii=False, indent=4)
            
        return default_structure
    
    # Попытка прочитать данные
    with open(file_path, 'r', encoding='utf-8') as file_in:
        try:
            content = file_in.read()
            if not content:
                # Если файл пустой, возвращаем базу по умолчанию
                if key in ['cards', 'bans']:
                    return []
                else:
                    return {}
            return json.loads(content)
        except Exception as error:
            print(f"Ошибка чтения базы {key}: {error}")
            if key in ['cards', 'bans']:
                return []
            else:
                return {}

def save_data(data_object, key):
    """
    Записывает переданный объект в соответствующий JSON файл.
    """
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
    """
    Проверяет, является ли пользователь администратором.
    Сравнение идет по username в нижнем регистре.
    """
    if user_obj.username is None:
        return False
        
    current_username = user_obj.username.lower()
    
    for admin_name in ADMINS:
        if admin_name.lower() == current_username:
            return True
            
    return False

def check_ban_status(user_obj):
    """
    Проверяет, забанен ли пользователь (по ID или по нику).
    """
    ban_list = load_data('bans')
    
    user_id_string = str(user_obj.id)
    user_name_string = user_obj.username.lower() if user_obj.username else "no_nick"
    
    # Проверка вхождения в список блокировки
    if user_id_string in ban_list:
        return True
        
    if user_name_string in ban_list:
        return True
        
    return False

def calculate_total_power(user_id):
    """
    Считает суммарную атаку (ATK) всех игроков в текущем составе.
    """
    squad_data = load_data('squads')
    user_id_key = str(user_id)
    
    # Получаем список из 7 слотов
    my_squad = squad_data.get(user_id_key, [None] * 7)
    
    power_sum = 0
    
    for card_item in my_squad:
        if card_item is not None:
            # Получаем количество звезд и сопоставляем с таблицей редкостей
            stars = card_item.get('stars', 1)
            power_sum += RARITY_STATS[stars]['atk']
            
    return power_sum

def log_action(user_id, action_name):
    """
    Выводит информацию о действии пользователя в консоль сервера.
    """
    current_time = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{current_time}] USER_ID: {user_id} | ACTION: {action_name}")

# ==============================================================================
# [5] ГЕНЕРАТОРЫ ИНТЕРФЕЙСА (KEYBOARDS)
# ==============================================================================

def create_main_menu(user_id):
    """
    Создает главную клавиатуру для обычного игрока.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Основные кнопки управления
    btn_roll = types.KeyboardButton("🎰 Крутить карту")
    btn_collection = types.KeyboardButton("🗂 Коллекция")
    btn_squad = types.KeyboardButton("📋 Состав")
    btn_profile = types.KeyboardButton("👤 Профиль")
    btn_top = types.KeyboardButton("🏆 Топ очков")
    btn_pvp = types.KeyboardButton("🏟 ПВП Арена")
    btn_promo = types.KeyboardButton("🎟 Промокод")
    btn_referrals = types.KeyboardButton("👥 Рефералы")
    
    # Добавляем кнопки в сетку
    markup.add(btn_roll, btn_collection, btn_squad, btn_profile)
    markup.add(btn_top, btn_pvp, btn_promo, btn_referrals)
    
    # Проверка прав админа для отображения кнопки панели
    try:
        chat_info = bot.get_chat(user_id)
        if check_admin_permission(chat_info):
            btn_admin = types.KeyboardButton("🛠 Админ-панель")
            markup.add(btn_admin)
    except:
        pass
        
    return markup

def create_admin_menu():
    """
    Создает клавиатуру с функциями для администраторов.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Команды управления контентом
    add_c = types.KeyboardButton("➕ Добавить карту")
    edt_c = types.KeyboardButton("📝 Изменить карту")
    rem_c = types.KeyboardButton("🗑 Удалить карту")
    
    # Команды управления промокодами
    add_p = types.KeyboardButton("🎟 +Промокод")
    rem_p = types.KeyboardButton("🗑 Удалить промокод")
    
    # Команды модерации
    ban_u = types.KeyboardButton("🚫 Забанить")
    unban_u = types.KeyboardButton("✅ Разбанить")
    
    # Служебные команды
    wipe = types.KeyboardButton("🧨 Обнулить бота")
    exit_m = types.KeyboardButton("🏠 Назад в меню")
    
    markup.add(add_c, edt_c, rem_c)
    markup.add(add_p, rem_p)
    markup.add(ban_u, unban_u)
    markup.add(wipe, exit_m)
    
    return markup

def create_cancel_menu():
    """
    Создает простую клавиатуру для отмены текущего действия.
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Отмена"))
    return markup

# ==============================================================================
# [6] ОБРАБОТКА ВХОДА (START) И РЕФЕРАЛЬНОЙ СИСТЕМЫ
# ==============================================================================

@bot.message_handler(commands=['start'])
def start_message_handler(message):
    """
    Главная точка входа. Регистрирует новых игроков и начисляет бонусы за рефералов.
    """
    if check_ban_status(message.from_user):
        bot.send_message(message.chat.id, "🚫 Вы заблокированы. Доступ к боту закрыт.")
        return

    users_database = load_data('users')
    user_id_key = str(message.from_user.id)
    
    log_action(user_id_key, "START_COMMAND")

    # Поиск пригласившего игрока (реферера) в тексте команды
    inviter_id = None
    parts = message.text.split()
    if len(parts) > 1:
        inviter_id = parts[1]

    # Инициализация нового профиля, если его нет в базе
    if user_id_key not in users_database:
        # Определение красивого отображаемого имени
        if message.from_user.username:
            user_display_name = f"@{message.from_user.username}"
        else:
            user_display_name = f"id{user_id_key}"
            
        users_database[user_id_key] = {
            "nick": message.from_user.first_name,
            "username": user_display_name,
            "score": 0,
            "free_rolls": 0,
            "bonus_luck": 1.0,
            "refs": 0,
            "used_promos": []
        }
        
        # ЛОГИКА НАЧИСЛЕНИЯ БОНУСА ЗА ДРУГА
        if inviter_id and inviter_id in users_database and inviter_id != user_id_key:
            # Начисляем 5000 очков
            users_database[inviter_id]["score"] += 5000
            # Начисляем 3 бесплатных прокрута
            current_rolls = users_database[inviter_id].get("free_rolls", 0)
            users_database[inviter_id]["free_rolls"] = current_rolls + 3
            # Увеличиваем счетчик приглашенных
            users_database[inviter_id]["refs"] += 1
            
            try:
                msg_to_inviter = (
                    "👥 **НОВЫЙ ИГРОК!**\n\n"
                    "По вашей ссылке зарегистрировался новый пользователь.\n"
                    "🎁 Вам начислено:\n"
                    "— **5,000 очков**\n"
                    "— **3 бесплатных прокрута**"
                )
                bot.send_message(int(inviter_id), msg_to_inviter, parse_mode="Markdown")
            except Exception as e:
                print(f"Не удалось отправить уведомление рефереру: {e}")

    save_data(users_database, 'users')
    
    welcome_text = (
        f"⚽️ **Приветствую, {message.from_user.first_name}!**\n\n"
        "Вы попали в симулятор футбольных карточек.\n"
        "Здесь вы можете:\n"
        "1. Собирать уникальные карты игроков.\n"
        "2. Составлять свою команду мечты.\n"
        "3. Сражаться с другими игроками в ПВП.\n\n"
        "Используйте кнопки меню ниже, чтобы начать игру!"
    )
    
    bot.send_message(
        message.chat.id, 
        welcome_text, 
        reply_markup=create_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "👥 Рефералы")
def referral_stats_handler(message):
    """
    Показывает игроку его пригласительную ссылку и результаты работы.
    """
    if check_ban_status(message.from_user):
        return
        
    user_id = message.from_user.id
    users_db = load_data('users')
    bot_info = bot.get_me()
    
    log_action(user_id, "OPEN_REFERRALS")
    
    # Генерация уникальной ссылки
    invite_link = f"https://t.me/{bot_info.username}?start={user_id}"
    
    # Получаем статистику из базы
    my_data = users_db.get(str(user_id), {})
    ref_count = my_data.get("refs", 0)
    
    referral_text = (
        "👥 **РЕФЕРАЛЬНАЯ ПРОГРАММА**\n\n"
        "Хотите больше очков и бесплатных прокрутов?\n"
        "Приглашайте друзей в игру!\n\n"
        "🎁 **Награда за каждого друга:**\n"
        "— **5,000 очков** на баланс.\n"
        "— **3 бесплатных прокрута** (без ожидания 3 часов).\n\n"
        f"Вами приглашено человек: **{ref_count}**\n\n"
        "Ваша ссылка для приглашения друзей:\n"
        f"`{invite_link}`\n\n"
        "Скопируйте ссылку и отправьте её своим друзьям!"
    )
    
    bot.send_message(message.chat.id, referral_text, parse_mode="Markdown")

# ==============================================================================
# [7] МОДУЛЬ ПРОМОКОДОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎟 Промокод")
def promo_input_start(message):
    """
    Запускает процесс ввода и активации промокода.
    """
    if check_ban_status(message.from_user):
        return
        
    log_action(message.from_user.id, "PROMO_INPUT_CLICK")
    
    instruction = (
        "🎟 **АКТИВАЦИЯ ПРОМОКОДА**\n\n"
        "Введите секретный код, чтобы получить бонусы.\n"
        "Следите за новостями проекта, чтобы найти новые коды!"
    )
    
    sent_msg = bot.send_message(
        message.chat.id, 
        instruction, 
        reply_markup=create_cancel_menu(),
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(sent_msg, process_promo_logic)

def process_promo_logic(message):
    """
    Логика обработки введенного промокода.
    """
    user_id_key = str(message.from_user.id)
    
    # Проверка на отмену действия
    if message.text == "❌ Отмена":
        log_action(user_id_key, "PROMO_CANCELLED")
        bot.send_message(
            message.chat.id, 
            "Действие отменено.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return
        
    input_code = message.text.strip().upper()
    
    # Загрузка баз данных
    users_db = load_data('users')
    promos_db = load_data('promos')
    
    # Проверка существования кода
    if input_code not in promos_db:
        log_action(user_id_key, f"PROMO_INVALID: {input_code}")
        bot.send_message(
            message.chat.id, 
            "❌ Такого промокода не существует или он уже истек.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return

    # Проверка: использовал ли юзер этот код раньше
    if input_code in users_db[user_id_key].get('used_promos', []):
        log_action(user_id_key, f"PROMO_ALREADY_USED: {input_code}")
        bot.send_message(
            message.chat.id, 
            "❌ Вы уже активировали этот промокод ранее.", 
            reply_markup=create_main_menu(message.from_user.id)
        )
        return

    # Извлечение данных о награде
    code_info = promos_db[input_code]
    reward_type = code_info['type']
    reward_val = code_info['value']
    
    # Начисление в зависимости от типа
    if reward_type == 'rolls':
        current = users_db[user_id_key].get('free_rolls', 0)
        users_db[user_id_key]['free_rolls'] = current + int(reward_val)
        success_msg = f"✅ Успех! Вы получили **{int(reward_val)} бесплатных прокрутов**!"
        
    elif reward_type == 'luck':
        users_db[user_id_key]['bonus_luck'] = float(reward_val)
        success_msg = f"✅ Успех! Ваша удача увеличена в **{reward_val} раз** на следующую попытку!"
        
    else: # По умолчанию считаем это очками (points)
        users_db[user_id_key]['score'] += int(reward_val)
        success_msg = f"✅ Успех! Вам начислено **{int(reward_val):,} очков**!"

    # Сохраняем информацию об использовании кода
    if 'used_promos' not in users_db[user_id_key]:
        users_db[user_id_key]['used_promos'] = []
        
    users_db[user_id_key]['used_promos'].append(input_code)
    
    log_action(user_id_key, f"PROMO_SUCCESS: {input_code}")
    
    save_data(users_db, 'users')
    
    bot.send_message(
        message.chat.id, 
        success_msg, 
        reply_markup=create_main_menu(message.from_user.id),
        parse_mode="Markdown"
    )

# ==============================================================================
# [8] ГЛАВНАЯ МЕХАНИКА: ПОЛУЧЕНИЕ КАРТ (ROLL SYSTEM)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎰 Крутить карту")
def roll_card_handler(message):
    """
    Основная игровая функция. Выдает случайную карту игроку.
    """
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    users_db = load_data('users')
    all_cards = load_data('cards')
    
    log_action(user_id_key, "ROLL_REQUEST")
    
    # Проверка: есть ли вообще карты в игре
    if not all_cards or len(all_cards) == 0:
        bot.send_message(message.chat.id, "❌ В игре пока нет созданных карт. Пожалуйста, подождите обновлений.")
        return
        
    current_time_stamp = time.time()
    bonus_rolls_available = users_db[user_id_key].get('free_rolls', 0)
    
    # ПРОВЕРКА КУЛДАУНА (3 ЧАСА = 10800 секунд)
    # Администраторы и игроки с бонусными прокрутами обходят таймер
    is_user_admin = check_admin_permission(message.from_user)
    
    if not is_user_admin and bonus_rolls_available <= 0:
        if user_id_key in roll_cooldowns:
            time_difference = current_time_stamp - roll_cooldowns[user_id_key]
            
            if time_difference < 10800:
                seconds_left = int(10800 - time_difference)
                hours = seconds_left // 3600
                minutes = (seconds_left % 3600) // 60
                
                wait_text = (
                    f"⏳ **СКАУТЫ ЕЩЕ НЕ ВЕРНУЛИСЬ!**\n\n"
                    f"Вы сможете крутить карту через {hours}ч {minutes}м.\n\n"
                    "🎟 Используйте промокоды или приглашайте друзей, чтобы получить бонусные прокруты без ожидания!"
                )
                bot.send_message(message.chat.id, wait_text, parse_mode="Markdown")
                return

    # РАСЧЕТ ВЕРОЯТНОСТЕЙ И ВЫБОР РЕДКОСТИ
    luck_multiplier = users_db[user_id_key].get('bonus_luck', 1.0)
    
    rarity_indices = sorted(RARITY_STATS.keys())
    chance_weights = []
    
    for r_idx in rarity_indices:
        base_chance = RARITY_STATS[r_idx]['chance']
        
        # Применяем множитель удачи к Эпическим (4) и Легендарным (5) картам
        if r_idx >= 4:
            base_chance = base_chance * luck_multiplier
            
        chance_weights.append(base_chance)

    # Случайный выбор редкости на основе весов
    final_rarity = random.choices(rarity_indices, weights=chance_weights)[0]
    
    # Фильтрация карт из базы по выбранной редкости
    potential_pool = []
    for card in all_cards:
        if card['stars'] == final_rarity:
            potential_pool.append(card)
    
    # Если карт выбранной редкости нет (ошибка наполнения базы), берем любую карту
    if not potential_pool:
        potential_pool = all_cards
        
    # Выбираем финальную награду
    won_card_object = random.choice(potential_pool)
    
    # Учет попытки
    if bonus_rolls_available > 0:
        users_db[user_id_key]['free_rolls'] = bonus_rolls_available - 1
        attempt_info = f"🎫 Использован бонусный прокрут. Осталось: {users_db[user_id_key]['free_rolls']}"
    else:
        roll_cooldowns[user_id_key] = current_time_stamp
        attempt_info = "⏳ Обычный прокрут использован. Следующий — через 3 часа."

    # Сбрасываем множитель удачи после использования
    users_db[user_id_key]['bonus_luck'] = 1.0

    # ПРОВЕРКА НА ПОВТОРЯЮЩУЮСЯ КАРТУ
    collections_db = load_data('colls')
    if user_id_key not in collections_db:
        collections_db[user_id_key] = []
        
    # Проверка: есть ли у игрока уже карта с таким именем
    is_duplicate = False
    for existing_card in collections_db[user_id_key]:
        if existing_card['name'] == won_card_object['name']:
            is_duplicate = True
            break
    
    if is_duplicate:
        # Компенсация за повтор — 30% от стандартной награды редкости
        points_to_give = int(RARITY_STATS[won_card_object['stars']]['score'] * 0.3)
        result_message = "🔄 **ПОВТОР!**\nУ вас уже есть этот игрок. Вам начислена компенсация очками (30%)."
    else:
        # Награда за новую карту — 100% очков
        points_to_give = RARITY_STATS[won_card_object['stars']]['score']
        result_message = "✨ **НОВЫЙ ИГРОК!**\nПоздравляем! Эта карта добавлена в вашу коллекцию."
        collections_db[user_id_key].append(won_card_object)
        save_data(collections_db, 'colls')

    # Обновление баланса игрока
    users_db[user_id_key]['score'] += points_to_give
    save_data(users_db, 'users')

    # ПОДГОТОВКА ВИЗУАЛЬНОГО ОФОРМЛЕНИЯ КАРТОЧКИ
    stars_str = "⭐" * won_card_object['stars']
    pos_full_name = POSITIONS_RU.get(won_card_object['pos'].upper(), won_card_object['pos'])
    
    caption_text = (
        f"⚽️ **{won_card_object['name']}**\n\n"
        f"📊 Редкость: {stars_str} ({RARITY_STATS[won_card_object['stars']]['label']})\n"
        f"🎯 Позиция: {pos_full_name}\n\n"
        f"💠 {result_message}\n"
        f"💰 Начислено: +{points_to_give:,} очков\n"
        f"📈 Ваш баланс: {users_db[user_id_key]['score']:,}\n\n"
        f"{attempt_info}"
    )
    
    log_action(user_id_key, f"WON_CARD: {won_card_object['name']}")
    
    bot.send_photo(
        message.chat.id, 
        won_card_object['photo'], 
        caption=caption_text, 
        parse_mode="Markdown"
    )

# ==============================================================================
# [9] МОДУЛЬ ПВП (БОИ С ДРУГИМИ ИГРОКАМИ)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🏟 ПВП Арена")
def pvp_hub_handler(message):
    """
    Выводит интерфейс для начала сражений.
    """
    if check_ban_status(message.from_user):
        return
    
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, "OPEN_PVP_ARENA")
    
    # Проверка кулдауна на ПВП (15 минут = 900 секунд)
    if not check_admin_permission(message.from_user):
        if user_id_key in pvp_cooldowns:
            elapsed_time = time.time() - pvp_cooldowns[user_id_key]
            if elapsed_time < 900:
                rem_sec = int(900 - elapsed_time)
                bot.send_message(message.chat.id, f"⏳ Ваши футболисты устали. Следующий матч через {rem_sec // 60} мин.")
                return

    # Создание Inline кнопок
    pvp_markup = types.InlineKeyboardMarkup(row_width=1)
    
    btn_rand = types.InlineKeyboardButton("🎲 Случайный соперник", callback_data="pvp_action_random")
    btn_user = types.InlineKeyboardButton("👤 Найти по нику", callback_data="pvp_action_by_user")
    
    pvp_markup.add(btn_rand, btn_user)
    
    my_team_power = calculate_total_power(user_id_key)
    
    arena_text = (
        "🏟 **ДОБРО ПОЖАЛОВАТЬ НА АРЕНУ!**\n\n"
        "Здесь решается, чья команда сильнее.\n"
        "Победа в матче принесет вам **1,000 очков**.\n\n"
        f"Ваша текущая мощь состава: **{my_team_power}**\n\n"
        "Выберите способ поиска противника:"
    )
    
    bot.send_message(
        message.chat.id, 
        arena_text, 
        reply_markup=pvp_markup, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "pvp_action_random")
def pvp_random_matchmaking(call):
    """
    Автоматический поиск случайного игрока с активным составом.
    """
    users_db = load_data('users')
    player1_id = str(call.from_user.id)
    
    p1_pwr = calculate_total_power(player1_id)
    
    if p1_pwr <= 0:
        bot.answer_callback_query(call.id, "❌ Ваш состав пуст! Назначьте игроков в меню 'Состав'.", show_alert=True)
        return

    # Собираем список всех игроков, у которых сила состава больше 0
    potential_opponents = []
    
    for uid_key in users_db.keys():
        if uid_key != player1_id:
            if calculate_total_power(uid_key) > 0:
                potential_opponents.append(uid_key)
            
    if not potential_opponents or len(potential_opponents) == 0:
        bot.answer_callback_query(call.id, "❌ Подходящие противники не найдены. Попробуйте позже.", show_alert=True)
        return
        
    # Случайный выбор из списка
    player2_id = random.choice(potential_opponents)
    
    log_action(player1_id, f"RANDOM_PVP_VS_{player2_id}")
    
    run_match_logic(call.message.chat.id, player1_id, player2_id)

@bot.callback_query_handler(func=lambda call: call.data == "pvp_action_by_user")
def pvp_search_by_username_start(call):
    """
    Запрашивает ввод ника для поиска конкретного оппонента.
    """
    log_action(call.from_user.id, "PVP_BY_USERNAME_CLICK")
    
    instruction = (
        "👤 **ПОИСК СОПЕРНИКА**\n\n"
        "Введите @username игрока или его цифровой ID, чтобы бросить ему вызов.\n"
        "Игрок должен быть зарегистрирован в боте и иметь активный состав."
    )
    
    sent_msg = bot.send_message(
        call.message.chat.id, 
        instruction, 
        reply_markup=create_cancel_menu(),
        parse_mode="Markdown"
    )
    
    bot.register_next_step_handler(sent_msg, process_pvp_search_by_input)

def process_pvp_search_by_input(message):
    """
    Поиск игрока в базе по введенной строке.
    """
    if message.text == "❌ Отмена":
        log_action(message.from_user.id, "PVP_SEARCH_CANCELLED")
        bot.send_message(message.chat.id, "Отменено.", reply_markup=create_main_menu(message.from_user.id))
        return
        
    search_query = message.text.replace("@", "").lower().strip()
    users_db = load_data('users')
    p1_id = str(message.from_user.id)
    
    found_p2_id = None
    
    # Линейный поиск по базе
    for uid, u_info in users_db.items():
        # Проверка по ID
        if uid == search_query:
            found_p2_id = uid
            break
        
        # Проверка по Username
        db_username = u_info.get('username', '').replace("@", "").lower()
        if db_username == search_query:
            found_p2_id = uid
            break
            
    # Обработка результатов поиска
    if not found_p2_id:
        bot.send_message(message.chat.id, "❌ Игрок с таким именем не найден в нашей базе.", reply_markup=create_main_menu(p1_id))
        return
        
    if found_p2_id == p1_id:
        bot.send_message(message.chat.id, "❌ Вы не можете играть против самого себя.", reply_markup=create_main_menu(p1_id))
        return
        
    # Проверка готовности состава оппонента
    p2_pwr = calculate_total_power(found_p2_id)
    if p2_pwr <= 0:
        bot.send_message(message.chat.id, "❌ У этого игрока пока не настроен футбольный состав.", reply_markup=create_main_menu(p1_id))
        return
        
    log_action(p1_id, f"PVP_BY_USERNAME_VS_{found_p2_id}")
    
    run_match_logic(message.chat.id, p1_id, found_p2_id)

def run_match_logic(chat_id, p1_id, p2_id):
    """
    Ядро ПВП-системы: расчет шансов и определение победителя.
    """
    users_db = load_data('users')
    
    p1_atk = calculate_total_power(p1_id)
    p2_atk = calculate_total_power(p2_id)
    
    # Математическая модель победы
    # Мы используем веса: сила в степени 1.3, чтобы сильные игроки побеждали чаще,
    # но у слабых всё равно оставался минимальный шанс на удачу.
    weight1 = float(p1_atk) ** 1.35
    weight2 = float(p2_atk) ** 1.35
    
    # Если оба состава пустые (теоретически), ставим равные шансы
    if weight1 == 0 and weight2 == 0:
        weight1, weight2 = 1, 1
        
    # Случайный выбор победителя
    winner_id = random.choices([p1_id, p2_id], weights=[weight1, weight2])[0]
    
    # Начисление награды
    users_db[winner_id]['score'] += 1000
    save_data(users_db, 'users')
    
    # Установка ограничения на следующую игру для инициатора
    pvp_cooldowns[p1_id] = time.time()
    
    # Формирование отчета о матче
    match_report = (
        "🏟 **ИТОГИ ФУТБОЛЬНОГО МАТЧА**\n\n"
        f"🏠 Хозяева: **{users_db[p1_id]['nick']}**\n"
        f"🛡 Сила команды: `{p1_atk}`\n\n"
        f"🚀 Гости: **{users_db[p2_id]['nick']}**\n"
        f"🛡 Сила команды: `{p2_atk}`\n\n"
        "➖➖➖➖➖➖➖➖➖➖\n"
        f"🏆 Победитель: **{users_db[winner_id]['username']}**\n"
        f"💰 Приз за победу: **+1,000 очков**"
    )
    
    bot.send_message(
        chat_id, 
        match_report, 
        parse_mode="Markdown", 
        reply_markup=create_main_menu(p1_id)
    )

# ==============================================================================
# [10] ПРОФИЛЬ, ТОП И ПРОСМОТР АЛЬБОМОВ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile_view_handler(message):
    """
    Отображает детальную статистику игрока.
    """
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, "VIEW_PROFILE")
    
    u_db = load_data('users')
    c_db = load_data('colls')
    
    user_info = u_db.get(user_id_key)
    
    count_cards = len(c_db.get(user_id_key, []))
    team_power = calculate_total_power(user_id_key)
    
    profile_text = (
        f"👤 **ВАШ ИГРОВОЙ ПРОФИЛЬ**\n\n"
        f"🆔 Ваш ID: `{user_id_key}`\n"
        f"👤 Имя: {user_info['nick']}\n\n"
        f"💠 Баланс очков: **{user_info['score']:,}**\n"
        f"🗂 В коллекции: **{count_cards}** игроков\n"
        f"🛡 Сила состава: **{team_power}**\n"
        f"🎫 Бонусные прокруты: **{user_info.get('free_rolls', 0)}**\n"
        f"👥 Приглашено друзей: **{user_info.get('refs', 0)}**"
    )
    
    bot.send_message(message.chat.id, profile_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏆 Топ очков")
def global_top_handler(message):
    """
    Выводит 10 самых богатых пользователей.
    """
    if check_ban_status(message.from_user):
        return
        
    log_action(message.from_user.id, "VIEW_LEADERBOARD")
    
    users_db = load_data('users')
    
    # Превращаем словарь в список кортежей и сортируем по очкам
    user_items = list(users_db.items())
    sorted_users = sorted(user_items, key=lambda item: item[1]['score'], reverse=True)
    
    # Берем первую десятку
    top_10 = sorted_users[:10]
    
    leaderboard_text = "🏆 **ГЛОБАЛЬНЫЙ РЕЙТИНГ (ТОП-10)**\n\n"
    
    for index, (uid, info) in enumerate(top_10, 1):
        # Экранируем ники
        name = info['username'].replace("_", "\\_")
        score = info['score']
        leaderboard_text += f"{index}. {name} — `{score:,}` очков\n"
    
    bot.send_message(message.chat.id, leaderboard_text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection_menu_handler(message):
    """
    Интерфейс выбора редкости для просмотра своего альбома.
    """
    if check_ban_status(message.from_user):
        return
        
    log_action(message.from_user.id, "OPEN_COLLECTION_MENU")
    
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for stars in range(1, 6):
        label = f"{'⭐' * stars} Показать этих игроков"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"view_coll_stars_{stars}"))
    
    msg_text = (
        "🗂 **ВАШ АЛЬБОМ КАРТОЧЕК**\n\n"
        "Здесь собраны все игроки, которых вы выбили.\n"
        "Выберите редкость для просмотра:"
    )
    
    bot.send_message(message.chat.id, msg_text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("view_coll_stars_"))
def show_filtered_collection_handler(call):
    """
    Показывает список имен карт определенной звездности.
    """
    target_stars = int(call.data.split("_")[-1])
    user_id_key = str(call.from_user.id)
    
    log_action(user_id_key, f"VIEW_STARS_{target_stars}")
    
    # Загружаем коллекцию именно этого юзера
    user_colls = load_data('colls').get(user_id_key, [])
    
    # Фильтруем список
    filtered_list = []
    for item in user_colls:
        if item['stars'] == target_stars:
            filtered_list.append(item)
    
    if not filtered_list:
        bot.answer_callback_query(call.id, f"У вас нет карт на {target_stars} звезд.", show_alert=True)
        return
        
    result_text = f"🗂 **ВАШИ КАРТЫ ({target_stars}⭐):**\n\n"
    
    for player in filtered_list:
        pos_ru = POSITIONS_RU.get(player['pos'].upper(), player['pos'])
        result_text += f"• **{player['name']}** ({pos_ru})\n"
        
    bot.send_message(call.message.chat.id, result_text, parse_mode="Markdown")

# ==============================================================================
# [11] МОДУЛЬ РЕДАКТИРОВАНИЯ СОСТАВА (КОМАНДА)
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "📋 Состав")
def squad_editor_main_handler(message):
    """
    Главный экран управления 7-ю игроками команды.
    """
    if check_ban_status(message.from_user):
        return
        
    user_id_key = str(message.from_user.id)
    log_action(user_id_key, "OPEN_SQUAD_EDITOR")
    
    bot.send_message(
        message.chat.id, 
        "📋 **РЕДАКТОР ВАШЕГО СОСТАВА**\n\nНажмите на слот, чтобы выбрать игрока из вашей коллекции на эту позицию.", 
        reply_markup=generate_dynamic_squad_kb(user_id_key), 
        parse_mode="Markdown"
    )

def generate_dynamic_squad_kb(uid):
    """
    Создает Inline-кнопки для каждого из 7 слотов состава.
    """
    squad_db = load_data('squads')
    current_players = squad_db.get(str(uid), [None] * 7)
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    for i in range(7):
        slot_config = SQUAD_SLOTS[i]
        assigned_card = current_players[i]
        
        if assigned_card is not None:
            # Если игрок назначен, показываем его имя и звезды
            btn_label = f"{slot_config['label']}: {assigned_card['name']} ({assigned_card['stars']}⭐)"
        else:
            # Если слот пуст
            btn_label = f"{slot_config['label']}: ❌ Не назначен"
            
        kb.add(types.InlineKeyboardButton(btn_label, callback_data=f"edit_slot_index_{i}"))
        
    return kb

@bot.callback_query_handler(func=lambda c: c.data.startswith("edit_slot_index_"))
def list_available_for_slot_handler(call):
    """
    Показывает список доступных карт в коллекции игрока для конкретной позиции.
    """
    slot_index = int(call.data.split("_")[-1])
    user_id_key = str(call.from_user.id)
    
    # Определяем, какой код позиции нужен (например, ПВ или ГК)
    target_position_code = SQUAD_SLOTS[slot_index]["code"]
    
    log_action(user_id_key, f"SELECTING_PLAYER_FOR_{target_position_code}")
    
    # Получаем всю коллекцию юзера
    my_collection = load_data('colls').get(user_id_key, [])
    
    # ФИЛЬТРАЦИЯ: выбираем только тех, кто подходит на позицию
    valid_choices = []
    for card in my_collection:
        # Приводим к верхнему регистру для избежания ошибок
        if card['pos'].upper() == target_position_code.upper():
            valid_choices.append(card)
    
    if not valid_choices or len(valid_choices) == 0:
        bot.answer_callback_query(call.id, f"❌ У вас в коллекции нет игроков позиции {target_position_code}!", show_alert=True)
        return
        
    choice_kb = types.InlineKeyboardMarkup(row_width=1)
    
    for player in valid_choices:
        label = f"{player['name']} ({player['stars']}⭐)"
        # Кодируем выбор (индекс слота + имя игрока)
        choice_kb.add(types.InlineKeyboardButton(label, callback_data=f"confirm_squad_set_{slot_index}_{player['name']}"))
        
    # Кнопка очистки слота
    choice_kb.add(types.InlineKeyboardButton("🚫 Очистить этот слот", callback_data=f"confirm_squad_set_{slot_index}_EMPTY_SLOT"))
    
    bot.edit_message_text(
        f"Выберите игрока для позиции **{target_position_code}**:", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=choice_kb, 
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_squad_set_"))
def save_player_to_squad_handler(call):
    """
    Записывает выбранного игрока в базу данных составов.
    """
    data_parts = call.data.split("_")
    slot_id = int(data_parts[3])
    p_name = data_parts[4]
    user_id_key = str(call.from_user.id)
    
    squad_db = load_data('squads')
    
    # Инициализация, если юзер зашел впервые
    if user_id_key not in squad_db:
        squad_db[user_id_key] = [None] * 7
        
    if p_name == "EMPTY":
        # Удаляем игрока из слота
        squad_db[user_id_key][slot_id] = None
        log_action(user_id_key, f"CLEARED_SLOT_{slot_id}")
    else:
        # Поиск полного объекта карты в коллекции
        user_coll = load_data('colls').get(user_id_key, [])
        target_obj = None
        for card in user_coll:
            if card['name'] == p_name:
                target_obj = card
                break
        
        # Записываем объект в выбранный индекс списка
        squad_db[user_id_key][slot_id] = target_obj
        log_action(user_id_key, f"SET_{p_name}_TO_SLOT_{slot_id}")
        
    save_data(squad_db, 'squads')
    
    # Возвращаемся в главное меню редактора
    bot.edit_message_text(
        "✅ Изменения успешно применены!", 
        call.message.chat.id, 
        call.message.message_id, 
        reply_markup=generate_dynamic_squad_kb(user_id_key)
    )

# ==============================================================================
# [12] АДМИНИСТРИРОВАНИЕ: УПРАВЛЕНИЕ КАРТАМИ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel_root_handler(message):
    """
    Открывает доступ к инструментам администратора.
    """
    if not check_admin_permission(message.from_user):
        return
        
    log_action(message.from_user.id, "OPEN_ADMIN_PANEL")
    
    bot.send_message(
        message.chat.id, 
        "🛠 **ГЛАВНОЕ МЕНЮ АДМИНИСТРАТОРА**\n\nИспользуйте кнопки ниже для управления базой данных бота.", 
        reply_markup=create_admin_menu(), 
        parse_mode="Markdown"
    )

# --- ПРОЦЕСС ДОБАВЛЕНИЯ КАРТЫ (ПОШАГОВЫЙ) ---

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def admin_add_player_step_1(message):
    """Шаг 1: Запрос имени."""
    if not check_admin_permission(message.from_user): return
    
    msg = bot.send_message(
        message.chat.id, 
        "Введите ФИО нового футболиста:", 
        reply_markup=create_cancel_menu()
    )
    bot.register_next_step_handler(msg, admin_add_player_step_2)

def admin_add_player_step_2(message):
    """Шаг 2: Запрос позиции."""
    if message.text == "❌ Отмена": return cancel_current_op(message)
    
    full_name = message.text.strip()
    
    msg = bot.send_message(
        message.chat.id, 
        f"Введите позицию для {full_name}\n(ГК, ЛЗ, ПЗ, ЦП, ЛВ, ПВ, КФ):"
    )
    bot.register_next_step_handler(msg, admin_add_player_step_3, full_name)

def admin_add_player_step_3(message, full_name):
    """Шаг 3: Запрос редкости."""
    if message.text == "❌ Отмена": return cancel_current_op(message)
    
    pos_code = message.text.upper().strip()
    
    msg = bot.send_message(
        message.chat.id, 
        f"Введите редкость (количество звезд от 1 до 5):"
    )
    bot.register_next_step_handler(msg, admin_add_player_step_4, full_name, pos_code)

def admin_add_player_step_4(message, full_name, pos_code):
    """Шаг 4: Запрос изображения."""
    if message.text == "❌ Отмена": return cancel_current_op(message)
    
    try:
        star_count = int(message.text)
        if star_count < 1 or star_count > 5:
            raise ValueError
            
        msg = bot.send_message(
            message.chat.id, 
            f"Отправьте фотографию для карточки игрока {full_name}:"
        )
        bot.register_next_step_handler(msg, admin_add_player_step_5_final, full_name, pos_code, star_count)
    except:
        bot.send_message(message.chat.id, "Ошибка! Нужно ввести число от 1 до 5. Попробуйте снова.")

def admin_add_player_step_5_final(message, full_name, pos_code, star_count):
    """Шаг 5: Сохранение в базу."""
    if not message.photo:
        bot.send_message(message.chat.id, "❌ Вы не прислали фото. Процесс прерван.")
        return
    
    # Получаем ID самого качественного фото
    image_file_id = message.photo[-1].file_id
    
    cards_database = load_data('cards')
    
    # Формируем объект
    new_card = {
        "name": full_name,
        "pos": pos_code,
        "stars": star_count,
        "photo": image_file_id
    }
    
    cards_database.append(new_card)
    save_data(cards_database, 'cards')
    
    log_action(message.from_user.id, f"ADMIN_ADDED_CARD: {full_name}")
    
    bot.send_message(
        message.chat.id, 
        f"✅ **УСПЕХ!**\nИгрок **{full_name}** ({pos_code}, {star_count}⭐) успешно добавлен в базу и доступен для выпадения!", 
        reply_markup=create_admin_menu(),
        parse_mode="Markdown"
    )

# --- ПРОЦЕСС УДАЛЕНИЯ КАРТЫ ---

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить карту")
def admin_remove_card_start(message):
    """Выводит список имен всех карт для удаления."""
    if not check_admin_permission(message.from_user): return
    
    all_cards = load_data('cards')
    
    if not all_cards:
        bot.send_message(message.chat.id, "В базе данных пока нет карт.")
        return
        
    kb = types.InlineKeyboardMarkup(row_width=1)
    for card in all_cards:
        kb.add(types.InlineKeyboardButton(f"❌ {card['name']}", callback_data=f"adm_remove_c_{card['name']}"))
        
    bot.send_message(message.chat.id, "Выберите карту для безвозвратного удаления:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_remove_c_"))
def admin_remove_card_execute(call):
    """Фактическое удаление из списка."""
    target_name = call.data.replace("adm_remove_c_", "")
    cards_db = load_data('cards')
    
    new_db = []
    for c in cards_db:
        if c['name'] != target_name:
            new_db.append(c)
            
    save_data(new_db, 'cards')
    
    log_action(call.from_user.id, f"ADMIN_REMOVED_CARD: {target_name}")
    
    bot.edit_message_text(
        f"🗑 Игрок **{target_name}** был полностью удален из игры.", 
        call.message.chat.id, 
        call.message.message_id,
        parse_mode="Markdown"
    )

# ==============================================================================
# [13] АДМИНИСТРИРОВАНИЕ: ПРОМОКОДЫ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🎟 +Промокод")
def admin_add_promo_start(message):
    """Начало создания промокода."""
    if not check_admin_permission(message.from_user): return
    
    msg = bot.send_message(
        message.chat.id, 
        "Введите название промокода (только ЛАТИННИЦА и ЦИФРЫ):", 
        reply_markup=create_cancel_menu()
    )
    bot.register_next_step_handler(msg, admin_add_promo_step_2)

def admin_add_promo_step_2(message):
    """Выбор типа награды."""
    if message.text == "❌ Отмена": return cancel_current_op(message)
    
    code_name = message.text.strip().upper()
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🎫 Прокруты (Rolls)", callback_data=f"adm_promo_type_{code_name}_rolls"),
        types.InlineKeyboardButton("💠 Очки (Points)", callback_data=f"adm_promo_type_{code_name}_points"),
        types.InlineKeyboardButton("🍀 Удача (Luck)", callback_data=f"adm_promo_type_{code_name}_luck")
    )
    
    bot.send_message(message.chat.id, f"Выберите тип бонуса для кода {code_name}:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_promo_type_"))
def admin_add_promo_step_3(call):
    """Запрос числового значения."""
    parts = call.data.split("_")
    code_name = parts[3]
    bonus_type = parts[4]
    
    msg = bot.send_message(call.message.chat.id, f"Введите число (количество бонуса для {bonus_type}):")
    bot.register_next_step_handler(msg, admin_add_promo_final, code_name, bonus_type)

def admin_add_promo_final(message, code_name, bonus_type):
    """Сохранение в базу промокодов."""
    try:
        numeric_value = float(message.text)
        
        promos_db = load_data('promos')
        promos_db[code_name] = {"type": bonus_type, "value": numeric_value}
        
        save_data(promos_db, 'promos')
        
        log_action(message.from_user.id, f"ADMIN_CREATED_PROMO: {code_name}")
        
        bot.send_message(
            message.chat.id, 
            f"✅ Промокод `{code_name}` на {bonus_type} ({numeric_value}) успешно создан!", 
            reply_markup=create_admin_menu(),
            parse_mode="Markdown"
        )
    except:
        bot.send_message(message.chat.id, "Ошибка! Введите числовое значение.")

@bot.message_handler(func=lambda m: m.text == "🗑 Удалить промокод")
def admin_list_promos_for_delete(message):
    """Список всех активных кодов для удаления."""
    if not check_admin_permission(message.from_user): return
    
    db = load_data('promos')
    if not db:
        bot.send_message(message.chat.id, "Активных промокодов нет.")
        return
        
    kb = types.InlineKeyboardMarkup(row_width=1)
    for code_key in db.keys():
        kb.add(types.InlineKeyboardButton(f"🗑 Удалить {code_key}", callback_data=f"adm_rem_promo_{code_key}"))
        
    bot.send_message(message.chat.id, "Выберите промокод для удаления:", reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_rem_promo_"))
def admin_remove_promo_execute(call):
    """Удаляет ключ из базы."""
    target_code = call.data.replace("adm_rem_promo_", "")
    db = load_data('promos')
    
    if target_code in db:
        del db[target_code]
        save_data(db, 'promos')
        
    log_action(call.from_user.id, f"ADMIN_DELETED_PROMO: {target_code}")
    
    bot.edit_message_text(f"✅ Промокод `{target_code}` был удален.", call.message.chat.id, call.message.message_id, parse_mode="Markdown")

# ==============================================================================
# [14] АДМИНИСТРИРОВАНИЕ: МОДЕРАЦИЯ И СБРОС
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🚫 Забанить")
def admin_ban_start(message):
    """Запрос цели для бана."""
    if not check_admin_permission(message.from_user): return
    
    msg = bot.send_message(
        message.chat.id, 
        "Введите @username или ID пользователя для блокировки:", 
        reply_markup=create_cancel_menu()
    )
    bot.register_next_step_handler(msg, lambda m: process_ban_toggle(m, True))

@bot.message_handler(func=lambda m: m.text == "✅ Разбанить")
def admin_unban_start(message):
    """Запрос цели для разбана."""
    if not check_admin_permission(message.from_user): return
    
    msg = bot.send_message(
        message.chat.id, 
        "Введите @username или ID пользователя для разблокировки:", 
        reply_markup=create_cancel_menu()
    )
    bot.register_next_step_handler(msg, lambda m: process_ban_toggle(m, False))

def process_ban_toggle(message, is_blocking):
    """Добавление/удаление из черного списка."""
    if message.text == "❌ Отмена": return cancel_current_op(message)
    
    target_val = message.text.replace("@", "").lower().strip()
    ban_db = load_data('bans')
    
    if is_blocking:
        if target_val not in ban_db:
            ban_db.append(target_val)
            res_txt = f"🚫 Пользователь `{target_val}` заблокирован."
        else:
            res_txt = "Этот пользователь уже в бане."
    else:
        if target_val in ban_db:
            ban_db.remove(target_val)
            res_txt = f"✅ Пользователь `{target_val}` разблокирован."
        else:
            res_txt = "Этого пользователя нет в списке банов."
            
    save_data(ban_db, 'bans')
    
    log_action(message.from_user.id, f"BAN_TOGGLE_{target_val}_{is_blocking}")
    
    bot.send_message(message.chat.id, res_txt, reply_markup=create_admin_menu(), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🧨 Обнулить бота")
def admin_wipe_confirmation(message):
    """Защита от случайного удаления всех данных."""
    if not check_admin_permission(message.from_user): return
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("🚨 ДА, СТЕРЕТЬ ВСЕ ДАННЫЕ", "❌ Отмена")
    
    bot.send_message(
        message.chat.id, 
        "⚠️ **ВНИМАНИЕ!**\nВы собираетесь удалить данные всех игроков (балансы, коллекции, составы).\nКарты и промокоды останутся. Вы уверены?", 
        reply_markup=kb,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "🚨 ДА, СТЕРЕТЬ ВСЕ ДАННЫЕ")
def admin_wipe_execute(message):
    """Финальная очистка баз юзеров."""
    if not check_admin_permission(message.from_user): return
    
    # Очищаем три файла
    save_data({}, 'users')
    save_data({}, 'colls')
    save_data({}, 'squads')
    
    log_action(message.from_user.id, "GLOBAL_DATABASE_WIPE")
    
    bot.send_message(
        message.chat.id, 
        "🧨 Все игровые данные пользователей были уничтожены.", 
        reply_markup=create_admin_menu()
    )

# ==============================================================================
# [15] СЛУЖЕБНЫЕ КОМАНДЫ И НАВИГАЦИЯ
# ==============================================================================

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def navigation_back_home(message):
    """Возврат в главное меню из любой точки."""
    bot.send_message(
        message.chat.id, 
        "Вы вернулись в главное меню игры.", 
        reply_markup=create_main_menu(message.from_user.id)
    )

def cancel_current_op(message):
    """Универсальная функция отмены шаговых действий."""
    bot.send_message(
        message.chat.id, 
        "Действие отменено администратором.", 
        reply_markup=create_admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == "❌ Отмена")
def global_cancel_handler(message):
    """Глобальный обработчик кнопки отмены."""
    bot.send_message(
        message.chat.id, 
        "Текущая операция прервана.", 
        reply_markup=create_main_menu(message.from_user.id)
    )

# ==============================================================================
# [16] ЗАПУСК ПРИЛОЖЕНИЯ
# ==============================================================================

if __name__ == "__main__":
    # Вывод системной информации при старте
    print("--------------------------------------------------")
    print("  FOOTBALL CARDS SIMULATOR BOT IS STARTING...")
    print(f"  ADMINS LOADED: {len(ADMINS)}")
    print(f"  FILES CHECKED: {len(DB_FILES)} units")
    print("--------------------------------------------------")
    
    try:
        # Бесконечный цикл опроса серверов Telegram
        bot.infinity_polling(timeout=20, long_polling_timeout=10)
    except Exception as server_error:
        print(f"Критическая ошибка сервера: {server_error}")
        time.sleep(5)
        # Перезапуск в случае падения
        os.execv(sys.executable, ['python'] + sys.argv)

# КОНЕЦ ФАЙЛА. ВСЕГО СТРОК: 1060+
# ==============================================================================
