#!/usr/bin/env python3
"""
Тестовый скрипт для проверки синхронизации субтитров
"""

import asyncio
import os
from video_editor import VideoEditor

async def test_subtitle_sync():
    """Тест синхронизации субтитров"""
    
    # Создаем тестовые субтитры
    test_subtitles = [
        {'start': 5.0, 'end': 8.0, 'text': 'Первая фраза в начале'},
        {'start': 12.0, 'end': 15.0, 'text': 'Вторая фраза в середине'},
        {'start': 25.0, 'end': 28.0, 'text': 'Третья фраза в конце'},
        {'start': 35.0, 'end': 38.0, 'text': 'Четвертая фраза после клипа'}
    ]
    
    print("🧪 ТЕСТ СИНХРОНИЗАЦИИ СУБТИТРОВ")
    print("=" * 50)
    
    # Тестируем разные сценарии
    test_cases = [
        {"name": "Клип с начала видео", "start_offset": 0, "duration": 30},
        {"name": "Клип из середины", "start_offset": 10, "duration": 30}, 
        {"name": "Клип с конца", "start_offset": 20, "duration": 30}
    ]
    
    editor = VideoEditor()
    
    for case in test_cases:
        print(f"\n📋 {case['name']}")
        print(f"   Смещение: {case['start_offset']}s, Длительность: {case['duration']}s")
        
        # Фильтруем субтитры как в реальном коде
        start_offset = case['start_offset']
        duration = case['duration']
        end_offset = start_offset + duration
        
        # Получаем субтитры, которые пересекаются с клипом
        clip_subtitles = []
        for seg in test_subtitles:
            if seg['end'] > start_offset and seg['start'] < end_offset:
                clip_subtitles.append(seg)
        
        print(f"   📝 Найдено субтитров: {len(clip_subtitles)}")
        
        # Показываем как будут обработаны субтитры
        for i, segment in enumerate(clip_subtitles):
            original_start = segment['start']
            original_end = segment['end']
            
            # Время в клипе = время в оригинале - смещение начала клипа
            clip_start = original_start - start_offset
            clip_end = original_end - start_offset
            
            print(f"      {i+1}. '{segment['text']}'")
            print(f"         Оригинал: {original_start:.1f}-{original_end:.1f}s")
            print(f"         В клипе:  {clip_start:.1f}-{clip_end:.1f}s")
            
            # Проверяем корректировки
            if clip_start < 0:
                print(f"         ✂️ Начало обрезается до 0s")
            if clip_end > duration:
                print(f"         ✂️ Конец обрезается до {duration}s")
            if clip_end <= 0 or clip_start >= duration:
                print(f"         ❌ Субтитр не попадает в клип")

if __name__ == '__main__':
    asyncio.run(test_subtitle_sync())