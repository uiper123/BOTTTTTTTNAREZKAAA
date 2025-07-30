import os
import asyncio
import logging
from pathlib import Path
from youtube_downloader import YouTubeDownloader
from video_editor import VideoEditor
from subtitle_generator import SubtitleGenerator
from google_drive_uploader import GoogleDriveUploader

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self):
        self.youtube_downloader = YouTubeDownloader()
        self.video_editor = VideoEditor()
        self.subtitle_generator = SubtitleGenerator()
        self.drive_uploader = GoogleDriveUploader()
        
        # Создаем рабочие директории
        self.temp_dir = Path("temp")
        self.output_dir = Path("output")
        self.temp_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)
    
    async def process_youtube_video(self, url: str, config: dict) -> dict:
        """Обработка YouTube видео"""
        try:
            # 1. Скачиваем видео
            logger.info(f"Скачивание YouTube видео: {url}")
            download_result = await self.youtube_downloader.download(url)
            
            if not download_result['success']:
                return {'success': False, 'error': download_result['error']}
            
            video_path = download_result['video_path']
            
            # 2. Обрабатываем видео
            result = await self.process_video_file(video_path, config)
            
            # 3. Удаляем скачанное видео
            if os.path.exists(video_path):
                os.remove(video_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обработки YouTube видео: {e}")
            return {'success': False, 'error': str(e)}
    
    async def process_video_file(self, video_path: str, config: dict) -> dict:
        """Обработка видео файла"""
        try:
            duration = config.get('duration', 30)
            
            # 1. Получаем информацию о видео
            video_info = self.video_editor.get_video_info(video_path)
            total_duration = video_info['duration']
            
            logger.info(f"Обработка видео длительностью {total_duration} секунд")
            
            # 2. Если видео больше 5 минут, нарезаем на чанки
            chunks = []
            if total_duration > 300:  # 5 минут
                chunks = await self.split_into_chunks(video_path, chunk_duration=300)
            else:
                chunks = [video_path]
            
            # 3. Обрабатываем каждый чанк
            all_clips = []
            for i, chunk_path in enumerate(chunks):
                logger.info(f"Обработка чанка {i+1}/{len(chunks)}")
                
                # Генерируем субтитры для чанка
                subtitles = await self.subtitle_generator.generate(chunk_path)
                
                # Нарезаем чанк на клипы
                clips = await self.video_editor.create_clips(
                    chunk_path, 
                    duration, 
                    subtitles,
                    start_index=len(all_clips),
                    config=config
                )
                
                all_clips.extend(clips)
                
                # Удаляем временный чанк (если это не оригинальный файл)
                if chunk_path != video_path and os.path.exists(chunk_path):
                    os.remove(chunk_path)
            
            # 4. Ждем завершения записи всех файлов
            import time
            logger.info("Ожидание завершения записи файлов...")
            time.sleep(3)  # Даем время на завершение записи
            
            # 5. Загружаем все клипы на Google Drive
            logger.info(f"Загрузка {len(all_clips)} клипов на Google Drive")
            upload_results = await self.drive_uploader.upload_clips(all_clips)
            
            # 5. Создаем файл со ссылками
            links_file = await self.create_links_file(upload_results)
            
            # 6. Очищаем временные файлы ТОЛЬКО после успешной загрузки
            successful_uploads = sum(1 for r in upload_results if r.get('success', False))
            if successful_uploads > 0:
                logger.info(f"Успешно загружено {successful_uploads}/{len(all_clips)} клипов, очищаем файлы")
                # Удаляем только успешно загруженные файлы
                self.cleanup_successful_files(all_clips, upload_results)
            else:
                logger.warning("Ни один клип не был загружен, файлы сохранены для повторной попытки")
            
            return {
                'success': True,
                'total_clips': len(all_clips),
                'links_file': links_file,
                'upload_results': upload_results
            }
            
        except Exception as e:
            logger.error(f"Ошибка обработки видео: {e}")
            return {'success': False, 'error': str(e)}
    
    async def split_into_chunks(self, video_path: str, chunk_duration: int = 300) -> list:
        """Нарезка видео на чанки по 5 минут"""
        try:
            video_info = self.video_editor.get_video_info(video_path)
            total_duration = video_info['duration']
            
            chunks = []
            start_time = 0
            chunk_index = 0
            
            while start_time < total_duration:
                end_time = min(start_time + chunk_duration, total_duration)
                
                chunk_path = self.temp_dir / f"chunk_{chunk_index}.mp4"
                
                # Вырезаем чанк
                success = await self.video_editor.extract_segment(
                    video_path, 
                    str(chunk_path), 
                    start_time, 
                    end_time - start_time
                )
                
                if success:
                    chunks.append(str(chunk_path))
                    chunk_index += 1
                
                start_time = end_time
            
            logger.info(f"Создано {len(chunks)} чанков")
            return chunks
            
        except Exception as e:
            logger.error(f"Ошибка нарезки на чанки: {e}")
            return [video_path]  # Возвращаем оригинальный файл
    
    async def create_links_file(self, upload_results: list) -> str:
        """Создание файла со ссылками на скачивание"""
        try:
            links_file = self.output_dir / "video_links.txt"
            
            with open(links_file, 'w', encoding='utf-8') as f:
                f.write("🎬 ССЫЛКИ НА СКАЧИВАНИЕ ШОТСОВ\n")
                f.write("=" * 50 + "\n\n")
                
                for i, result in enumerate(upload_results, 1):
                    if result['success']:
                        f.write(f"Фрагмент {i:03d}: {result['download_url']}\n")
                
                f.write(f"\n📊 Всего создано: {len(upload_results)} шотсов\n")
                f.write(f"✅ Успешно загружено: {sum(1 for r in upload_results if r['success'])}\n")
            
            return str(links_file)
            
        except Exception as e:
            logger.error(f"Ошибка создания файла ссылок: {e}")
            return None
    
    def cleanup_successful_files(self, clip_paths: list, upload_results: list):
        """Очистка только успешно загруженных файлов"""
        try:
            import time
            import gc
            
            # Принудительная сборка мусора для освобождения файловых дескрипторов
            gc.collect()
            
            # Небольшая задержка для завершения всех операций с файлами
            time.sleep(2)  # Увеличиваем задержку
            
            # Удаляем только файлы, которые успешно загрузились
            for i, clip_path in enumerate(clip_paths):
                try:
                    # Проверяем, был ли этот клип успешно загружен
                    if i < len(upload_results) and upload_results[i].get('success', False):
                        if os.path.exists(clip_path):
                            # Пытаемся удалить файл несколько раз
                            for attempt in range(5):  # Больше попыток
                                try:
                                    os.remove(clip_path)
                                    logger.info(f"Удален успешно загруженный файл: {clip_path}")
                                    break
                                except PermissionError:
                                    if attempt < 4:
                                        time.sleep(1)  # Больше времени между попытками
                                        continue
                                    else:
                                        logger.warning(f"Не удалось удалить файл {clip_path} - файл занят, оставляем для ручного удаления")
                    else:
                        logger.info(f"Файл {clip_path} не был загружен, сохраняем для повторной попытки")
                        
                except Exception as e:
                    logger.warning(f"Ошибка удаления файла {clip_path}: {e}")
            
            # Очищаем временную директорию от вспомогательных файлов
            for file in self.temp_dir.glob("*"):
                try:
                    if file.is_file() and not file.name.startswith('clip_'):
                        file.unlink()
                except Exception as e:
                    logger.warning(f"Ошибка удаления временного файла {file}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки успешно загруженных файлов: {e}")

    def cleanup_temp_files(self, clip_paths: list):
        """Очистка всех временных файлов (используется при ошибках)"""
        try:
            import time
            import gc
            
            # Принудительная сборка мусора для освобождения файловых дескрипторов
            gc.collect()
            
            # Небольшая задержка для завершения всех операций с файлами
            time.sleep(1)
            
            for clip_path in clip_paths:
                try:
                    if os.path.exists(clip_path):
                        # Пытаемся удалить файл несколько раз
                        for attempt in range(3):
                            try:
                                os.remove(clip_path)
                                break
                            except PermissionError:
                                if attempt < 2:
                                    time.sleep(0.5)
                                    continue
                                else:
                                    logger.warning(f"Не удалось удалить файл {clip_path} - файл занят")
                except Exception as e:
                    logger.warning(f"Ошибка удаления файла {clip_path}: {e}")
            
            # Очищаем временную директорию
            for file in self.temp_dir.glob("*"):
                try:
                    if file.is_file():
                        file.unlink()
                except Exception as e:
                    logger.warning(f"Ошибка удаления временного файла {file}: {e}")
                    
        except Exception as e:
            logger.error(f"Ошибка очистки временных файлов: {e}")