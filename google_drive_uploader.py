import os
import pickle
import base64
import json
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

class GoogleDriveUploader:
    def __init__(self):
        """Инициализация и аутентификация."""
        self.creds = None  # Всегда инициализируем creds
        try:
            load_dotenv()
            token_base64 = os.getenv('GOOGLE_OAUTH_TOKEN_BASE64')
            if not token_base64:
                raise ValueError("Переменная окружения GOOGLE_OAUTH_TOKEN_BASE64 не найдена.")

            token_json = base64.b64decode(token_base64).decode('utf-8')
            creds_info = json.loads(token_json)
            
            self.creds = Credentials.from_authorized_user_info(creds_info, ['https://www.googleapis.com/auth/drive.file'])

            if not self.creds.valid:
                if self.creds.expired and self.creds.refresh_token:
                    print("Токен Google истек, обновляем...")
                    self.creds.refresh(Request())
                else:
                    # Этот блок не должен выполняться в автоматическом режиме
                    print("Требуется повторная аутентификация Google.")
                    self.creds = None # Сбрасываем, если не удалось обновить
        except Exception as e:
            print(f"❌ Ошибка при инициализации GoogleDriveUploader: {e}")
            self.creds = None # Убедимся, что creds None в случае любой ошибки
    
    def upload_file(self, file_path, file_name):
        """Загружает файл на Google Drive и возвращает ссылку."""
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                raise Exception("Не удалось получить учетные данные Google.")

        try:
            service = build('drive', 'v3', credentials=self.creds)
            
            file_metadata = {'name': file_name}
            media = MediaFileUpload(file_path, mimetype='video/mp4')
            
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            print(f"Файл '{file_name}' успешно загружен. ID: {file.get('id')}")
            return file.get('webViewLink')

        except Exception as e:
            print(f"Ошибка при загрузке файла на Google Drive: {e}")
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