import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from video_processor import VideoProcessor

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.video_processor = VideoProcessor()
        self.user_settings = {}  # Хранение настроек пользователей
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user_id = update.effective_user.id
        self.user_settings[user_id] = {
            'duration': 30,
            'title': 'ФРАГМЕНТ',
            'subtitle': 'Часть'
        }  # Настройки по умолчанию
        
        await update.message.reply_text(
            "🎬 Привет! Я бот для нарезки видео на шотсы.\n\n"
            "📝 Команды:\n"
            "/start - Начать работу\n"
            "/duration <секунды> - Установить длительность шотсов (по умолчанию 30 сек)\n"
            "/title <текст> - Установить заголовок (по умолчанию 'ФРАГМЕНТ')\n"
            "/subtitle <текст> - Установить подзаголовок (по умолчанию 'Часть')\n"
            "/settings - Показать текущие настройки\n"
            "/help - Помощь\n\n"
            "📹 Отправь мне:\n"
            "• Ссылку на YouTube видео\n"
            "• Видео файл\n\n"
            "Я нарежу его на шотсы и загружу на Google Drive!"
        )
    
    async def set_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /duration для установки длительности шотсов"""
        user_id = update.effective_user.id
        
        if not context.args:
            current_duration = self.user_settings.get(user_id, {}).get('duration', 30)
            await update.message.reply_text(f"⏱ Текущая длительность: {current_duration} секунд")
            return
            
        try:
            duration = int(context.args[0])
            if duration < 5 or duration > 300:
                await update.message.reply_text("⚠️ Длительность должна быть от 5 до 300 секунд")
                return
                
            if user_id not in self.user_settings:
                self.user_settings[user_id] = {}
            self.user_settings[user_id]['duration'] = duration
            
            await update.message.reply_text(f"✅ Длительность установлена: {duration} секунд")
            
        except ValueError:
            await update.message.reply_text("⚠️ Введите число секунд")
    
    async def set_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /title для установки заголовка"""
        user_id = update.effective_user.id
        
        if not context.args:
            current_title = self.user_settings.get(user_id, {}).get('title', 'ФРАГМЕНТ')
            await update.message.reply_text(f"📝 Текущий заголовок: '{current_title}'")
            return
        
        title = ' '.join(context.args)
        if len(title) > 50:
            await update.message.reply_text("⚠️ Заголовок слишком длинный (максимум 50 символов)")
            return
        
        # Инициализируем настройки пользователя если их нет
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'duration': 30,
                'title': 'ФРАГМЕНТ',
                'subtitle': 'Часть'
            }
        
        self.user_settings[user_id]['title'] = title
        self.user_settings[user_id]['custom_title'] = True  # Флаг что заголовок пользовательский
        
        await update.message.reply_text(f"✅ Заголовок установлен: '{title}'")
    
    async def set_subtitle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /subtitle для установки подзаголовка"""
        user_id = update.effective_user.id
        
        if not context.args:
            current_subtitle = self.user_settings.get(user_id, {}).get('subtitle', 'Часть')
            await update.message.reply_text(f"📝 Текущий подзаголовок: '{current_subtitle}'")
            return
        
        subtitle = ' '.join(context.args)
        if len(subtitle) > 50:
            await update.message.reply_text("⚠️ Подзаголовок слишком длинный (максимум 50 символов)")
            return
        
        # Инициализируем настройки пользователя если их нет
        if user_id not in self.user_settings:
            self.user_settings[user_id] = {
                'duration': 30,
                'title': 'ФРАГМЕНТ',
                'subtitle': 'Часть'
            }
        
        self.user_settings[user_id]['subtitle'] = subtitle
        self.user_settings[user_id]['custom_subtitle'] = True  # Флаг что подзаголовок пользовательский
        
        await update.message.reply_text(f"✅ Подзаголовок установлен: '{subtitle}'")
    
    async def show_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /settings для показа текущих настроек"""
        user_id = update.effective_user.id
        settings = self.user_settings.get(user_id, {
            'duration': 30,
            'title': 'ФРАГМЕНТ',
            'subtitle': 'Часть'
        })
        
        await update.message.reply_text(
            f"⚙️ Текущие настройки:\n\n"
            f"⏱ Длительность: {settings.get('duration', 30)} секунд\n"
            f"📝 Заголовок: '{settings.get('title', 'ФРАГМЕНТ')}'\n"
            f"📝 Подзаголовок: '{settings.get('subtitle', 'Часть')}'\n\n"
            f"Для изменения используйте команды:\n"
            f"/duration <секунды>\n"
            f"/title <текст>\n"
            f"/subtitle <текст>"
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            "🎬 Бот для нарезки видео на шотсы\n\n"
            "📝 Команды:\n"
            "/duration <секунды> - Длительность шотсов (5-300 сек)\n"
            "/title <текст> - Заголовок (например: 'ЭПИЗОД')\n"
            "/subtitle <текст> - Подзаголовок (например: 'Серия')\n"
            "/settings - Показать текущие настройки\n\n"
            "📹 Как использовать:\n"
            "1. Настройте параметры командами выше\n"
            "2. Отправьте ссылку на YouTube или видео файл\n"
            "3. Дождитесь обработки\n"
            "4. Получите ссылки на готовые шотсы\n\n"
            "⚙️ Особенности:\n"
            "• Субтитры по одному слову с анимацией\n"
            "• Пользовательские заголовки\n"
            "• Высокое качество видео\n"
            "• Автоматическая загрузка на Google Drive\n"
            "• Поддержка больших видео (нарезка на чанки)\n\n"
            "💡 Примеры заголовков:\n"
            "/title УРОК → 'УРОК 1', 'УРОК 2'...\n"
            "/subtitle Глава → 'Глава 1', 'Глава 2'..."
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений"""
        user_id = update.effective_user.id
        message = update.message
        
        # Получаем настройки пользователя
        user_config = self.user_settings.get(user_id, {
            'duration': 30,
            'title': 'ФРАГМЕНТ',
            'subtitle': 'Часть'
        })
        
        if message.text and ('youtube.com' in message.text or 'youtu.be' in message.text):
            # Обработка YouTube ссылки
            await self.process_youtube_url(update, message.text, user_config)
            
        elif message.video:
            # Обработка видео файла
            await self.process_video_file(update, message.video, user_config)
            
        else:
            await update.message.reply_text(
                "⚠️ Отправьте ссылку на YouTube видео или видео файл"
            )
    
    async def process_youtube_url(self, update: Update, url: str, config: dict):
        """Обработка YouTube ссылки"""
        await update.message.reply_text("🔄 Начинаю обработку YouTube видео...")
        
        try:
            # Запускаем обработку видео (автоматически использует cookies если доступны)
            result = await self.video_processor.process_youtube_video(url, config)
            
            if result['success']:
                await self.send_results(update, result)
            else:
                await update.message.reply_text(f"❌ Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки YouTube: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке видео")
    
    async def process_video_file(self, update: Update, video, config: dict):
        """Обработка видео файла"""
        await update.message.reply_text("🔄 Начинаю обработку видео файла...")
        
        try:
            # Скачиваем файл
            file = await video.get_file()
            file_path = f"temp_video_{update.effective_user.id}.mp4"
            await file.download_to_drive(file_path)
            
            # Запускаем обработку
            result = await self.video_processor.process_video_file(file_path, config)
            
            # Удаляем временный файл
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if result['success']:
                await self.send_results(update, result)
            else:
                await update.message.reply_text(f"❌ Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки файла: {e}")
            await update.message.reply_text("❌ Произошла ошибка при обработке видео")
    
    async def send_results(self, update: Update, result: dict):
        """Отправка результатов пользователю"""
        links_file = result.get('links_file')
        total_clips = result.get('total_clips', 0)
        
        await update.message.reply_text(
            f"✅ Обработка завершена!\n"
            f"📊 Создано шотсов: {total_clips}\n"
            f"📁 Все файлы загружены на Google Drive"
        )
        
        if links_file and os.path.exists(links_file):
            # Отправляем файл со ссылками
            with open(links_file, 'rb') as f:
                await update.message.reply_document(
                    document=f,
                    filename="video_links.txt",
                    caption="📋 Ссылки на все созданные шотсы"
                )
    
    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.token).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("duration", self.set_duration))
        application.add_handler(CommandHandler("title", self.set_title))
        application.add_handler(CommandHandler("subtitle", self.set_subtitle))
        application.add_handler(CommandHandler("settings", self.show_settings))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(MessageHandler(filters.TEXT | filters.VIDEO, self.handle_message))
        
        # Запускаем бота
        logger.info("Бот запущен...")
        application.run_polling()

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()