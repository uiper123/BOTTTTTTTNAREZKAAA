import os
import asyncio
import logging
import whisper
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

class SubtitleGenerator:
    def __init__(self):
        # Загружаем легкую модель Whisper
        self.model = None
        self.model_name = "base"  # Можно использовать "tiny" для еще большей скорости
    
    def _load_model(self):
        """Ленивая загрузка модели"""
        if self.model is None:
            logger.info(f"Загрузка модели Whisper: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
    
    async def generate(self, video_path: str) -> list:
        """Генерация субтитров для видео"""
        try:
            loop = asyncio.get_event_loop()
            subtitles = await loop.run_in_executor(
                None,
                self._generate_sync,
                video_path
            )
            return subtitles
            
        except Exception as e:
            logger.error(f"Ошибка генерации субтитров: {e}")
            return []
    
    def _generate_sync(self, video_path: str) -> list:
        """Синхронная генерация субтитров"""
        try:
            self._load_model()
            
            logger.info(f"Генерация субтитров для: {video_path}")
            
            # Извлекаем аудио и генерируем субтитры с детальными временными метками
            result = self.model.transcribe(
                video_path,
                language='ru',  # Русский язык
                word_timestamps=True,  # Временные метки для слов
                verbose=False
            )
            
            # Сначала пробуем получить субтитры по словам из сегментов
            word_subtitles = []
            for segment in result['segments']:
                if 'words' in segment and segment['words']:
                    # Если в сегменте есть слова с временными метками
                    for word_info in segment['words']:
                        word = word_info.get('word', '').strip()
                        start = word_info.get('start', segment['start'])
                        end = word_info.get('end', segment['end'])
                        
                        if word:
                            word_subtitles.append({
                                'start': start,
                                'end': end,
                                'text': word
                            })
                else:
                    # Если нет детальных слов, разбиваем текст сегмента на слова
                    words = segment['text'].strip().split()
                    if words:
                        segment_duration = segment['end'] - segment['start']
                        word_duration = segment_duration / len(words)
                        
                        for i, word in enumerate(words):
                            start = segment['start'] + (i * word_duration)
                            end = start + word_duration
                            
                            word_subtitles.append({
                                'start': start,
                                'end': end,
                                'text': word
                            })
            
            if word_subtitles:
                logger.info(f"Создано {len(word_subtitles)} субтитров по словам")
                return word_subtitles
            
            # Если не удалось получить слова, используем сегменты
            subtitles = []
            for segment in result['segments']:
                subtitle = {
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text'].strip()
                }
                subtitles.append(subtitle)
            
            logger.info(f"Создано {len(subtitles)} субтитров по сегментам")
            return subtitles
            
        except Exception as e:
            logger.error(f"Ошибка синхронной генерации субтитров: {e}")
            return []
    
    def _create_word_subtitles(self, words: list) -> list:
        """Создание субтитров по одному слову для лучшей анимации"""
        try:
            subtitles = []
            
            for word_info in words:
                word = word_info.get('word', '').strip()
                start = word_info.get('start', 0)
                end = word_info.get('end', 0)
                
                if not word:
                    continue
                
                # Создаем субтитр для каждого слова отдельно
                subtitle = {
                    'start': start,
                    'end': end,
                    'text': word
                }
                subtitles.append(subtitle)
            
            return subtitles
            
        except Exception as e:
            logger.error(f"Ошибка создания субтитров по словам: {e}")
            return []
    
    def save_srt(self, subtitles: list, output_path: str):
        """Сохранение субтитров в формате SRT"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    start_time = self._seconds_to_srt_time(sub['start'])
                    end_time = self._seconds_to_srt_time(sub['end'])
                    
                    f.write(f"{i}\n")
                    f.write(f"{start_time} --> {end_time}\n")
                    f.write(f"{sub['text']}\n\n")
            
            logger.info(f"Субтитры сохранены: {output_path}")
            
        except Exception as e:
            logger.error(f"Ошибка сохранения SRT: {e}")
    
    def _seconds_to_srt_time(self, seconds: float) -> str:
        """Конвертация секунд в формат времени SRT"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millisecs = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millisecs:03d}"