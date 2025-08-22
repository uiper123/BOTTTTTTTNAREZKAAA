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
    
    async def create_clips_parallel(self, video_path: str, clip_duration: int, subtitles: list, start_index: int = 0, config: dict = None, max_parallel: int = 4) -> list:
        """ПАРАЛЛЕЛЬНОЕ создание клипов с максимальным использованием GPU"""
        try:
            video_info = self.get_video_info(video_path)
            total_duration = video_info['duration']
            
            # Планируем все клипы заранее
            clip_tasks = []
            current_time = 0
            clip_index = start_index
            
            while current_time < total_duration:
                remaining_time = total_duration - current_time
                
                # Если оставшееся время меньше заданной длительности - пропускаем
                if remaining_time < clip_duration:
                    logger.info(f"Пропущен последний кусок: {remaining_time:.1f} сек < {clip_duration} сек")
                    break
                
                clip_path = self.output_dir / f"clip_{clip_index:03d}.mp4"
                
                # Добавляем задачу в список
                clip_tasks.append({
                    'input_path': video_path,
                    'output_path': str(clip_path),
                    'start_time': current_time,
                    'duration': clip_duration,
                    'subtitles': subtitles,
                    'clip_number': clip_index + 1,
                    'config': config
                })
                
                current_time += clip_duration
                clip_index += 1
            
            logger.info(f"🚀 ПАРАЛЛЕЛЬНАЯ ОБРАБОТКА: {len(clip_tasks)} клипов, макс. параллельно: {max_parallel}")
            
            # Обрабатываем клипы пакетами для максимального использования GPU
            clips = []
            semaphore = asyncio.Semaphore(max_parallel)  # Ограничиваем количество параллельных задач
            
            async def process_clip_task(task):
                async with semaphore:
                    success = await self.create_styled_clip(
                        task['input_path'],
                        task['output_path'],
                        task['start_time'],
                        task['duration'],
                        task['subtitles'],
                        task['clip_number'],
                        task['config']
                    )
                    if success:
                        return task['output_path']
                    return None
            
            # Запускаем все задачи параллельно
            results = await asyncio.gather(*[process_clip_task(task) for task in clip_tasks], return_exceptions=True)
            
            # Собираем успешные результаты
            for result in results:
                if isinstance(result, str):  # Успешный результат
                    clips.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Ошибка создания клипа: {result}")
            
            logger.info(f"✅ ПАРАЛЛЕЛЬНО создано {len(clips)}/{len(clip_tasks)} клипов")
            return clips
            
        except Exception as e:
            logger.error(f"Ошибка параллельного создания клипов: {e}")
            return []

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
        
        gpu_available = self._check_gpu_support()
        video_info = self.get_video_info(input_path)
        original_width = video_info['width']
        original_height = video_info['height']
        original_fps = video_info['fps']
        is_large_video = original_width >= 2160 or original_height >= 2160

        # --- Общая логика для GPU и CPU ---
        logger.info(f"🎬 ОБРАБОТКА КЛИПА {clip_number}:")
        logger.info(f"   📐 Исходное разрешение: {original_width}x{original_height} ({original_height}p)")
        logger.info(f"   🎞️  FPS: {original_fps}")
        logger.info(f"   🎯 Целевое разрешение: 1080x1920 (вертикальный формат)")

        quality_type = "SD"
        if original_height >= 2160: quality_type = "4K Ultra HD"
        elif original_height >= 1440: quality_type = "2K/1440p"
        elif original_height >= 1080: quality_type = "Full HD 1080p"
        elif original_height >= 720: quality_type = "HD 720p"
        logger.info(f"   🏆 Качество исходного видео: {quality_type}")

        target_screen_width = 1080
        target_screen_height = 1920
        original_aspect = original_width / original_height
        target_aspect = target_screen_width / target_screen_height
        center_video_height = int(target_screen_height * 0.8)
        
        crop_needed = False
        if original_aspect > target_aspect:
            target_height = center_video_height
            target_width = int(target_height * original_aspect)
            crop_needed = target_width > target_screen_width
            if crop_needed:
                crop_width = target_screen_width
                crop_height = target_height
        else:
            target_height = center_video_height
            target_width = int(target_height * original_aspect)
        
        target_width -= target_width % 2
        target_height -= target_height % 2

        # --- Выбор пайплайна: GPU или CPU ---
        if gpu_available:
            logger.info(f"   🚀 Используем GPU-ускоренный пайплайн")
            input_kwargs = {'ss': start_time, 't': duration, 'c:v': 'h264_cuvid'}
            main_video = ffmpeg.input(input_path, **input_kwargs)
            
            # Пайплайн для размытого фона на GPU
            blurred_bg = (
                main_video.video
                .filter('scale_npp', 1080, 1920, force_original_aspect_ratio='increase', interp_algo='bicubic')
                .filter('crop', 1080, 1920)
                .filter('gblur', sigma=20) # gblur будет на CPU, ffmpeg-python обработает
            )

            # Пайплайн для основного видео на GPU
            main_scaled = (
                main_video.video
                .filter('scale_npp', target_width, target_height, interp_algo='lanczos' if is_large_video else 'bicubic')
            )
            if crop_needed:
                main_scaled = main_scaled.filter('crop', crop_width, crop_height, x='(iw-ow)/2', y='(ih-oh)/2')
            
            # Наложение. ffmpeg-python должен сам разобраться с hwdownload/hwupload
            video_with_bg = ffmpeg.filter([blurred_bg, main_scaled], 'overlay', x='(W-w)/2', y='(H-h)/2')

        else:
            logger.info(f"   💻 Используем CPU-пайплайн")
            main_video = ffmpeg.input(input_path, ss=start_time, t=duration)
            
            blurred_bg = (
                main_video.video
                .filter('scale', 1080, 1920, force_original_aspect_ratio='increase')
                .filter('crop', 1080, 1920)
                .filter('gblur', sigma=20)
            )
            
            main_scaled = main_video.video.filter('scale', target_width, target_height, flags='lanczos' if is_large_video else 'bicubic')
            if crop_needed:
                main_scaled = main_scaled.filter('crop', crop_width, crop_height, x='(iw-ow)/2', y='(ih-oh)/2')

            video_with_bg = ffmpeg.filter([blurred_bg, main_scaled], 'overlay', x='(W-w)/2', y='(H-h)/2')

        # --- Общая часть для рендеринга текста и субтитров (на CPU) ---
        if config:
            title_template = config.get('title', 'ФРАГМЕНТ')
            subtitle_template = config.get('subtitle', 'Часть')
            custom_title = config.get('custom_title', False)
            custom_subtitle = config.get('custom_subtitle', False)
        else:
            title_template, subtitle_template, custom_title, custom_subtitle = 'ФРАГМЕНТ', 'Часть', False, False

        title_text = title_template if custom_title else f"{title_template} {clip_number}"
        subtitle_text = subtitle_template if custom_subtitle else f"{subtitle_template} {clip_number}"
        
        title_start_time = 8.0
        video_with_text = video_with_bg.drawtext(
            text=title_text, fontfile=self.font_path, fontsize=60, fontcolor=self.title_color,
            x='(w-text_w)/2', y='100', enable=f'between(t,{title_start_time},{duration})'
        ).drawtext(
            text=subtitle_text, fontfile=self.font_path, fontsize=80, fontcolor=self.subtitle_color,
            x='(w-text_w)/2', y='200', enable=f'between(t,{title_start_time},{duration})'
        )
        
        final_video = self._add_animated_subtitles(video_with_text, subtitles, start_time, duration)
        audio = main_video.audio
        
        # Финальное масштабирование и вывод
        if gpu_available:
            final_video_scaled = final_video.filter('hwupload_cuda').filter('scale_npp', 1080, 1920)
            output_params = {
                'vcodec': 'h264_nvenc', 'acodec': 'aac', 'preset': 'p4', 'tune': 'hq', 'rc': 'vbr',
                'cq': 16, 'pix_fmt': 'yuv420p', 'gpu': 0, 'b:v': '12M', 'b:a': '192k',
                'maxrate': '18M', 'bufsize': '24M', 'threads': '0', 'bf': '4', 'refs': '4',
                'profile:v': 'high', 'level': '4.1'
            }
            ffmpeg.output(final_video_scaled, audio, output_path, **output_params).overwrite_output().run(quiet=True)
            logger.info(f"   ✅ Клип {clip_number} создан с GPU ускорением (1080x1920)")
        else:
            final_video_scaled = final_video.filter('scale', 1080, 1920)
            output_params = {
                'vcodec': 'libx264', 'acodec': 'aac', 'preset': 'medium', 'crf': 20,
                'pix_fmt': 'yuv420p', 'profile': 'high', 'level': '4.1', 'b:a': '192k',
                'maxrate': '10M', 'bufsize': '15M', 'bf': '3', 'refs': '3'
            }
            ffmpeg.output(final_video_scaled, audio, output_path, **output_params).overwrite_output().run(quiet=True)
            logger.info(f"   ✅ Клип {clip_number} создан с CPU (1080x1920)")
    
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
        """Проверка поддержки GPU для ffmpeg"""
        try:
            import subprocess
            
            # Проверяем доступность NVENC (NVIDIA GPU кодировщик)
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if 'h264_nvenc' in result.stdout:
                logger.info("✅ GPU поддержка (NVENC) доступна для ffmpeg")
                return True
            else:
                logger.info("❌ GPU поддержка недоступна, используем CPU")
                return False
                
        except Exception as e:
            logger.warning(f"Ошибка проверки GPU: {e}, используем CPU")
            return False