# database.py
# Работа с базой данных SQLite

import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DATABASE = "bot_database.db"


class Database:
    def __init__(self, db_path=DATABASE):
        self.db_path = db_path
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для работы с БД"""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Таблица пользователей (сессии)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица совещаний
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meetings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_username TEXT NOT NULL,
                    date TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    duration_minutes INTEGER NOT NULL,
                    participants TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Таблица уведомлений
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    meeting_id INTEGER NOT NULL,
                    participant_username TEXT NOT NULL,
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(meeting_id) REFERENCES meetings(id)
                )
            """)

    # ======================== УПРАВЛЕНИЕ СЕССИЯМИ ========================

    def add_user_session(self, user_id, username):
        """Добавить пользователя в сессию"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Проверяем, нет ли уже сессии
            cursor.execute("SELECT * FROM user_sessions WHERE user_id = ?", (user_id,))
            if cursor.fetchone():
                return False

            cursor.execute(
                "INSERT INTO user_sessions (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            return True

    def get_user_session(self, user_id):
        """Получить имя пользователя из сессии"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM user_sessions WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def remove_user_session(self, user_id):
        """Удалить пользователя из сессии"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))

    # ======================== УПРАВЛЕНИЕ СОВЕЩАНИЯМИ ========================

    def add_meeting(self, creator_username, date, start_time, duration_minutes, participants):
        """Добавить новое совещание"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            participants_json = json.dumps(participants)

            cursor.execute("""
                INSERT INTO meetings (creator_username, date, start_time, duration_minutes, participants)
                VALUES (?, ?, ?, ?, ?)
            """, (creator_username, date, start_time, duration_minutes, participants_json))

            return cursor.lastrowid

    def get_all_meetings(self):
        """Получить все совещания"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, creator_username, date, start_time, duration_minutes, participants
                FROM meetings
                ORDER BY date DESC, start_time DESC
            """)
            return cursor.fetchall()

    def get_meetings_by_creator(self, creator_username):
        """Получить совещания по создателю"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, creator_username, date, start_time, duration_minutes, participants
                FROM meetings
                WHERE creator_username = ?
                ORDER BY date DESC, start_time DESC
            """, (creator_username,))
            return cursor.fetchall()

    def get_meetings_by_participant(self, participant_username):
        """Получить совещания по участнику"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, creator_username, date, start_time, duration_minutes, participants
                FROM meetings
                WHERE participants LIKE ?
                ORDER BY date DESC, start_time DESC
            """, (f'%"{participant_username}"%',))
            return cursor.fetchall()

    def get_meeting_by_id(self, meeting_id):
        """Получить совещание по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, creator_username, date, start_time, duration_minutes, participants
                FROM meetings
                WHERE id = ?
            """, (meeting_id,))
            return cursor.fetchone()

    def delete_meeting(self, meeting_id):
        """Удалить совещание по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Удаляем уведомления
            cursor.execute("DELETE FROM notifications WHERE meeting_id = ?", (meeting_id,))

            # Удаляем совещание
            cursor.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))

            return True

    def get_past_meetings(self, creator_username=None):
        """Получить прошедшие совещания"""
        from utils import get_end_time
        from datetime import datetime

        today = datetime.now().strftime("%d.%m")

        with self.get_connection() as conn:
            cursor = conn.cursor()

            if creator_username:
                cursor.execute("""
                    SELECT id, creator_username, date, start_time, duration_minutes, participants
                    FROM meetings
                    WHERE creator_username = ?
                    ORDER BY date ASC, start_time ASC
                """, (creator_username,))
            else:
                cursor.execute("""
                    SELECT id, creator_username, date, start_time, duration_minutes, participants
                    FROM meetings
                    ORDER BY date ASC, start_time ASC
                """)

            all_meetings = cursor.fetchall()
            past_meetings = []

            for meeting in all_meetings:
                meeting_date = meeting[2]  # date

                # Сравниваем даты (формат: DD.MM)
                if meeting_date < today:
                    past_meetings.append(meeting)

            return past_meetings

    def get_future_meetings(self, creator_username):
        """Получить будущие совещания создателя"""
        from datetime import datetime

        today = datetime.now().strftime("%d.%m")

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, creator_username, date, start_time, duration_minutes, participants
                FROM meetings
                WHERE creator_username = ?
                ORDER BY date DESC, start_time DESC
            """, (creator_username,))

            all_meetings = cursor.fetchall()
            future_meetings = []

            for meeting in all_meetings:
                meeting_date = meeting[2]  # date

                # Сравниваем даты
                if meeting_date >= today:
                    future_meetings.append(meeting)

            return future_meetings

    # ======================== УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ ========================

    def add_notification(self, meeting_id, participant_username):
        """Добавить уведомление"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO notifications (meeting_id, participant_username)
                VALUES (?, ?)
            """, (meeting_id, participant_username))

    def get_notifications(self, participant_username):
        """Получить уведомления участника"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM notifications
                WHERE participant_username = ? AND is_read = 0
                ORDER BY created_at DESC
            """, (participant_username,))
            return cursor.fetchall()

    def mark_notification_as_read(self, notification_id):
        """Отметить уведомление как прочитанное"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE notifications SET is_read = 1 WHERE id = ?
            """, (notification_id,))

    # ======================== ПРОВЕРКА ДОСТУПНОСТИ ========================

    def check_user_availability(self, username, date, start_time, duration_minutes):
        """Проверить доступность пользователя в указанное время"""
        from utils import get_end_time

        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Получаем все совещания пользователя в этот день
            cursor.execute("""
                SELECT date, start_time, duration_minutes, participants
                FROM meetings
                WHERE date = ?
            """, (date,))

            meetings = cursor.fetchall()

            # Новое совещание: время с start_time до end_time
            new_end_time = get_end_time(start_time, duration_minutes)

            for meeting in meetings:
                meeting_date, meeting_start, meeting_duration, participants_json = meeting
                participants = json.loads(participants_json)

                # Если пользователь участник
                if username in participants:
                    meeting_end = get_end_time(meeting_start, meeting_duration)

                    # Проверяем пересечение времени
                    if not (new_end_time <= meeting_start or start_time >= meeting_end):
                        return False

            return True

    def get_database_size(self):
        """Получить размер БД в байтах"""
        import os
        if os.path.exists(self.db_path):
            return os.path.getsize(self.db_path)
        return 0

    def get_database_info(self):
        """Получить информацию о БД"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Количество совещаний
            cursor.execute("SELECT COUNT(*) FROM meetings")
            meetings_count = cursor.fetchone()[0]

            # Количество активных сессий
            cursor.execute("SELECT COUNT(*) FROM user_sessions")
            sessions_count = cursor.fetchone()[0]

            # Количество уведомлений
            cursor.execute("SELECT COUNT(*) FROM notifications")
            notifications_count = cursor.fetchone()[0]

            return {
                "meetings": meetings_count,
                "sessions": sessions_count,
                "notifications": notifications_count,
                "database_size": self.get_database_size()
            }


# Глобальный экземпляр БД
db = Database()