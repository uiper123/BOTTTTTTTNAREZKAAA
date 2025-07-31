#!/usr/bin/env python3
"""
Диагностика проблемы с количеством клипов
"""

import asyncio
import logging
import os
from pathlib import Path
from video_editor import VideoEditor
from video_processor import VideoProcessor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def debug_clips_calculation():
    """Диагностика расчета количества клипов"""
    
    # Ищем видео файлы
    temp_dir = Path("temp")
    video_files = []
    
    if temp_dir.exists():
        video_files.extend(list(temp_dir.glob("*.mp4")))
    
    if not video_files:
        print("❌ Нет видео файлов для анализа в папке temp/")
        return
    
    # Берем первый найденный файл
    video_path = str(video_files[0])
    print(f"🎬 Анализируем видео: {video_path}")
    
    # Создаем объекты
    video_editor = VideoEditor()
    video_processor = VideoProcessor()
    
    try:
        # Получаем информацию о видео
        video_info = video_editor.get_video_info(video_path)
        total_duration = video_info['duration']
        
        print(f"⏱️  Общая длительность: {total_duration:.1f} секунд ({total_duration/60:.1f} минут)")
        
        # Параметры нарезки
        clip_duration = 15  # секунд на клип
        chunk_duration = 300  # секунд на чанк (5 минут)
        
        # Теоретическое количество клипов
        theoretical_clips = int(total_duration // clip_duration)
        print(f"🧮 Теоретически клипов: {theoretical_clips} ({total_duration:.1f} / {clip_duration} = {theoretical_clips})")
        
        # Количество чанков
        import math
        num_chunks = math.ceil(total_duration / chunk_duration)
        print(f"📦 Количество чанков: {num_chunks} (по {chunk_duration} сек)")
        
        # Детальный анализ по чанкам
        print(f"\n📊 ДЕТАЛЬНЫЙ АНАЛИЗ ПО ЧАНКАМ:")
        print("=" * 60)
        
        total_expected_clips = 0
        
        for i in range(num_chunks):
            start_time = i * chunk_duration
            actual_chunk_duration = min(chunk_duration, total_duration - start_time)
            
            # Сколько клипов должно быть в этом чанке
            clips_in_chunk = int(actual_chunk_duration // clip_duration)
            total_expected_clips += clips_in_chunk
            
            print(f"Чанк {i+1}: {start_time:.1f}-{start_time + actual_chunk_duration:.1f} сек "
                  f"({actual_chunk_duration:.1f} сек) → {clips_in_chunk} клипов")
        
        print(f"\n📈 ИТОГО ожидается клипов: {total_expected_clips}")
        
        # Проверяем строгий таймлайн
        print(f"\n⚠️  ПРОВЕРКА СТРОГОГО ТАЙМЛАЙНА:")
        print("=" * 60)
        
        min_duration = clip_duration * 0.95  # 95% от длительности клипа
        print(f"Минимальная длительность клипа: {min_duration:.1f} сек")
        
        strict_timeline_clips = 0
        for i in range(num_chunks):
            start_time = i * chunk_duration
            actual_chunk_duration = min(chunk_duration, total_duration - start_time)
            
            # Симулируем строгий таймлайн
            current_time = 0
            chunk_clips = 0
            
            while current_time < actual_chunk_duration:
                remaining_time = actual_chunk_duration - current_time
                
                if remaining_time < clip_duration:
                    print(f"  Чанк {i+1}: Пропущен последний кусок {remaining_time:.1f} сек < {clip_duration} сек")
                    break
                
                actual_clip_duration = min(clip_duration, remaining_time)
                
                if actual_clip_duration < min_duration:
                    print(f"  Чанк {i+1}: Пропущен кусок {actual_clip_duration:.1f} сек < {min_duration:.1f} сек")
                    current_time += clip_duration
                    continue
                
                chunk_clips += 1
                current_time += clip_duration
            
            strict_timeline_clips += chunk_clips
            print(f"Чанк {i+1}: {chunk_clips} клипов (строгий таймлайн)")
        
        print(f"\n🎯 ФИНАЛЬНЫЙ РЕЗУЛЬТАТ:")
        print(f"Теоретически: {theoretical_clips} клипов")
        print(f"По чанкам: {total_expected_clips} клипов") 
        print(f"Строгий таймлайн: {strict_timeline_clips} клипов")
        
        if strict_timeline_clips < theoretical_clips * 0.8:
            print(f"⚠️  ПРОБЛЕМА: Строгий таймлайн отбрасывает слишком много клипов!")
            print(f"   Потеря: {theoretical_clips - strict_timeline_clips} клипов ({((theoretical_clips - strict_timeline_clips) / theoretical_clips * 100):.1f}%)")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(debug_clips_calculation())