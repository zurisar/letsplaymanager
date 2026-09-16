import os
import json
import uuid
from database import APP_DATA_DIR

class ProfileManager:
    def __init__(self):
        # Файл реестра будет лежать в Documents/LetsPlayManager/profiles.json
        self.profiles_file = os.path.join(APP_DATA_DIR, "profiles.json")
        self.data = self._load_or_migrate()

    def _load_or_migrate(self):
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Если файла нет, создаем базовый каркас
        if not os.path.exists(self.profiles_file):
            default_data = {
                "last_used_profile": "default",
                "show_selector_on_startup": True,
                "profiles": {
                    "default": {
                        "name": "Основной профиль",
                        "avatar_path": "",
                        "config_file": "config.json",
                        "db_file": "letsplay.db"
                    }
                }
            }
            self._save(default_data)
            
        with open(self.profiles_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # --- АВТО-ПРИВЯЗКА АВАТАРА ПО УМОЛЧАНИЮ ---
        default_profile = data.get("profiles", {}).get("default")
        if default_profile and not default_profile.get("avatar_path"):
            import shutil
            default_avatar_source = os.path.join(BASE_DIR, "assets", "avatar_default.jpg")
            default_avatar_dest = os.path.join(APP_DATA_DIR, "avatar_default.jpg")
            
            # Если картинка есть в папке с программой
            if os.path.exists(default_avatar_source):
                # Копируем ее в Документы, чтобы она не потерялась при обновлениях
                if not os.path.exists(default_avatar_dest):
                    try:
                        shutil.copy2(default_avatar_source, default_avatar_dest)
                    except Exception:
                        pass
                
                # Обновляем путь в реестре
                default_profile["avatar_path"] = default_avatar_dest
                self._save(data)
        # ------------------------------------------

        return data

    def _save(self, data):
        with open(self.profiles_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def save(self):
        """Принудительное сохранение текущего состояния реестра."""
        self._save(self.data)

    def get_all_profiles(self):
        return self.data.get("profiles", {})

    def get_profile(self, profile_id):
        return self.data["profiles"].get(profile_id)

    def get_last_used_profile(self):
        profile_id = self.data.get("last_used_profile", "default")
        # Если последнего профиля больше нет (например, был удален), откатываемся
        if profile_id not in self.data["profiles"]:
            profile_id = "default"
        return self.get_profile(profile_id), profile_id

    def set_last_used(self, profile_id):
        if profile_id in self.data["profiles"]:
            self.data["last_used_profile"] = profile_id
            self.save()

    # --- CRUD ОПЕРАЦИИ ДЛЯ ПРОФИЛЕЙ ---

    def create_profile(self, name, avatar_path=""):
        """Генерирует уникальный ID профиля и привязывает к нему новые файлы"""
        profile_id = "profile_" + uuid.uuid4().hex[:8]
        self.data["profiles"][profile_id] = {
            "name": name,
            "avatar_path": avatar_path,
            "config_file": f"config_{profile_id}.json",
            "db_file": f"letsplay_{profile_id}.db"
        }
        self.save()
        return profile_id

    def edit_profile(self, profile_id, name=None, avatar_path=None):
        """Обновляет имя и/или аватарку существующего профиля"""
        if profile_id in self.data["profiles"]:
            if name is not None:
                self.data["profiles"][profile_id]["name"] = name
            if avatar_path is not None:
                self.data["profiles"][profile_id]["avatar_path"] = avatar_path
            self.save()
            return True
        return False

    def delete_profile(self, profile_id):
        """Удаляет профиль из реестра и физически стирает его файлы с диска"""
        if profile_id == "default":
            # Защита от удаления базового профиля
            return False 

        if profile_id in self.data["profiles"]:
            p_data = self.data["profiles"][profile_id]
            
            # Собираем абсолютные пути ко всем файлам профиля
            db_path = os.path.join(APP_DATA_DIR, p_data.get("db_file", ""))
            config_path = os.path.join(APP_DATA_DIR, p_data.get("config_file", ""))
            avatar_path = p_data.get("avatar_path", "")
            
            # Физически удаляем файлы с диска
            for file_path in [db_path, config_path, avatar_path]:
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError:
                        pass # Файл может быть занят другим процессом
            
            del self.data["profiles"][profile_id]
            
            # Если мы удалили профиль, который был выбран последним, сбрасываем на default
            if self.data.get("last_used_profile") == profile_id:
                self.data["last_used_profile"] = "default"
                
            self.save()
            return True
        return False
    
    def generate_profile_id(self):
        """Возвращает новый ID, но еще не записывает его в реестр"""
        return "profile_" + uuid.uuid4().hex[:8]

    def add_profile_with_id(self, profile_id, name, avatar_path=""):
        """Добавляет профиль с заранее сгенерированным ID"""
        self.data["profiles"][profile_id] = {
            "name": name,
            "avatar_path": avatar_path,
            "config_file": f"config_{profile_id}.json",
            "db_file": f"letsplay_{profile_id}.db"
        }
        self.save()