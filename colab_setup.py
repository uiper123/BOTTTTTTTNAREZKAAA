#!/usr/bin/env python3
"""
Скрипт быстрой настройки для Google Colab
Автоматизирует процесс настройки бота в облачной среде
"""

import os
import sys
import subprocess
import json
import base64
import pickle
from pathlib import Path

def install_dependencies():
    """Установка всех необходимых зависимостей"""
    print("🔧 Установка зависимостей...")
    
    # Системные пакеты
    subprocess.run(['apt', 'update', '-qq'], check=True)
    subprocess.run(['apt', 'install', '-y', 'ffmpeg', 'fonts-liberation'], check=True)
    
    # Python пакеты
    packages = [
        'python-telegram-bot==20.7',
        'yt-dlp',
        'openai-whisper',
        'google-api-python-client',
        'google-auth-httplib2',
        'google-auth-oauthlib',
        'python-dotenv',
        'Pillow',
        'moviepy'
    ]
    
    for package in packages:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', package], check=True)
    
    print("✅ Все зависимости установлены!")

def setup_environment():
    """Настройка рабочего окружения"""
    print("📁 Настройка рабочего окружения...")
    
    # Создаем необходимые папки
    folders = ['temp', 'output']
    for folder in folders:
        Path(folder).mkdir(exist_ok=True)
    
    # Скачиваем шрифт
    try:
        import urllib.request
        urllib.request.urlretrieve(
            'https://github.com/google/fonts/raw/main/ofl/roboto/Roboto-Bold.ttf',
            'Obelix Pro.ttf'
        )
        print("✅ Шрифт загружен!")
    except:
        # Fallback на системный шрифт
        subprocess.run(['cp', '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf', 'Obelix Pro.ttf'])
        print("✅ Использован системный шрифт!")

def create_env_file(telegram_token, google_token_base64):
    """Создание .env файла с настройками"""
    print("📝 Создание .env файла...")
    
    env_content = f"""# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN={telegram_token}

# Google Drive Configuration
GOOGLE_OAUTH_TOKEN_BASE64={google_token_base64}

# Video Processing Settings
DEFAULT_CLIP_DURATION=30
DEFAULT_TITLE=ФРАГМЕНТ
DEFAULT_SUBTITLE=Часть
WHISPER_MODEL=base
MAX_CHUNK_DURATION=300
"""
    
    with open('.env', 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    print("✅ Файл .env создан!")

def setup_google_oauth():
    """Интерактивная настройка Google OAuth"""
    print("🔐 Настройка Google OAuth...")
    
    print("Для настройки Google Drive API вам нужно:")
    print("1. Перейти в Google Cloud Console")
    print("2. Создать проект и включить Drive API")
    print("3. Создать OAuth 2.0 credentials")
    print("4. Скачать JSON файл")
    
    oauth_json = input("Вставьте содержимое OAuth JSON файла: ")
    
    try:
        # Проверяем валидность JSON
        json.loads(oauth_json)
        
        # Сохраняем в файл
        with open('credentials.json', 'w') as f:
            f.write(oauth_json)
        
        # Настраиваем OAuth flow
        from google_auth_oauthlib.flow import Flow
        
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        
        flow = Flow.from_client_secrets_file(
            'credentials.json',
            scopes=SCOPES,
            redirect_uri='http://localhost'
        )
        
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        print(f"🔗 Перейдите по ссылке: {auth_url}")
        auth_code = input("Введите код авторизации: ")
        
        flow.fetch_token(code=auth_code)
        credentials = flow.credentials
        
        # Конвертируем в base64
        token_data = pickle.dumps(credentials)
        token_base64 = base64.b64encode(token_data).decode('utf-8')
        
        print("✅ Google OAuth настроен!")
        return token_base64
        
    except Exception as e:
        print(f"❌ Ошибка настройки OAuth: {e}")
        return None

def setup_cookies():
    """Настройка cookies для YouTube"""
    print("🍪 Настройка cookies для YouTube...")
    print("Cookies помогают:")
    print("- Скачивать возрастные видео")
    print("- Обходить региональные ограничения")
    print("- Получать доступ к приватным видео")
    print("- Избегать блокировок YouTube")
    
    use_cookies = input("Хотите настроить cookies? (y/n): ").lower().strip()
    
    if use_cookies in ['y', 'yes', 'да', 'д']:
        print("\nДля получения cookies:")
        print("1. Откройте YouTube в браузере и войдите в аккаунт")
        print("2. Установите расширение 'Get cookies.txt LOCALLY'")
        print("3. Экспортируйте cookies в формате Netscape")
        print("4. Скопируйте содержимое файла")
        print("\nВставьте содержимое cookies.txt (для завершения введите 'END'):")
        
        cookies_lines = []
        while True:
            line = input()
            if line.strip().upper() == "END":
                break
            cookies_lines.append(line)
        
        if cookies_lines:
            # Сохраняем cookies
            with open('cookies.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(cookies_lines))
            
            # Проверяем качество cookies
            youtube_cookies = sum(1 for line in cookies_lines if 'youtube.com' in line or 'google.com' in line)
            
            print(f"✅ Cookies сохранены! ({len(cookies_lines)} строк)")
            print(f"🎥 YouTube cookies: {youtube_cookies}")
            
            if youtube_cookies > 0:
                print("✅ Можно скачивать приватные видео!")
                return True
            else:
                print("⚠️ YouTube cookies не найдены")
                return False
        else:
            print("❌ Cookies не введены")
            # Создаем пустой файл
            with open('cookies.txt', 'w') as f:
                f.write('# No cookies\n')
            return False
    else:
        print("⏭️ Пропускаем настройку cookies")
        # Создаем пустой файл для совместимости
        with open('cookies.txt', 'w') as f:
            f.write('# No cookies\n')
        return False

def test_setup():
    """Тестирование настройки"""
    print("🧪 Тестирование настройки...")
    
    try:
        # Проверяем импорты
        from youtube_downloader import YouTubeDownloader
        from video_editor import VideoEditor
        from subtitle_generator import SubtitleGenerator
        from google_drive_uploader import GoogleDriveUploader
        from video_processor import VideoProcessor
        
        # Создаем объекты
        downloader = YouTubeDownloader()
        editor = VideoEditor()
        subtitle_gen = SubtitleGenerator()
        uploader = GoogleDriveUploader()
        processor = VideoProcessor()
        
        print("✅ Все компоненты работают!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        return False

def main():
    """Основная функция настройки"""
    print("🎬 Настройка YouTube Video Bot для Google Colab")
    print("=" * 50)
    
    # Шаг 1: Установка зависимостей
    install_dependencies()
    
    # Шаг 2: Настройка окружения
    setup_environment()
    
    # Шаг 3: Получение токенов
    telegram_token = input("Введите Telegram Bot Token: ")
    
    if not telegram_token:
        print("❌ Telegram токен обязателен!")
        return
    
    google_token = setup_google_oauth()
    
    if not google_token:
        print("❌ Не удалось настроить Google OAuth!")
        return
    
    # Шаг 4: Настройка cookies
    cookies_enabled = setup_cookies()
    
    # Шаг 5: Создание .env файла
    create_env_file(telegram_token, google_token)
    
    # Шаг 6: Тестирование
    if test_setup():
        print("\n🎉 Настройка завершена успешно!")
        print("🚀 Теперь можно запускать бота:")
        print("   python bot.py")
    else:
        print("\n❌ Настройка завершена с ошибками")
        print("🔧 Проверьте логи и повторите настройку")

if __name__ == "__main__":
    main()