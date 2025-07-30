import os
import asyncio
import logging
import yt_dlp
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def download(self, url: str, use_cookies: bool = False) -> dict:
        """Скачивание видео с YouTube - раздельно видео и аудио с объединением"""
        try:
            # Запускаем скачивание в отдельном потоке
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, 
                self._download_separate_and_merge, 
                url, 
                use_cookies
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка скачивания YouTube: {e}")
            return {'success': False, 'error': str(e)}
    
    def _download_separate_and_merge(self, url: str, use_cookies: bool = False) -> dict:
        """Скачивание видео и аудио отдельно с последующим объединением"""
        try:
            # Базовые настройки для yt-dlp
            base_opts = {
                'noplaylist': True,
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
            }
            
            # Добавляем cookies если нужно
            if use_cookies and os.path.exists('cookies.txt'):
                base_opts['cookiefile'] = 'cookies.txt'
            
            # Получаем информацию о видео
            with yt_dlp.YoutubeDL(base_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'video')
                duration = info.get('duration', 0)
                
                # Очищаем название для использования в именах файлов
                safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                safe_title = safe_title[:50]  # Ограничиваем длину
                
                logger.info(f"Скачивание: {title} ({duration} сек)")
                
                # Анализируем доступные форматы
                formats = info.get('formats', [])
                
                # Находим лучшее видео (без аудио)
                video_formats = [f for f in formats if 
                               f.get('vcodec') != 'none' and 
                               f.get('acodec') == 'none' and
                               f.get('height')]
                
                # Находим лучшее аудио
                audio_formats = [f for f in formats if 
                               f.get('vcodec') == 'none' and 
                               f.get('acodec') != 'none']
                
                logger.info(f"Найдено видео форматов: {len(video_formats)}")
                logger.info(f"Найдено аудио форматов: {len(audio_formats)}")
                
                if not video_formats or not audio_formats:
                    logger.warning("Не найдены отдельные видео или аудио потоки, используем комбинированный формат")
                    return self._download_combined_format(url, base_opts, safe_title, title, duration)
                
                # Выбираем лучшее качество видео (приоритет HD)
                def video_quality_key(x):
                    height = x.get('height') or 0
                    tbr = x.get('tbr') or 0
                    return (height, tbr)
                
                best_video = max(video_formats, key=video_quality_key)
                
                # Выбираем лучшее качество аудио
                def audio_quality_key(x):
                    abr = x.get('abr') or x.get('tbr') or 0
                    ext_bonus = 1 if x.get('ext') == 'm4a' else 0
                    return (abr, ext_bonus)
                
                best_audio = max(audio_formats, key=audio_quality_key)
                
                logger.info(f"Выбрано видео: {best_video.get('format_id')} "
                           f"({best_video.get('width')}x{best_video.get('height')}, "
                           f"{best_video.get('ext')})")
                logger.info(f"Выбрано аудио: {best_audio.get('format_id')} "
                           f"({best_audio.get('abr', 'unknown')} kbps, "
                           f"{best_audio.get('ext')})")
                
                # Пути для временных файлов - используем более простые имена
                video_temp = self.temp_dir / f"video_{best_video.get('format_id')}.{best_video.get('ext', 'mp4')}"
                audio_temp = self.temp_dir / f"audio_{best_audio.get('format_id')}.{best_audio.get('ext', 'm4a')}"
                final_output = self.temp_dir / f"{safe_title}.mp4"
                
                # СНАЧАЛА скачиваем аудио (для лучшего качества)
                audio_opts = base_opts.copy()
                audio_opts.update({
                    'format': best_audio.get('format_id'),
                    'outtmpl': str(audio_temp),
                    'retries': 3,  # Больше попыток для аудио
                    'fragment_retries': 3,
                })
                
                logger.info(f"Скачивание аудио в: {audio_temp}")
                try:
                    with yt_dlp.YoutubeDL(audio_opts) as ydl:
                        ydl.download([url])
                except Exception as e:
                    logger.error(f"Ошибка скачивания аудио: {e}")
                    # Пробуем другой аудио формат
                    if len(audio_formats) > 1:
                        logger.info("Пробуем альтернативный аудио формат...")
                        # Берем второй лучший аудио формат
                        alt_audio = sorted(audio_formats, key=audio_quality_key, reverse=True)[1]
                        audio_temp_alt = self.temp_dir / f"audio_{alt_audio.get('format_id')}.{alt_audio.get('ext', 'm4a')}"
                        
                        audio_opts_alt = base_opts.copy()
                        audio_opts_alt.update({
                            'format': alt_audio.get('format_id'),
                            'outtmpl': str(audio_temp_alt),
                        })
                        
                        try:
                            with yt_dlp.YoutubeDL(audio_opts_alt) as ydl:
                                ydl.download([url])
                            audio_temp = audio_temp_alt  # Используем альтернативный файл
                            logger.info(f"Успешно скачан альтернативный аудио: {audio_temp}")
                        except Exception as e2:
                            logger.error(f"Альтернативный аудио тоже не скачался: {e2}")
                            return {'success': False, 'error': f'Не удалось скачать аудио: {e}'}
                    else:
                        return {'success': False, 'error': f'Ошибка скачивания аудио: {e}'}
                
                # ПОТОМ скачиваем видео
                video_opts = base_opts.copy()
                video_opts.update({
                    'format': best_video.get('format_id'),
                    'outtmpl': str(video_temp),
                    'retries': 3,
                    'fragment_retries': 3,
                })
                
                logger.info(f"Скачивание видео в: {video_temp}")
                try:
                    with yt_dlp.YoutubeDL(video_opts) as ydl:
                        ydl.download([url])
                except Exception as e:
                    logger.error(f"Ошибка скачивания видео: {e}")
                    # Проверяем, скачался ли файл несмотря на ошибку
                    if not video_temp.exists():
                        # Ищем по паттерну
                        video_pattern = f"video_{best_video.get('format_id')}.*"
                        video_files = list(self.temp_dir.glob(video_pattern))
                        if not video_files:
                            return {'success': False, 'error': f'Ошибка скачивания видео: {e}'}
                        else:
                            video_temp = video_files[0]
                            logger.info(f"Видео файл найден несмотря на ошибку: {video_temp}")
                    else:
                        logger.info("Видео файл скачался успешно несмотря на JSON ошибку")
                
                # Проверяем что файлы скачались и ищем их если имена изменились
                logger.info(f"Проверка файлов...")
                logger.info(f"Содержимое temp папки: {list(self.temp_dir.glob('*'))}")
                
                # Ищем видео файл
                if not video_temp.exists():
                    # Ищем по паттерну
                    video_pattern = f"video_{best_video.get('format_id')}.*"
                    video_files = list(self.temp_dir.glob(video_pattern))
                    if video_files:
                        video_temp = video_files[0]
                        logger.info(f"Найден видео файл: {video_temp}")
                    else:
                        logger.error(f"Видео файл не найден. Ожидался: {video_temp}")
                        return {'success': False, 'error': 'Видео файл не скачался'}
                
                # Ищем аудио файл
                if not audio_temp.exists():
                    # Ищем по паттерну
                    audio_pattern = f"audio_{best_audio.get('format_id')}.*"
                    audio_files = list(self.temp_dir.glob(audio_pattern))
                    if audio_files:
                        audio_temp = audio_files[0]
                        logger.info(f"Найден аудио файл: {audio_temp}")
                    else:
                        logger.error(f"Аудио файл не найден. Ожидался: {audio_temp}")
                        return {'success': False, 'error': 'Аудио файл не скачался'}
                
                # Объединяем с помощью FFmpeg
                logger.info("Объединение видео и аудио...")
                ffmpeg_cmd = [
                    'ffmpeg', '-y',  # -y для перезаписи
                    '-i', str(video_temp),
                    '-i', str(audio_temp),
                    '-c:v', 'copy',  # Копируем видео без перекодирования
                    '-c:a', 'aac',   # Перекодируем аудио в AAC если нужно
                    '-shortest',     # Обрезаем по самому короткому потоку
                    str(final_output)
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    logger.error(f"Ошибка FFmpeg: {result.stderr}")
                    return {'success': False, 'error': f'Ошибка объединения: {result.stderr}'}
                
                # Удаляем временные файлы
                try:
                    video_temp.unlink()
                    audio_temp.unlink()
                except:
                    pass  # Игнорируем ошибки удаления
                
                if not final_output.exists():
                    return {'success': False, 'error': 'Итоговый файл не создался'}
                
                logger.info(f"Успешно скачано и объединено: {final_output}")
                
                return {
                    'success': True,
                    'video_path': str(final_output),
                    'title': title,
                    'duration': duration
                }
                
        except Exception as e:
            logger.error(f"Ошибка скачивания и объединения: {e}")
            return {'success': False, 'error': str(e)}
    
    def _download_combined_format(self, url: str, base_opts: dict, safe_title: str, title: str, duration: int) -> dict:
        """Fallback метод для скачивания комбинированного формата"""
        try:
            logger.info("Используем комбинированный формат...")
            
            # Настройки для комбинированного скачивания
            combined_opts = base_opts.copy()
            combined_opts.update({
                'format': (
                    # Сначала пробуем лучшие HD форматы
                    'best[height>=720][height<=1080][ext=mp4]/'
                    'best[height>=720][height<=1080]/'
                    # Затем любые HD
                    'best[height>=720]/'
                    # SD форматы
                    'best[height>=480][ext=mp4]/'
                    'best[height>=480]/'
                    # Любые доступные
                    'best[ext=mp4]/'
                    'best'
                ),
                'outtmpl': str(self.temp_dir / f"{safe_title}.%(ext)s"),
                'merge_output_format': 'mp4',
            })
            
            logger.info("Скачивание комбинированного формата...")
            with yt_dlp.YoutubeDL(combined_opts) as ydl:
                ydl.download([url])
            
            # Ищем скачанный файл
            video_files = list(self.temp_dir.glob(f"{safe_title}.*"))
            video_files = [f for f in video_files if f.suffix in ['.mp4', '.mkv', '.webm']]
            
            if not video_files:
                return {'success': False, 'error': 'Комбинированный файл не найден после скачивания'}
            
            # Берем первый найденный файл
            video_path = str(video_files[0])
            
            logger.info(f"Успешно скачан комбинированный формат: {video_path}")
            
            return {
                'success': True,
                'video_path': video_path,
                'title': title,
                'duration': duration
            }
            
        except Exception as e:
            logger.error(f"Ошибка скачивания комбинированного формата: {e}")
            return {'success': False, 'error': str(e)}
    
    def download_with_cookies(self, url: str, cookies_file: str = 'cookies.txt') -> dict:
        """Скачивание с использованием cookies"""
        if not os.path.exists(cookies_file):
            logger.warning(f"Файл cookies не найден: {cookies_file}")
            return self.download(url, use_cookies=False)
        
        return self.download(url, use_cookies=True)