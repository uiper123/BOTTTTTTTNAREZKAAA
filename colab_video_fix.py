#!/usr/bin/env python3
"""
Исправление для video_editor.py в Google Colab
Отключает проблемные GPU функции и использует CPU кодировщики
"""

import os
import logging

logger = logging.getLogger(__name__)

def patch_video_editor():
    """Патчит video_editor.py для работы в Colab"""
    try:
        print("🔧 Исправляем video_editor.py для Google Colab...")
        
        # Читаем оригинальный файл
        with open('video_editor.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Создаем резервную копию
        with open('video_editor_backup.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("💾 Создана резервная копия: video_editor_backup.py")
        
        # Исправления для Colab
        fixes = [
            # 1. Отключаем GPU проверку - всегда возвращаем False
            (
                "def _check_gpu_support(self) -> bool:",
                "def _check_gpu_support(self) -> bool:\n        \"\"\"Проверка поддержки GPU для ffmpeg - ОТКЛЮЧЕНО ДЛЯ COLAB\"\"\"\n        logger.info(\"❌ GPU поддержка принудительно отключена для Colab\")\n        return False"
            ),
            
            # 2. Убираем hwaccel параметры из GPU ввода
            (
                "main_video = ffmpeg.input(\n                input_path, \n                ss=start_time, \n                t=duration,\n                hwaccel='cuda',\n                hwaccel_output_format='cuda'\n            )",
                "main_video = ffmpeg.input(input_path, ss=start_time, t=duration)"
            ),
            
            # 3. Упрощаем CPU кодировщик - убираем сложные параметры
            (
                "ffmpeg\n                .output(final_video, audio, output_path, \n                       vcodec='libx264',       # CPU кодировщик\n                       acodec='aac',\n                       preset='fast',          # Быстрый пресет для CPU\n                       crf=18,                 # Качество для CPU\n                       pix_fmt='yuv420p',      # Совместимость\n                       s='1080x1920',          # ПРИНУДИТЕЛЬНО 9:16 формат\n                       **{'b:v': '8M',         # Битрейт видео 8 Мбит/с\n                          'b:a': '192k',       # Битрейт аудио 192 кбит/с\n                          'maxrate': '10M',    # Максимальный битрейт\n                          'bufsize': '16M'})   # Размер буфера",
                "ffmpeg\n                .output(final_video, audio, output_path, \n                       vcodec='libx264',\n                       acodec='aac',\n                       preset='ultrafast',     # Самый быстрый пресет\n                       crf=23,                 # Более быстрое качество\n                       pix_fmt='yuv420p',\n                       s='1080x1920')"
            )
        ]
        
        # Применяем исправления
        modified_content = content
        for old, new in fixes:
            if old in modified_content:
                modified_content = modified_content.replace(old, new)
                print(f"✅ Применено исправление: {old[:50]}...")
            else:
                print(f"⚠️ Не найдено для замены: {old[:50]}...")
        
        # Сохраняем исправленный файл
        with open('video_editor.py', 'w', encoding='utf-8') as f:
            f.write(modified_content)
        
        print("✅ video_editor.py исправлен для Google Colab!")
        print("📝 Изменения:")
        print("  - GPU поддержка отключена")
        print("  - Убраны hwaccel параметры")
        print("  - Упрощены параметры кодировщика")
        print("  - Использован ultrafast пресет")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка исправления: {e}")
        return False

def restore_backup():
    """Восстанавливает оригинальный файл из резервной копии"""
    try:
        if os.path.exists('video_editor_backup.py'):
            with open('video_editor_backup.py', 'r', encoding='utf-8') as f:
                content = f.read()
            
            with open('video_editor.py', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print("✅ video_editor.py восстановлен из резервной копии")
            return True
        else:
            print("❌ Резервная копия не найдена")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        return False

def main():
    """Основная функция"""
    print("🎯 ИСПРАВЛЕНИЕ VIDEO_EDITOR ДЛЯ COLAB")
    print("=" * 50)
    
    if patch_video_editor():
        print("\n🎉 Исправления применены успешно!")
        print("💡 Теперь можно запускать обработку видео в Colab")
        print("🔄 Для восстановления оригинала используйте restore_backup()")
    else:
        print("\n❌ Не удалось применить исправления")

if __name__ == "__main__":
    main()