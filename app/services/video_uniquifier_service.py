"""
Сервис для создания уникальных видео для каждого пользователя
app/services/video_uniquifier.py
"""
import os
import asyncio
import tempfile
import random
import hashlib
from pathlib import Path
import logging
from typing import Optional, List, Dict
import ffmpeg
from datetime import datetime

# Google Drive imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings
from app.database.connection import AsyncSessionLocal
from app.database.crud import UserCRUD

logger = logging.getLogger(__name__)

# Google Drive API настройки
SCOPES = ['https://www.googleapis.com/auth/drive']

class VideoUniquifierService:
    """Сервис для создания уникальных версий видео"""
    
    def __init__(self):
        self.service = None
        self.video_materials_folder_id = None
        self.temp_dir = Path("temp_videos")
        self.temp_dir.mkdir(exist_ok=True)
    
    async def initialize_google_drive(self):
        """Инициализация Google Drive API с OAuth 2.0 (обновлённая версия)"""
        try:
            key_file_path = os.path.join(os.getcwd(), settings.OAuth_client)

            if not os.path.exists(key_file_path):
                logger.error(f"❌ OAuth client file not found: {key_file_path}")
                return False

            # -----------------------------------------------------------------
            # ← ИЗМЕНЕНО: берём имя/путь к token.json из переменной окружения
            #             или из settings.GOOGLE_TOKEN_FILE
            # -----------------------------------------------------------------
            token_file_env = os.getenv("GOOGLE_TOKEN_FILE", settings.GOOGLE_TOKEN_FILE)  # ← ИЗМЕНЕНО
            # если указано относительное имя, «привязываем» к текущей директории
            token_path = (                                                          # ← ИЗМЕНЕНО
                token_file_env if os.path.isabs(token_file_env)
                else os.path.join(os.getcwd(), token_file_env)
            )
            # -----------------------------------------------------------------

            # Проверяем существующие credentials
            creds = None
            if os.path.exists(token_path):
                logger.info(f"📋 Loading existing token from {token_path}...")
                creds = Credentials.from_authorized_user_file(token_path, SCOPES)

            # Если credentials отсутствуют или недействительны
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("🔄 Refreshing expired token...")
                    creds.refresh(Request())

                    # Сохраняем обновлённый токен
                    with open(token_path, 'w') as token:
                        token.write(creds.to_json())
                    logger.info(f"✅ Token refreshed and saved to {token_path}")

                else:
                    # ❌ ПРОБЛЕМА: Нет токена и нет браузера на сервере
                    logger.error("❌ No valid token found and no browser available for OAuth")
                    logger.error("🔧 SOLUTION: Create token.json on a machine with browser:")
                    logger.error("   1. Run create_token.py script on machine with GUI")
                    logger.error("   2. Copy generated token.json to server")
                    logger.error(f"   3. Place token.json here: {token_path}")
                    return False

            # Инициализируем сервис
            self.service = build('drive', 'v3', credentials=creds)

            # Создаём или находим папку «видео-материалы»
            self.video_materials_folder_id = await self._get_or_create_video_folder()

            logger.info("✅ Google Drive API initialized with OAuth 2.0")
            return True

        except Exception as e:
            logger.error(f"❌ Error initializing Google Drive: {e}")
            return False

    
    async def _get_or_create_video_folder(self) -> str:
        """Получить или создать папку 'видео-материалы'"""
        try:
            # Ищем существующую папку
            results = self.service.files().list(
                q="name='видео-материалы' and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                folder_id = folders[0]['id']
                logger.info(f"✅ Found existing video folder: {folder_id}")
                return folder_id
            
            # Создаем новую папку
            folder_metadata = {
                'name': 'видео-материалы',
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"✅ Created new video folder: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"❌ Error with video folder: {e}")
            raise
    
    async def get_all_users_for_video_processing(self) -> List[Dict]:
        """Получить всех пользователей для создания видео"""
        try:
            async with AsyncSessionLocal() as session:
                # Получаем всех завершивших онбординг пользователей
                from sqlalchemy import select
                from app.database.models import User, OnboardingStage
                
                result = await session.execute(
                    select(User).where(
                        User.onboarding_stage == OnboardingStage.COMPLETED
                    )
                )
                users = result.scalars().all()
                
                user_list = []
                for user in users:
                    user_data = {
                        'telegram_id': user.telegram_id,
                        'username': user.username or f"user_{user.telegram_id}",
                        'full_name': user.full_name,
                        'ref_code': user.ref_code
                    }
                    user_list.append(user_data)
                
                logger.info(f"📊 Found {len(user_list)} users for video processing")
                return user_list
                
        except Exception as e:
            logger.error(f"❌ Error getting users: {e}")
            return []
    
    def generate_unique_params(self, user_identifier: str) -> Dict:
        """Генерируем уникальные параметры для пользователя"""
        # Используем user_identifier как seed для воспроизводимости
        random.seed(hashlib.md5(user_identifier.encode()).hexdigest())
        
        params = {
            # Размер кадра (легкое масштабирование)
            'scale_factor': random.uniform(0.98, 1.02),
            # Скорость видео (очень небольшие изменения)
            'speed': random.choice([0.98, 0.99, 1.0, 1.01, 1.02]),
            # Рамка/подложка
            'border_size': random.randint(2, 8),
            'border_color': random.choice(['black', 'white', '#1a1a1a', '#f0f0f0']),
            # Водяной знак
            'watermark_text': f"ID:{user_identifier[-6:]}",
            'watermark_position': random.choice(['top_left', 'top_right', 'bottom_left', 'bottom_right']),
            'watermark_opacity': random.uniform(0.1, 0.3),
            # Звук
            'volume': random.uniform(0.95, 1.05),
            # Смещение начала/конца (очень маленькие)
            'start_offset': random.uniform(0, 0.5),
            'end_offset': random.uniform(0, 0.5),
            # Цветовая коррекция (минимальные изменения)
            'brightness': random.uniform(0.98, 1.02),
            'contrast': random.uniform(0.98, 1.02),
            'saturation': random.uniform(0.98, 1.02),
            # Случайное зерно для шума (для уникальности хеша)
            'noise_seed': random.randint(1000, 9999)
        }
        
        return params
    
    async def create_unique_video(self, source_video_path: str, user_data: Dict, 
                                 output_path: str) -> bool:
        """Создание уникальной версии видео"""
        try:
            logger.info(f"Input video path: {source_video_path}, exists: {os.path.exists(source_video_path)}")
            logger.info(f"Output video path: {output_path}")

            user_identifier = f"{user_data['telegram_id']}_{user_data['ref_code']}"
            params = self.generate_unique_params(user_identifier)
            
            logger.info(f"🎬 Creating unique video for {user_data['username']}")
            logger.info(f"FFmpeg params: {params}")
            
            # Получаем информацию о видео
            probe = ffmpeg.probe(source_video_path, cmd='/usr/bin/ffprobe')
            video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
            duration = float(probe['format']['duration'])
            
            # Вычисляем новую продолжительность
            new_duration = duration - params['start_offset'] - params['end_offset']
            
            if new_duration <= 0:
                new_duration = duration  # Если слишком короткое, не обрезаем
                params['start_offset'] = 0
                params['end_offset'] = 0
            
            # Строим pipeline обработки
            input_video = ffmpeg.input(source_video_path, ss=params['start_offset'])
            
            # Видео обработка
            video = input_video.video
            
            # Масштабирование (если нужно)
            if abs(params['scale_factor'] - 1.0) > 0.001:
                new_width = int(int(video_info['width']) * params['scale_factor'])
                new_height = int(int(video_info['height']) * params['scale_factor'])
                # Убеждаемся, что размеры четные (требование x264)
                new_width = new_width if new_width % 2 == 0 else new_width + 1
                new_height = new_height if new_height % 2 == 0 else new_height + 1
                video = ffmpeg.filter(video, 'scale', new_width, new_height)
            
            # Добавляем небольшую рамку
            if params['border_size'] > 0:
                video = ffmpeg.filter(
                    video, 'pad', 
                    width=f"iw+{params['border_size']*2}",
                    height=f"ih+{params['border_size']*2}",
                    x=params['border_size'],
                    y=params['border_size'],
                    color=params['border_color']
                )
            
            # Цветовая коррекция (минимальная)
            video = ffmpeg.filter(
                video, 'eq',
                brightness=params['brightness'] - 1,
                contrast=params['contrast'],
                saturation=params['saturation']
            )
            
            # Водяной знак (очень незаметный)
            watermark_positions = {
                'top_left': f'x=10:y=10',
                'top_right': f'x=w-text_w-10:y=10',
                'bottom_left': f'x=10:y=h-text_h-10',
                'bottom_right': f'x=w-text_w-10:y=h-text_h-10'
            }
            
            video = ffmpeg.filter(
                video, 'drawtext',
                text=params['watermark_text'],
                fontsize=12,
                fontcolor=f'white@{params["watermark_opacity"]}',
                **dict(item.split('=') for item in watermark_positions[params['watermark_position']].split(':'))
            )
            
            # Аудио обработка
            audio = input_video.audio
            
            # Громкость
            if abs(params['volume'] - 1.0) > 0.001:
                audio = ffmpeg.filter(audio, 'volume', params['volume'])
            
            # Скорость (если изменена)
            if abs(params['speed'] - 1.0) > 0.001:
                video = ffmpeg.filter(video, 'setpts', f"{1/params['speed']}*PTS")
                audio = ffmpeg.filter(audio, 'atempo', params['speed'])
            
            # Обрезка по времени
            if params['end_offset'] > 0:
                video = ffmpeg.filter(video, 'trim', duration=new_duration)
                audio = ffmpeg.filter(audio, 'atrim', duration=new_duration)
            
            # Объединяем и выводим
            out = ffmpeg.output(
                video, audio, output_path,
                **{
                    'c:v': 'libx264',  # Видеокодек
                    'c:a': 'aac',      # Аудиокодек
                    'preset': 'fast',  # Пресет кодирования
                    'crf': '28',       # Качество видео (увеличено для сжатия)
                    'f': 'mp4',        # Формат выходного файла
                    'map_metadata': '-1'  # Удаление всех метаданных
                }
            )
            
            # Логируем эквивалентную команду FFmpeg
            ffmpeg_cmd = out.compile(cmd='/usr/bin/ffmpeg')
            logger.info(f"FFmpeg command: {' '.join(ffmpeg_cmd)}")
            
            # Запускаем обработку
            try:
                process = await asyncio.get_event_loop().run_in_executor(
                    None, 
                    lambda: ffmpeg.run(out, overwrite_output=True, quiet=False, cmd='/usr/bin/ffmpeg', capture_stderr=True)
                )
            except ffmpeg.Error as e:
                logger.error(f"FFmpeg stderr: {e.stderr.decode()}")
                raise
            
            logger.info(f"✅ Created unique video for {user_data['username']}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error creating video for {user_data['username']}: {e}")
            return False
    
    async def upload_to_user_folder(self, video_path: str, user_data: Dict) -> bool:
        """Загрузка видео в папку пользователя на Google Drive"""
        try:
            username = user_data['username']
            
            # Создаем или находим папку пользователя
            user_folder_id = await self._get_or_create_user_folder(username)
            
            # Подготавливаем метаданные файла
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"unique_video_{timestamp}.mp4"
            
            file_metadata = {
                'name': filename,
                'parents': [user_folder_id],
                'description': f'Уникальное видео для пользователя {username} (ID: {user_data["telegram_id"]})'
            }
            
            # Загружаем файл
            media = MediaFileUpload(video_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            web_link = file.get('webViewLink')
            
            logger.info(f"✅ Video uploaded for {username}: {file_id}, link: {web_link}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error uploading video for {user_data['username']}: {e}")
            return False
    
    async def _get_or_create_user_folder(self, username: str) -> str:
        """Получить или создать папку пользователя"""
        try:
            # Ищем существующую папку пользователя
            results = self.service.files().list(
                q=f"name='{username}' and '{self.video_materials_folder_id}' in parents and mimeType='application/vnd.google-apps.folder'",
                fields="files(id, name)"
            ).execute()
            
            folders = results.get('files', [])
            
            if folders:
                return folders[0]['id']
            
            # Создаем новую папку
            folder_metadata = {
                'name': username,
                'parents': [self.video_materials_folder_id],
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"✅ Created folder for user {username}: {folder_id}")
            return folder_id
            
        except Exception as e:
            logger.error(f"❌ Error with user folder for {username}: {e}")
            raise
    
    async def process_video_for_all_users(self, source_video_path: str, 
                                        progress_callback=None) -> Dict:
        """Основной метод - обработка видео для всех пользователей"""
        logger.info("🎬 Starting video processing for all users")
        
        # Инициализируем Google Drive
        if not await self.initialize_google_drive():
            return {
                'success': False,
                'error': 'Failed to initialize Google Drive',
                'processed': 0,
                'total': 0,
                'success_rate': 0,  # ✅ Добавляем отсутствующий ключ
                'errors': ['Failed to initialize Google Drive - check token.json file']
            }
        
        # Получаем список пользователей
        users = await self.get_all_users_for_video_processing()
        
        if not users:
            return {
                'success': False,
                'error': 'No users found',
                'processed': 0,
                'total': 0
            }
        
        total_users = len(users)
        processed_count = 0
        errors = []
        
        logger.info(f"📊 Processing video for {total_users} users")
        
        for i, user_data in enumerate(users):
            try:
                username = user_data['username']
                
                # Уведомляем о прогрессе (для админа, пользователи не получают)
                if progress_callback:
                    await progress_callback(i + 1, total_users, username)
                
                # Создаем временный файл для уникального видео
                temp_video_path = self.temp_dir / f"{username}_{user_data['telegram_id']}_unique.mp4"
                
                # Создаем уникальное видео
                if await self.create_unique_video(source_video_path, user_data, str(temp_video_path)):
                    # Загружаем на Google Drive
                    if await self.upload_to_user_folder(str(temp_video_path), user_data):
                        processed_count += 1
                    else:
                        errors.append(f"Upload failed for {username}")
                else:
                    errors.append(f"Video creation failed for {username}")
                
                # Удаляем временный файл
                if temp_video_path.exists():
                    temp_video_path.unlink()
                
                # Небольшая пауза между обработками
                await asyncio.sleep(0.5)
                
            except Exception as e:
                error_msg = f"Error processing {user_data.get('username', 'unknown')}: {e}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
        
        # Очищаем временную папку
        self._cleanup_temp_files()
        
        result = {
            'success': processed_count > 0,
            'processed': processed_count,
            'total': total_users,
            'errors': errors,
            'success_rate': (processed_count / total_users * 100) if total_users > 0 else 0
        }
        
        logger.info(f"🎉 Video processing completed: {processed_count}/{total_users} successful")
        return result
    
    def _cleanup_temp_files(self):
        """Очистка временных файлов"""
        try:
            for file_path in self.temp_dir.glob("*.mp4"):
                file_path.unlink()
            logger.info("🧹 Temporary files cleaned up")
        except Exception as e:
            logger.error(f"❌ Error cleaning temp files: {e}")

# Глобальный экземпляр сервиса
video_uniquifier_service = VideoUniquifierService()
