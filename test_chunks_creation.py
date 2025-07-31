#!/usr/bin/env python3
"""
Тест создания чанков для диагностики проблемы
"""

import asyncio
import logging
import os
from pathlib import Path
from video_processor import VideoProcessor
from video_editor import VideoEditor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_chunks_creation():
    """Тестируем только создание чанков"""
    
    # Ищем видео файлы
    test_files = []
    
    # Проверяем разные папки
    for folder in ["temp", ".", "output"]:
        folder_path = Path(folder)
        if folder_path.exists():
            test_files.extend(list(folder_path.glob("*.mp4")))
            test_files.extend(list(folder_path.glob("*.mkv")))
            test_files.extend(list(folder_path.glob("*.avi")))
    
    if not test_files:
        print("❌ Нет видео файлов для тестирования")
        print("Поместите видео файл в папку temp/ или в корень проекта")
        return
    
    # Берем первый найденный файл
    video_path = str(test_files[0])
    print(f"🎬 Тестируем создание чанков для: {video_path}")
    
    # Создаем объекты
    video_processor = VideoProcessor()
    video_editor = VideoEditor()
    
    try:
        # Получаем информацию о видео
        video_info = video_editor.get_video_info(video_path)
        total_duration = video_info['duration']
        
        print(f"⏱️  Длительность видео: {total_duration:.1f} секунд ({total_duration/60:.1f} минут)")
        
        # Вычисляем ожидаемое количество чанков
        chunk_duration = 300  # 5 минут
        import math
        expected_chunks = math.ceil(total_duration / chunk_duration)
        
        print(f"📦 Ожидается чанков: {expected_chunks}")
        print(f"🎯 Ожидается клипов (по 15 сек): {int(total_duration // 15)}")
        
        # Создаем чанки
        print(f"\n🚀 НАЧИНАЕМ СОЗДАНИЕ ЧАНКОВ...")
        print("=" * 60)
        
        chunks = await video_processor.split_into_chunks(video_path, chunk_duration=300)
        
        print(f"\n📊 РЕЗУЛЬТАТ СОЗДАНИЯ ЧАНКОВ:")
        print(f"   Создано чанков: {len(chunks)}")
        print(f"   Ожидалось: {expected_chunks}")
        
        if len(chunks) < expected_chunks:
            print(f"⚠️  ПРОБЛЕМА: Создано меньше чанков чем ожидалось!")
            print(f"   Потеряно: {expected_chunks - len(chunks)} чанков")
        
        # Проверяем каждый чанк детально
        print(f"\n🔍 ДЕТАЛЬНАЯ ПРОВЕРКА ЧАНКОВ:")
        print("=" * 60)
        
        total_chunks_duration = 0
        for i, chunk_path in enumerate(chunks):
            try:
                if os.path.exists(chunk_path):
                    chunk_info = video_editor.get_video_info(chunk_path)
                    chunk_duration_actual = chunk_info['duration']
                    total_chunks_duration += chunk_duration_actual
                    file_size = os.path.getsize(chunk_path) / (1024 * 1024)  # MB
                    
                    print(f"✅ Чанк {i+1}: {chunk_duration_actual:.1f} сек, {file_size:.1f} МБ")
                    print(f"   Путь: {chunk_path}")
                else:
                    print(f"❌ Чанк {i+1}: ФАЙЛ НЕ СУЩЕСТВУЕТ - {chunk_path}")
            except Exception as e:
                print(f"❌ Чанк {i+1}: ОШИБКА - {e}")
        
        print(f"\n📈 ИТОГОВАЯ СТАТИСТИКА:")
        print(f"   Исходное видео: {total_duration:.1f} сек")
        print(f"   Сумма чанков: {total_chunks_duration:.1f} сек")
        coverage = (total_chunks_duration / total_duration) * 100 if total_duration > 0 else 0
        print(f"   Покрытие: {coverage:.1f}%")
        
        if coverage < 95:
            print(f"⚠️  КРИТИЧЕСКАЯ ПРОБЛЕМА: Чанки покрывают только {coverage:.1f}% видео!")
            print(f"   Потеряно: {total_duration - total_chunks_duration:.1f} секунд видео")
        else:
            print(f"✅ Чанки покрывают {coverage:.1f}% видео - это нормально")
        
        # Очищаем созданные чанки
        print(f"\n🧹 ОЧИСТКА ТЕСТОВЫХ ЧАНКОВ...")
        for chunk_path in chunks:
            if chunk_path != video_path and os.path.exists(chunk_path):
                try:
                    os.remove(chunk_path)
                    print(f"   Удален: {chunk_path}")
                except Exception as e:
                    print(f"   Ошибка удаления {chunk_path}: {e}")
        
        print(f"\n🏁 ТЕСТ ЗАВЕРШЕН")
        
    except Exception as e:
        print(f"❌ Ошибка теста: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chunks_creation())