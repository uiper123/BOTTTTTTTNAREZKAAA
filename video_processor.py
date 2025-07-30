import os
import asyncio
import subprocess
import tempfile
import shutil
from pathlib import Path
import yt_dlp
import whisper
from google_drive_uploader import GoogleDriveUploader
from video_editor import VideoEditor

class VideoProcessor:
    def __init__(self):
        self.drive_uploader = GoogleDriveUploader()
        self.video_editor = VideoEditor()
        self.whisper_model = whisper.load_model("base")
        
    async def process_video(self, video_path, duration, title, subtitle, user_id):
        """Основная функция обработки видео"""
        temp_dir = f"temp_{user_id}"
        try:
            # Создаем временную директорию для пользователя
            os.makedirs(temp_dir, exist_ok=True)
            
            # Получаем информацию о видео
            video_info = self._get_video_info(video_path)
            video_duration = video_info['duration']
            
            # Если видео длинное, разбиваем на чанки по 5 минут
            chunks = []
            if video_duration > 300:  # 5 минут
                chunks = await self._split_video_to_chunks(video_path, temp_dir)
            else:
                chunks = [video_path]
            
            all_clips = []
            
            # Обрабатываем каждый чанк
            for i, chunk_path in enumerate(chunks):
                print(f"Обрабатываем чанк {i+1}/{len(chunks)}")
                
                # Генерируем субтитры для чанка
                subtitles = await self._generate_subtitles(chunk_path)
                
                # Нарезаем чанк на клипы
                clips = await self._create_clips(
                    chunk_path, duration, title, subtitle, subtitles, temp_dir, i
                )
                all_clips.extend(clips)
            
            # Загружаем клипы на Google Drive
            uploaded_links_file = await self._upload_clips_to_drive(all_clips)
            
            # Создаем файл со ссылками
            links_file = await self._create_links_file(uploaded_links_file, user_id)
            
            return {
                'success': True, 
                'clips_count': len(all_clips), 
                'links_file': links_file
            }
            
        except Exception as e:
            print(f"Критическая ошибка в process_video: {e}")
            import traceback
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            # Гарантированно удаляем временную директорию
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Удалена временная директория: {temp_dir}")
    
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
        """Скачивание видео с YouTube"""
        output_path = f"youtube_video_{user_id}.%(ext)s"
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': output_path,
            'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
            'ignoreerrors': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if 'entries' in info:
                # Playlist, take the first video
                info = info['entries'][0]
            
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                # Fallback if the specific format failed
                ydl_opts['format'] = 'best'
                with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                    info = ydl_fallback.extract_info(url, download=True)
                    filename = ydl_fallback.prepare_filename(info)

        return filename
    
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
    
    async def _split_video_to_chunks(self, video_path, temp_dir):
        """Разбивка видео на чанки по 5 минут"""
        chunks = []
        chunk_duration = 300  # 5 минут
        
        video_info = self._get_video_info(video_path)
        total_duration = video_info['duration']
        
        chunk_count = int(total_duration // chunk_duration) + 1
        print(f"Разбиваем видео на {chunk_count} чанков по {chunk_duration} секунд")
        
        for i in range(chunk_count):
            start_time = i * chunk_duration
            chunk_path = os.path.join(temp_dir, f"chunk_{i}.mp4")
            
            cmd = [
                'ffmpeg', '-i', video_path,
                '-ss', str(start_time),
                '-t', str(chunk_duration),
                '-c', 'copy',
                chunk_path, '-y'
            ]
            
            print(f"Создаем чанк {i+1}/{chunk_count}: {chunk_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Ошибка создания чанка {i}: {result.stderr}")
                continue
            
            if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 0:
                chunks.append(chunk_path)
                print(f"Чанк {i+1} создан успешно")
            else:
                print(f"Чанк {i+1} не создался или пустой")
        
        print(f"Создано {len(chunks)} чанков")
        return chunks
    
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
    
    async def _upload_clips_to_drive(self, clips):
        """Загрузка клипов на Google Drive"""
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