#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений YouTube загрузчика
"""

import asyncio
import logging
from youtube_downloader import YouTubeDownloader

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_youtube_download():
    """Тест скачивания YouTube видео с новыми исправлениями"""
    
    # URL для тестирования (короткое видео)
    test_url = "https://www.youtube.com/watch?v=R8nRcTmo3xE"
    
    print("🧪 Тестируем исправления YouTube загрузчика...")
    print(f"📺 URL: {test_url}")
    
    downloader = YouTubeDownloader()
    
    # Тест 1: Скачивание с cookies
    print("\n🍪 Тест 1: Скачивание с cookies...")
    result1 = await downloader.download(test_url, use_cookies=True)
    
    if result1['success']:
        print(f"✅ Успешно скачано с cookies: {result1['video_path']}")
        print(f"📝 Название: {result1['title']}")
        print(f"⏱️ Длительность: {result1['duration']} сек")
        return True
    else:
        print(f"❌ Ошибка с cookies: {result1['error']}")
    
    # Тест 2: Скачивание без cookies
    print("\n🚫 Тест 2: Скачивание без cookies...")
    result2 = await downloader.download(test_url, use_cookies=False)
    
    if result2['success']:
        print(f"✅ Успешно скачано без cookies: {result2['video_path']}")
        print(f"📝 Название: {result2['title']}")
        print(f"⏱️ Длительность: {result2['duration']} сек")
        return True
    else:
        print(f"❌ Ошибка без cookies: {result2['error']}")
    
    print("\n❌ Все методы не сработали")
    return False

if __name__ == "__main__":
    success = asyncio.run(test_youtube_download())
    
    if success:
        print("\n🎉 Тест прошел успешно! Загрузчик работает.")
    else:
        print("\n💔 Тест не прошел. Нужны дополнительные исправления.")
        print("\n🔧 Возможные решения:")
        print("1. Обновите yt-dlp: pip install --upgrade yt-dlp")
        print("2. Обновите cookies.txt файл")
        print("3. Попробуйте другое видео")
        print("4. Проверьте интернет соединение")