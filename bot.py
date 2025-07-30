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
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        await update.message.reply_text(
            "Привет! Я бот для нарезки видео на шотсы.\n\n"
            "Отправь мне:\n"
            "• Ссылку на YouTube видео\n"
            "• Видео файл\n\n"
            "Команды:\n"
            "/duration <секунды> - установить длительность шотсов (по умолчанию 30 сек)\n"
            "/title <заголовок> - установить заголовок\n"
            "/subtitle <подзаголовок> - установить подзаголовок\n"
            "/cookies - установить cookies для доступа к приватным видео"
        )
    
    async def set_duration(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка длительности шотсов"""
        try:
            duration = int(context.args[0])
            context.user_data['duration'] = duration
            await update.message.reply_text(f"Длительность шотсов установлена: {duration} секунд")
        except (IndexError, ValueError):
            await update.message.reply_text("Использование: /duration <секунды>")
    
    async def set_title(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка заголовка"""
        if context.args:
            title = ' '.join(context.args)
            context.user_data['title'] = title
            await update.message.reply_text(f"Заголовок установлен: {title}")
        else:
            await update.message.reply_text("Использование: /title <текст заголовка>")
    
    async def set_subtitle(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка подзаголовка"""
        if context.args:
            subtitle = ' '.join(context.args)
            context.user_data['subtitle'] = subtitle
            await update.message.reply_text(f"Подзаголовок установлен: {subtitle}")
        else:
            await update.message.reply_text("Использование: /subtitle <текст подзаголовка>")
    
    async def set_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Установка cookies для yt-dlp"""
        await update.message.reply_text(
            "Отправьте содержимое cookies файла в следующем сообщении.\n\n"
            "Cookies должны быть в формате Netscape или JSON.\n"
            "Например, экспортированные из браузера через расширение."
        )
        context.user_data['waiting_for_cookies'] = True
    
    async def process_cookies(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка cookies файла"""
        try:
            cookies_content = update.message.text
            
            # Сохраняем cookies в файл
            with open('cookies.txt', 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            
            await update.message.reply_text(
                "✅ Cookies файл сохранен!\n"
                "Теперь можно скачивать видео с ограниченным доступом."
            )
            
            # Сбрасываем флаг ожидания
            context.user_data['waiting_for_cookies'] = False
            
        except Exception as e:
            logger.error(f"Ошибка сохранения cookies: {e}")
            await update.message.reply_text(f"❌ Ошибка сохранения cookies: {str(e)}")
            context.user_data['waiting_for_cookies'] = False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка сообщений"""
        message = update.message
        
        # Проверяем, ждем ли мы cookies
        if context.user_data.get('waiting_for_cookies'):
            await self.process_cookies(update, context)
            return
        
        # Проверяем, есть ли видео файл
        if message.video:
            await self.process_video_file(update, context)
        # Проверяем, есть ли ссылка на YouTube
        elif message.text and ('youtube.com' in message.text or 'youtu.be' in message.text):
            await self.process_youtube_url(update, context)
        else:
            await message.reply_text("Отправьте видео файл или ссылку на YouTube")
    
    async def process_video_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка видео файла"""
        await update.message.reply_text("Начинаю обработку видео файла...")
        
        # Получаем параметры пользователя
        duration = context.user_data.get('duration', 30)
        title = context.user_data.get('title', 'Заголовок')
        subtitle = context.user_data.get('subtitle', 'Подзаголовок')
        
        try:
            # Скачиваем файл
            file = await context.bot.get_file(update.message.video.file_id)
            file_path = f"temp_video_{update.effective_user.id}.mp4"
            await file.download_to_drive(file_path)
            
            # Обрабатываем видео
            result = await self.video_processor.process_video(
                file_path, duration, title, subtitle, update.effective_user.id
            )
            
            if result['success']:
                await update.message.reply_text(
                    f"Обработка завершена!\n"
                    f"Создано {result['clips_count']} клипов\n"
                    f"Ссылка на файл со ссылками: {result['links_file']}"
                )
            else:
                await update.message.reply_text(f"Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки видео: {e}")
            await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    
    async def process_youtube_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка ссылки YouTube"""
        await update.message.reply_text("Начинаю скачивание и обработку YouTube видео...")
        
        # Получаем параметры пользователя
        duration = context.user_data.get('duration', 30)
        title = context.user_data.get('title', 'Заголовок')
        subtitle = context.user_data.get('subtitle', 'Подзаголовок')
        
        try:
            result = await self.video_processor.process_youtube_video(
                update.message.text, duration, title, subtitle, update.effective_user.id
            )
            
            if result['success']:
                await update.message.reply_text(
                    f"Обработка завершена!\n"
                    f"Создано {result['clips_count']} клипов\n"
                    f"Ссылка на файл со ссылками: {result['links_file']}"
                )
            else:
                await update.message.reply_text(f"Ошибка: {result['error']}")
                
        except Exception as e:
            logger.error(f"Ошибка обработки YouTube: {e}")
            await update.message.reply_text(f"Произошла ошибка: {str(e)}")
    
    def run(self):
        """Запуск бота"""
        application = Application.builder().token(self.token).build()
        
        # Добавляем обработчики
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("duration", self.set_duration))
        application.add_handler(CommandHandler("title", self.set_title))
        application.add_handler(CommandHandler("subtitle", self.set_subtitle))
        application.add_handler(CommandHandler("cookies", self.set_cookies))
        application.add_handler(MessageHandler(filters.ALL, self.handle_message))
        
        # Запускаем бота
        application.run_polling()

if __name__ == '__main__':
    bot = TelegramBot()
    bot.run()