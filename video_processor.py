import os
import asyncio
import logging
import ffmpeg
from pathlib import Path
from youtube_downloader import YouTubeDownloader
from video_editor import VideoEditor
from subtitle_generator import SubtitleGenerator
from google_drive_uploader import GoogleDriveUploader
from gpu_monitor import GPUMonitor

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
            # 1. Скачиваем видео (автоматически использует cookies если доступны)
            logger.info(f"Скачивание YouTube видео: {url}")
            download_result = await self.youtube_downloader.download_with_cookies(url)
            
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
        """Обработка видео файла с мониторингом GPU"""
        try:
            duration = config.get('duration', 30)
            
            # Запускаем мониторинг GPU
            gpu_monitor = GPUMonitor()
            monitor_task = asyncio.create_task(gpu_monitor.start_monitoring(interval=1.0))
            
            try:
                # 1. Получаем информацию о видео
                video_info = self.video_editor.get_video_info(video_path)
                total_duration = video_info['duration']
                
                logger.info(f"🎮 Обработка видео длительностью {total_duration} секунд с мониторингом GPU")
                
                # 2. Если видео больше 5 минут, нарезаем на чанки
                chunks = []
                if total_duration > 300:  # 5 минут
                    logger.info(f"🔪 Видео {total_duration:.1f} сек > 300 сек, нарезаем на чанки")
                    chunks = await self.split_into_chunks(video_path, chunk_duration=300)
                    logger.info(f"📦 Создано чанков: {len(chunks)}")
                else:
                    logger.info(f"📹 Видео {total_duration:.1f} сек <= 300 сек, обрабатываем целиком")
                    chunks = [video_path]
            
                # КРИТИЧЕСКАЯ ПРОВЕРКА: убеждаемся что все чанки существуют
                existing_chunks = []
                for i, chunk_path in enumerate(chunks):
                    if os.path.exists(chunk_path):
                        chunk_info = self.video_editor.get_video_info(chunk_path)
                        existing_chunks.append(chunk_path)
                        logger.info(f"✅ Чанк {i+1} существует: {chunk_path} ({chunk_info['duration']:.1f} сек)")
                    else:
                        logger.error(f"❌ Чанк {i+1} НЕ СУЩЕСТВУЕТ: {chunk_path}")
                
                logger.info(f"📊 ИТОГО готовых чанков: {len(existing_chunks)}/{len(chunks)}")
                chunks = existing_chunks
                
                # 3. Обрабатываем каждый чанк
                all_clips = []
                total_expected_clips = 0
                
                for i, chunk_path in enumerate(chunks):
                    logger.info(f"🎬 НАЧИНАЕМ обработку чанка {i+1}/{len(chunks)}: {chunk_path}")
                    
                    try:
                        # Получаем информацию о чанке
                        chunk_info = self.video_editor.get_video_info(chunk_path)
                        chunk_duration = chunk_info['duration']
                        expected_clips_in_chunk = int(chunk_duration // duration)
                        total_expected_clips += expected_clips_in_chunk
                        
                        logger.info(f"   📏 Длительность чанка: {chunk_duration:.1f} сек")
                        logger.info(f"   🎯 Ожидается клипов: {expected_clips_in_chunk}")
                        
                        # Генерируем субтитры для чанка
                        logger.info(f"   🎤 Генерируем субтитры...")
                        subtitles = await self.subtitle_generator.generate(chunk_path)
                        logger.info(f"   ✅ Субтитры готовы: {len(subtitles)} фраз")
                        
                        # Нарезаем чанк на клипы
                        logger.info(f"   ✂️  Нарезаем на клипы...")
                        # Используем МАКСИМАЛЬНУЮ параллельную обработку для Tesla T4
                        clips = await self.video_editor.create_clips_parallel(
                            chunk_path, 
                            duration, 
                            subtitles,
                            start_index=len(all_clips),
                            config=config,
                            max_parallel=32  # МАКСИМАЛЬНАЯ параллельность для Tesla T4 (15GB памяти)
                        )
                        
                        logger.info(f"   🎉 Создано клипов из чанка {i+1}: {len(clips)}")
                        all_clips.extend(clips)
                        
                    except Exception as e:
                        logger.error(f"❌ ОШИБКА обработки чанка {i+1}: {e}")
                        continue
                    
                    # Удаляем временный чанк (если это не оригинальный файл)
                    if chunk_path != video_path and os.path.exists(chunk_path):
                        os.remove(chunk_path)
                        logger.info(f"   🗑️  Удален временный чанк: {chunk_path}")
                
                # ФИНАЛЬНАЯ СТАТИСТИКА
                logger.info(f"🏁 ФИНАЛЬНАЯ СТАТИСТИКА ОБРАБОТКИ:")
                logger.info(f"   📹 Исходное видео: {total_duration:.1f} сек")
                logger.info(f"   📦 Обработано чанков: {len(chunks)}")
                logger.info(f"   🎯 Ожидалось клипов: {total_expected_clips}")
                logger.info(f"   ✅ Создано клипов: {len(all_clips)}")
                logger.info(f"   📊 Эффективность: {len(all_clips)/total_expected_clips*100:.1f}%" if total_expected_clips > 0 else "   📊 Эффективность: 0%")
                
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
                
            finally:
                # Останавливаем мониторинг GPU
                gpu_monitor.stop_monitoring()
                await monitor_task
                gpu_monitor.print_summary()
            
        except Exception as e:
            logger.error(f"Ошибка обработки видео: {e}")
            return {'success': False, 'error': str(e)}
    
    async def split_into_chunks(self, video_path: str, chunk_duration: int = 300) -> list:
        """МАКСИМАЛЬНО БЫСТРАЯ нарезка видео на чанки (как в вашем примере + параллельность)"""
        try:
            video_info = self.video_editor.get_video_info(video_path)
            total_duration = int(video_info['duration'])
            
            # Если видео короткое - не делим на части (как в вашем примере)
            if total_duration <= chunk_duration:
                logger.info(f"Видео {total_duration} сек <= {chunk_duration} сек, не делим на чанки")
                return [video_path]
            
            # Вычисляем количество частей (как в вашем примере)
            import math
            num_chunks = math.ceil(total_duration / chunk_duration)
            logger.info(f"Делим видео {total_duration} сек на {num_chunks} чанков по {chunk_duration} сек")
            
            # Подготавливаем все задачи для параллельной обработки
            chunk_tasks = []
            chunk_paths = []
            
            for i in range(num_chunks):
                start_time = i * chunk_duration
                actual_duration = min(chunk_duration, total_duration - start_time)
                chunk_path = self.temp_dir / f"chunk_{i}.mp4"
                
                chunk_tasks.append({
                    'input_path': video_path,
                    'output_path': str(chunk_path),
                    'start_time': start_time,
                    'duration': actual_duration,
                    'index': i
                })
                chunk_paths.append(str(chunk_path))
            
            logger.info(f"Начинаем СУПЕР БЫСТРУЮ параллельную нарезку {len(chunk_tasks)} чанков...")
            
            # ПАРАЛЛЕЛЬНО создаем все чанки с прямыми командами ffmpeg
            tasks = [
                self._create_chunk_ultra_fast(task) 
                for task in chunk_tasks
            ]
            
            # Ждем завершения всех задач
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Проверяем результаты
            successful_chunks = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Ошибка создания чанка {i}: {result}")
                elif result:
                    successful_chunks.append(chunk_paths[i])
                    logger.info(f"✅ Чанк {i+1}/{num_chunks} готов: {chunk_tasks[i]['duration']} сек")
                else:
                    logger.warning(f"❌ Не удалось создать чанк {i}")
            
            logger.info(f"🚀 СУПЕР БЫСТРО создано {len(successful_chunks)}/{num_chunks} чанков")
            
            # КРИТИЧЕСКАЯ ДИАГНОСТИКА: проверяем каждый чанк
            logger.info(f"🔍 ДИАГНОСТИКА СОЗДАННЫХ ЧАНКОВ:")
            total_chunks_duration = 0
            for i, chunk_path in enumerate(successful_chunks):
                try:
                    if os.path.exists(chunk_path):
                        chunk_info = self.video_editor.get_video_info(chunk_path)
                        chunk_duration = chunk_info['duration']
                        total_chunks_duration += chunk_duration
                        logger.info(f"   ✅ Чанк {i+1}: {chunk_duration:.1f} сек - {chunk_path}")
                    else:
                        logger.error(f"   ❌ Чанк {i+1}: ФАЙЛ НЕ СУЩЕСТВУЕТ - {chunk_path}")
                except Exception as e:
                    logger.error(f"   ❌ Чанк {i+1}: ОШИБКА ЧТЕНИЯ - {e}")
            
            logger.info(f"📊 ИТОГО длительность чанков: {total_chunks_duration:.1f} сек из {total_duration:.1f} сек")
            coverage = (total_chunks_duration / total_duration) * 100 if total_duration > 0 else 0
            logger.info(f"📈 Покрытие видео чанками: {coverage:.1f}%")
            
            if coverage < 95:
                logger.warning(f"⚠️  ПРОБЛЕМА: Чанки покрывают только {coverage:.1f}% исходного видео!")
            
            return successful_chunks
            
        except Exception as e:
            logger.error(f"Ошибка супер быстрой нарезки на чанки: {e}")
            return [video_path]  # Возвращаем оригинальный файл
    
    async def _create_chunk_ultra_fast(self, task: dict) -> bool:
        """СУПЕР БЫСТРОЕ создание чанка с таймаутом и fallback"""
        try:
            logger.info(f"🚀 Начинаем создание чанка {task['index']}: {task['start_time']}-{task['start_time'] + task['duration']} сек")
            
            loop = asyncio.get_event_loop()
            
            # Добавляем таймаут 60 секунд для каждого чанка
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    self._create_chunk_direct_command,
                    task['input_path'],
                    task['output_path'], 
                    task['start_time'],
                    task['duration']
                ),
                timeout=60.0  # 60 секунд таймаут
            )
            
            # Проверяем, что файл действительно создался
            if os.path.exists(task['output_path']):
                file_size = os.path.getsize(task['output_path'])
                logger.info(f"✅ Чанк {task['index']} создан успешно: {file_size} байт")
                return True
            else:
                logger.error(f"❌ Чанк {task['index']} НЕ СОЗДАЛСЯ: файл отсутствует")
                return False
            
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Таймаут создания чанка {task['index']}, пробуем CPU fallback")
            # Пробуем CPU fallback
            try:
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self._create_chunk_cpu_fallback,
                        task['input_path'],
                        task['output_path'], 
                        task['start_time'],
                        task['duration']
                    ),
                    timeout=120.0  # 2 минуты для CPU
                )
                logger.info(f"✅ Чанк {task['index']} создан через CPU fallback")
                return True
            except Exception as fallback_error:
                logger.error(f"❌ CPU fallback тоже не сработал для чанка {task['index']}: {fallback_error}")
                return False
                
        except Exception as e:
            logger.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА создания чанка {task['index']}: {e}")
            logger.error(f"   Параметры чанка: start={task['start_time']}, duration={task['duration']}, output={task['output_path']}")
            return False
    
    def _create_chunk_direct_command(self, input_path: str, output_path: str, start_time: int, duration: int):
        """Прямая команда ffmpeg с GPU ускорением для максимальной скорости"""
        import subprocess
        
        # Проверяем доступность GPU
        gpu_available = self._check_gpu_support()
        
        if gpu_available:
            # GPU ускоренная команда (NVIDIA)
            cmd = [
                'ffmpeg',
                '-hwaccel', 'cuda',           # Аппаратное ускорение CUDA
                '-hwaccel_output_format', 'cuda',  # Выходной формат CUDA
                '-ss', str(start_time),       # Время начала
                '-i', input_path,             # Входной файл
                '-t', str(duration),          # Длительность
                '-c:v', 'h264_nvenc',         # GPU кодировщик NVIDIA
                '-c:a', 'copy',               # Аудио копируем
                '-preset', 'p1',              # Самый быстрый пресет для NVENC
                '-tune', 'hq',                # Высокое качество
                '-rc', 'vbr',                 # Переменный битрейт
                '-cq', '20',                  # Более высокое качество для Tesla T4
                '-b:v', '8M',                 # Увеличенный битрейт для Tesla T4
                '-maxrate', '12M',            # Увеличенный максимальный битрейт
                '-bufsize', '16M',            # Увеличенный размер буфера для Tesla T4
                '-gpu', '0',                  # Используем первый GPU
                '-threads', '0',              # Автоматическое определение потоков
                '-bf', '3',                   # B-кадры для лучшего сжатия
                '-refs', '3'                  # Референсные кадры
                '-avoid_negative_ts', 'make_zero',
                '-y',                         # Перезаписывать без вопросов
                output_path
            ]
            logger.info(f"🎮 Используем GPU для нарезки чанка")
        else:
            # Обычная CPU команда (как раньше)
            cmd = [
                'ffmpeg',
                '-ss', str(start_time),        # Время начала
                '-i', input_path,              # Входной файл
                '-t', str(duration),           # Длительность
                '-c', 'copy',                  # Копирование без перекодирования
                '-avoid_negative_ts', 'make_zero',
                '-y',                          # Перезаписывать без вопросов
                output_path
            ]
            logger.info(f"💻 Используем CPU для нарезки чанка")
        
        # Запускаем команду с правильной кодировкой для Windows
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True,
            encoding='utf-8',  # Принудительно используем UTF-8
            errors='ignore',   # Игнорируем ошибки кодировки
            check=False        # Не бросаем исключение при ошибке
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка ffmpeg: {result.stderr}")
            # Если GPU команда не сработала, пробуем CPU
            if gpu_available:
                logger.warning("GPU команда не сработала, пробуем CPU...")
                return self._create_chunk_cpu_fallback(input_path, output_path, start_time, duration)
            else:
                raise Exception(f"ffmpeg завершился с кодом {result.returncode}")
    
    def _check_gpu_support(self) -> bool:
        """Проверка поддержки GPU для ffmpeg"""
        try:
            import subprocess
            
            # Проверяем наличие NVIDIA GPU
            result = subprocess.run(
                ['nvidia-smi'], 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='ignore',
                check=False
            )
            if result.returncode != 0:
                return False
            
            # Проверяем поддержку NVENC в ffmpeg
            result = subprocess.run(
                ['ffmpeg', '-encoders'], 
                capture_output=True, 
                text=True,
                encoding='utf-8',
                errors='ignore',
                check=False
            )
            if 'h264_nvenc' in result.stdout:
                logger.info("✅ GPU поддержка (NVENC) доступна")
                return True
            else:
                logger.info("❌ GPU поддержка (NVENC) недоступна")
                return False
                
        except Exception as e:
            logger.warning(f"Ошибка проверки GPU: {e}")
            return False
    
    def _create_chunk_cpu_fallback(self, input_path: str, output_path: str, start_time: int, duration: int):
        """Резервная CPU команда если GPU не работает"""
        import subprocess
        
        cmd = [
            'ffmpeg',
            '-ss', str(start_time),
            '-i', input_path,
            '-t', str(duration),
            '-c', 'copy',
            '-avoid_negative_ts', 'make_zero',
            '-y',
            output_path
        ]
        
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            encoding='utf-8',
            errors='ignore',
            check=False
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка CPU fallback: {result.stderr}")
            raise Exception(f"CPU fallback завершился с кодом {result.returncode}")
    
    async def _create_chunk_fast(self, task: dict) -> bool:
        """Быстрое создание одного чанка (старый метод через python-ffmpeg)"""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._create_chunk_sync_fast,
                task['input_path'],
                task['output_path'], 
                task['start_time'],
                task['duration']
            )
            return True
        except Exception as e:
            logger.error(f"Ошибка создания чанка {task['index']}: {e}")
            return False
    
    def _create_chunk_sync_fast(self, input_path: str, output_path: str, start_time: float, duration: float):
        """Синхронное быстрое создание чанка с максимальной оптимизацией"""
        # МАКСИМАЛЬНО БЫСТРАЯ нарезка с stream copy
        (
            ffmpeg
            .input(input_path, 
                   ss=start_time,           # Точное время начала
                   t=duration,              # Длительность
                   copyts=True)             # Сохраняем временные метки
            .output(output_path, 
                   vcodec='copy',           # Копируем видео (без перекодирования)
                   acodec='copy',           # Копируем аудио (без перекодирования)
                   avoid_negative_ts='make_zero',  # Избегаем проблем с таймингом
                   map_metadata=0,          # Копируем метаданные
                   movflags='faststart')    # Оптимизация для быстрого старта
            .overwrite_output()
            .run(quiet=True, capture_stdout=True, capture_stderr=True)
        )
    
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