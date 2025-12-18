# auto_cleanup.py
# Автоматическое удаление прошедших совещаний

import threading
import time
import logging
from datetime import datetime, timedelta
from database import db

logger = logging.getLogger(__name__)

class AutoCleanup:
    """Автоматическое удаление прошедших совещаний"""
    
    def __init__(self, check_interval=3600):
        """
        Инициализация автоочистки
        check_interval - интервал проверки в секундах (по умолчанию 1 час)
        """
        self.check_interval = check_interval
        self.running = False
        self.thread = None
    
    def start(self):
        """Запустить автоочистку в отдельном потоке"""
        if self.running:
            logger.warning("⚠️ Автоочистка уже запущена")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self.thread.start()
        logger.info("🧹 Автоочистка старых совещаний запущена")
    
    def stop(self):
        """Остановить автоочистку"""
        self.running = False
        logger.info("🛑 Автоочистка остановлена")
    
    def _cleanup_loop(self):
        """Основной цикл проверки и удаления"""
        while self.running:
            try:
                self._cleanup_old_meetings()
            except Exception as e:
                logger.error(f"❌ Ошибка при очистке: {e}")
            
            # Ждем перед следующей проверкой
            time.sleep(self.check_interval)
    
    def _cleanup_old_meetings(self):
        """Удалить все прошедшие совещания"""
        today = datetime.now().strftime("%d.%m")
        
        try:
            # Получаем все совещания
            all_meetings = db.get_all_meetings()
            
            deleted_count = 0
            
            for meeting in all_meetings:
                meeting_id = meeting[0]
                date_str = meeting[2]
                
                # Если дата совещания раньше текущей - удаляем
                if date_str < today:
                    db.delete_meeting(meeting_id)
                    deleted_count += 1
            
            if deleted_count > 0:
                logger.info(f"🧹 Удалено прошедших совещаний: {deleted_count}")
                info = db.get_database_info()
                logger.info(f"📊 В БД осталось совещаний: {info['meetings']}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка при удалении совещаний: {e}")
    
    def cleanup_now(self):
        """Выполнить очистку прямо сейчас (не ждать интервала)"""
        logger.info("🧹 Запуск немедленной очистки...")
        self._cleanup_old_meetings()
        logger.info("✅ Очистка завершена")


# Глобальный экземпляр
cleanup = AutoCleanup(check_interval=3600)  # Проверка каждый час