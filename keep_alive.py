# keep_alive.py
# Keep-Alive сервис для Render
# Отправляет фиктивные запросы каждую минуту, чтобы бот не отключался
# Работает в отдельном потоке, не мешает пользователям

import requests
import time
import logging
import os
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class KeepAlive:
    """Класс для поддержания активности бота на Render"""
    
    def __init__(self, bot_url=None, interval=60):
        """
        Инициализация Keep-Alive сервиса
        
        Args:
            bot_url: URL сервиса на Render (опционально, может быть None для локального)
            interval: интервал проверки в секундах (по умолчанию 60 сек = 1 минута)
        """
        self.bot_url = bot_url
        self.interval = interval
        self.running = False
        self.thread = None
        self.request_count = 0
        
        logger.info("🔄 Keep-Alive сервис инициализирован")
    
    def start(self):
        """Запустить Keep-Alive в отдельном потоке"""
        if self.running:
            logger.warning("⚠️ Keep-Alive уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._keep_alive_loop, daemon=True)
        self.thread.start()
        
        logger.info(f"✅ Keep-Alive запущен (интервал: {self.interval} сек)")
    
    def stop(self):
        """Остановить Keep-Alive"""
        self.running = False
        logger.info("🛑 Keep-Alive остановлен")
    
    def _keep_alive_loop(self):
        """Основной цикл Keep-Alive"""
        while self.running:
            try:
                self._send_ping()
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"❌ Ошибка в Keep-Alive: {e}")
                time.sleep(self.interval)
    
    def _send_ping(self):
        """Отправить фиктивный запрос"""
        try:
            self.request_count += 1
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            if self.bot_url:
                # Если есть URL - отправляем HTTP запрос
                response = requests.get(self.bot_url, timeout=5)
                if response.status_code == 200:
                    logger.debug(f"🔄 [{self.request_count}] Keep-Alive ping успешен ({timestamp})")
                else:
                    logger.debug(f"🔄 [{self.request_count}] Ping вернул {response.status_code} ({timestamp})")
            else:
                # Если URL нет - просто логируем (локальный режим)
                logger.debug(f"🔄 [{self.request_count}] Keep-Alive активен ({timestamp})")
        
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ [{self.request_count}] Keep-Alive timeout ({timestamp})")
        except Exception as e:
            logger.warning(f"⚠️ [{self.request_count}] Keep-Alive ошибка: {e}")
    
    def get_stats(self):
        """Получить статистику Keep-Alive"""
        return {
            'running': self.running,
            'requests_sent': self.request_count,
            'interval': self.interval,
            'bot_url': self.bot_url or 'локальный режим'
        }


# Глобальный экземпляр Keep-Alive
keep_alive = None


def init_keep_alive(render_url=None, interval=60):
    """
    Инициализировать и запустить Keep-Alive
    
    Args:
        render_url: URL сервиса на Render (опционально)
        interval: интервал в секундах (по умолчанию 60)
    
    Returns:
        Экземпляр KeepAlive
    """
    global keep_alive
    
    # Получаем URL из переменной окружения или используем параметр
    url = os.getenv('RENDER_URL', render_url)
    
    keep_alive = KeepAlive(bot_url=url, interval=interval)
    keep_alive.start()
    
    return keep_alive


def stop_keep_alive():
    """Остановить Keep-Alive"""
    global keep_alive
    if keep_alive:
        keep_alive.stop()
