import os
import subprocess
from PIL import Image, ImageDraw, ImageFont
import tempfile

class VideoEditor:
    def __init__(self):
        # Получаем абсолютный путь к шрифту
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.font_path = os.path.join(current_dir, "Obelix Pro.ttf")
        
        # Проверяем, существует ли файл шрифта
        if not os.path.exists(self.font_path):
            print(f"ВНИМАНИЕ: Шрифт не найден: {self.font_path}")
            # Используем системный шрифт как fallback
            self.font_path = "arial"
        
    def create_clip(self, input_video, output_path, start_time, duration, title, subtitle, subtitles):
        """Создание клипа с эффектами"""
        temp_dir = None
        try:
            print(f"Начинаем создание клипа: {output_path}")
            temp_dir = tempfile.mkdtemp()
            print(f"Временная директория: {temp_dir}")
            
            # 1. Извлекаем сегмент видео
            segment_path = os.path.join(temp_dir, "segment.mp4")
            print("Шаг 1: Извлечение сегмента...")
            self._extract_segment(input_video, segment_path, start_time, duration)
            
            # 2. Создаем фоновое видео с блюром
            blurred_bg_path = os.path.join(temp_dir, "blurred_bg.mp4")
            print("Шаг 2: Создание размытого фона...")
            self._create_blurred_background(segment_path, blurred_bg_path)
            
            # 3. Создаем основное видео по центру
            centered_video_path = os.path.join(temp_dir, "centered.mp4")
            print("Шаг 3: Создание центрированного видео...")
            self._create_centered_video(segment_path, centered_video_path)
            
            # 4. Накладываем основное видео на фон
            combined_path = os.path.join(temp_dir, "combined.mp4")
            print("Шаг 4: Наложение видео на фон...")
            self._overlay_videos(blurred_bg_path, centered_video_path, combined_path)
            
            # 5. Добавляем заголовки
            with_titles_path = os.path.join(temp_dir, "with_titles.mp4")
            print("Шаг 5: Добавление заголовков...")
            self._add_titles(combined_path, with_titles_path, title, subtitle)
            
            # 6. Добавляем субтитры с анимацией
            print("Шаг 6: Добавление субтитров...")
            self._add_animated_subtitles(with_titles_path, output_path, subtitles, start_time)
            
            # Проверяем, что файл создался
            if os.path.exists(output_path):
                print(f"Клип успешно создан: {output_path}")
                file_size = os.path.getsize(output_path)
                print(f"Размер файла: {file_size} байт")
            else:
                print(f"ОШИБКА: Файл не создался: {output_path}")
                return False
            
            return True
            
        except Exception as e:
            print(f"Ошибка создания клипа: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Гарантированно очищаем временные файлы
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Удалена промежуточная временная директория: {temp_dir}")
    
    def _extract_segment(self, input_video, output_path, start_time, duration):
        """Извлечение сегмента видео"""
        cmd = [
            'ffmpeg', '-i', input_video,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'aac', '-b:a', '192k',
            output_path, '-y'
        ]
        print(f"Команда FFmpeg: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Ошибка FFmpeg: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        print("Сегмент извлечен успешно")
    
    def _create_blurred_background(self, input_video, output_path):
        """Создание размытого фона на весь экран"""
        cmd = [
            'ffmpeg', '-i', input_video,
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy', output_path, '-y'
        ]
        print(f"Команда FFmpeg (фон): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Ошибка FFmpeg (фон): {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        print("Размытый фон создан успешно")
    
    def _create_centered_video(self, input_video, output_path):
        """Создание центрированного видео с сохранением пропорций и обрезкой"""
        cmd = [
            'ffmpeg', '-i', input_video,
            '-vf', 'scale=1080:1536:force_original_aspect_ratio=increase,crop=1080:1536',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy', output_path, '-y'
        ]
        print(f"Команда FFmpeg (центр с обрезкой): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Ошибка FFmpeg (центр): {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        print("Центрированное видео с обрезкой создано успешно")
    
    def _overlay_videos(self, background_path, overlay_path, output_path):
        """Наложение одного видео на другое по центру с отступом"""
        cmd = [
            'ffmpeg', '-i', background_path, '-i', overlay_path,
            '-filter_complex', '[0:v][1:v]overlay=(W-w)/2:(H-h)/2+100',
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '18',
            '-c:a', 'copy', output_path, '-y'
        ]
        print(f"Команда FFmpeg (наложение): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"Ошибка FFmpeg (наложение): {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr}")
        print("Наложение видео выполнено успешно")
    
    def _add_titles(self, input_video, output_path, title, subtitle):
        """Добавление заголовков"""
        try:
            # Используем шрифт Obelix Pro
            if os.path.exists(self.font_path) and self.font_path.endswith('.ttf'):
                # Экранируем путь для FFmpeg для Windows
                path = self.font_path.replace('\\', '/')
                font_path_escaped = path.replace(':', '\\:')
                print(f"Используем шрифт Obelix Pro: {self.font_path}")
            else:
                font_path_escaped = "arial"
                print("Используем системный шрифт Arial (шрифт по умолчанию не найден)")

            # Простое экранирование текста для FFmpeg
            title_safe = title.replace("'", r"\'").replace(":", r"\:").replace("%", r"\%")
            subtitle_safe = subtitle.replace("'", r"\'").replace(":", r"\:").replace("%", r"\%")
            
            print(f"Добавляем заголовки: '{title_safe}' и '{subtitle_safe}'")
            
            # Создаем фильтр для заголовков с правильным экранированием
            title_filter = f"drawtext=fontfile='{font_path_escaped}':text='{title_safe}':fontsize=60:fontcolor=red:x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.5:boxborderw=5"
            subtitle_filter = f"drawtext=fontfile='{font_path_escaped}':text='{subtitle_safe}':fontsize=80:fontcolor=red:x=(w-text_w)/2:y=160:box=1:boxcolor=black@0.5:boxborderw=5"
            
            cmd = [
                'ffmpeg', '-i', input_video,
                '-vf', f"{title_filter},{subtitle_filter}",
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                '-c:a', 'copy',
                output_path, '-y'
            ]
            
            print(f"Команда FFmpeg (заголовки): {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode != 0:
                print(f"Ошибка FFmpeg (заголовки): {result.stderr}")
                # Если не удается добавить заголовки, пробуем с системным шрифтом
                print("Пробуем с системным шрифтом Arial...")
                arial_path = 'C:\\Windows\\Fonts\\arial.ttf' # Исправленный путь для Windows
                title_filter_fallback = f"drawtext=fontfile='{arial_path}':text='{title_safe}':fontsize=60:fontcolor=red:x=(w-text_w)/2:y=80:box=1:boxcolor=black@0.5:boxborderw=5"
                subtitle_filter_fallback = f"drawtext=fontfile='{arial_path}':text='{subtitle_safe}':fontsize=80:fontcolor=red:x=(w-text_w)/2:y=160:box=1:boxcolor=black@0.5:boxborderw=5"
                
                cmd_fallback = [
                    'ffmpeg', '-i', input_video,
                    '-vf', f"{title_filter_fallback},{subtitle_filter_fallback}",
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                    '-c:a', 'copy',
                    output_path, '-y'
                ]
                
                result_fallback = subprocess.run(cmd_fallback, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                if result_fallback.returncode != 0:
                    print(f"Ошибка FFmpeg (fallback): {result_fallback.stderr}")
                    print("Не удалось добавить заголовки даже с системным шрифтом")
                    import shutil
                    shutil.copy2(input_video, output_path)
                    print("Заголовки пропущены из-за ошибки")
                else:
                    print("Заголовки добавлены с системным шрифтом")
            else:
                print("Заголовки добавлены успешно с шрифтом Obelix Pro")
                
        except Exception as e:
            print(f"Ошибка при добавлении заголовков: {e}")
            import traceback
            traceback.print_exc()
            import shutil
            shutil.copy2(input_video, output_path)

    def _add_animated_subtitles(self, input_video, output_path, subtitles, start_offset):
        """Добавление анимированных субтитров"""
        try:
            # Экранируем путь к шрифту для FFmpeg
            path = self.font_path.replace('\\', '/')
            font_path_escaped = path.replace(':', '\\:')

            if not subtitles:
                print("Субтитров нет, копируем файл без изменений")
                import shutil
                shutil.copy2(input_video, output_path)
                return
            
            print(f"Добавляем {len(subtitles)} субтитров с анимацией подпрыгивания")
            
            # Создаем фильтры для анимированных субтитров по одному слову
            subtitle_filters = []
            
            for i, segment in enumerate(subtitles):
                # Корректируем время относительно начала клипа
                start_time = segment['start'] - start_offset
                end_time = segment['end'] - start_offset
                
                # Пропускаем субтитры, которые не попадают в клип
                if start_time < 0:
                    start_time = 0
                if end_time <= 0:
                    continue
                if start_time >= 30:  # Максимальная длительность клипа
                    break
                if end_time > 30:
                    end_time = 30
                
                # Очищаем текст
                text = segment['text'].strip()
                if not text:
                    continue
                
                # Разбиваем текст на слова
                words = text.split()
                if not words:
                    continue
                
                # Вычисляем время для каждого слова
                segment_duration = end_time - start_time
                word_duration = segment_duration / len(words) if len(words) > 0 else segment_duration
                
                print(f"Сегмент {i+1}: '{text}' -> {len(words)} слов ({start_time:.1f}s - {end_time:.1f}s)")
                
                # Создаем субтитр для каждого слова
                for word_idx, word in enumerate(words):
                    word_start = start_time + (word_idx * word_duration)
                    word_end = word_start + word_duration
                    
                    # Экранируем слово для FFmpeg
                    word_safe = word.replace("'", r"\'").replace(":", r"\:").replace("%", r"\%").replace(",", r"\,")
                    
                    if not word_safe:
                        continue
                    
                    print(f"  Слово {word_idx+1}: '{word_safe}' ({word_start:.1f}s - {word_end:.1f}s)")
                    
                    # Создаем анимацию подпрыгивания для каждого слова
                    bounce_filter = (
                        f"drawtext=fontfile='{font_path_escaped}':text='{word_safe}':fontsize=70:fontcolor=white:"
                        f"bordercolor=black:borderw=2:x=(w-text_w)/2:"
                        f"y=h-400+20*sin(2*PI*t):enable='between(t,{word_start:.2f},{word_end:.2f})'"
                    )
                    subtitle_filters.append(bounce_filter)
            
            if subtitle_filters:
                # Объединяем все фильтры субтитров
                filter_string = ','.join(subtitle_filters)
                
                cmd = [
                    'ffmpeg', '-i', input_video,
                    '-vf', filter_string,
                    '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p',
                    '-c:a', 'copy',
                    output_path, '-y'
                ]
                
                print(f"Команда FFmpeg (субтитры): ffmpeg -i input -vf [фильтры субтитров] output")
                result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                
                if result.returncode != 0:
                    print(f"Ошибка FFmpeg (субтитры): {result.stderr}")
                    # Если субтитры не удалось добавить, копируем без них
                    import shutil
                    shutil.copy2(input_video, output_path)
                    print("Субтитры пропущены, файл скопирован без изменений")
                else:
                    print("Анимированные субтитры добавлены успешно")
            else:
                print("Нет подходящих субтитров для клипа")
                import shutil
                shutil.copy2(input_video, output_path)
                
        except Exception as e:
            print(f"Ошибка при добавлении субтитров: {e}")
            import traceback
            traceback.print_exc()
            import shutil
            shutil.copy2(input_video, output_path)