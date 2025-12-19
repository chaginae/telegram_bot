# База данных для бота БЕЗ Persistent Disk (версия для Render.com)
# БД хранится в /tmp (временная память, теряется при перезагрузке)

import sqlite3
import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с БД SQLite (БЕЗ диска)"""

    def __init__(self):
        """Инициализация БД"""
        # БД в временной папке /tmp (Render автоматически очищает)
        # При перезагрузке сервиса БД теряется
        db_path = os.getenv('DB_PATH', '/tmp/bot_database.db')

        self.db_path = db_path
        self.connection = None

        logger.warning(f"⚠️ БД БЕЗ ДИСКА: {self.db_path}")
        logger.warning("⚠️ ВНИМАНИЕ: Данные теряются при перезагрузке сервиса!")

        # Инициализируем БД
        self._init_db()
        logger.info(f"✅ БД инициализирована (БЕЗ Persistent Disk)")

    def _get_connection(self):
        """Получить соединение с БД"""
        if self.connection is None:
            self.connection = sqlite3.connect(self.db_path, timeout=10)
        return self.connection

    def _init_db(self):
        """Инициализировать структуру БД"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Таблица пользователей и их сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                login_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица совещаний
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator_username TEXT NOT NULL,
                date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                participants TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Таблица уведомлений
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                participant_username TEXT NOT NULL,
                read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (meeting_id) REFERENCES meetings(id)
            )
        ''')

        conn.commit()
        logger.info("✅ Структура БД инициализирована")

    # ======================== СЕССИИ ========================

    def add_user_session(self, user_id, username):
        """Добавить пользователя в сессию"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Проверяем, не в сессии ли уже
            cursor.execute('SELECT user_id FROM user_sessions WHERE user_id = ?', (user_id,))
            if cursor.fetchone():
                logger.warning(f"⚠️ Пользователь {user_id} уже в сессии")
                return False

            cursor.execute(
                'INSERT INTO user_sessions (user_id, username) VALUES (?, ?)',
                (user_id, username)
            )
            conn.commit()
            logger.info(f"✅ Пользователь {username} добавлен в сессию")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении сессии: {e}")
            return False

    def get_user_session(self, user_id):
        """Получить пользователя из сессии"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT username FROM user_sessions WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()

            return result[0] if result else None
        except Exception as e:
            logger.error(f"❌ Ошибка при получении сессии: {e}")
            return None

    def remove_user_session(self, user_id):
        """Удалить пользователя из сессии"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('DELETE FROM user_sessions WHERE user_id = ?', (user_id,))
            conn.commit()
            logger.info(f"✅ Пользователь {user_id} удален из сессии")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении сессии: {e}")
            return False

    # ======================== СОВЕЩАНИЯ ========================

    def add_meeting(self, creator_username, date, start_time, duration_minutes, participants):
        """Добавить новое совещание"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            participants_json = json.dumps(participants)

            cursor.execute(
                '''INSERT INTO meetings 
                   (creator_username, date, start_time, duration_minutes, participants) 
                   VALUES (?, ?, ?, ?, ?)''',
                (creator_username, date, start_time, duration_minutes, participants_json)
            )
            conn.commit()

            meeting_id = cursor.lastrowid
            logger.info(f"✅ Совещание {meeting_id} создано")
            return meeting_id
        except Exception as e:
            logger.error(f"❌ Ошибка при создании совещания: {e}")
            return None

    def get_all_meetings(self):
        """Получить все совещания"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM meetings ORDER BY date, start_time')
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении совещаний: {e}")
            return []

    def get_meetings_by_creator(self, creator_username):
        """Получить совещания создателя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM meetings WHERE creator_username = ? ORDER BY date, start_time',
                (creator_username,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении совещаний: {e}")
            return []

    def get_meetings_by_participant(self, participant_username):
        """Получить совещания участника"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Получаем все совещания и фильтруем по участникам
            cursor.execute('SELECT * FROM meetings ORDER BY date, start_time')
            all_meetings = cursor.fetchall()

            result = []
            for meeting in all_meetings:
                participants = json.loads(meeting[5])
                if participant_username in participants:
                    result.append(meeting)

            return result
        except Exception as e:
            logger.error(f"❌ Ошибка при получении совещаний участника: {e}")
            return []

    def get_past_meetings(self, creator_username=None):
        """Получить прошедшие совещания"""
        try:
            today = datetime.now().strftime("%d.%m")
            conn = self._get_connection()
            cursor = conn.cursor()

            if creator_username:
                cursor.execute(
                    'SELECT * FROM meetings WHERE creator_username = ? AND date < ? ORDER BY date DESC',
                    (creator_username, today)
                )
            else:
                cursor.execute(
                    'SELECT * FROM meetings WHERE date < ? ORDER BY date DESC',
                    (today,)
                )

            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении прошедших совещаний: {e}")
            return []

    def get_future_meetings(self, creator_username):
        """Получить будущие совещания"""
        try:
            today = datetime.now().strftime("%d.%m")
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'SELECT * FROM meetings WHERE creator_username = ? AND date >= ? ORDER BY date',
                (creator_username, today)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении будущих совещаний: {e}")
            return []

    def get_meeting_by_id(self, meeting_id):
        """Получить совещание по ID"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
            return cursor.fetchone()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении совещания: {e}")
            return None

    def delete_meeting(self, meeting_id):
        """Удалить совещание"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Удаляем уведомления
            cursor.execute('DELETE FROM notifications WHERE meeting_id = ?', (meeting_id,))

            # Удаляем совещание
            cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))

            conn.commit()
            logger.info(f"✅ Совещание {meeting_id} удалено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении совещания: {e}")
            return False

    def check_user_availability(self, username, date, start_time, duration):
        """Проверить свободен ли пользователь"""
        try:
            # Парсим время
            start_hour, start_min = map(int, start_time.split(':'))
            duration_hours = duration // 60
            duration_mins = duration % 60
            end_hour = start_hour + duration_hours
            end_min = start_min + duration_mins

            if end_min >= 60:
                end_hour += 1
                end_min -= 60

            end_time = f"{end_hour:02d}:{end_min:02d}"

            # Получаем все совещания на эту дату
            all_meetings = self.get_all_meetings()

            for meeting in all_meetings:
                if meeting[2] != date:  # Не та дата
                    continue

                # Проверяем участников
                participants = json.loads(meeting[5])
                if username not in participants:
                    continue

                # Парсим время совещания
                m_start = meeting[3]
                m_start_hour, m_start_min = map(int, m_start.split(':'))
                m_duration = meeting[4]
                m_duration_hours = m_duration // 60
                m_duration_mins = m_duration % 60
                m_end_hour = m_start_hour + m_duration_hours
                m_end_min = m_start_min + m_duration_mins

                if m_end_min >= 60:
                    m_end_hour += 1
                    m_end_min -= 60

                m_end_time = f"{m_end_hour:02d}:{m_end_min:02d}"

                # Проверяем пересечение времени
                if (start_time < m_end_time and end_time > m_start):
                    return False  # Занят

            return True  # Свободен
        except Exception as e:
            logger.error(f"❌ Ошибка при проверке доступности: {e}")
            return True  # На случай ошибки разрешаем

    # ======================== УВЕДОМЛЕНИЯ ========================

    def add_notification(self, meeting_id, participant_username):
        """Добавить уведомление участнику"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                'INSERT INTO notifications (meeting_id, participant_username) VALUES (?, ?)',
                (meeting_id, participant_username)
            )
            conn.commit()
            logger.info(f"✅ Уведомление добавлено {participant_username}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка при добавлении уведомления: {e}")
            return False

    def get_notifications(self, username):
        """Получить уведомления пользователя"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                '''SELECT n.*, m.* FROM notifications n
                   JOIN meetings m ON n.meeting_id = m.id
                   WHERE n.participant_username = ? AND n.read = 0''',
                (username,)
            )
            return cursor.fetchall()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении уведомлений: {e}")
            return []

    # ======================== ИНФОРМАЦИЯ ========================

    def get_database_info(self):
        """Получить информацию о БД"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) FROM meetings')
            meetings_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM notifications')
            notifications_count = cursor.fetchone()[0]

            cursor.execute('SELECT COUNT(*) FROM user_sessions')
            sessions_count = cursor.fetchone()[0]

            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0

            info = {
                'meetings': meetings_count,
                'notifications': notifications_count,
                'sessions': sessions_count,
                'database_size': db_size,
                'storage': '❌ БЕЗ ДИСКА - данные теряются при перезагрузке!'
            }

            logger.warning(f"⚠️ БД информация: {info}")
            return info
        except Exception as e:
            logger.error(f"❌ Ошибка при получении информации о БД: {e}")
            return {}


# Глобальный экземпляр БД
db = Database()