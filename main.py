import telebot
from telebot import types
import random
import time
import json
import os

# --- [1] КОНФИГУРАЦИЯ ---
TOKEN = "8693121162:AAETyvJphmP-yreamHk-IXqshKqyMP0-3X8"
ADMINS = ["1674945230", "7908057052"] 
bot = telebot.TeleBot(TOKEN)

# Настройка КД (в секундах).
COOLDOWN_TIME = 3600 

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

SQUAD_POSITIONS = ['LF', 'CF', 'RF', 'CM', 'LB', 'RB', 'GK']

# Словари для хранения кулдаунов в памяти
last_roll = {}
match_cooldowns = {}  # Учет КД на матчи: {'uid_turbo': timestamp, 'uid_long45': timestamp}
pvp_queue = []        # Очередь для матча 5 мин

# Текстовые заготовки для опасных моментов в Долгом матче
MATCH_EVENTS = [
    "🔥 {attacker} перехватывает мяч в центре поля и убегает в контратаку!",
    "🎯 {attacker} исполняет великолепный штрафной удар из-за пределов площадки!",
    "комбо {attacker} разыгрывает красивую стеночку возле штрафной площади соперника!",
    "🏃‍♂️ Нападающий команды {attacker} на огромной скорости обыгрывает защитника!",
    "📐 {attacker} подает угловой! В штрафной идет жесткая борьба за мяч!"
]

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
    try: return "⭐️" * int(count)
    except: return "⭐️"

def is_admin_user(user):
    return str(user.id) in ADMINS

def get_squad_rating(uid):
    """Вспомогательная функция расчета общего OVR состава"""
    squads = load_db('squads')
    user_squad = squads.get(uid, {})
    total_ovr = 0
    count = 0
    for pos in SQUAD_POSITIONS:
        if user_squad.get(pos):
            try:
                total_ovr += int(user_squad[pos]['ovr'])
                count += 1
            except: pass
    return total_ovr, count

# --- [3] КЛАВИАТУРЫ ---
def main_kb(user):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Получить карту", "🗂 Коллекция")
    markup.row("⚽️ Мой состав", "⚔️ Матч")
    markup.row("👤 Профиль", "🏆 Топ игроков")
    markup.row("💎 Премиум")
    if is_admin_user(user):
        markup.add("🛠 Админ-панель")
    return markup

# --- [4] ЛОГИКА ИГРЫ ---

@bot.message_handler(commands=['start'])
def start(m):
    uid = str(m.from_user.id)
    users = load_db('users')
    if uid not in users:
        users[uid] = {
            "score": 0, 
            "username": m.from_user.username or f"user_{uid}",
            "matches_played": 0,
            "last_match_reset": time.time()
        }
        save_db(users, 'users')
    
    bot.send_message(m.chat.id, "👋 Привет! Это бот СЛС карточек. Собирай состав и побеждай в матчах!", 
                     reply_markup=main_kb(m.from_user), parse_mode="Markdown")

# Открытие паков
@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll_start(m):
    uid = str(m.from_user.id)
    if not is_admin_user(m.from_user):
        now = time.time()
        if uid in last_roll and now - last_roll[uid] < COOLDOWN_TIME:
            remains = int(COOLDOWN_TIME - (now - last_roll[uid]))
            return bot.send_message(m.chat.id, f"⏳ Нужно подождать еще {remains // 60} мин. {remains % 60} сек.")

    cards = load_db('cards')
    if not cards: return bot.send_message(m.chat.id, "❌ В игре пока нет карточек!")

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("🎁 Открыть", callback_data="open_pack"))
    markup.row(types.InlineKeyboardButton("⬅️ Отмена", callback_data="cancel_pack"))

    try:
        with open('465d12ab-8fc3-4bc1-853e-dd4c3a10de12.png', 'rb') as photo:
            bot.send_photo(m.chat.id, photo, caption="🎁 **Бесплатный пак готов!**", reply_markup=markup, parse_mode="Markdown")
    except FileNotFoundError:
        bot.send_message(m.chat.id, "🎁 **Бесплатный пак готов!**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["open_pack", "cancel_pack"])
def pack_callback(call):
    uid = str(call.from_user.id)
    if call.data == "cancel_pack":
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        return

    if not is_admin_user(call.from_user):
        now = time.time()
        if uid in last_roll and now - last_roll[uid] < COOLDOWN_TIME:
            bot.answer_callback_query(call.id, "⏳ Кулдаун еще не прошел!", show_alert=True)
            return
        last_roll[uid] = now

    bot.answer_callback_query(call.id, "Открываем пак...")
    cards, users, colls = load_db('cards'), load_db('users'), load_db('colls')
    won = random.choice(cards)
    
    if uid not in colls: colls[uid] = []
    is_new = not any(c['name'] == won['name'] for c in colls[uid])
    base_pts = STATS.get(int(won.get('stars', 1)), {"score": 500})["score"]
    added_pts = base_pts if is_new else int(base_pts * 0.3)
    
    if uid not in users: users[uid] = {"score": 0, "username": call.from_user.username or f"user_{uid}"}
    users[uid]['score'] += int(added_pts)
    
    if is_new:
        colls[uid].append(won)
        save_db(colls, 'colls')
    save_db(users, 'users')
    
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass

    caption = (
        f"⚽️ **{won['name']}** ({"🆕 Новая карта!" if is_new else "♻️ Повторка"})\n"
        f"║ 📊 OVR: `{won.get('ovr', '—')}`\n"
        f"║ ⚽️ POSITION: `{won.get('pos', '—')}`\n"
        f" — — — — — — — — — —\n"
        f"💠 Очки: +{int(added_pts):,} | Всего: {users[uid]['score']:,}"
    )
    bot.send_photo(call.message.chat.id, won['photo'], caption=caption, parse_mode="Markdown")

# --- [5] СИСТЕМА СОСТАВА (SQUAD) ---
def get_user_squad(uid):
    squads = load_db('squads')
    if uid not in squads:
        squads[uid] = {pos: None for pos in SQUAD_POSITIONS}
        save_db(squads, 'squads')
    return squads[uid]

@bot.message_handler(func=lambda m: m.text == "⚽️ Мой состав")
def my_squad(m):
    uid = str(m.from_user.id)
    squad = get_user_squad(uid)
    total_ovr, players_count = get_squad_rating(uid)
    avg_ovr = round(total_ovr / players_count, 1) if players_count > 0 else 0

    pos_display = {pos: f"🏃‍♂️ {squad[pos]['name']} ({squad[pos]['ovr']})" if squad[pos] else "➕ [Пусто]" for pos in SQUAD_POSITIONS}

    text = (
        f"⚽️ **ВАШ СУПЕР-СОСТАВ** ⚽️\n"
        f"📊 Средний OVR команды: `{avg_ovr}`\n"
        f" — — — — — — — — — — — —\n\n"
        f"🔥 **АТАКА:**\n"
        f" ├ ↖️ **LF:** {pos_display['LF']}\n"
        f" ├ ⬆️ **CF:** {pos_display['CF']}\n"
        f" └ ↗️ **RF:** {pos_display['RF']}\n\n"
        f"🧠 **ПОЛУЗАЩИТА:**\n"
        f" └ 🔄 **CM:** {pos_display['CM']}\n\n"
        f"🛡 **ЗАЩИТА:**\n"
        f" ├ ⏪ **LB:** {pos_display['LB']}\n"
        f" └ ⏩ **RB:** {pos_display['RB']}\n\n"
        f"🧤 **ВРАТАРЬ:**\n"
        f" └ 🥅 **GK:** {pos_display['GK']}\n"
        f" — — — — — — — — — — — —\n"
        f"Чтобы изменить игрока на позиции, нажмите кнопку ниже👇"
    )

    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton("LF", callback_data="sq_choose_LF"),
               types.InlineKeyboardButton("CF", callback_data="sq_choose_CF"),
               types.InlineKeyboardButton("RF", callback_data="sq_choose_RF"))
    markup.row(types.InlineKeyboardButton("CM", callback_data="sq_choose_CM"))
    markup.row(types.InlineKeyboardButton("LB", callback_data="sq_choose_LB"),
               types.InlineKeyboardButton("RB", callback_data="sq_choose_RB"))
    markup.row(types.InlineKeyboardButton("GK", callback_data="sq_choose_GK"))
    
    bot.send_message(m.chat.id, text, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("sq_choose_"))
def squad_choose_position(call):
    uid = str(call.from_user.id)
    target_pos = call.data.replace("sq_choose_", "")
    my_cards = load_db('colls').get(uid, [])
    available_players = [c for c in my_cards if str(c.get('pos', '')).strip().upper() == target_pos.upper()]
    
    if not available_players:
        return bot.answer_callback_query(call.id, f"❌ У вас в коллекции нет игроков на позицию {target_pos}!", show_alert=True)

    markup = types.InlineKeyboardMarkup()
    for p in available_players:
        markup.add(types.InlineKeyboardButton(f"🏃‍♂️ {p['name']} (OVR: {p.get('ovr', '—')})", callback_data=f"sq_set_{target_pos}_{p['name']}"))
    markup.add(types.InlineKeyboardButton("↩️ Назад в состав", callback_data="sq_back"))
    
    bot.edit_message_text(f"🎯 Выберите игрока на позицию **{target_pos}**:", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("sq_set_"))
def squad_set_player(call):
    uid = str(call.from_user.id)
    data_parts = call.data.replace("sq_set_", "").split("_")
    pos, player_name = data_parts[0], "_".join(data_parts[1:])

    colls, squads = load_db('colls'), load_db('squads')
    player_card = next((c for c in colls.get(uid, []) if c['name'] == player_name), None)
    
    if player_card:
        if uid not in squads: squads[uid] = {}
        squads[uid][pos] = player_card
        save_db(squads, 'squads')
        bot.answer_callback_query(call.id, f"✅ {player_name} теперь в основе!", show_alert=True)
    
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    call.message.from_user = call.from_user
    my_squad(call.message)

@bot.callback_query_handler(func=lambda call: call.data == "sq_back")
def squad_back_inline(call):
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except: pass
    call.message.from_user = call.from_user
    my_squad(call.message)

# --- [6] МЕНЮ МАТЧЕЙ И РЕЖИМЫ ---

def check_match_limits(uid):
    """Сброс и проверка дневных лимитов (7 матчей в день)"""
    users = load_db('users')
    if uid not in users: return True, 0
    
    user = users[uid]
    now = time.time()
    
    # Если прошло больше суток (86400 сек) с момента последнего сброса — обновляем лимит
    if now - user.get('last_match_reset', 0) > 86400:
        user['matches_played'] = 0
        user['last_match_reset'] = now
        save_db(users, 'users')
        
    played = user.get('matches_played', 0)
    if played >= 7:
        return False, played
    return True, played

def get_match_menu_kb():
    markup = types.InlineKeyboardMarkup()
    markup.row(types.InlineKeyboardButton(f"🚀 Турбо ({len(pvp_queue)} ищет)", callback_data="match_start_turbo"))
    markup.row(types.InlineKeyboardButton("⏱ Долгий матч (45 сек) (0 ищет)", callback_data="match_start_long45"))
    markup.row(types.InlineKeyboardButton(f"⏳ Долгий матч (5 мин) ({len(pvp_queue)} ищет)", callback_data="match_start_pvp"))
    markup.row(types.InlineKeyboardButton("⬅️ В меню", callback_data="match_to_menu"))
    return markup

@bot.message_handler(func=lambda m: m.text == "⚔️ Матч")
def match_menu(m):
    uid = str(m.from_user.id)
    _, count = get_squad_rating(uid)
    
    if count < 7:
        return bot.send_message(m.chat.id, "❌ Чтобы играть в матчи, ваш состав должен быть полностью заполнен (7 игроков)!")

    can_play, played_count = check_match_limits(uid)
    
    text = (
        f"⚔️ **ВЫБЕРИТЕ РЕЖИМ МАТЧА** ⚔️\n\n"
        f"📊 **Ежедневный лимит:** `{played_count}/7`\n"
        f" — — — — — — — — — — — — — — —\n\n"
        f"🚀 **Турбо-матч (Авторасчет):** Быстрый матч без выборов. Кулдаун: 30 мин.\n"
        f"⏱ **Долгий матч (45 сек):** 10 моментов, тактика и шансы. Кулдаун: 5 мин.\n"
        f"⏳ **Долгий матч (5 мин):** Тот же H2H, но бот ищет оппонента до 5 мин и пингует в чат при нахождении!"
    )
    
    try:
        with open('465d12ab-8fc3-4bc1-853e-dd4c3a10de12.png', 'rb') as photo:
            bot.send_photo(m.chat.id, photo, caption=text, reply_markup=get_match_menu_kb(), parse_mode="Markdown")
    except FileNotFoundError:
        bot.send_message(m.chat.id, text, reply_markup=get_match_menu_kb(), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("match_"))
def handle_match_callbacks(call):
    uid = str(call.from_user.id)
    action = call.data.replace("match_", "")
    now = time.time()

    if action == "to_menu":
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        return bot.send_message(call.message.chat.id, "Вы вернулись в главное меню.", reply_markup=main_kb(call.from_user))

    # Проверка общего лимита на игры
    can_play, _ = check_match_limits(uid)
    if not can_play and not is_admin_user(call.from_user):
        return bot.answer_callback_query(call.id, "❌ Вы исчерпали лимит матчей на сегодня (7/7)!", show_alert=True)

    # 1. РЕЖИМ: ТУРБО-МАТЧ (Авторасчет)
    if action == "start_turbo":
        kd_key = f"{uid}_turbo"
        if kd_key in match_cooldowns and now - match_cooldowns[kd_key] < 1800 and not is_admin_user(call.from_user):
            remains = int(1800 - (now - match_cooldowns[kd_key]))
            return bot.answer_callback_query(call.id, f"⏳ Кулдаун! Подождите {remains // 60} мин.", show_alert=True)
        
        match_cooldowns[kd_key] = now
        bot.answer_callback_query(call.id, "Запуск Турбо-матча...")
        
        # Симулируем расчет против бота
        my_ovr, _ = get_squad_rating(uid)
        bot_ovr = random.randint(min(60, my_ovr - 5), my_ovr + 8)
        
        # Расчет шансов на основе разницы OVR
        my_goals = random.choices([0, 1, 2, 3, 4, 5], weights=[15, 25, 30, 18, 9, 3] if my_ovr >= bot_ovr else [30, 30, 20, 12, 6, 2])[0]
        bot_goals = random.choices([0, 1, 2, 3, 4, 5], weights=[30, 30, 20, 12, 6, 2] if my_ovr >= bot_ovr else [15, 25, 30, 18, 9, 3])[0]
        
        users = load_db('users')
        users[uid]['matches_played'] = users[uid].get('matches_played', 0) + 1
        
        if my_goals > bot_goals:
            res_text = "🎉 **ПОБЕДА!** Получено +1,500 очков."
            users[uid]['score'] += 1500
        elif my_goals == bot_goals:
            res_text = "🤝 **НИЧЬЯ!** Получено +500 очков."
            users[uid]['score'] += 500
        else:
            res_text = "📉 **ПОРАЖЕНИЕ.** Очки не начислены."
        
        save_db(users, 'users')
        
        result_msg = (
            f"🚀 **РЕЗУЛЬТАТ ТУРБО-МАТЧА**\n\n"
            f"👥 Твоя команда (OVR {my_ovr // 7})  *{my_goals}* : *{bot_goals}* Бот-Оппонент (OVR {bot_ovr // 7})\n\n"
            f"{res_text}"
        )
        bot.edit_message_caption(result_msg, call.message.chat.id, call.message.message_id, reply_markup=get_match_menu_kb(), parse_mode="Markdown")

    # 2. РЕЖИМ: ДОЛГИЙ МАТЧ (45 секунд текстовой трансляции)
    elif action == "start_long45":
        kd_key = f"{uid}_long45"
        if kd_key in match_cooldowns and now - match_cooldowns[kd_key] < 300 and not is_admin_user(call.from_user):
            remains = int(300 - (now - match_cooldowns[kd_key]))
            return bot.answer_callback_query(call.id, f"⏳ Кулдаун! Подождите {remains} сек.", show_alert=True)
            
        match_cooldowns[kd_key] = now
        bot.answer_callback_query(call.id, "Матч начинается!")
        
        my_ovr, _ = get_squad_rating(uid)
        bot_ovr = random.randint(max(50, my_ovr - 10), my_ovr + 10)
        
        my_score = 0
        bot_score = 0
        
        # Симулируем 10 опасных моментов пошагово
        for minute in range(9, 91, 9):
            attacker = "Вы" if random.randint(0, my_ovr + bot_ovr) <= my_ovr else "Бот"
            event = random.choice(MATCH_EVENTS).format(attacker="Ваша команда" if attacker == "Вы" else "Команда Бота")
            
            is_goal = random.random() < (0.35 if attacker == "Вы" else 0.28)
            if is_goal:
                event += " ⚽️ **ГОООЛ!**"
                if attacker == "Вы": my_score += 1
                else: bot_score += 1
            else:
                event += " ❌ Мимо ворот!"
                
            step_text = (
                f"⏱ **Долгий матч: {minute}' минута**\n"
                f"📊 Счет: *{my_score}* : *{bot_score}*\n\n"
                f"{event}"
            )
            try:
                bot.edit_message_caption(step_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            except: pass
            time.sleep(3) # задержка между моментами матча
            
        users = load_db('users')
        users[uid]['matches_played'] = users[uid].get('matches_played', 0) + 1
        
        if my_score > bot_score:
            res_text = "🏆 **Финальный свисток! Вы победили!** (+2,500 очков)"
            users[uid]['score'] += 2500
        elif my_score == bot_score:
            res_text = "🤝 **Боевая ничья!** (+1,000 очков)"
            users[uid]['score'] += 1000
        else:
            res_text = "😢 **Поражение в упорной борьбе.** (+0 очков)"
            
        save_db(users, 'users')
        
        final_text = (
            f"🏁 **МАТЧ ЗАВЕРШЕН!**\n"
            f"📊 Финальный счет: *{my_score}* : *{bot_score}*\n\n"
            f"{res_text}"
        )
        bot.send_message(call.message.chat.id, final_text, reply_markup=main_kb(call.from_user), parse_mode="Markdown")

    # 3. РЕЖИМ: ДОЛГИЙ МАТЧ (PVP Поиск 5 минут)
    elif action == "start_pvp":
        if uid in pvp_queue:
            return bot.answer_callback_query(call.id, "🔎 Вы уже находитесь в поиске соперника!", show_alert=True)
            
        bot.answer_callback_query(call.id, "Встаем в очередь поиска...")
        pvp_queue.append(uid)
        
        # Обновляем плашку поиска для текущего юзера
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=get_match_menu_kb())
        except: pass
        
        # Проверяем, набралась ли пара
        if len(pvp_queue) >= 2:
            p1 = pvp_queue.pop(0)
            p2 = pvp_queue.pop(0)
            
            users = load_db('users')
            u1_name = users.get(p1, {}).get('username', f"id_{p1}")
            u2_name = users.get(p2, {}).get('username', f"id_{p2}")
            
            # Уведомляем обоих игроков в личные сообщения о нахождении игры
            match_found_text = f"🥅 **Соперник найден!**\n\n🟢 @{u1_name}  *VS* 🔴 @{u2_name}\n\nМатч симулируется..."
            bot.send_message(p1, match_found_text, parse_mode="Markdown")
            bot.send_message(p2, match_found_text, parse_mode="Markdown")
            
            ovr1, _ = get_squad_rating(p1)
            ovr2, _ = get_squad_rating(p2)
            
            # Итоговый счет матча
            g1 = random.choices([0,1,2,3,4], weights=[20,35,25,15,5] if ovr1 >= ovr2 else [35,30,20,10,5])[0]
            g2 = random.choices([0,1,2,3,4], weights=[35,30,20,10,5] if ovr1 >= ovr2 else [20,35,25,15,5])[0]
            
            users[p1]['matches_played'] = users[p1].get('matches_played', 0) + 1
            users[p2]['matches_played'] = users[p2].get('matches_played', 0) + 1
            
            if g1 > g2:
                users[p1]['score'] += 3500
                res_p1, res_p2 = "🎉 **Победа! (+3,500 очков)**", "📉 Поражение. (0 очков)"
            elif g1 == g2:
                users[p1]['score'] += 1500
                users[p2]['score'] += 1500
                res_p1 = res_p2 = "🤝 **Ничья! (+1,500 очков)**"
            else:
                users[p2]['score'] += 3500
                res_p1, res_p2 = "📉 Поражение. (0 очков)", "🎉 **Победа! (+3,500 очков)**"
                
            save_db(users, 'users')
            
            bot.send_message(p1, f"🏁 **Итог PVP-Матча:**\nВы *{g1}* : *{g2}* @{u2_name}\n\n{res_p1}", parse_mode="Markdown")
            bot.send_message(p2, f"🏁 **Итог PVP-Матча:**\nВы *{g2}* : *{g1}* @{u1_name}\n\n{res_p2}", parse_mode="Markdown")

# --- [7] ОСТАЛЬНЫЕ КОМАНДЫ БОТА ---

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
    if not my_cards: return bot.send_message(m.chat.id, "🗂 Ваша коллекция пока пуста!")
    
    text = f"🗂 **ВАША КОЛЛЕКЦИЯ ({len(my_cards)} шт.):**\n\n"
    for card in my_cards:
        text += f"• {card['name']} | ПОЗ: `{card.get('pos', '—')}` | OVR: {card.get('ovr', '—')} ({get_stars(card.get('stars', 1))})\n"
    bot.send_message(m.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):
    uid = str(m.from_user.id)
    u = load_db('users').get(uid, {"score": 0, "username": m.from_user.username or f"user_{uid}"})
    c = len(load_db('colls').get(uid, []))
    text = (
        f"👤 **ВАШ ПРОФИЛЬ**\n — — — — — — — —\n"
        f"🆔 ID: `{uid}`\n"
        f"💠 Очки: `{u['score']:,}`\n"
        f"🗂 Коллекция: {c} шт.\n — — — — — — — —"
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

# --- Пошаговое добавление карты ---
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
    msg = bot.send_message(m.chat.id, f"3️⃣ Введите НАЗВАНИЕ СОБЫТИЯ (например: TOTY 25/26):")
    bot.register_next_step_handler(msg, add_step_pos, name, ovr)

def add_step_pos(m, name, ovr):
    event = m.text
    msg = bot.send_message(m.chat.id, f"4️⃣ Введите ОСНОВНУЮ ПОЗИЦИЮ (строго как в схеме: LF, CF, RF, CM, LB, RB, GK):")
    bot.register_next_step_handler(msg, add_step_rarity, name, ovr, event)

def add_step_rarity(m, name, ovr, event):
    pos = m.text.strip().upper()
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
    if not m.photo: return bot.send_message(m.chat.id, "❌ Ошибка! Фото не отправлено.")
    
    cards = load_db('cards')
    cards.append({
        "name": name, "ovr": ovr, "event": event, "pos": pos, "rarity": rarity,
        "stars": int(stars) if stars.isdigit() else 1, "photo": m.photo[-1].file_id
    })
    save_db(cards, 'cards')
    bot.send_message(m.chat.id, f"✅ Карта *{name}* успешно создана!", reply_markup=main_kb(m.from_user), parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🏠 Назад в меню")
def back(m): bot.send_message(m.chat.id, "Главное меню:", reply_markup=main_kb(m.from_user))

if __name__ == '__main__':
    print("Бот запущен и готов к работе!")
    bot.infinity_polling()
