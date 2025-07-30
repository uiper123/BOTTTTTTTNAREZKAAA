import os
import pickle
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

class GoogleDriveUploader:
    def __init__(self):
        self.service = self._authenticate()
        
    def _authenticate(self):
        """Аутентификация в Google Drive API"""
        try:
            # Декодируем токен из base64
            token_base64 = os.getenv('GOOGLE_OAUTH_TOKEN_BASE64')
            if not token_base64:
                raise Exception("GOOGLE_OAUTH_TOKEN_BASE64 не найден в переменных окружения")
            
            # Декодируем и загружаем credentials
            token_data = base64.b64decode(token_base64)
            credentials = pickle.loads(token_data)
            
            # Обновляем токен если необходимо
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            
            # Создаем сервис
            service = build('drive', 'v3', credentials=credentials)
            return service
            
        except Exception as e:
            print(f"Ошибка аутентификации Google Drive: {e}")
            raise
    
    async def upload_file(self, file_path, filename):
        """Загрузка файла на Google Drive"""
        try:
            # Метаданные файла
            file_metadata = {
                'name': filename,
                'parents': [self._get_or_create_folder()]
            }
            
            # Загружаем файл
            media = MediaFileUpload(file_path, resumable=True)
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            
            file_id = file.get('id')
            
            # Делаем файл общедоступным
            self.service.permissions().create(
                fileId=file_id,
                body={'role': 'reader', 'type': 'anyone'}
            ).execute()
            
            # Возвращаем прямую ссылку для скачивания
            download_link = f"https://drive.google.com/uc?export=download&id={file_id}"
            return download_link
            
        except Exception as e:
            print(f"Ошибка загрузки файла {filename}: {e}")
            raise
    
    def _get_or_create_folder(self):
        """Получение или создание папки для видео"""
        folder_name = "Telegram Bot Videos"
        
        # Ищем существующую папку
        results = self.service.files().list(
            q=f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder'",
            fields="files(id, name)"
        ).execute()
        
        folders = results.get('files', [])
        
        if folders:
            return folders[0]['id']
        else:
            # Создаем новую папку
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            
            folder = self.service.files().create(
                body=folder_metadata,
                fields='id'
            ).execute()
            
            return folder.get('id')
    
    def list_files(self):
        """Список файлов в папке (для отладки)"""
        try:
            folder_id = self._get_or_create_folder()
            results = self.service.files().list(
                q=f"'{folder_id}' in parents",
                fields="files(id, name, createdTime)"
            ).execute()
            
            files = results.get('files', [])
            return files
            
        except Exception as e:
            print(f"Ошибка получения списка файлов: {e}")
            return []