#!/usr/bin/env python3
"""
Диагностика и исправление проблем с ffmpeg в Google Colab
"""

import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

def check_ffmpeg():
    """Проверка установки и версии ffmpeg"""
    try:
        print("🔍 Проверяем ffmpeg...")
        
        # Проверяем версию
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ ffmpeg найден: {version_line}")
            return True
        else:
            print("❌ ffmpeg не найден или не работает")
            return False
            
    except FileNotFoundError:
        print("❌ ffmpeg не установлен")
        return False
    except Exception as e:
        print(f"❌ Ошибка проверки ffmpeg: {e}")
        return False

def check_codecs():
    """Проверка доступных кодеков"""
    try:
        print("\n🔍 Проверяем доступные кодеки...")
        
        # Проверяем кодировщики
        result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            encoders = result.stdout
            
            # Проверяем основные кодеки
            codecs_to_check = {
                'libx264': 'H.264 (CPU)',
                'h264_nvenc': 'H.264 (NVIDIA GPU)',
                'aac': 'AAC аудио'
            }
            
            available_codecs = []
            for codec, description in codecs_to_check.items():
                if codec in encoders:
                    print(f"✅ {description}: доступен")
                    available_codecs.append(codec)
                else:
                    print(f"❌ {description}: недоступен")
            
            return available_codecs
        else:
            print("❌ Не удалось получить список кодеков")
            return []
            
    except Exception as e:
        print(f"❌ Ошибка проверки кодеков: {e}")
        return []

def test_simple_encode():
    """Тест простого кодирования"""
    try:
        print("\n🧪 Тестируем простое кодирование...")
        
        # Создаем тестовое видео (черный экран 1 секунда)
        test_input = "test_input.mp4"
        test_output = "test_output.mp4"
        
        # Создаем тестовый файл
        create_cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', 'color=black:size=640x480:duration=1',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-y', test_input
        ]
        
        result = subprocess.run(create_cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print(f"❌ Не удалось создать тестовый файл: {result.stderr}")
            return False
        
        print("✅ Тестовый файл создан")
        
        # Тестируем кодирование с нашими параметрами
        encode_cmd = [
            'ffmpeg', '-i', test_input,
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-pix_fmt', 'yuv420p', '-s', '1080x1920',
            '-c:a', 'aac', '-y', test_output
        ]
        
        result = subprocess.run(encode_cmd, capture_output=True, text=True, check=False)
        
        # Очищаем тестовые файлы
        for f in [test_input, test_output]:
            if os.path.exists(f):
                os.remove(f)
        
        if result.returncode == 0:
            print("✅ Тест кодирования прошел успешно")
            return True
        else:
            print(f"❌ Тест кодирования не удался: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка теста кодирования: {e}")
        return False

def install_ffmpeg():
    """Установка/переустановка ffmpeg в Colab"""
    try:
        print("\n🔧 Устанавливаем/обновляем ffmpeg...")
        
        # Обновляем пакеты
        print("1️⃣ Обновляем список пакетов...")
        subprocess.run(['apt', 'update'], capture_output=True, check=False)
        
        # Устанавливаем ffmpeg
        print("2️⃣ Устанавливаем ffmpeg...")
        result = subprocess.run(['apt', 'install', '-y', 'ffmpeg'], 
                              capture_output=True, text=True, check=False)
        
        if result.returncode == 0:
            print("✅ ffmpeg установлен успешно")
            return True
        else:
            print(f"❌ Ошибка установки ffmpeg: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        return False

def fix_permissions():
    """Исправление прав доступа"""
    try:
        print("\n🔧 Исправляем права доступа...")
        
        # Создаем необходимые директории
        dirs_to_create = ['output', 'temp']
        for dir_name in dirs_to_create:
            if not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
                print(f"✅ Создана директория: {dir_name}")
        
        # Проверяем права на запись
        test_file = "temp/test_write.txt"
        try:
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            print("✅ Права на запись в temp/ работают")
        except Exception as e:
            print(f"❌ Проблемы с правами на запись: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка исправления прав: {e}")
        return False

def diagnose_error(error_message: str):
    """Диагностика конкретной ошибки"""
    print(f"\n🔍 Анализируем ошибку: {error_message}")
    
    common_fixes = {
        "No such file or directory": "Проверьте пути к файлам",
        "Permission denied": "Проблемы с правами доступа",
        "Invalid argument": "Неправильные параметры ffmpeg",
        "Encoder not found": "Кодировщик недоступен",
        "Protocol not found": "Проблемы с протоколом",
        "Cannot allocate memory": "Недостаточно памяти"
    }
    
    for error_pattern, fix in common_fixes.items():
        if error_pattern.lower() in error_message.lower():
            print(f"💡 Возможное решение: {fix}")
            return fix
    
    print("💡 Общие рекомендации:")
    print("  - Перезапустите runtime в Colab")
    print("  - Проверьте доступное место на диске")
    print("  - Убедитесь, что входной файл существует")
    
    return None

def main():
    """Основная функция диагностики"""
    print("🎯 ДИАГНОСТИКА FFMPEG В COLAB")
    print("=" * 50)
    
    # Проверяем ffmpeg
    ffmpeg_ok = check_ffmpeg()
    
    if not ffmpeg_ok:
        print("\n🔧 Пытаемся установить ffmpeg...")
        if install_ffmpeg():
            ffmpeg_ok = check_ffmpeg()
    
    if ffmpeg_ok:
        # Проверяем кодеки
        available_codecs = check_codecs()
        
        # Проверяем права доступа
        permissions_ok = fix_permissions()
        
        # Тестируем кодирование
        if 'libx264' in available_codecs and 'aac' in available_codecs:
            encode_ok = test_simple_encode()
        else:
            print("⚠️ Пропускаем тест кодирования - нет необходимых кодеков")
            encode_ok = False
        
        # Итоговый отчет
        print("\n📊 ИТОГОВЫЙ ОТЧЕТ:")
        print(f"  ffmpeg: {'✅' if ffmpeg_ok else '❌'}")
        print(f"  Кодеки: {'✅' if available_codecs else '❌'}")
        print(f"  Права доступа: {'✅' if permissions_ok else '❌'}")
        print(f"  Тест кодирования: {'✅' if encode_ok else '❌'}")
        
        if all([ffmpeg_ok, available_codecs, permissions_ok, encode_ok]):
            print("\n🎉 Все проверки прошли успешно!")
            print("💡 Теперь можно запускать обработку видео")
        else:
            print("\n⚠️ Есть проблемы, которые нужно исправить")
    
    else:
        print("\n❌ ffmpeg недоступен - обработка видео невозможна")

if __name__ == "__main__":
    main()