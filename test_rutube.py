#!/usr/bin/env python3
"""
Тестовый скрипт для проверки поддержки Rutube в yt-dlp
"""

import asyncio
import logging
from youtube_downloader import YouTubeDownloader

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

async def test_rutube_support():
    """Тестирование поддержки Rutube"""
    downloader = YouTubeDownloader()
    
    # Примеры URL для тестирования (замените на реальные)
    test_urls = [
        # Добавьте сюда реальные URL с Rutube для тестирования
        # "https://rutube.ru/video/example/",
    ]
    
    print("🔍 Проверка поддержки Rutube в yt-dlp...")
    
    # Проверяем под