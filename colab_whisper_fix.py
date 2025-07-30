#!/usr/bin/env python3
"""
Скрипт для исправления проблем с Whisper в Google Colab
Запустите этот файл в начале работы в Colab
"""

import subprocess
import sys
import logging

logger = logging.getLogger(__name__)

def install_whisper():
    """Установка правильной версии OpenAI Whisper"""
    try:
        print("🔧 Исправляем проблемы с Whisper в Colab...")
        
        # Удаляем конфликтующие версии
        print("1️⃣ Удаляем старые версии...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "whisper"], 
                      capture_output=True)
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "openai-whisper"], 
                      capture_output=True)
        
        # Устанавливаем правильную версию
        print("2️⃣ Устанавливаем OpenAI Whisper...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "openai-whisper", "--upgrade", "--force-reinstall"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка установки: {result.stderr}")
            return False
        
        # Проверяем установку
        print("3️⃣ Проверяем установку...")
        try:
            import whisper
            if hasattr(whisper, 'load_model'):
                print("✅ OpenAI Whisper установлен правильно!")
                
                # Предзагружаем модель для ускорения
                print("4️⃣ Предзагружаем модель 'base'...")
                model = whisper.load_model("base")
                print("✅ Модель 'base' загружена успешно!")
                
                return True
            else:
                print("❌ Whisper установлен, но load_model недоступен")
                return False
                
        except ImportError as e:
            print(f"❌ Не удалось импортировать whisper: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Общая ошибка установки: {e}")
        return False

def install_alternative_whisper():
    """Установка faster-whisper как альтернативы"""
    try:
        print("🚀 Устанавливаем faster-whisper как альтернативу...")
        
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "faster-whisper", "--upgrade"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка установки faster-whisper: {result.stderr}")
            return False
        
        # Проверяем
        try:
            from faster_whisper import WhisperModel
            print("✅ faster-whisper установлен успешно!")
            
            # Предзагружаем модель
            print("4️⃣ Предзагружаем faster-whisper модель 'base'...")
            model = WhisperModel("base")
            print("✅ faster-whisper модель 'base' загружена!")
            
            return True
            
        except ImportError as e:
            print(f"❌ Не удалось импортировать faster-whisper: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка установки faster-whisper: {e}")
        return False

def main():
    """Основная функция установки"""
    print("🎯 ИСПРАВЛЕНИЕ WHISPER ДЛЯ COLAB")
    print("=" * 50)
    
    # Сначала пробуем основной Whisper
    if install_whisper():
        print("\n🎉 OpenAI Whisper готов к работе!")
        return True
    
    print("\n⚠️ OpenAI Whisper не удалось установить, пробуем альтернативу...")
    
    # Если не получилось, пробуем faster-whisper
    if install_alternative_whisper():
        print("\n🎉 faster-whisper готов к работе!")
        return True
    
    print("\n❌ Не удалось установить ни одну версию Whisper")
    print("💡 Попробуйте перезапустить runtime в Colab и запустить снова")
    return False

if __name__ == "__main__":
    success = main()
    if not success:
        print("\n🔧 РУЧНАЯ УСТАНОВКА:")
        print("Выполните в Colab:")
        print("!pip uninstall -y whisper openai-whisper")
        print("!pip install openai-whisper --upgrade --force-reinstall")
        print("Затем перезапустите runtime")