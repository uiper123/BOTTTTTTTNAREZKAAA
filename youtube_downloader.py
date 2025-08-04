import os
import asyncio
import logging
import yt_dlp
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

class YouTubeDownloader:
    """
    Универсальный загрузчик видео с поддержкой множества платформ через yt-dlp:
    - YouTube
    - Rutube (все типы: видео, каналы, плейлисты, фильмы)
    - VK Video
    - Twitch
    - И многие другие (более 1000 сайтов)
    """
    def __init__(self):
        self.temp_dir = Path("temp")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def download(self, url: str, use_cookies: bool = False) -> dict:
        """
        Скачивание видео с поддерживаемых платформ - раздельно видео и аудио с объединением
        
        Поддерживаемые платформы включают:
        - YouTube (youtube.com, youtu.be)
        - Rutube (rutube.ru) - видео, каналы, плейлисты, фильмы
        - VK Video
        - Twitch
        - И более 1000 других сайтов
        
        Args:
            url: URL видео с любой поддерживаемой платформы
            use_cookies: Использовать cookies для авторизации
        """
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
            # Базовые настройки для yt-dlp с обходом блокировок
            base_opts = {
                'noplaylist': True,
                'extract_flat': False,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
                # Обход блокировок YouTube - более агрессивные настройки
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web', 'ios', 'mweb'],
                        'player_skip': ['webpage', 'configs'],
                        'skip': ['hls', 'dash'],
                        'innertube_host': 'studio.youtube.com',
                        'innertube_key': 'AIzaSyBUPetSUmoZL-OhlxA7wSac5XinrygCqMo'
                    }
                },
                # Дополнительные заголовки для обхода блокировок
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Accept-Encoding': 'gzip,deflate',
                    'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                    'Keep-Alive': '300',
                    'Connection': 'keep-alive',
                },
                # Настройки для обхода ограничений
                'sleep_interval': 1,
                'max_sleep_interval': 5,
                'sleep_interval_requests': 1,
                'retries': 5,
                'fragment_retries': 5,
                'skip_unavailable_fragments': True,
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
                
                # Логируем информацию о языках аудиодорожек
                for i, af in enumerate(audio_formats[:5]):  # Показываем первые 5
                    lang = af.get('language', 'неизвестно')
                    abr = af.get('abr', af.get('tbr', 'неизвестно'))
                    logger.info(f"Аудио {i+1}: язык={lang}, битрейт={abr}, формат={af.get('ext', 'неизвестно')}")
                
                if not video_formats or not audio_formats:
                    logger.warning("Не найдены отдельные видео или аудио потоки, пробуем альтернативные методы")
                    # Сначала пробуем альтернативные методы
                    alt_result = self._try_alternative_methods(url, safe_title, title, duration)
                    if alt_result['success']:
                        return alt_result
                    # Если альтернативные методы не сработали, пробуем комбинированный формат
                    return self._download_combined_format(url, base_opts, safe_title, title, duration)
                
                # Выбираем лучшее качество видео (приоритет 4K/1440p/1080p)
                def video_quality_key(x):
                    height = x.get('height') or 0
                    width = x.get('width') or 0
                    tbr = x.get('tbr') or 0
                    fps = x.get('fps') or 30
                    vcodec = x.get('vcodec', '')
                    
                    # Бонус за высокое разрешение
                    resolution_bonus = height * width
                    
                    # Бонус за высокий битрейт
                    bitrate_bonus = tbr * 10
                    
                    # Бонус за высокий FPS (60fps лучше 30fps)
                    fps_bonus = fps * 100
                    
                    # Бонус за лучшие кодеки
                    codec_bonus = 0
                    if 'vp9' in vcodec.lower():
                        codec_bonus = 50000  # VP9 - лучший кодек
                    elif 'h264' in vcodec.lower() or 'avc' in vcodec.lower():
                        codec_bonus = 30000  # H.264 - хороший кодек
                    
                    return (resolution_bonus + bitrate_bonus + fps_bonus + codec_bonus, height, tbr)
                
                best_video = max(video_formats, key=video_quality_key)
                
                # Выбираем лучшее качество аудио с приоритетом русского языка
                def audio_quality_key(x):
                    abr = x.get('abr') or x.get('tbr') or 0
                    acodec = x.get('acodec', '').lower()
                    ext = x.get('ext', '').lower()
                    
                    # Бонус за высокий битрейт (приоритет качеству)
                    bitrate_bonus = abr * 100
                    
                    # Бонус за лучшие аудио кодеки
                    codec_bonus = 0
                    if 'opus' in acodec:
                        codec_bonus = 10000  # Opus - лучший кодек для качества
                    elif 'aac' in acodec:
                        codec_bonus = 8000   # AAC - хороший кодек
                    elif 'mp3' in acodec:
                        codec_bonus = 5000   # MP3 - стандартный
                    
                    # Бонус за лучшие форматы контейнеров
                    format_bonus = 0
                    if ext == 'm4a':
                        format_bonus = 1000  # M4A - лучший контейнер для AAC
                    elif ext == 'webm':
                        format_bonus = 800   # WebM - хорош для Opus
                    elif ext == 'mp3':
                        format_bonus = 500   # MP3 - стандартный
                    
                    # ПРИОРИТЕТ РУССКОГО ЯЗЫКА
                    lang = x.get('language', '').lower()
                    lang_code = x.get('language_preference', 0)
                    
                    # Бонус за русский язык
                    russian_bonus = 0
                    if 'ru' in lang or 'rus' in lang or lang_code == 1:
                        russian_bonus = 100000  # МАКСИМАЛЬНЫЙ бонус за русский
                    elif lang == '' or lang == 'und':
                        russian_bonus = 50000   # Средний бонус за неопределенный (часто основной)
                    
                    return (russian_bonus + bitrate_bonus + codec_bonus + format_bonus, abr, codec_bonus)
                
                best_audio = max(audio_formats, key=audio_quality_key)
                
                logger.info(f"🎥 ВЫБРАНО ВИДЕО МАКСИМАЛЬНОГО КАЧЕСТВА:")
                logger.info(f"   📺 Формат: {best_video.get('format_id')}")
                logger.info(f"   📐 Разрешение: {best_video.get('width')}x{best_video.get('height')} ({best_video.get('height')}p)")
                logger.info(f"   🎞️  FPS: {best_video.get('fps', 'неизвестно')}")
                logger.info(f"   💾 Битрейт: {best_video.get('tbr', 'неизвестно')} kbps")
                logger.info(f"   🔧 Кодек: {best_video.get('vcodec', 'неизвестно')}")
                logger.info(f"   📦 Контейнер: {best_video.get('ext')}")
                
                logger.info(f"🎵 ВЫБРАНО АУДИО МАКСИМАЛЬНОГО КАЧЕСТВА:")
                logger.info(f"   🎤 Формат: {best_audio.get('format_id')}")
                logger.info(f"   🔊 Битрейт: {best_audio.get('abr', 'неизвестно')} kbps")
                logger.info(f"   🔧 Кодек: {best_audio.get('acodec', 'неизвестно')}")
                logger.info(f"   📦 Контейнер: {best_audio.get('ext')}")
                logger.info(f"   🌍 Язык: {best_audio.get('language', 'неизвестно')}")
                
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
            logger.error(f"Ошибка основного метода скачивания: {e}")
            
            # Если основной метод не сработал, пробуем альтернативные методы
            try:
                # Получаем базовую информацию о видео для альтернативных методов
                with yt_dlp.YoutubeDL({'noplaylist': True}) as ydl:
                    info = ydl.extract_info(url, download=False)
                    title = info.get('title', 'video')
                    duration = info.get('duration', 0)
                    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
                
                logger.info("Основной метод не сработал, пробуем альтернативные...")
                alt_result = self._try_alternative_methods(url, safe_title, title, duration)
                if alt_result['success']:
                    return alt_result
                    
            except Exception as e2:
                logger.error(f"Альтернативные методы тоже не сработали: {e2}")
            
            return {'success': False, 'error': str(e)}
    
    def _try_alternative_methods(self, url: str, safe_title: str, title: str, duration: int) -> dict:
        """Альтернативные методы скачивания для проблемных видео"""
        logger.info("Пробуем альтернативные методы скачивания...")
        
        # Метод 1: Только Android клиент
        android_opts = {
            'noplaylist': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'player_skip': ['webpage'],
                }
            },
            'format': 'best[ext=mp4]/best',
            'outtmpl': str(self.temp_dir / f"{safe_title}_android.%(ext)s"),
            'http_headers': {
                'User-Agent': 'com.google.android.youtube/17.36.4 (Linux; U; Android 12; GB) gzip',
            },
        }
        
        try:
            logger.info("Пробуем Android клиент...")
            with yt_dlp.YoutubeDL(android_opts) as ydl:
                ydl.download([url])
            
            video_files = list(self.temp_dir.glob(f"{safe_title}_android.*"))
            if video_files:
                return {
                    'success': True,
                    'video_path': str(video_files[0]),
                    'title': title,
                    'duration': duration
                }
        except Exception as e:
            logger.warning(f"Android клиент не сработал: {e}")
        
        # Метод 2: iOS клиент
        ios_opts = {
            'noplaylist': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios'],
                    'player_skip': ['webpage'],
                }
            },
            'format': 'best[ext=mp4]/best',
            'outtmpl': str(self.temp_dir / f"{safe_title}_ios.%(ext)s"),
            'http_headers': {
                'User-Agent': 'com.google.ios.youtube/17.36.4 (iPhone14,3; U; CPU iOS 15_6 like Mac OS X)',
            },
        }
        
        try:
            logger.info("Пробуем iOS клиент...")
            with yt_dlp.YoutubeDL(ios_opts) as ydl:
                ydl.download([url])
            
            video_files = list(self.temp_dir.glob(f"{safe_title}_ios.*"))
            if video_files:
                return {
                    'success': True,
                    'video_path': str(video_files[0]),
                    'title': title,
                    'duration': duration
                }
        except Exception as e:
            logger.warning(f"iOS клиент не сработал: {e}")
        
        # Метод 3: Embed метод
        embed_opts = {
            'noplaylist': True,
            'extract_flat': False,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web'],
                    'player_skip': ['configs'],
                }
            },
            'format': 'worst[ext=mp4]/worst',  # Берем худшее качество, но рабочее
            'outtmpl': str(self.temp_dir / f"{safe_title}_embed.%(ext)s"),
        }
        
        # Пробуем embed URL
        embed_url = url.replace('watch?v=', 'embed/').replace('youtu.be/', 'youtube.com/embed/')
        
        try:
            logger.info("Пробуем embed метод...")
            with yt_dlp.YoutubeDL(embed_opts) as ydl:
                ydl.download([embed_url])
            
            video_files = list(self.temp_dir.glob(f"{safe_title}_embed.*"))
            if video_files:
                return {
                    'success': True,
                    'video_path': str(video_files[0]),
                    'title': title,
                    'duration': duration
                }
        except Exception as e:
            logger.warning(f"Embed метод не сработал: {e}")
        
        return {'success': False, 'error': 'Все альтернативные методы не сработали'}

    def _download_combined_format(self, url: str, base_opts: dict, safe_title: str, title: str, duration: int) -> dict:
        """Fallback метод для скачивания комбинированного формата"""
        try:
            logger.info("Используем комбинированный формат...")
            
            # Настройки для комбинированного скачивания
            combined_opts = base_opts.copy()
            combined_opts.update({
                'format': (
                    # МАКСИМАЛЬНОЕ КАЧЕСТВО: сначала пробуем 4K и выше
                    'best[height>=2160][ext=mp4]/best[height>=2160]/'
                    # Затем 1440p (2K)
                    'best[height>=1440][height<2160][ext=mp4]/best[height>=1440][height<2160]/'
                    # Затем 1080p Full HD
                    'best[height>=1080][height<1440][ext=mp4]/best[height>=1080][height<1440]/'
                    # 720p HD
                    'best[height>=720][height<1080][ext=mp4]/best[height>=720][height<1080]/'
                    # SD форматы как fallback
                    'best[height>=480][ext=mp4]/best[height>=480]/'
                    # Любые доступные с приоритетом MP4
                    'best[ext=mp4]/best'
                ),
                'outtmpl': str(self.temp_dir / f"{safe_title}.%(ext)s"),
                'merge_output_format': 'mp4',
                # Дополнительные настройки качества
                'writesubtitles': False,  # Не скачиваем субтитры для скорости
                'writeautomaticsub': False,
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }],
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
        """Скачивание с использованием cookies для различных платформ"""
        if not os.path.exists(cookies_file):
            logger.warning(f"Файл cookies не найден: {cookies_file}")
            return self.download(url, use_cookies=False)
        
        # Проверяем что cookies файл не пустой
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content or content == '# No cookies':
                    logger.info("Cookies файл пустой, скачиваем без cookies")
                    return self.download(url, use_cookies=False)
                
                # Определяем платформу по URL и проверяем соответствующие cookies
                url_lower = url.lower()
                platform_detected = False
                
                if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
                    if 'youtube.com' in content or 'google.com' in content:
                        logger.info("Найдены YouTube cookies, используем их для скачивания")
                        platform_detected = True
                elif 'rutube.ru' in url_lower:
                    if 'rutube.ru' in content:
                        logger.info("Найдены Rutube cookies, используем их для скачивания")
                        platform_detected = True
                elif 'vk.com' in url_lower or 'vk.ru' in url_lower:
                    if 'vk.com' in content or 'vk.ru' in content:
                        logger.info("Найдены VK cookies, используем их для скачивания")
                        platform_detected = True
                elif 'twitch.tv' in url_lower:
                    if 'twitch.tv' in content:
                        logger.info("Найдены Twitch cookies, используем их для скачивания")
                        platform_detected = True
                
                if platform_detected:
                    return self.download(url, use_cookies=True)
                else:
                    logger.info("Соответствующие cookies не найдены, скачиваем без cookies")
                    return self.download(url, use_cookies=False)
                    
        except Exception as e:
            logger.error(f"Ошибка чтения cookies файла: {e}")
            return self.download(url, use_cookies=False)