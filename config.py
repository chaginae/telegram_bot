# Конфиг с пользователями и настройками проекта

# Список всех пользователей системы
USERS_DB = {
    "Рыжов Д.А.": "rd",
    "Гвоздарев Р.С.": "gr",
    "Наконечный Г.В.": "ng",
    "Базанов М.М. 1": "bm1",
    "Базанов М.М. 2": "bm2",
    "Морозов Д.А.": "md",
    "Варгасов А.В.": "va",
    "Помыкалов Д.А.": "pd",
    "Доронцев И.Г.": "di",
    "Аревков Г.Г.": "ag",
    "Елисеева О.Н.": "eo",
    "Игонин Д.М.": "id",
}

# Создатели (могут создавать совещания)
CREATORS = {
    "Гвоздарев Р.С.",
    "Рыжов Д.А.",
    "Наконечный Г.В.",
    "Базанов М.М. 1",
}

# Приглашенные (не могут создавать совещания)
GUESTS = set(USERS_DB.keys()) - CREATORS

# Доступное время для совещаний
MEETING_TIMES = ["09:00", "10:00", "11:00", "14:00", "15:00", "16:00"]

# Продолжительность совещаний в минутах
MEETING_DURATIONS = [30, 60, 120, 180]

# Количество рабочих дней для отображения
WORKDAYS_COUNT = 10

# Рабочие дни недели (0 = понедельник, 4 = пятница)
WORKDAYS = [0, 1, 2, 3, 4]

# Настройки БД
DATABASE_FILE = "bot_database.db"

# Состояния пользователя
class States:
    """Состояния пользователя для машины состояний"""
    START = 1
    CHOOSE_USER = 2
    ENTER_PASSWORD = 3
    MAIN_MENU = 4
    CREATE_MEETING_DATE = 5
    CREATE_MEETING_TIME = 6
    CREATE_MEETING_DURATION = 7
    CREATE_MEETING_PARTICIPANTS = 8
    CONFIRM_PARTICIPANTS = 9
    VIEW_MY_MEETINGS = 10
    VIEW_CALENDAR = 11
    VIEW_GUEST_MEETINGS = 12
    VIEW_GUEST_CALENDAR = 13