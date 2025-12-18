# main_with_auto_cleanup.py
# Telegram бот для управления совещаниями (версия с автоматическим удалением старых совещаний)

import telebot
from telebot import types
import logging
from datetime import datetime
import json
import threading
import time

from config import USERS_DB, CREATORS, MEETING_TIMES, MEETING_DURATIONS
from database import db
from auto_cleanup import cleanup
from utils import (
    get_next_workdays, get_available_times, format_duration,
    get_end_time, format_participants_list
)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Токен бота (ВАШ ТОКЕН ЗДЕСЬ)
TELEGRAM_TOKEN = "7263661310:AAFXxJ0qeifSOJA9PM0MI4H81efQ2LoLxrI"

# Инициализация бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Хранилище временных данных пользователя
user_data = {}


# ======================== КОМАНДЫ ========================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id

    # Проверяем, не в сессии ли пользователь
    if db.get_user_session(user_id):
        bot.reply_to(message, "❌ Вы уже в сессии! Используйте /logout для выхода.")
        return

    # Создаем клавиатуру с пользователями
    markup = create_users_keyboard()
    bot.send_message(user_id, "👋 Добро пожаловать! Выберите своё имя и фамилию:", reply_markup=markup)

    # Сохраняем состояние
    user_data[user_id] = {"state": "choosing_user"}


@bot.message_handler(commands=['help'])
def cmd_help(message):
    """Обработчик команды /help"""
    bot.send_message(
        message.from_user.id,
        "📖 Справка по командам:\n\n"
        "/start - Начало работы\n"
        "/logout - Выход из аккаунта\n"
        "/help - Показать эту справку\n\n"
        "Используйте кнопки меню для навигации."
    )


@bot.message_handler(commands=['logout'])
def cmd_logout(message):
    """Обработчик команды /logout"""
    user_id = message.from_user.id
    db.remove_user_session(user_id)
    user_data.pop(user_id, None)
    bot.send_message(user_id, "👋 Вы вышли из аккаунта.")


# ======================== КЛАВИАТУРЫ ========================

def create_users_keyboard():
    """Создать клавиатуру со списком пользователей"""
    markup = types.InlineKeyboardMarkup()
    users = list(USERS_DB.keys())

    for user in users:
        button = types.InlineKeyboardButton(text=user, callback_data=f"user:{user}")
        markup.add(button)

    return markup


def create_main_menu_keyboard(is_creator):
    """Создать главное меню"""
    markup = types.InlineKeyboardMarkup()

    if is_creator:
        markup.add(types.InlineKeyboardButton(text="➕ Новое совещание", callback_data="new_meeting"))
        markup.add(types.InlineKeyboardButton(text="📋 Созданные мной", callback_data="my_meetings"))
        markup.add(types.InlineKeyboardButton(text="📅 Календарь совещаний", callback_data="calendar"))
        markup.add(types.InlineKeyboardButton(text="🗑️ Удалить старые", callback_data="delete_old_meetings"))
    else:
        markup.add(types.InlineKeyboardButton(text="📋 Мои совещания", callback_data="guest_meetings"))
        markup.add(types.InlineKeyboardButton(text="📅 Календарь совещаний", callback_data="guest_calendar"))

    markup.add(types.InlineKeyboardButton(text="🚪 Выход", callback_data="logout"))
    return markup


def create_dates_keyboard():
    """Создать клавиатуру с датами"""
    markup = types.InlineKeyboardMarkup()
    workdays = get_next_workdays()

    for _, date_str in workdays:
        button = types.InlineKeyboardButton(text=date_str, callback_data=f"date:{date_str}")
        markup.add(button)

    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_menu"))
    return markup


def create_times_keyboard(date_str):
    """Создать клавиатуру со временем"""
    markup = types.InlineKeyboardMarkup()

    # Если дата сегодня, фильтруем время
    today = datetime.now().strftime("%d.%m")
    if date_str == today:
        times = get_available_times()
    else:
        times = MEETING_TIMES

    for time_slot in times:
        button = types.InlineKeyboardButton(text=time_slot, callback_data=f"time:{time_slot}")
        markup.add(button)

    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_dates"))
    return markup


def create_durations_keyboard():
    """Создать клавиатуру с продолжительностью"""
    markup = types.InlineKeyboardMarkup()

    for duration in MEETING_DURATIONS:
        formatted = format_duration(duration)
        button = types.InlineKeyboardButton(text=formatted, callback_data=f"duration:{duration}")
        markup.add(button)

    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_times"))
    return markup


def create_participants_keyboard(creator_username):
    """Создать клавиатуру с участниками"""
    markup = types.InlineKeyboardMarkup()
    participants = [user for user in USERS_DB.keys() if user != creator_username]

    for participant in sorted(participants):
        button = types.InlineKeyboardButton(text=participant, callback_data=f"participant:{participant}")
        markup.add(button)

    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_durations"))
    return markup


def create_confirm_participants_keyboard():
    """Создать клавиатуру подтверждения участников"""
    markup = types.InlineKeyboardMarkup()

    markup.add(types.InlineKeyboardButton(text="✅ Состав сформирован", callback_data="confirm_participants"))
    markup.add(types.InlineKeyboardButton(text="➕ Добавить еще", callback_data="add_more_participants"))
    markup.add(types.InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_participants"))

    return markup


def create_back_button():
    """Создать кнопку назад в главное меню"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu"))
    return markup


def create_delete_meetings_keyboard(past_meetings):
    """Создать клавиатуру для удаления совещаний"""
    markup = types.InlineKeyboardMarkup()

    if not past_meetings:
        markup.add(types.InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu"))
        return markup

    for meeting in past_meetings:
        meeting_id = meeting[0]
        date_str = meeting[2]
        start_time = meeting[3]
        end_time = get_end_time(start_time, meeting[4])

        button_text = f"🗑️ {date_str} {start_time}-{end_time}"
        button = types.InlineKeyboardButton(text=button_text, callback_data=f"delete_meeting:{meeting_id}")
        markup.add(button)

    markup.add(types.InlineKeyboardButton(text="◀️ Назад в меню", callback_data="back_to_menu"))
    return markup


def create_delete_confirmation_keyboard(meeting_id):
    """Создать клавиатуру подтверждения удаления"""
    markup = types.InlineKeyboardMarkup()

    markup.add(types.InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete:{meeting_id}"))
    markup.add(types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_delete"))

    return markup


# ======================== ОБРАБОТЧИКИ CALLBACK ========================

@bot.callback_query_handler(func=lambda call: call.data.startswith("user:"))
def process_user_choice(call):
    """Обработчик выбора пользователя"""
    user_id = call.from_user.id
    username = call.data.split(":", 1)[1]

    bot.edit_message_text(
        f"Вы выбрали: {username}\n\nВведите пароль:",
        call.message.chat.id,
        call.message.message_id
    )

    user_data[user_id] = {"username": username, "state": "entering_password"}
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda message: user_data.get(message.from_user.id, {}).get("state") == "entering_password")
def process_password(message):
    """Обработчик ввода пароля"""
    user_id = message.from_user.id
    password = message.text

    if user_id not in user_data:
        bot.send_message(user_id, "❌ Ошибка: пожалуйста, начните сначала. /start")
        return

    username = user_data[user_id]["username"]

    # Проверяем пароль
    if USERS_DB.get(username) != password:
        bot.send_message(user_id, "❌ Неверный пароль! Попробуйте еще раз:")
        return

    # Добавляем пользователя в сессию
    if not db.add_user_session(user_id, username):
        bot.send_message(user_id, "❌ Ошибка: вы уже в сессии в другом месте!")
        return

    bot.send_message(user_id, "✅ Идентификация успешна!")

    # Определяем, создатель ли это
    is_creator = username in CREATORS

    # Показываем главное меню
    markup = create_main_menu_keyboard(is_creator)
    bot.send_message(user_id, f"👋 Добро пожаловать, {username}!\n\nВыберите действие:", reply_markup=markup)

    user_data[user_id]["state"] = "main_menu"


@bot.callback_query_handler(func=lambda call: call.data == "new_meeting")
def process_new_meeting(call):
    """Обработчик создания нового совещания"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    if not username:
        bot.answer_callback_query(call.id, "❌ Сессия истекла", show_alert=True)
        return

    if username not in CREATORS:
        bot.answer_callback_query(call.id, "❌ У вас нет прав создавать совещания", show_alert=True)
        return

    # Инициализируем данные совещания
    if user_id not in user_data:
        user_data[user_id] = {}

    user_data[user_id]["meeting"] = {
        "creator": username,
        "participants": []
    }

    markup = create_dates_keyboard()
    bot.edit_message_text("📅 Выберите дату:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("date:"))
def process_meeting_date(call):
    """Обработчик выбора даты совещания"""
    user_id = call.from_user.id
    date_str = call.data.split(":", 1)[1]

    if user_id not in user_data or "meeting" not in user_data[user_id]:
        user_data[user_id] = {"meeting": {}}

    user_data[user_id]["meeting"]["date"] = date_str

    markup = create_times_keyboard(date_str)
    bot.edit_message_text(f"🕐 Выберите время (дата: {date_str}):", call.message.chat.id, call.message.message_id,
                          reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("time:"))
def process_meeting_time(call):
    """Обработчик выбора времени совещания"""
    user_id = call.from_user.id
    time_str = call.data.split(":", 1)[1]

    user_data[user_id]["meeting"]["time"] = time_str

    markup = create_durations_keyboard()
    bot.edit_message_text(f"⏱️ Выберите продолжительность (время: {time_str}):", call.message.chat.id,
                          call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("duration:"))
def process_meeting_duration(call):
    """Обработчик выбора продолжительности совещания"""
    user_id = call.from_user.id
    duration = int(call.data.split(":", 1)[1])

    user_data[user_id]["meeting"]["duration"] = duration

    username = db.get_user_session(user_id)

    markup = create_participants_keyboard(username)
    bot.edit_message_text(f"👥 Выберите участников (продолжительность: {format_duration(duration)}):",
                          call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("participant:"))
def process_add_participant(call):
    """Обработчик добавления участника"""
    user_id = call.from_user.id
    participant = call.data.split(":", 1)[1]

    meeting = user_data[user_id]["meeting"]

    # Проверяем, свободен ли участник
    if not db.check_user_availability(participant, meeting["date"], meeting["time"], meeting["duration"]):
        bot.answer_callback_query(call.id, f"❌ {participant} занят в это время!", show_alert=True)
        return

    # Добавляем или удаляем участника
    if participant not in meeting["participants"]:
        meeting["participants"].append(participant)
        bot.answer_callback_query(call.id, f"✅ {participant} добавлен")
    else:
        meeting["participants"].remove(participant)
        bot.answer_callback_query(call.id, f"❌ {participant} удален")

    # Показываем список добавленных участников
    participants_list = "\n".join([f"• {p}" for p in meeting["participants"]]) if meeting["participants"] else "нет"

    markup = create_confirm_participants_keyboard()
    bot.edit_message_text(
        f"Добавленные участники:\n{participants_list}\n\nДобавить еще?",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )


@bot.callback_query_handler(func=lambda call: call.data == "confirm_participants")
def process_confirm_participants(call):
    """Обработчик подтверждения состава участников"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    meeting = user_data[user_id]["meeting"]

    # Сохраняем совещание в БД
    meeting_id = db.add_meeting(
        creator_username=meeting["creator"],
        date=meeting["date"],
        start_time=meeting["time"],
        duration_minutes=meeting["duration"],
        participants=meeting["participants"]
    )

    # Отправляем уведомления участникам
    end_time = get_end_time(meeting["time"], meeting["duration"])

    for participant in meeting["participants"]:
        db.add_notification(meeting_id, participant)

    bot.edit_message_text(
        "✅ Совещание успешно создано!\n\n"
        f"Дата: {meeting['date']}\n"
        f"Время: {meeting['time']} - {end_time}\n"
        f"Участники: {', '.join(meeting['participants']) if meeting['participants'] else 'без участников'}\n\n"
        "Участникам отправлены уведомления.",
        call.message.chat.id,
        call.message.message_id
    )

    # Возвращаемся в главное меню
    is_creator = username in CREATORS
    markup = create_main_menu_keyboard(is_creator)
    bot.send_message(user_id, "Выберите действие:", reply_markup=markup)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "add_more_participants")
def process_add_more(call):
    """Обработчик кнопки добавить еще участников"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    markup = create_participants_keyboard(username)
    bot.edit_message_text("👥 Выберите участников:", call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "my_meetings")
def process_my_meetings(call):
    """Обработчик просмотра своих совещаний"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    if not username:
        bot.answer_callback_query(call.id, "❌ Сессия истекла", show_alert=True)
        return

    meetings = db.get_meetings_by_creator(username)
    workdays = get_next_workdays()
    workday_dates = {date_str: None for _, date_str in workdays}

    # Группируем совещания по датам
    for meeting in meetings:
        date_str = meeting[2]
        if date_str in workday_dates:
            if workday_dates[date_str] is None:
                workday_dates[date_str] = []
            workday_dates[date_str].append(meeting)

    # Формируем ответ
    response = "📋 Созданные вами совещания:\n\n"

    for date_str in workday_dates:
        if workday_dates[date_str] is None:
            response += f"📅 {date_str} - у Вас нет совещаний\n\n"
        elif len(workday_dates[date_str]) == 1:
            meeting = workday_dates[date_str][0]
            end_time = get_end_time(meeting[3], meeting[4])
            participants = json.loads(meeting[5])
            response += (
                f"📅 {date_str} - у Вас совещание с {meeting[3]} по {end_time}, "
                f"участники: {', '.join(participants)}\n\n"
            )
        else:
            response += f"📅 {date_str} - у Вас {len(workday_dates[date_str])} совещаний в этот день:\n"
            for meeting in workday_dates[date_str]:
                end_time = get_end_time(meeting[3], meeting[4])
                participants = json.loads(meeting[5])
                response += f"    с {meeting[3]} по {end_time}, участники: {', '.join(participants)}\n"
            response += "\n"

    markup = create_back_button()
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "calendar")
def process_calendar(call):
    """Обработчик просмотра календаря совещаний"""
    user_id = call.from_user.id

    all_meetings = db.get_all_meetings()
    workdays = get_next_workdays()
    workday_dates = {date_str: {} for _, date_str in workdays}

    # Группируем совещания по датам и создателям
    for meeting in all_meetings:
        date_str = meeting[2]
        if date_str in workday_dates:
            creator = meeting[1]
            if creator not in workday_dates[date_str]:
                workday_dates[date_str][creator] = []
            workday_dates[date_str][creator].append(meeting)

    # Формируем ответ
    response = "📅 Календарь совещаний:\n\n"

    for date_str in workday_dates:
        if not workday_dates[date_str]:
            response += f"{date_str} - в этот день ни у кого нет совещаний\n\n"
        elif len(workday_dates[date_str]) == 1:
            creator = list(workday_dates[date_str].keys())[0]
            meetings = workday_dates[date_str][creator]
            response += f"{date_str} - в этот день у {creator} {len(meetings)} {'совещание' if len(meetings) == 1 else 'совещаний'}:\n"
            for meeting in meetings:
                end_time = get_end_time(meeting[3], meeting[4])
                participants = json.loads(meeting[5])
                response += f"    с {meeting[3]} по {end_time}. Участники: {', '.join(participants)}\n"
            response += "\n"
        else:
            total_meetings = sum(len(meetings) for meetings in workday_dates[date_str].values())
            response += f"{date_str} - В этот день {total_meetings} совещаний.\n"
            for creator, meetings in workday_dates[date_str].items():
                response += f"    У {creator} {len(meetings)} {'совещание' if len(meetings) == 1 else 'совещаний'}:\n"
                for meeting in meetings:
                    end_time = get_end_time(meeting[3], meeting[4])
                    participants = json.loads(meeting[5])
                    response += f"        с {meeting[3]} по {end_time}. Участники: {', '.join(participants)}\n"
            response += "\n"

    markup = create_back_button()
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "delete_old_meetings")
def process_delete_old_meetings(call):
    """Обработчик просмотра старых совещаний для удаления"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    if not username:
        bot.answer_callback_query(call.id, "❌ Сессия истекла", show_alert=True)
        return

    # Получаем прошедшие совещания
    past_meetings = db.get_past_meetings(username)

    if not past_meetings:
        bot.edit_message_text(
            "✅ У вас нет прошедших совещаний для удаления.\n\n"
            "Все ваши совещания еще впереди!",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=create_back_button()
        )
        bot.answer_callback_query(call.id)
        return

    # Формируем ответ
    response = f"🗑️ Прошедшие совещания ({len(past_meetings)} шт):\n\n"
    response += "Выберите совещание для удаления:\n"

    markup = create_delete_meetings_keyboard(past_meetings)

    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delete_meeting:"))
def process_select_delete_meeting(call):
    """Обработчик выбора совещания для удаления"""
    user_id = call.from_user.id
    meeting_id = int(call.data.split(":", 1)[1])

    # Получаем информацию о совещании
    meeting = db.get_meeting_by_id(meeting_id)

    if not meeting:
        bot.answer_callback_query(call.id, "❌ Совещание не найдено", show_alert=True)
        return

    date_str = meeting[2]
    start_time = meeting[3]
    duration = meeting[4]
    end_time = get_end_time(start_time, duration)
    participants = json.loads(meeting[5])

    response = (
        f"❓ Вы уверены, что хотите удалить это совещание?\n\n"
        f"📅 Дата: {date_str}\n"
        f"🕐 Время: {start_time} - {end_time}\n"
        f"👥 Участники: {', '.join(participants) if participants else 'нет'}\n\n"
        f"⚠️ Это действие нельзя отменить!"
    )

    markup = create_delete_confirmation_keyboard(meeting_id)
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_delete:"))
def process_confirm_delete(call):
    """Обработчик подтверждения удаления"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)
    meeting_id = int(call.data.split(":", 1)[1])

    # Получаем информацию о совещании
    meeting = db.get_meeting_by_id(meeting_id)

    if not meeting:
        bot.answer_callback_query(call.id, "❌ Совещание не найдено", show_alert=True)
        return

    # Проверяем, что это совещание пользователя
    if meeting[1] != username:
        bot.answer_callback_query(call.id, "❌ Это не ваше совещание", show_alert=True)
        return

    # Удаляем совещание из БД
    db.delete_meeting(meeting_id)

    date_str = meeting[2]
    start_time = meeting[3]
    end_time = get_end_time(start_time, meeting[4])

    bot.edit_message_text(
        f"✅ Совещание удалено!\n\n"
        f"📅 {date_str}, {start_time} - {end_time}\n\n"
        f"Совещание удалено из базы данных.",
        call.message.chat.id,
        call.message.message_id
    )

    # Возвращаемся в главное меню
    is_creator = username in CREATORS
    markup = create_main_menu_keyboard(is_creator)
    bot.send_message(user_id, "Выберите действие:", reply_markup=markup)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "cancel_delete")
def process_cancel_delete(call):
    """Обработчик отмены удаления"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    bot.edit_message_text(
        "❌ Удаление отменено.",
        call.message.chat.id,
        call.message.message_id
    )

    # Возвращаемся в главное меню
    is_creator = username in CREATORS
    markup = create_main_menu_keyboard(is_creator)
    bot.send_message(user_id, "Выберите действие:", reply_markup=markup)

    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "guest_meetings")
def process_guest_meetings(call):
    """Обработчик просмотра совещаний для приглашенных"""
    user_id = call.from_user.id
    username = db.get_user_session(user_id)

    if not username:
        bot.answer_callback_query(call.id, "❌ Сессия истекла", show_alert=True)
        return

    meetings = db.get_meetings_by_participant(username)
    workdays = get_next_workdays()
    workday_dates = {date_str: None for _, date_str in workdays}

    # Группируем совещания по датам
    for meeting in meetings:
        date_str = meeting[2]
        if date_str in workday_dates:
            if workday_dates[date_str] is None:
                workday_dates[date_str] = []
            workday_dates[date_str].append(meeting)

    # Формируем ответ
    response = "📋 Ваши совещания:\n\n"

    for date_str in workday_dates:
        if workday_dates[date_str] is None:
            response += f"📅 {date_str} - В этот день у Вас нет совещаний\n\n"
        else:
            response += f"📅 {date_str} - В этот день у Вас {len(workday_dates[date_str])} {'совещание' if len(workday_dates[date_str]) == 1 else 'совещаний'}:\n"
            for meeting in workday_dates[date_str]:
                end_time = get_end_time(meeting[3], meeting[4])
                creator = meeting[1]
                participants = json.loads(meeting[5])
                response += f"    с {meeting[3]} по {end_time} у {creator}. Участники: {', '.join(participants)}\n"
            response += "\n"

    markup = create_back_button()
    bot.edit_message_text(response, call.message.chat.id, call.message.message_id, reply_markup=markup)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "guest_calendar")
def process_guest_calendar(call):
    """Обработчик просмотра полного календаря для приглашенных"""
    # Используем ту же логику что и для создателей
    process_calendar(call)


@bot.callback_query_handler(func=lambda call: call.data == "logout")
def process_logout_button(call):
    """Обработчик кнопки выхода"""
    user_id = call.from_user.id
    db.remove_user_session(user_id)
    user_data.pop(user_id, None)

    bot.edit_message_text("👋 Вы вышли из аккаунта.", call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(
    func=lambda call: call.data in ["back_to_menu", "back_to_dates", "back_to_times", "back_to_durations",
                                    "back_to_participants"])
def process_back(call):
    """Обработчик кнопок назад"""
    user_id = call.from_user.id

    if call.data == "back_to_menu":
        username = db.get_user_session(user_id)
        is_creator = username in CREATORS
        markup = create_main_menu_keyboard(is_creator)
        bot.edit_message_text("Выберите действие:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_to_dates":
        markup = create_dates_keyboard()
        bot.edit_message_text("📅 Выберите дату:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "back_to_times":
        date_str = user_data[user_id]["meeting"]["date"]
        markup = create_times_keyboard(date_str)
        bot.edit_message_text(f"🕐 Выберите время (дата: {date_str}):", call.message.chat.id, call.message.message_id,
                              reply_markup=markup)

    elif call.data == "back_to_durations":
        time_str = user_data[user_id]["meeting"]["time"]
        markup = create_durations_keyboard()
        bot.edit_message_text(f"⏱️ Выберите продолжительность (время: {time_str}):", call.message.chat.id,
                              call.message.message_id, reply_markup=markup)

    elif call.data == "back_to_participants":
        username = db.get_user_session(user_id)
        markup = create_participants_keyboard(username)
        bot.edit_message_text("👥 Выберите участников:", call.message.chat.id, call.message.message_id,
                              reply_markup=markup)

    bot.answer_callback_query(call.id)


# ======================== ЗАПУСК БОТА ========================

def run_bot():
    """Запустить бота в отдельном потоке"""
    logger.info("🤖 Бот запускается...")
    bot.infinity_polling()


def main():
    """Главная функция - запуск бота в фоновом режиме"""
    logger.info("🚀 Запуск бота в фоновом режиме...")

    # Запускаем автоочистку
    cleanup.start()

    # Создаем поток для бота
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()

    logger.info("✅ Бот запущен в фоновом режиме")
    logger.info("🧹 Автоочистка активирована - старые совещания удаляются каждый час")
    logger.info("💡 Чтобы остановить, нажми Ctrl+C")

    # Основной поток остается в работе
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен")
        cleanup.stop()


if __name__ == "__main__":
    main()