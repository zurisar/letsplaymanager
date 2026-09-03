import sys
import os
import json
import logging
import shutil
import updater
from database import DB_NAME, APP_DATA_DIR

APP_VERSION = "0.6"

# Теперь config.py лежит в папке core, поэтому BASE_DIR это папка уровнем выше
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')
LOG_FILE = os.path.join(BASE_DIR, 'run.log')

# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
def setup_logging():
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        encoding='utf-8'
    )

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.critical("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))

# Подменяем стандартный обработчик ошибок на наш
sys.excepthook = handle_exception

# --- КОНФИГУРАЦИЯ ---
def load_config():
    default_config = {
        "version": APP_VERSION,
        "language": "ru_ru",
        "gimp_path": r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe",
        "notepad_path": "notepad.exe",
        "desc_name": "desc.txt",
        "preview_name": "preview.jpg",
        "recordings_folder": "", 
        "renders_folder": "",     
        "video_editor_path": "" 
    }
    
    # Перенос старого конфига (оставляем для обратной совместимости на один патч)
    old_config_path = os.path.join(BASE_DIR, "config.json")
    if os.path.exists(old_config_path) and not os.path.exists(CONFIG_FILE):
        shutil.copy2(old_config_path, CONFIG_FILE)
        logging.info("Старый конфиг успешно перенесен в Документы.")
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            return default_config

    old_version = config.get("version", "0.1")
    if old_version < APP_VERSION:
        logging.info(f"Обнаружена новая версия программы: {APP_VERSION}. Запуск миграций...")
        updater.apply_migrations(DB_NAME, old_version, APP_VERSION)
        config["version"] = APP_VERSION
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        save_config(config)

    return config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# --- ЛОКАЛИЗАЦИЯ ---
TRANSLATIONS = {}

def load_language(lang_code):
    global TRANSLATIONS
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = BASE_DIR
        
    lang_path = os.path.join(base_path, "lang", f"{lang_code}.json")
    
    if os.path.exists(lang_path):
        with open(lang_path, 'r', encoding='utf-8') as f:
            TRANSLATIONS = json.load(f)
    else:
        TRANSLATIONS = {}

def _(key, default_text=""):
    return TRANSLATIONS.get(key, default_text or key)