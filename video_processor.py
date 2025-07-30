import os
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
import concurrent.futures
from multiprocessing import cpu_count
import yt_dlp
import whisper
import torch
from google_drive_uploader import GoogleDriveUploader
from video_editor import VideoEditor
import math

class VideoProcessor:
    def __init__(self):
        self.drive_uploader = GoogleDriveUploader()
        self.video_editor = VideoEditor()
        
        # Оптимизация для Colab
        self.max_workers = min(cpu_count(), 8)  # Ограничиваем до 8 потоков
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Загружаем Whisper модель на GPU если доступно
        print(f"Используем устройство: {self.device}")
        print(f"Максимум потоков: {self.max_workers}")
        
        # Используем более быструю модель для Colab
        model_size = "small" if self.device == "cuda" else "tiny"
        self.whisper_model = whisper.load_model(model_size, device=self.device)
        print(f"Загружена Whisper модель: {model_size}")
        
    async def process_video(self, video_path, duration, title, subtitle, user_id):
        """Основная функция обработки видео с параллельной обработкой"""
        temp_dir = f"temp_{user_id}"
        try:
            # Создаем временную директорию для пользователя
            os.makedirs(temp_dir, exist_ok=True)
            
            # Получаем информацию о видео
            video_info = self._get_video_info(video_path)
            video_duration = video_info['duration']
            
            print(f"🎬 Обрабатываем видео длительностью {video_duration:.1f} секунд")
            
            # Умная нарезка на чанки
            chunks = []
            MIN_CHUNKABLE_DURATION = 45 # Не нарезаем видео короче 45 секунд
            
            if video_duration > MIN_CHUNKABLE_DURATION:
                chunks = await self._split_video_to_chunks_parallel(video_path, temp_dir, 180) # Чанки по 3 минуты
            else:
                chunks = [video_path] # Обрабатываем как один чанк
            
            print(f"📦 Создано {len(chunks)} чанков для обработки")
            
            # ПАРАЛЛЕЛЬНАЯ обработка чанков
            all_clips = []
            chunk_tasks = []
            
            # Создаем задачи для параллельной обработки чанков
            for i, chunk_path in enumerate(chunks):
                task = self._process_chunk_parallel(chunk_path, duration, title, subtitle, temp_dir, i)
                chunk_tasks.append(task)
            
            # Выполняем все чанки параллельно
            print(f"🚀 Запускаем параллельную обработку {len(chunk_tasks)} чанков...")
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            # Собираем результаты
            for i, result in enumerate(chunk_results):
                if isinstance(result, Exception):
                    print(f"❌ Ошибка обработки чанка {i}: {result}")
                else:
                    all_clips.extend(result)
                    print(f"✅ Чанк {i+1} обработан: {len(result)} клипов")
            
            print(f"🎯 Всего создано {len(all_clips)} клипов")
            
            # ПАРАЛЛЕЛЬНАЯ загрузка на Google Drive
            uploaded_links_file = await self._upload_clips_to_drive_parallel(all_clips)
            
            # Создаем файл со ссылками
            links_file = await self._create_links_file(uploaded_links_file, user_id)
            
            return {
                'success': True, 
                'clips_count': len(all_clips), 
                'links_file': links_file
            }
            
        except Exception as e:
            print(f"💥 Критическая ошибка в process_video: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            # Гарантированно удаляем временную директорию
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"🧹 Удалена временная директория: {temp_dir}")
    
    async def process_youtube_video(self, url, duration, title, subtitle, user_id):
        """Обработка видео с YouTube"""
        downloaded_video_path = None
        try:
            print("Начинаю скачивание видео с YouTube...")
            downloaded_video_path = await self._download_youtube_video(url, user_id)
            print(f"Видео успешно скачано: {downloaded_video_path}")
            
            # Обрабатываем скачанное видео
            return await self.process_video(
                downloaded_video_path, duration, title, subtitle, user_id
            )
            
        except Exception as e:
            print(f"Ошибка при обработке YouTube видео: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            # Гарантированно удаляем скачанное видео
            if downloaded_video_path and os.path.exists(downloaded_video_path):
                os.remove(downloaded_video_path)
                print(f"Удален временный видеофайл: {downloaded_video_path}")
    
    async def _download_youtube_video(self, url, user_id):
        """Скачивание видео с YouTube с проверкой и fallback'ом"""
        output_template = f"youtube_video_{user_id}.%(ext)s"
        
        # Основные опции скачивания
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_template,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            'quiet': True, # Уменьшаем спам в логах
            'no_warnings': True,
        }
        
        downloaded_filepath = None
        
        try:
            print("Попытка скачивания в лучшем качестве (mp4)...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Получаем реальное имя файла после скачивания
                downloaded_filepath = ydl.prepare_filename(info)

        except Exception as e:
            print(f"⚠️ Первая попытка не удалась: {e}")
            print("Попытка скачивания в любом лучшем качестве (fallback)...")
            ydl_opts['format'] = 'best' # Более простой и надежный формат
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded_filepath = ydl.prepare_filename(info)
            except Exception as fallback_e:
                print(f"❌ Резервный метод скачивания также не удался: {fallback_e}")
                raise Exception("Не удалось скачать видео. Проверьте URL и cookies.") from fallback_e

        # Финальная проверка, существует ли файл
        if not downloaded_filepath or not os.path.exists(downloaded_filepath):
            raise Exception(f"Скачивание завершилось, но итоговый файл не был создан. YouTube может блокировать скачивание (403 Forbidden).")
            
        print(f"✅ Видео успешно сохранено как: {downloaded_filepath}")
        return downloaded_filepath
    
    def _get_video_info(self, video_path):
        """Получение информации о видео"""
        if not os.path.exists(video_path):
            raise Exception(f"Видео файл не найден: {video_path}")
        
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Ошибка ffprobe: {result.stderr}")
            raise Exception(f"Не удалось получить информацию о видео: {result.stderr}")
        
        import json
        try:
            info = json.loads(result.stdout)
            duration = float(info['format']['duration'])
            print(f"Информация о видео получена: длительность {duration} секунд")
            return {'duration': duration}
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise Exception(f"Ошибка парсинга информации о видео: {e}")
    
    async def _split_video_to_chunks_parallel(self, video_path, temp_dir, chunk_duration):
        """ПАРАЛЛЕЛЬНАЯ разбивка видео на чанки"""
        video_info = self._get_video_info(video_path)
        total_duration = video_info['duration']
        
        # Исправленная математика для нарезки
        chunk_count = math.ceil(total_duration / chunk_duration)
        
        print(f"⚡ ПАРАЛЛЕЛЬНАЯ разбивка на {chunk_count} чанков по ~{chunk_duration} секунд")
        
        # Создаем задачи для параллельного создания чанков
        chunk_tasks = []
        for i in range(chunk_count):
            start_time = i * chunk_duration
            # Последний чанк может быть короче
            current_chunk_duration = min(chunk_duration, total_duration - start_time)
            chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp4")
            
            if current_chunk_duration <= 0: continue

            task = self._create_chunk_async(video_path, chunk_path, start_time, current_chunk_duration, i, chunk_count)
            chunk_tasks.append(task)
        
        # Выполняем все задачи параллельно
        chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
        
        # Собираем успешные чанки
        chunks = []
        for i, result in enumerate(chunk_results):
            if isinstance(result, Exception):
                print(f"❌ Ошибка создания чанка {i}: {result}")
            elif result:
                chunks.append(result)
                print(f"✅ Чанк {i+1} создан")
        
        print(f"🎯 Создано {len(chunks)} чанков параллельно")
        return chunks
    
    async def _create_chunk_async(self, video_path, chunk_path, start_time, duration, index, total):
        """Асинхронное создание одного чанка"""
        loop = asyncio.get_event_loop()
        
        def create_chunk():
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ss', str(start_time),
                '-t', str(duration),
                '-c', 'copy',
                chunk_path, '-y',
                '-loglevel', 'error'  # Уменьшаем вывод логов
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                return chunk_path
            else:
                print(f"⚠️ Ошибка создания чанка {index+1}: {result.stderr}")
                return None
        
        # Выполняем в отдельном потоке
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            result = await loop.run_in_executor(executor, create_chunk)
            return result
    
    async def _process_chunk_parallel(self, chunk_path, duration, title, subtitle, temp_dir, chunk_index):
        """ПАРАЛЛЕЛЬНАЯ обработка одного чанка"""
        try:
            print(f"🔄 Обрабатываем чанк {chunk_index+1}...")
            
            # Генерируем субтитры асинхронно
            subtitles_task = self._generate_subtitles_async(chunk_path)
            
            # Получаем информацию о видео
            video_info = self._get_video_info(chunk_path)
            total_duration = video_info['duration']
            
            # Ждем субтитры
            subtitles = await subtitles_task
            
            # Создаем клипы параллельно
            clips = await self._create_clips_parallel(
                chunk_path, duration, title, subtitle, subtitles, temp_dir, chunk_index, total_duration
            )
            
            return clips
            
        except Exception as e:
            print(f"💥 Ошибка обработки чанка {chunk_index}: {e}")
            return []
    
    async def _generate_subtitles_async(self, video_path):
        """Асинхронная генерация субтитров"""
        loop = asyncio.get_event_loop()
        
        def generate():
            try:
                # Используем fp16 для ускорения на GPU
                result = self.whisper_model.transcribe(
                    video_path,
                    fp16=self.device == "cuda",
                    language="ru"  # Указываем язык для ускорения
                )
                return result['segments']
            except Exception as e:
                print(f"⚠️ Ошибка генерации субтитров: {e}")
                return []
        
        # Выполняем в отдельном потоке для GPU операций
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(executor, generate)
            return result
    
    async def _create_clips_parallel(self, video_path, duration, title, subtitle, subtitles, temp_dir, chunk_index, total_duration):
        """ПАРАЛЛЕЛЬНОЕ создание клипов из чанка"""
        clips = []
        
        try:
            # Вычисляем количество клипов
            if total_duration <= duration:
                clip_count = 1
                actual_duration = total_duration
            else:
                clip_count = int(total_duration // duration)
                actual_duration = duration
            
            print(f"🎬 Создаем {clip_count} клипов из чанка {chunk_index+1}")
            
            # Создаем задачи для параллельного создания клипов
            clip_tasks = []
            for i in range(clip_count):
                start_time = i * duration
                clip_path = os.path.join(temp_dir, f"clip_{chunk_index}_{i}.mp4")
                
                clip_duration = actual_duration if total_duration <= duration else duration
                
                # Получаем субтитры для этого временного отрезка
                clip_subtitles = [
                    seg for seg in subtitles 
                    if seg['start'] >= start_time and seg['end'] <= start_time + clip_duration
                ]
                
                task = self._create_single_clip_async(
                    video_path, clip_path, start_time, clip_duration,
                    title, subtitle, clip_subtitles, i, clip_count
                )
                clip_tasks.append(task)
            
            # Выполняем все клипы параллельно (но ограничиваем количество одновременных задач)
            batch_size = min(4, self.max_workers)  # Не более 4 клипов одновременно
            
            for i in range(0, len(clip_tasks), batch_size):
                batch = clip_tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                for j, result in enumerate(batch_results):
                    if isinstance(result, Exception):
                        print(f"❌ Ошибка создания клипа {i+j+1}: {result}")
                    elif result:
                        clips.append(result)
                        print(f"✅ Клип {i+j+1} создан")
            
            print(f"🎯 Чанк {chunk_index+1}: создано {len(clips)} клипов")
            return clips
            
        except Exception as e:
            print(f"💥 Ошибка в _create_clips_parallel: {e}")
            return clips
    
    async def _create_single_clip_async(self, video_path, clip_path, start_time, duration, title, subtitle, subtitles, clip_index, total_clips):
        """Асинхронное создание одного клипа"""
        loop = asyncio.get_event_loop()
        
        def create_clip():
            try:
                # Используем video_editor для создания клипа.
                # Теперь это обычная функция, ее можно вызывать напрямую
                success = self.video_editor.create_clip(
                    video_path, clip_path, start_time, duration,
                    title, subtitle, subtitles
                )
                return clip_path if success else None
            except Exception as e:
                print(f"⚠️ Ошибка создания клипа {clip_index+1}: {e}")
                return None
        
        # Выполняем в отдельном потоке
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(executor, create_clip)
            return result
    
    async def _generate_subtitles(self, video_path):
        """Генерация субтитров с помощью Whisper"""
        try:
            result = self.whisper_model.transcribe(video_path)
            return result['segments']
        except Exception as e:
            print(f"Ошибка генерации субтитров: {e}")
            return []
    
    async def _create_clips(self, video_path, duration, title, subtitle, subtitles, temp_dir, chunk_index):
        """Создание клипов из видео"""
        clips = []
        
        try:
            video_info = self._get_video_info(video_path)
            total_duration = video_info['duration']
            
            print(f"Длительность видео: {total_duration} секунд")
            print(f"Длительность клипа: {duration} секунд")
            
            # Если видео короче заданной длительности, создаем один клип из всего видео
            if total_duration <= duration:
                print(f"Видео короче {duration} секунд, создаем один клип из всего видео")
                clip_count = 1
                actual_duration = total_duration
            else:
                clip_count = int(total_duration // duration)
                actual_duration = duration
                
            print(f"Планируется создать {clip_count} клипов")
            
            for i in range(clip_count):
                start_time = i * duration
                clip_path = os.path.join(temp_dir, f"clip_{chunk_index}_{i}.mp4")
                
                # Для коротких видео используем фактическую длительность
                clip_duration = actual_duration if total_duration <= duration else duration
                
                print(f"Создаем клип {i+1}/{clip_count}, начало: {start_time}с, длительность: {clip_duration}с")
                
                # Получаем субтитры для этого временного отрезка
                clip_subtitles = [
                    seg for seg in subtitles 
                    if seg['start'] >= start_time and seg['end'] <= start_time + clip_duration
                ]
                
                # Создаем клип с эффектами
                success = await self.video_editor.create_clip(
                    video_path, clip_path, start_time, clip_duration,
                    title, subtitle, clip_subtitles
                )
                
                if success:
                    clips.append(clip_path)
                    print(f"Клип {i+1} создан успешно")
                else:
                    print(f"Ошибка создания клипа {i+1}")
            
            print(f"Всего создано клипов: {len(clips)}")
            return clips
            
        except Exception as e:
            print(f"Ошибка в _create_clips: {e}")
            return clips
    
    async def _upload_clips_to_drive_parallel(self, clips):
        """ПАРАЛЛЕЛЬНАЯ загрузка клипов на Google Drive"""
        print(f"📤 Начинаем параллельную загрузку {len(clips)} клипов на Google Drive...")
        
        # Создаем задачи для параллельной загрузки
        upload_tasks = []
        for i, clip_path in enumerate(clips):
            task = self._upload_single_clip_async(clip_path, i + 1)
            upload_tasks.append(task)
        
        # Выполняем загрузку батчами (не более 3 одновременно для стабильности)
        batch_size = 3
        uploaded_links = []
        
        for i in range(0, len(upload_tasks), batch_size):
            batch = upload_tasks[i:i + batch_size]
            print(f"📤 Загружаем батч {i//batch_size + 1}/{(len(upload_tasks) + batch_size - 1)//batch_size}")
            
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    print(f"❌ Ошибка загрузки клипа {i+j+1}: {result}")
                elif result:
                    uploaded_links.append(result)
                    print(f"✅ Клип {i+j+1} загружен")
        
        print(f"🎯 Загружено {len(uploaded_links)} клипов на Google Drive")
        return uploaded_links
    
    async def _upload_single_clip_async(self, clip_path, fragment_number):
        """Асинхронная загрузка одного клипа"""
        loop = asyncio.get_event_loop()
        
        def upload_clip():
            try:
                # Используем синхронную версию загрузки в отдельном потоке
                link = self.drive_uploader.upload_file(clip_path, f"clip_{fragment_number}.mp4")
                return {
                    'fragment': fragment_number,
                    'link': link
                }
            except Exception as e:
                print(f"⚠️ Ошибка загрузки клипа {fragment_number}: {e}")
                return None
        
        # Выполняем в отдельном потоке
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            result = await loop.run_in_executor(executor, upload_clip)
            return result
    
    async def _upload_clips_to_drive(self, clips):
        """Загрузка клипов на Google Drive (старый метод для совместимости)"""
        uploaded_links = []
        
        for i, clip_path in enumerate(clips):
            try:
                link = await self.drive_uploader.upload_file(clip_path, f"clip_{i+1}.mp4")
                uploaded_links.append({
                    'fragment': i + 1,
                    'link': link
                })
            except Exception as e:
                print(f"Ошибка загрузки клипа {clip_path}: {e}")
        
        return uploaded_links
    
    async def _create_links_file(self, uploaded_links, user_id):
        """Создание файла со ссылками"""
        links_content = "Ссылки на скачивание клипов:\n\n"
        
        for item in uploaded_links:
            links_content += f"Фрагмент {item['fragment']}: {item['link']}\n"
        
        links_file_path = f"links_{user_id}.txt"
        with open(links_file_path, 'w', encoding='utf-8') as f:
            f.write(links_content)
        
        # Загружаем файл со ссылками на Drive
        links_file_url = await self.drive_uploader.upload_file(
            links_file_path, f"links_{user_id}.txt"
        )
        
        # Удаляем локальный файл
        os.remove(links_file_path)
        
        return links_file_url