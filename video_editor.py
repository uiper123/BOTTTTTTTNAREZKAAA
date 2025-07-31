import os
import asyncio
import logging
import ffmpeg
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class VideoEditor:
    def __init__(self):
        self.output_dir = Path("output")
        self.output_dir.mkdir(exist_ok=True)
        
        # Настройки для оформления
        self.font_path = "Obelix Pro.ttf"  # Путь к шрифту
        self.title_color = "red"
        self.subtitle_color = "red"
    
    def get_video_info(self, video_path: str) -> dict:
        """Получение информации о видео"""
        try:
            probe = ffmpeg.probe(video_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            
            if not video_stream:
                raise ValueError("Видео поток не найден")
            
            duration = float(probe['format']['duration'])
            width = int(video_stream['width'])
            height = int(video_stream['height'])
            fps = eval(video_stream['r_frame_rate'])
            
            return {
                'duration': duration,
                'width': width,
                'height': height,
                'fps': fps
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения информации о видео: {e}")
            raise
    
    async def extract_segment(self, input_path: str, output_path: str, start_time: float, duration: float) -> bool:
        """Извлечение сегмента видео"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._extract_segment_sync,
                input_path, output_path, start_time, duration
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка извлечения сегмента: {e}")
            return False
    
    def _extract_segment_sync(self, input_path: str, output_path: str, start_time: float, duration: float):
        """Синхронное извлечение сегмента"""
        (
            ffmpeg
            .input(input_path, ss=start_time, t=duration)
            .output(output_path, vcodec='libx264', acodec='aac')
            .overwrite_output()
            .run(quiet=True)
        )
    
    async def create_clips(self, video_path: str, clip_duration: int, subtitles: list, start_index: int = 0, config: dict = None) -> list:
        """Создание клипов из видео со строгим таймлайном"""
        try:
            video_info = self.get_video_info(video_path)
            total_duration = video_info['duration']
            
            clips = []
            current_time = 0
            clip_index = start_index
            skipped_clips = 0
            
            while current_time < total_duration:
                end_time = current_time + clip_duration
                
                # СТРОГИЙ ТАЙМЛАЙН: только клипы точной длительности
                remaining_time = total_duration - current_time
                
                # Если оставшееся время меньше заданной длительности - пропускаем
                if remaining_time < clip_duration:
                    logger.info(f"Пропущен последний кусок: {remaining_time:.1f} сек < {clip_duration} сек (строгий таймлайн)")
                    skipped_clips += 1
                    break
                
                clip_path = self.output_dir / f"clip_{clip_index:03d}.mp4"
                
                # Создаем клип с точной длительностью
                success = await self.create_styled_clip(
                    video_path,
                    str(clip_path),
                    current_time,
                    clip_duration,  # Всегда используем точную длительность
                    subtitles,
                    clip_index + 1,
                    config
                )
                
                if success:
                    clips.append(str(clip_path))
                    logger.info(f"Создан клип {clip_index + 1}: {current_time:.1f}-{current_time + clip_duration:.1f} сек ({clip_duration} сек)")
                    clip_index += 1
                else:
                    logger.warning(f"Не удалось создать клип {clip_index + 1}")
                
                current_time += clip_duration
            
            # Детальная статистика
            expected_clips = int(total_duration // clip_duration)
            logger.info(f"📊 СТАТИСТИКА СОЗДАНИЯ КЛИПОВ:")
            logger.info(f"   Длительность видео: {total_duration:.1f} сек")
            logger.info(f"   Ожидалось клипов: {expected_clips}")
            logger.info(f"   Создано клипов: {len(clips)}")
            logger.info(f"   Пропущено клипов: {skipped_clips}")
            logger.info(f"   Эффективность: {len(clips)/expected_clips*100:.1f}%")
            
            return clips
            
        except Exception as e:
            logger.error(f"Ошибка создания клипов: {e}")
            return []
    
    async def create_styled_clip(self, input_path: str, output_path: str, start_time: float, 
                               duration: float, subtitles: list, clip_number: int, config: dict = None) -> bool:
        """Создание стилизованного клипа"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._create_styled_clip_sync,
                input_path, output_path, start_time, duration, subtitles, clip_number, config
            )
            return True
            
        except Exception as e:
            logger.error(f"Ошибка создания стилизованного клипа: {e}")
            return False
    
    def _create_styled_clip_sync(self, input_path: str, output_path: str, start_time: float,
                               duration: float, subtitles: list, clip_number: int, config: dict = None):
        """Синхронное создание стилизованного клипа с GPU ускорением"""
        
        # Проверяем доступность GPU
        gpu_available = self._check_gpu_support()
        
        # Всегда используем CPU ввод для стабильности в Colab
        main_video = ffmpeg.input(input_path, ss=start_time, t=duration)
        logger.info(f"💻 Используем CPU для создания клипа {clip_number}")
        
        # Создаем размытый фон (растягиваем на весь экран) - ВЕРТИКАЛЬНЫЙ ФОРМАТ
        blurred_bg = (
            main_video
            .video
            .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')  # Принудительно вертикальный
            .filter('crop', 1080, 1920)  # Обрезаем до точного размера
            .filter('gblur', sigma=20)
        )
        
        # Основное видео по центру - улучшенное масштабирование
        # Получаем информацию об исходном видео
        video_info = self.get_video_info(input_path)
        original_width = video_info['width']
        original_height = video_info['height']
        
        # Целевые размеры для вертикального формата (9:16)
        target_screen_width = 1080
        target_screen_height = 1920
        
        # ИСПРАВЛЕННЫЙ АЛГОРИТМ МАСШТАБИРОВАНИЯ
        
        # Определяем доступную область для видео (оставляем место для текста)
        text_area_height = 400  # Место для заголовков сверху
        available_width = target_screen_width
        available_height = target_screen_height - text_area_height
        
        # Вычисляем соотношения сторон
        original_aspect = original_width / original_height
        available_aspect = available_width / available_height
        
        # Для больших видео (4K+) используем более агрессивное масштабирование
        is_large_video = original_width >= 2160 or original_height >= 2160
        
        # ЕДИНЫЙ АЛГОРИТМ МАСШТАБИРОВАНИЯ (исправлен)
        if original_aspect > available_aspect:
            # Широкое видео - масштабируем по ширине
            target_width = available_width
            target_height = int(available_width / original_aspect)
        else:
            # Высокое или квадратное видео - масштабируем по высоте
            target_height = available_height
            target_width = int(available_height * original_aspect)
        
        # Убеждаемся, что размеры четные и в разумных пределах
        target_width = min(target_width, available_width)
        target_height = min(target_height, available_height)
        target_width = target_width - (target_width % 2)
        target_height = target_height - (target_height % 2)
        
        # Минимальные размеры для качества
        min_width = 800   # Еще больше увеличили минимальную ширину
        min_height = 450  # Еще больше увеличили минимальную высоту
        
        if target_width < min_width or target_height < min_height:
            logger.info("Применяем минимальные размеры для качества")
            if original_aspect > 1:  # Широкое видео
                target_width = min_width
                target_height = int(min_width / original_aspect)
                if target_height < min_height:
                    target_height = min_height
                    target_width = int(min_height * original_aspect)
            else:  # Высокое видео
                target_height = min_height
                target_width = int(min_height * original_aspect)
                if target_width < min_width:
                    target_width = min_width
                    target_height = int(min_width / original_aspect)
            
            # Снова проверяем четность
            target_width = target_width - (target_width % 2)
            target_height = target_height - (target_height % 2)
        
        # Финальная проверка
        if target_width <= 0 or target_height <= 0:
            logger.warning("Неправильные размеры, используем безопасные значения")
            target_width = 854   # Увеличили безопасные размеры
            target_height = 480  # 16:9 соотношение
            target_width = target_width - (target_width % 2)
            target_height = target_height - (target_height % 2)
        
        logger.info(f"Исходное видео: {original_width}x{original_height} (соотношение: {original_aspect:.2f})")
        logger.info(f"Доступная область: {available_width}x{available_height} (соотношение: {available_aspect:.2f})")
        
        if original_aspect > available_aspect:
            logger.info("Масштабирование по ширине (видео широкое)")
        else:
            logger.info("Масштабирование по высоте (видео высокое)")
            
        logger.info(f"Масштабирование: {original_width}x{original_height} -> {target_width}x{target_height}")
        
        # Используем улучшенное масштабирование для больших видео
        if is_large_video:
            # Для больших видео используем высококачественный алгоритм масштабирования
            main_scaled = (
                main_video
                .video
                .filter('scale', target_width, target_height, 
                       flags='lanczos')  # Высококачественный алгоритм
            )
            logger.info(f"Используется Lanczos масштабирование для большого видео")
        else:
            # Для обычных видео используем стандартное масштабирование
            main_scaled = (
                main_video
                .video
                .filter('scale', target_width, target_height)
            )
        
        # Накладываем основное видео на размытый фон
        video_with_bg = ffmpeg.filter([blurred_bg, main_scaled], 'overlay', 
                                    x='(W-w)/2', y='(H-h)/2')
        
        # Получаем пользовательские заголовки из config
        if config:
            title_template = config.get('title', 'ФРАГМЕНТ')
            subtitle_template = config.get('subtitle', 'Часть')
            custom_title = config.get('custom_title', False)
            custom_subtitle = config.get('custom_subtitle', False)
        else:
            title_template = 'ФРАГМЕНТ'
            subtitle_template = 'Часть'
            custom_title = False
            custom_subtitle = False
        
        # Формируем заголовки
        if custom_title:
            # Если заголовок пользовательский - не добавляем цифру
            title_text = title_template
        else:
            # Если стандартный - добавляем номер клипа
            title_text = f"{title_template} {clip_number}"
            
        if custom_subtitle:
            # Если подзаголовок пользовательский - не добавляем цифру
            subtitle_text = subtitle_template
        else:
            # Если стандартный - добавляем номер клипа
            subtitle_text = f"{subtitle_template} {clip_number}"
        
        # Заголовок (сверху) - появляется с 8 секунды
        title_start_time = 8.0  # Заголовки появляются с 8 секунды
        video_with_title = video_with_bg.drawtext(
            text=title_text,
            fontfile=self.font_path if os.path.exists(self.font_path) else None,
            fontsize=60,
            fontcolor=self.title_color,
            x='(w-text_w)/2',
            y='100',
            enable=f'between(t,{title_start_time},{duration})'
        )
        
        # Подзаголовок (под заголовком) - появляется с 8 секунды
        video_with_subtitle = video_with_title.drawtext(
            text=subtitle_text,
            fontfile=self.font_path if os.path.exists(self.font_path) else None,
            fontsize=80,  # Больше заголовка
            fontcolor=self.subtitle_color,
            x='(w-text_w)/2',
            y='200',
            enable=f'between(t,{title_start_time},{duration})'
        )
        
        # Добавляем субтитры с анимацией
        final_video = self._add_animated_subtitles(
            video_with_subtitle, 
            subtitles, 
            start_time, 
            duration
        )
        
        # Аудио
        audio = main_video.audio
        
        # ПРИНУДИТЕЛЬНО добавляем финальное масштабирование до 9:16
        final_video_scaled = final_video.filter('scale', 1080, 1920, force_original_aspect_ratio='decrease').filter('pad', 1080, 1920, '(ow-iw)/2', '(oh-ih)/2')
        
        # Финальный вывод с GPU/CPU кодировщиком
        if gpu_available:
            # GPU ускоренный вывод (NVIDIA NVENC)
            (
                ffmpeg
                .output(final_video_scaled, audio, output_path, 
                       vcodec='h264_nvenc',    # GPU кодировщик NVIDIA
                       acodec='aac',
                       preset='fast',          # Быстрый пресет для GPU
                       cq=18,                  # Качество для NVENC (аналог CRF)
                       pix_fmt='yuv420p',      # Совместимость
                       **{'b:v': '8M',         # Битрейт видео 8 Мбит/с
                          'b:a': '192k',       # Битрейт аудио 192 кбит/с
                          'maxrate': '10M',    # Максимальный битрейт
                          'bufsize': '16M'})   # Размер буфера
                .overwrite_output()
                .run(quiet=True)
            )
            logger.info(f"🎮 Клип {clip_number} создан с GPU ускорением (1080x1920)")
        else:
            # CPU вывод с улучшенным качеством для больших видео
            if is_large_video:
                # Для больших видео используем лучшие настройки качества
                (
                    ffmpeg
                    .output(final_video_scaled, audio, output_path, 
                           vcodec='libx264',
                           acodec='aac',
                           preset='medium',        # Лучший баланс скорость/качество
                           crf=20,                 # Высокое качество для больших видео
                           pix_fmt='yuv420p',
                           **{'b:v': '6M',         # Битрейт для качества
                              'b:a': '192k',
                              'maxrate': '8M',
                              'bufsize': '12M'})
                    .overwrite_output()
                    .run(quiet=True)
                )
                logger.info(f"💻 Большое видео - клип {clip_number} создан с высоким качеством (1080x1920)")
            else:
                # Для обычных видео используем быстрые настройки
                (
                    ffmpeg
                    .output(final_video_scaled, audio, output_path, 
                           vcodec='libx264',
                           acodec='aac',
                           preset='fast',          # Быстрый пресет
                           crf=22,                 # Хорошее качество
                           pix_fmt='yuv420p')
                    .overwrite_output()
                    .run(quiet=True)
                )
                logger.info(f"💻 Клип {clip_number} создан с CPU (1080x1920)")
    
    def _add_animated_subtitles(self, video, subtitles: list, start_time: float, duration: float):
        """Добавление анимированных субтитров"""
        if not subtitles:
            return video
        
        # Фильтруем субтитры для текущего сегмента
        segment_subtitles = []
        for sub in subtitles:
            sub_start = sub['start'] - start_time
            sub_end = sub['end'] - start_time
            
            # Проверяем, попадает ли субтитр в текущий сегмент
            if sub_end > 0 and sub_start < duration:
                # Корректируем время для сегмента
                adjusted_start = max(0, sub_start)
                adjusted_end = min(duration, sub_end)
                
                segment_subtitles.append({
                    'text': sub['text'],
                    'start': adjusted_start,
                    'end': adjusted_end
                })
        
        # Добавляем каждый субтитр с анимацией подпрыгивания
        result_video = video
        for i, sub in enumerate(segment_subtitles):
            # Создаем анимацию подпрыгивания (поднимаем выше)
            bounce_y = f"h-600-20*sin(2*PI*t*3)"  # Подпрыгивание выше
            
            result_video = result_video.drawtext(
                text=sub['text'],
                fontfile=self.font_path if os.path.exists(self.font_path) else None,
                fontsize=70,  # Увеличил размер субтитров
                fontcolor='white',
                bordercolor='black',
                borderw=3,  # Увеличил толщину обводки
                x='(w-text_w)/2',
                y=bounce_y,
                enable=f"between(t,{sub['start']},{sub['end']})"
            )
        
        return result_video
    
    def _check_gpu_support(self) -> bool:
        """Проверка поддержки GPU для ffmpeg - ОТКЛЮЧЕНО ДЛЯ COLAB"""
        # В Google Colab GPU поддержка часто вызывает проблемы с ffmpeg
        # Принудительно отключаем для стабильности
        logger.info("❌ GPU поддержка принудительно отключена для Colab")
        return False