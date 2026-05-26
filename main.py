import telebot
from telebot import types
import random
import time
import json
import os
import threading

# =========================
# КОНФИГ
# =========================

TOKEN = "TOKEN_HERE"

ADMINS = [
    "1674945230",
    "7908057052"
]

bot = telebot.TeleBot(TOKEN)

COOLDOWN_TIME = 5400

FILES = {
    "cards": "cards_data.json",
    "colls": "collections_data.json",
    "users": "users_stats.json",
    "squads": "squads_data.json"
}

STATS = {
    1: {"score": 1000},
    2: {"score": 2000},
    3: {"score": 4000},
    4: {"score": 6000},
    5: {"score": 10000}
}

SQUAD_POSITIONS = [
    "LF",
    "CF",
    "RF",
    "CM",
    "LB",
    "RB",
    "GK"
]

last_roll = {}
match_cooldowns = {}
pvp_queue = []

BOT_TEAMS = [
    "🤖 Cyber FC",
    "🦾 Робот Юнайтед",
    "🧠 ИИ Сити",
    "⚡️ Нейро Атлетик",
    "👾 Пиксель ФК",
    "🛰 Спутник Спартак",
    "💻 Матрица Сити",
    "⚙️ ФК Вортекс"
]

BOT_TACTICS = [
    "🚌 Автобус 4-3",
    "⚔️ Атака 3-4",
    "⚖️ Баланс 3-3"
]

# =========================
# БАЗА ДАННЫХ
# =========================

def load_db(key):

    if not os.path.exists(FILES[key]):

        result = {}

        if key == "cards":
            result = []

        save_db(result, key)

        return result

    with open(FILES[key], "r", encoding="utf-8") as f:

        try:
            return json.load(f)

        except:
            return {} if key != "cards" else []


def save_db(data, key):

    with open(FILES[key], "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=4
        )


def is_admin(user):

    return str(user.id) in ADMINS


def get_stars(count):

    try:
        return "⭐" * int(count)

    except:
        return "⭐"


def get_squad_rating(uid):

    squads = load_db("squads")

    squad = squads.get(uid, {})

    total = 0
    count = 0

    for pos in SQUAD_POSITIONS:

        if squad.get(pos):

            try:
                total += int(squad[pos]["ovr"])
                count += 1

            except:
                pass

    return total, count


# =========================
# КЛАВИАТУРА
# =========================

def main_kb(user):

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row(
        "Получить карту",
        "🗂 Коллекция"
    )

    markup.row(
        "⚽️ Мой состав",
        "⚔️ Матч"
    )

    markup.row(
        "👤 Профиль",
        "🏆 Топ игроков"
    )

    markup.row(
        "💎 Премиум"
    )

    if is_admin(user):
        markup.row("🛠 Админ-панель")

    return markup


# =========================
# START
# =========================

@bot.message_handler(commands=["start"])
def start(m):

    uid = str(m.from_user.id)

    users = load_db("users")

    if uid not in users:

        users[uid] = {
            "score": 0,
            "username": m.from_user.username or f"user_{uid}",
            "matches_played": 0,
            "last_match_reset": time.time()
        }

        save_db(users, "users")

    bot.send_message(
        m.chat.id,
        "👋 Добро пожаловать в карточный футбольный бот!",
        reply_markup=main_kb(m.from_user)
    )


# =========================
# ПОЛУЧИТЬ КАРТУ
# =========================

@bot.message_handler(func=lambda m: m.text == "Получить карту")
def roll_card(m):

    uid = str(m.from_user.id)

    if not is_admin(m.from_user):

        now = time.time()

        if uid in last_roll:

            if now - last_roll[uid] < COOLDOWN_TIME:

                remains = int(
                    COOLDOWN_TIME - (
                        now - last_roll[uid]
                    )
                )

                return bot.send_message(
                    m.chat.id,
                    f"⏳ Подождите {remains // 60} мин."
                )

    cards = load_db("cards")

    if not cards:
        return bot.send_message(
            m.chat.id,
            "❌ Карточек нет."
        )

    won = random.choice(cards)

    users = load_db("users")
    colls = load_db("colls")

    if uid not in colls:
        colls[uid] = []

    is_new = not any(
        c["name"] == won["name"]
        for c in colls[uid]
    )

    if is_new:

        colls[uid].append(won)

        save_db(colls, "colls")

    points = STATS.get(
        int(won.get("stars", 1)),
        {"score": 500}
    )["score"]

    users[uid]["score"] += points

    save_db(users, "users")

    last_roll[uid] = time.time()

    text = (
        f"⚽️ {won['name']}\n"
        f"📊 OVR: {won.get('ovr', '—')}\n"
        f"⚽️ POS: {won.get('pos', '—')}\n"
        f"✨ RARITY: {won.get('rarity', '—')}\n"
        f"{get_stars(won.get('stars', 1))}\n\n"
        f"+{points} очков"
    )

    bot.send_photo(
        m.chat.id,
        won["photo"],
        caption=text
    )


# =========================
# КОЛЛЕКЦИЯ
# =========================

@bot.message_handler(func=lambda m: m.text == "🗂 Коллекция")
def collection(m):

    uid = str(m.from_user.id)

    cards = load_db("colls").get(uid, [])

    if not cards:

        return bot.send_message(
            m.chat.id,
            "❌ Коллекция пуста."
        )

    text = "🗂 Ваша коллекция:\n\n"

    for card in cards:

        text += (
            f"• {card['name']} | "
            f"{card.get('pos', '—')} | "
            f"OVR {card.get('ovr', '—')}\n"
        )

    bot.send_message(
        m.chat.id,
        text
    )


# =========================
# ПРОФИЛЬ
# =========================

@bot.message_handler(func=lambda m: m.text == "👤 Профиль")
def profile(m):

    uid = str(m.from_user.id)

    users = load_db("users")

    user = users.get(uid)

    cards = len(
        load_db("colls").get(uid, [])
    )

    text = (
        f"👤 Профиль\n\n"
        f"🆔 ID: {uid}\n"
        f"💠 Очки: {user['score']}\n"
        f"🗂 Карточек: {cards}"
    )

    bot.send_message(
        m.chat.id,
        text
    )


# =========================
# ТОП ИГРОКОВ
# =========================

@bot.message_handler(func=lambda m: m.text == "🏆 Топ игроков")
def top_players(m):

    users = load_db("users")

    sorted_users = sorted(
        users.items(),
        key=lambda x: x[1]["score"],
        reverse=True
    )

    text = "🏆 ТОП ИГРОКОВ\n\n"

    for i, (uid, data) in enumerate(
        sorted_users[:10],
        1
    ):

        text += (
            f"{i}. "
            f"@{data['username']} — "
            f"{data['score']}\n"
        )

    bot.send_message(
        m.chat.id,
        text
    )


# =========================
# ПРЕМИУМ
# =========================

@bot.message_handler(func=lambda m: m.text == "💎 Премиум")
def premium(m):

    bot.send_message(
        m.chat.id,
        "💎 Премиум\n\nПисать: @admin"
    )


# =========================
# МОЙ СОСТАВ
# =========================

def get_user_squad(uid):

    squads = load_db("squads")

    if uid not in squads:

        squads[uid] = {
            pos: None
            for pos in SQUAD_POSITIONS
        }

        save_db(squads, "squads")

    return squads[uid]


@bot.message_handler(func=lambda m: m.text == "⚽️ Мой состав")
def my_squad(m):

    uid = str(m.from_user.id)

    squad = get_user_squad(uid)

    total, count = get_squad_rating(uid)

    avg = round(total / count, 1) if count > 0 else 0

    text = (
        f"⚽️ СОСТАВ\n\n"
        f"📊 Средний OVR: {avg}\n\n"
    )

    for pos in SQUAD_POSITIONS:

        player = squad.get(pos)

        if player:

            text += (
                f"{pos} — "
                f"{player['name']} "
                f"({player['ovr']})\n"
            )

        else:

            text += f"{pos} — Пусто\n"

    bot.send_message(
        m.chat.id,
        text
    )


# =========================
# АДМИНКА
# =========================

@bot.message_handler(func=lambda m: m.text == "🛠 Админ-панель")
def admin_panel(m):

    if not is_admin(m.from_user):
        return

    markup = types.ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    markup.row("➕ Добавить карту")
    markup.row("🏠 Назад")

    bot.send_message(
        m.chat.id,
        "🛠 Админ-панель",
        reply_markup=markup
    )


# =========================
# ДОБАВЛЕНИЕ КАРТ
# =========================

@bot.message_handler(func=lambda m: m.text == "➕ Добавить карту")
def add_card_start(m):

    if not is_admin(m.from_user):
        return

    msg = bot.send_message(
        m.chat.id,
        "Введите имя игрока:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_ovr
    )


def add_card_ovr(m):

    name = m.text

    msg = bot.send_message(
        m.chat.id,
        "Введите OVR:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_pos,
        name
    )


def add_card_pos(m, name):

    ovr = m.text

    msg = bot.send_message(
        m.chat.id,
        "Введите позицию:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_rarity,
        name,
        ovr
    )


def add_card_rarity(m, name, ovr):

    pos = m.text

    msg = bot.send_message(
        m.chat.id,
        "Введите редкость:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_stars,
        name,
        ovr,
        pos
    )


def add_card_stars(m, name, ovr, pos):

    rarity = m.text

    msg = bot.send_message(
        m.chat.id,
        "Введите звезды:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_photo,
        name,
        ovr,
        pos,
        rarity
    )


def add_card_photo(m, name, ovr, pos, rarity):

    stars = m.text

    msg = bot.send_message(
        m.chat.id,
        "Отправьте фото:"
    )

    bot.register_next_step_handler(
        msg,
        add_card_finish,
        name,
        ovr,
        pos,
        rarity,
        stars
    )


def add_card_finish(
    m,
    name,
    ovr,
    pos,
    rarity,
    stars
):

    if not m.photo:

        return bot.send_message(
            m.chat.id,
            "❌ Фото не найдено."
        )

    cards = load_db("cards")

    cards.append({
        "name": name,
        "ovr": ovr,
        "pos": pos,
        "rarity": rarity,
        "stars": int(stars),
        "photo": m.photo[-1].file_id
    })

    save_db(cards, "cards")

    bot.send_message(
        m.chat.id,
        f"✅ Карта {name} добавлена!"
    )


# =========================
# НАЗАД
# =========================

@bot.message_handler(func=lambda m: m.text == "🏠 Назад")
def back(m):

    bot.send_message(
        m.chat.id,
        "Главное меню",
        reply_markup=main_kb(m.from_user)
    )


# =========================
# ЗАПУСК
# =========================

if __name__ == "__main__":

    print("Бот запущен!")

    bot.infinity_polling()
