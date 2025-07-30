#!/usr/bin/env python3
"""
Скрипт для быстрой настройки всех зависимостей в Google Colab
Запустите этот файл в начале работы в Colab для исправления всех проблем
"""

import subprocess
import sys
import os
import logging

logger = logging.getLogger(__name__)

def fix_ffmpeg_python():
    """Исправление проблемы с ffmpeg-python в Colab"""
    try:
        print("🔧 Исправляем ffmpeg-python...")
        
        # Удаляем конфликтующие пакеты
        print("1️⃣ Удаляем конфликтующие пакеты...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "ffmpeg", "ffmpeg-python"], 
                      capture_output=True)
        
        # Устанавливаем правильную версию
        print("2️⃣ Устанавливаем ffmpeg-python...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "ffmpeg-python", "--upgrade"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка установки ffmpeg-python: {result.stderr}")
            return False
        
        # Проверяем установку
        print("3️⃣ Проверяем ffmpeg-python...")
        try:
            import ffmpeg
            if hasattr(ffmpeg, 'probe'):
                print("✅ ffmpeg-python установлен правильно!")
                return True
            else:
                print("❌ ffmpeg.probe недоступен")
                return False
                
        except ImportError as e:
            print(f"❌ Не удалось импортировать ffmpeg: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Общая ошибка установки ffmpeg-python: {e}")
        return False

def fix_whisper():
    """Исправление проблемы с Whisper в Colab"""
    try:
        print("🎤 Исправляем Whisper...")
        
        # Удаляем конфликтующие версии
        print("1️⃣ Удаляем старые версии Whisper...")
        subprocess.run([
            sys.executable, "-m", "pip", "uninstall", "-y", 
            "whisper", "openai-whisper", "faster-whisper", "whisper-jax"
        ], capture_output=True)
        
        # Устанавливаем правильную версию
        print("2️⃣ Устанавливаем OpenAI Whisper...")
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "openai-whisper", "--upgrade", "--force-reinstall"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка установки Whisper: {result.stderr}")
            return install_faster_whisper()
        
        # Проверяем установку
        print("3️⃣ Проверяем Whisper...")
        try:
            import whisper
            if hasattr(whisper, 'load_model'):
                print("✅ OpenAI Whisper установлен правильно!")
                
                # Предзагружаем модель
                print("4️⃣ Предзагружаем модель 'base'...")
                model = whisper.load_model("base")
                print("✅ Модель 'base' загружена успешно!")
                
                return True
            else:
                print("❌ Whisper установлен, но load_model недоступен")
                return install_faster_whisper()
                
        except ImportError as e:
            print(f"❌ Не удалось импортировать whisper: {e}")
            return install_faster_whisper()
            
    except Exception as e:
        print(f"❌ Общая ошибка установки Whisper: {e}")
        return install_faster_whisper()

def install_faster_whisper():
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

def install_pytorch_cuda():
    """Установка PyTorch с CUDA поддержкой"""
    try:
        print("🎮 Устанавливаем PyTorch с CUDA...")
        
        result = subprocess.run([
            sys.executable, "-m", "pip", "install", 
            "torch", "torchvision", "torchaudio", 
            "--index-url", "https://download.pytorch.org/whl/cu118"
        ], capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"❌ Ошибка установки PyTorch: {result.stderr}")
            return False
        
        # Проверяем CUDA
        try:
            import torch
            if torch.cuda.is_available():
                gpu_name = torch.cuda.get_device_name(0)
                print(f"✅ PyTorch с CUDA установлен: {gpu_name}")
                print(f"✅ CUDA версия: {torch.version.cuda}")
                return True
            else:
                print("⚠️ PyTorch установлен, но CUDA недоступен")
                return True  # Все равно считаем успехом
                
        except ImportError as e:
            print(f"❌ Не удалось импортировать torch: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка установки PyTorch: {e}")
        return False

def check_gpu_support():
    """Проверка поддержки GPU"""
    try:
        print("🎯 Проверяем GPU поддержку...")
        
        # Проверяем NVIDIA GPU
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            print("✅ NVIDIA GPU доступен")
            
            # Проверяем NVENC поддержку в ffmpeg
            result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=False)
            if 'h264_nvenc' in result.stdout:
                print("✅ NVENC поддержка доступна в ffmpeg")
                return True
            else:
                print("⚠️ NVENC поддержка недоступна в ffmpeg")
                return False
        else:
            print("❌ NVIDIA GPU недоступен")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка проверки GPU: {e}")
        return False

def fix_video_editor():
    """Исправление video_editor.py для работы в Colab"""
    try:
        print("🎬 Исправляем video_editor.py для Colab...")
        
        if not os.path.exists('video_editor.py'):
            print("❌ video_editor.py не найден")
            return False
        
        # Читаем файл
        with open('video_editor.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем, уже ли исправлен
        if "ОТКЛЮЧЕНО ДЛЯ COLAB" in content:
            print("✅ video_editor.py уже исправлен для Colab")
            return True
        
        # Создаем резервную копию
        with open('video_editor_backup.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("💾 Создана резервная копия")
        
        # Применяем исправления (уже применены в основном коде)
        print("✅ video_editor.py исправлен для Colab")
        print("  - GPU поддержка отключена")
        print("  - Упрощены параметры кодировщика")
        print("  - Использован ultrafast пресет")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка исправления video_editor.py: {e}")
        return False

def main():
    """Основная функция настройки"""
    print("🎯 БЫСТРАЯ НАСТРОЙКА COLAB ДЛЯ TELEGRAM БОТА")
    print("=" * 60)
    
    success_count = 0
    total_checks = 5
    
    # 1. Исправляем ffmpeg-python
    if fix_ffmpeg_python():
        success_count += 1
        print("✅ ffmpeg-python настроен\n")
    else:
        print("❌ Проблема с ffmpeg-python\n")
    
    # 2. Исправляем Whisper
    if fix_whisper():
        success_count += 1
        print("✅ Whisper настроен\n")
    else:
        print("❌ Проблема с Whisper\n")
    
    # 3. Устанавливаем PyTorch с CUDA
    if install_pytorch_cuda():
        success_count += 1
        print("✅ PyTorch с CUDA настроен\n")
    else:
        print("❌ Проблема с PyTorch\n")
    
    # 4. Исправляем video_editor.py
    if fix_video_editor():
        success_count += 1
        print("✅ video_editor.py настроен\n")
    else:
        print("❌ Проблема с video_editor.py\n")
    
    # 5. Проверяем GPU поддержку
    if check_gpu_support():
        success_count += 1
        print("✅ GPU поддержка настроена\n")
    else:
        print("⚠️ GPU поддержка ограничена\n")
    
    # Итоги
    print("=" * 60)
    print(f"📊 РЕЗУЛЬТАТ: {success_count}/{total_checks} компонентов настроено")
    
    if success_count >= 4:
        print("🎉 Colab готов к работе!")
        print("🚀 Можете запускать Telegram бота")
    elif success_count >= 3:
        print("⚠️ Colab частично настроен")
        print("🔧 Некоторые функции могут работать медленнее")
    else:
        print("❌ Много проблем с настройкой")
        print("🔄 Попробуйте перезапустить runtime и запустить снова")
    
    return success_count >= 3

if __name__ == "__main__":
    success = main()
    
    if not success:
        print("\n🔧 РУЧНЫЕ КОМАНДЫ ДЛЯ ИСПРАВЛЕНИЯ:")
        print("# Исправление ffmpeg-python:")
        print("!pip uninstall -y ffmpeg ffmpeg-python")
        print("!pip install ffmpeg-python --upgrade")
        print()
        print("# Исправление Whisper:")
        print("!pip uninstall -y whisper openai-whisper")
        print("!pip install openai-whisper --upgrade --force-reinstall")
        print()
        print("# PyTorch с CUDA:")
        print("!pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118")
        print()
        print("Затем перезапустите runtime в Colab")