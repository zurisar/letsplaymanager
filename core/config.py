import sys
import os
import json
import logging
import shutil
import updater
import platform
import subprocess

# Добавляем импорты для работы с темами
from PyQt6.QtGui import QPalette, QColor
from PyQt6.QtCore import Qt

# Импортируем сам модуль database, чтобы брать из него динамический db_path
import database
from database import APP_DATA_DIR

APP_VERSION = "0.7"

# Теперь config.py лежит в папке core, поэтому BASE_DIR это папка уровнем выше
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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
def load_config(config_filename="config.json"):
    is_win = platform.system() == "Windows"
    default_config = {
        "version": APP_VERSION,
        "language": "ru_ru",
        "theme": "dark",
        "gimp_path": r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe" if is_win else "gimp",
        "notepad_path": "notepad.exe" if is_win else "xdg-open",
        "notes_name": "notes.txt",
        "preview_name": "preview.jpg",
        "recordings_folder": "", 
        "renders_folder": "",     
        "video_editor_path": "" if is_win else "kdenlive",
        "default_codec": "h264_cpu"
    }
    
    config_path = os.path.join(APP_DATA_DIR, config_filename)
    
    # Перенос старого конфига (оставляем для обратной совместимости, работает для профиля по умолчанию)
    old_config_path = os.path.join(BASE_DIR, "config.json")
    if config_filename == "config.json" and os.path.exists(old_config_path) and not os.path.exists(config_path):
        shutil.copy2(old_config_path, config_path)
        logging.info("Старый конфиг успешно перенесен в Документы.")
    
    if not os.path.exists(config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
        
    with open(config_path, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            return default_config
        
    # --- МИГРАЦИЯ КОНФИГА: Замена desc_name на notes_name ---
    if "desc_name" in config:
        # Переносим значение в новый ключ и удаляем старый
        config["notes_name"] = config.pop("desc_name")
        
        # Если у пользователя стояло стандартное "desc.txt", принудительно меняем на "notes.txt"
        if config["notes_name"] == "desc.txt":
            config["notes_name"] = "notes.txt"
            
        save_config(config, config_filename)
        logging.info("Ключ desc_name успешно мигрирован в notes_name в config.json")

    old_version = config.get("version", "0.1")
    if old_version < APP_VERSION:
        logging.info(f"Обнаружена новая версия программы: {APP_VERSION}. Запуск миграций...")
        # Используем динамический путь к БД из модуля database
        updater.apply_migrations(database.db_path, old_version, APP_VERSION)
        config["version"] = APP_VERSION
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        save_config(config, config_filename)

    return config

def save_config(config, config_filename="config.json"):
    config_path = os.path.join(APP_DATA_DIR, config_filename)
    with open(config_path, 'w', encoding='utf-8') as f:
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


# --- ТЕМЫ ОФОРМЛЕНИЯ ---
def apply_theme(app, theme_name="dark"):
    app.setStyle("Fusion")
    
    if theme_name == "dark":
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        
        dark_palette.setColor(QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.Text, Qt.GlobalColor.white)
        
        dark_palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
        dark_palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
        
        dark_palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        dark_palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
        
        app.setPalette(dark_palette)
    else:
        app.setPalette(app.style().standardPalette())

# --- ПАЛИТРА ИНТЕРФЕЙСА ---
THEME_COLORS = {
    # Ключ: {"light": "HEX", "dark": "HEX"}
    "deleted_folder": {"light": "#add8e6", "dark": "#1f425c"},
    "past_date": {"light": "#add8e6", "dark": "#1f425c"},
    "future_date": {"light": "#ffffe0", "dark": "#4a451c"},
}

def get_color(color_key, current_theme="dark"):
    """Возвращает QColor на основе ключа и текущей темы"""
    hex_code = THEME_COLORS.get(color_key, {}).get(current_theme, "#000000")
    return QColor(hex_code)

def open_path(path):
    """Универсальное открытие файлов и папок в зависимости от ОС"""
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin":  # macOS
        subprocess.call(["open", path])
    else:  # Linux и остальные
        subprocess.call(["xdg-open", path])