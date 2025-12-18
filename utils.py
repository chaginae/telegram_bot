# utils.py
# Вспомогательные функции

from datetime import datetime, timedelta
from config import WORKDAYS, WORKDAYS_COUNT, MEETING_TIMES
import json

def get_next_workdays(start_date=None, count=WORKDAYS_COUNT):
    """
    Получить список следующих рабочих дней (пн-пт)
    
    Args:
        start_date: дата начала (datetime), если None - текущая дата
        count: количество рабочих дней
    
    Returns:
        список кортежей (дата, дата_строка_ДД.МММ)
    """
    if start_date is None:
        start_date = datetime.now()
    
    workdays = []
    current_date = start_date
    
    while len(workdays) < count:
        if current_date.weekday() in WORKDAYS:
            date_str = current_date.strftime("%d.%m")
            workdays.append((current_date, date_str))
        current_date += timedelta(days=1)
    
    return workdays


def get_available_times(current_hour=None):
    """
    Получить доступное время для совещаний
    Если сейчас 10:30, то 9:00 и 10:00 недоступны
    
    Args:
        current_hour: текущий час (если None - текущее время)
    
    Returns:
        список доступного времени
    """
    if current_hour is None:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute
    else:
        current_minute = 0
    
    available = []
    for time_str in MEETING_TIMES:
        hour, minute = map(int, time_str.split(':'))
        # Если время уже прошло или идет прямо сейчас, пропускаем
        if hour > current_hour or (hour == current_hour and minute > current_minute):
            available.append(time_str)
    
    return available


def format_duration(minutes):
    """Форматировать продолжительность в читаемый вид"""
    if minutes == 30:
        return "30 минут"
    elif minutes == 60:
        return "1 час"
    elif minutes == 120:
        return "2 часа"
    elif minutes == 180:
        return "3 часа"
    return f"{minutes} минут"


def time_to_minutes(time_str):
    """Преобразовать время (ЧЧ:ММ) в минуты"""
    h, m = map(int, time_str.split(':'))
    return h * 60 + m


def minutes_to_time(minutes):
    """Преобразовать минуты в время (ЧЧ:ММ)"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"


def get_end_time(start_time, duration_minutes):
    """Получить время окончания совещания"""
    start_minutes = time_to_minutes(start_time)
    end_minutes = start_minutes + duration_minutes
    return minutes_to_time(end_minutes)


def parse_date_string(date_str):
    """
    Преобразовать строку ДД.ММ в объект datetime
    
    Args:
        date_str: строка вида "ДД.ММ"
    
    Returns:
        объект datetime
    """
    day, month = map(int, date_str.split('.'))
    now = datetime.now()
    
    # Определяем год (если месяц меньше текущего, это следующий год)
    year = now.year if month >= now.month else now.year + 1
    
    return datetime(year, month, day)


def escape_html(text):
    """Экранировать HTML символы"""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    return text


def format_participants_list(participants):
    """Форматировать список участников"""
    if not participants:
        return ""
    
    if isinstance(participants, str):
        participants = json.loads(participants)
    
    return ", ".join(participants)


def create_buttons_grid(items, columns=2):
    """
    Создать сетку кнопок из списка
    
    Args:
        items: список элементов
        columns: количество столбцов
    
    Returns:
        список списков (для формирования InlineKeyboardMarkup)
    """
    grid = []
    for i in range(0, len(items), columns):
        row = items[i:i + columns]
        grid.append(row)
    return grid