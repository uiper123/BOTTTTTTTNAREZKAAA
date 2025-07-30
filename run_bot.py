#!/usr/bin/env python3
"""
Запуск Telegram бота для нарезки видео на шотсы
"""

import sys
import os
from bot import TelegramBot

def main():
    """Основная функция запуска"""
    try:
        print("Запуск Telegram бота для нарезки видео...")
        print("Для остановки нажмите Ctrl+C")
        
        bot = TelegramBot()
        bot.run()
        
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"Ошибка запуска бота: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()