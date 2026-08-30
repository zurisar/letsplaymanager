import sys
import logging
import traceback
import os
import json
import re # Для поиска чисел в названии папок (ep1, ep12)
import subprocess
import math
import shutil
import webbrowser
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QDate # <--- Добавлен QDate
from PyQt6.QtWidgets import (QApplication, QCalendarWidget, QMainWindow, QMenu, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
                             QComboBox, QLabel, QHeaderView, QFileDialog, QInputDialog, 
                             QCheckBox, QDialog, QFormLayout, QSpinBox, QLineEdit, QMessageBox,
                             QTextEdit)
from PyQt6.QtGui import QColor
from database import (init_db, add_game, get_games, add_episode_if_not_exists, 
                      get_episodes, get_uploads, toggle_upload, update_episode_metadata,
                      get_videohostings, update_episode_title, get_upload_url,
                      add_videohosting, delete_videohosting, update_game_ai_url,
                      update_episode_publish_date, update_upload_url, mark_episode_deleted,
                      get_shorts, add_short_to_db, update_short_field, get_short_uploads,
                      update_short_upload_status, update_short_url, delete_game_full,
                      update_game)

import updater # <--- Импортируем наш новый модуль обновлений
from database import DB_NAME, APP_DATA_DIR # Берем пути из базы

APP_VERSION = "0.5.1" # <--- ТЕКУЩАЯ ВЕРСИЯ ПРИЛОЖЕНИЯ

# Конфиг теперь тоже живет в AppData, чтобы не стираться при обновлении
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')
# Получаем точный путь к папке, где лежит main.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'run.log')


# --- НАСТРОЙКА ЛОГИРОВАНИЯ ---
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8' # Чтобы кириллица писалась корректно
)

# Функция для перехвата критических ошибок (крашей)
def handle_exception(exc_type, exc_value, exc_traceback):
    # Пропускаем стандартное прерывание с клавиатуры (Ctrl+C)
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Записываем ошибку в лог
    logging.critical("Необработанное исключение:", exc_info=(exc_type, exc_value, exc_traceback))

# Подменяем стандартный обработчик ошибок на наш
sys.excepthook = handle_exception

from database import APP_DATA_DIR # Импортируем наш новый путь к Документам

# Теперь конфиг будет лежать в той же папке, что и база данных
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')

# --- АВТО-ПЕРЕНОС СТАРОГО КОНФИГА ---
old_config_path = os.path.join(BASE_DIR, "config.json")
if os.path.exists(old_config_path) and not os.path.exists(CONFIG_FILE):
    import shutil
    shutil.copy2(old_config_path, CONFIG_FILE)
    logging.info("Старый конфиг успешно перенесен в Документы.")

def load_config():
    # Настройки по умолчанию (добавлены записи и рендеры)
    default_config = {
        "version": APP_VERSION,
        "language": "ru_ru",
        "gimp_path": r"C:\Program Files\GIMP 2\bin\gimp-2.10.exe",
        "notepad_path": "notepad.exe",
        "desc_name": "desc.txt",
        "preview_name": "preview.jpg",
        "recordings_folder": "", # Новое: Папка, куда пишет OBS
        "renders_folder": "",     # Новое: Папка, где лежат папки с играми
        "video_editor_path": "" # Новое: видеоредактор
    }
    
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, indent=4, ensure_ascii=False)
        return default_config
        
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        try:
            config = json.load(f)
        except json.JSONDecodeError:
            return default_config

    # --- ЛОГИКА ОБНОВЛЕНИЯ (МИГРАЦИИ) ---
    # Если в старом конфиге нет версии, считаем, что это версия "0.1"
    old_version = config.get("version", "0.1")
    
    if old_version < APP_VERSION:
        logging.info(f"Обнаружена новая версия программы: {APP_VERSION}. Запуск миграций...")
        # 1. Запускаем обновление базы данных
        updater.apply_migrations(DB_NAME, old_version, APP_VERSION)
        
        # 2. Обновляем версию в самом конфиге
        config["version"] = APP_VERSION
        
        # 3. Добавляем новые ключи в конфиг, если их там не было
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
                
        # Сохраняем обновленный конфиг
        save_config(config)

    return config

def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# Глобальный словарь для хранения переводов
TRANSLATIONS = {}

def load_language(lang_code):
    global TRANSLATIONS
    
    # Определяем, запущены ли мы из скомпилированного .exe или через python.exe
    if getattr(sys, 'frozen', False):
        # Если это скомпилированный .exe, ищем папку lang рядом с исполняемым файлом
        base_path = os.path.dirname(sys.executable)
    else:
        # Если обычный запуск скрипта
        base_path = BASE_DIR
        
    lang_path = os.path.join(base_path, "lang", f"{lang_code}.json")
    
    if os.path.exists(lang_path):
        with open(lang_path, 'r', encoding='utf-8') as f:
            TRANSLATIONS = json.load(f)
    else:
        TRANSLATIONS = {}
# Функция, которая ищет перевод по ключу.
# Общепринятый стандарт в Python - называть функцию перевода символом подчеркивания `_`
def _(key, default_text=""):
    # Если ключ найден - возвращаем перевод. Если нет - fallback на default_text или сам ключ
    return TRANSLATIONS.get(key, default_text or key)

class SettingsDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle(_("title_settings"))
        self.resize(500, 150)
        self.config = config

        layout = QFormLayout(self)

        # --- Выбор языка ---
        self.lang_selector = QComboBox()
        self.lang_selector.addItem("Русский", userData="ru_ru")
        self.lang_selector.addItem("English", userData="en_us")
        
        current_lang = self.config.get("language", "ru_ru")
        index = self.lang_selector.findData(current_lang)
        if index >= 0:
            self.lang_selector.setCurrentIndex(index)
            
        layout.addRow("Язык / Language:", self.lang_selector)

        # --- ПАПКИ ---
        recordings_layout = QHBoxLayout()
        self.recordings_input = QLineEdit(self.config.get("recordings_folder", ""))
        rec_btn = QPushButton(_("btn_browse", "Обзор"))
        rec_btn.clicked.connect(lambda: self.browse_folder(self.recordings_input))
        recordings_layout.addWidget(self.recordings_input)
        recordings_layout.addWidget(rec_btn)
        layout.addRow(_("lbl_video_source_folder"), recordings_layout)

        renders_layout = QHBoxLayout()
        self.renders_input = QLineEdit(self.config.get("renders_folder", ""))
        ren_btn = QPushButton(_("btn_browse", "Обзор"))
        ren_btn.clicked.connect(lambda: self.browse_folder(self.renders_input))
        renders_layout.addWidget(self.renders_input)
        renders_layout.addWidget(ren_btn)
        layout.addRow(_("lbl_video_render_folder"), renders_layout)

        # 1. Путь к Текстовому редактору (переименовано в text_editor_input)
        text_editor_layout = QHBoxLayout()
        self.text_editor_input = QLineEdit(self.config.get("notepad_path", "notepad.exe"))
        text_editor_btn = QPushButton(_("btn_browse"))
        text_editor_btn.clicked.connect(self.browse_text_editor) # <--- Уникальный метод
        text_editor_layout.addWidget(self.text_editor_input)
        text_editor_layout.addWidget(text_editor_btn)
        layout.addRow(_("lbl_text_editor"), text_editor_layout)

        # 2. Путь к GIMP
        gimp_layout = QHBoxLayout()
        self.gimp_input = QLineEdit(self.config.get("gimp_path", ""))
        gimp_btn = QPushButton(_("btn_browse"))
        gimp_btn.clicked.connect(self.browse_gimp)
        gimp_layout.addWidget(self.gimp_input)
        gimp_layout.addWidget(gimp_btn)
        layout.addRow(_("lbl_gimp_path"), gimp_layout)

        # --- Видеоредактор (переименовано в video_editor_input) ---
        video_editor_layout = QHBoxLayout()
        self.video_editor_input = QLineEdit(self.config.get("video_editor_path", ""))
        video_editor_btn = QPushButton("Обзор")
        video_editor_btn.clicked.connect(self.browse_video_editor) # <--- Уникальный метод
        video_editor_layout.addWidget(self.video_editor_input)
        video_editor_layout.addWidget(video_editor_btn)
        layout.addRow(f"{_('lbl_videoeditor')} (.exe):", video_editor_layout)

        # 3. Имена файлов
        self.desc_input = QLineEdit(self.config.get("desc_name", "desc.txt"))
        layout.addRow(_("lbl_desc_filename"), self.desc_input)

        self.prev_input = QLineEdit(self.config.get("preview_name", "preview.jpg"))
        layout.addRow(_("lbl_preview_filename"), self.prev_input)

        # --- Кнопка управления видеохостингами ---
        hostings_btn = QPushButton(_("btn_videohosting_manager"))
        hostings_btn.clicked.connect(self.open_manage_hostings)
        layout.addRow(hostings_btn)

        # 4. Кнопки сохранения
        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    # --- МЕТОДЫ ОБЗОРА (теперь у каждого свое имя) ---

    def browse_gimp(self):
        file, ignored = QFileDialog.getOpenFileName(self, _("title_select_gimp"), "", "Executable Files (*.exe)")
        if file:
            self.gimp_input.setText(file)

    def browse_text_editor(self): # Для текстового редактора
        file, ignored = QFileDialog.getOpenFileName(self, _("title_select_editor"), "", "Executable Files (*.exe)")
        if file:
            self.text_editor_input.setText(file)

    def browse_video_editor(self): # Для видеоредактора
        file, ignored = QFileDialog.getOpenFileName(self, _("lbl_select_videoeditor_exe"), "", "Executable (*.exe)")
        if file:
            self.video_editor_input.setText(file)

    def open_manage_hostings(self):
        dialog = ManageHostingsDialog(self)
        dialog.exec()

    def browse_folder(self, line_edit):
        folder = QFileDialog.getExistingDirectory(self, _("lbl_select_folder"))
        if folder:
            line_edit.setText(folder)

    def accept(self):
        # 1. Собираем данные со всех полей интерфейса и обновляем словарь
        self.config["language"] = self.lang_selector.currentData()
        self.config["recordings_folder"] = self.recordings_input.text().strip()
        self.config["renders_folder"] = self.renders_input.text().strip()
        
        self.config["notepad_path"] = self.text_editor_input.text().strip()
        self.config["gimp_path"] = self.gimp_input.text().strip()
        self.config["video_editor_path"] = self.video_editor_input.text().strip()
        
        self.config["desc_name"] = self.desc_input.text().strip()
        self.config["preview_name"] = self.prev_input.text().strip()

        # 2. Физически сохраняем обновленный словарь в файл config.json
        # (Функция save_config уже должна быть у вас в main.py)
        save_config(self.config)

        # 3. Закрываем окно (вызываем оригинальный метод закрытия)
        super().accept()

class ManageHostingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("title_manage_hostings", "Управление видеохостингами"))
        self.resize(450, 300)
        
        layout = QVBoxLayout(self)
        
        # 1. Таблица существующих хостингов
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([f"{_('lbl_key')} (system)", _("lbl_displayname")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        self.load_data()
        
        # 2. Форма добавления нового хостинга
        form_layout = QHBoxLayout()
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText(_("dlg_tooltip_eg_videohosting_key"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText(_("dlg_tooltip_eg_videohosting_name"))
        self.add_btn = QPushButton(_("btn_add"))
        self.add_btn.clicked.connect(self.add_hosting)
        
        form_layout.addWidget(self.key_input)
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(self.add_btn)
        layout.addLayout(form_layout)
        
        # 3. Кнопка удаления
        self.del_btn = QPushButton(_("btn_delete_selected_vh"))
        self.del_btn.setStyleSheet("background-color: lightcoral;")
        self.del_btn.clicked.connect(self.delete_hosting)
        layout.addWidget(self.del_btn)
        
    def load_data(self):
        self.table.setRowCount(0)
        hostings = get_videohostings()
        self.table.setRowCount(len(hostings))
        for row, (h_id, h_key, h_name) in enumerate(hostings):
            item_key = QTableWidgetItem(h_key)
            item_key.setData(Qt.ItemDataRole.UserRole, h_id)
            self.table.setItem(row, 0, item_key)
            self.table.setItem(row, 1, QTableWidgetItem(h_name))
            
    def add_hosting(self):
        key = self.key_input.text().strip()
        name = self.name_input.text().strip()
        if not key or not name:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_both_field_error"))
            return
        
        # Ключ должен быть только из латиницы/цифр (для безопасности БД)
        if not re.match(r'^[a-zA-Z0-9_]+$', key):
            QMessageBox.warning(self, _("msg_title_error"), _("msg_key_name_error"))
            return

        if add_videohosting(key, name):
            self.key_input.clear()
            self.name_input.clear()
            self.load_data()
        else:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_vh_key_inuse"))
            
    def delete_hosting(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        h_id = self.table.item(current_row, 0).data(Qt.ItemDataRole.UserRole)
        h_name = self.table.item(current_row, 1).text()
        
        reply = QMessageBox.question(
            self, _("msg_title_confirmation"), 
            f"{_('msg_vh_delete_column')} «{h_name}»?\n{_('msg_vh_delete_all')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            delete_videohosting(h_id)
            self.load_data()

class FFmpegWorker(QThread):
    # Добавился новый сигнал progress, который будет отдавать строку текста
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            # Используем Popen для чтения вывода в реальном времени
            # stderr=subprocess.STDOUT перенаправляет ошибки в общий поток вывода
            process = subprocess.Popen(
                self.cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=0x08000000
            )
            
            # Читаем вывод строка за строкой, пока процесс работает
            for line in process.stdout:
                # Отправляем строку в интерфейс
                self.progress.emit(line.strip())
            
            # Ждем окончательного завершения
            process.wait()
            
            if process.returncode == 0:
                self.finished.emit(True, _("status_done"))
            else:
                self.finished.emit(False, _("status_conversion_error"))
        except Exception as e:
            self.finished.emit(False, str(e))

class ProgressDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"{_('title_conversion')} (FFmpeg)")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Текстовое поле только для чтения
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        # Устанавливаем моноширинный шрифт (как в консоли)
        self.log_output.setStyleSheet("font-family: Consolas; font-size: 10pt;")
        layout.addWidget(self.log_output)
        
    def append_log(self, text):
        # Добавляем строку
        self.log_output.append(text)
        # Автоматически прокручиваем вниз
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class AddGameDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.manual_path = False # <--- Флаг ручного выбора пути
        self.setWindowTitle(_("title_add_new_game"))
        self.resize(500, 200)

        layout = QFormLayout(self)

        self.name_input = QLineEdit()
        self.name_input.textChanged.connect(self.update_folder_path)
        layout.addRow(_("lbl_game_name"), self.name_input)

        # --- НОВЫЙ БЛОК: Поле ввода + Кнопка Обзор ---
        folder_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_btn = QPushButton(_("btn_browse", "Обзор"))
        self.folder_btn.clicked.connect(self.browse_folder)
        
        folder_layout.addWidget(self.folder_input)
        folder_layout.addWidget(self.folder_btn)
        layout.addRow(_("lbl_game_folder"), folder_layout)
        # ---------------------------------------------

        self.ai_url_input = QLineEdit()
        self.ai_url_input.setPlaceholderText("https://chatgpt.com/...")
        layout.addRow(_("lbl_ai_chat_link"), self.ai_url_input)

        # --- НОВОЕ: Поле Steam ID ---
        self.steam_input = QLineEdit()
        self.steam_input.setPlaceholderText("Например: 108600 (Project Zomboid)")
        layout.addRow("Steam ID (опционально):", self.steam_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save", "Сохранить"))
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(_("btn_cancel", "Отмена"))
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    # --- НОВЫЙ МЕТОД ---
    def browse_folder(self):
        # Начинаем обзор с папки рендеров для удобства
        start_dir = self.config.get("renders_folder", "")
        folder = QFileDialog.getExistingDirectory(self, "Выберите папку для игры", start_dir)
        if folder:
            self.folder_input.setText(folder)
            self.manual_path = True # Пользователь сам выбрал путь, отключаем автогенерацию
    # -------------------

    def update_folder_path(self):
        """Автоматически формирует путь к папке игры при вводе названия"""
        renders_dir = self.config.get("renders_folder", "")
        if renders_dir:
            # Убираем запрещенные символы для Windows
            safe_name = re.sub(r'[\\/*?:"<>|]', "", self.name_input.text().strip())
            if safe_name:
                self.folder_input.setText(os.path.join(renders_dir, safe_name))
            else:
                self.folder_input.clear()

class EditGameDialog(QDialog):
    def __init__(self, parent, game_name, game_data):
        super().__init__(parent)
        self.setWindowTitle(f"Редактирование: {game_name}")
        self.resize(500, 150)
        
        layout = QFormLayout(self)

        self.name_input = QLineEdit(game_name)
        layout.addRow("Название игры:", self.name_input)

        self.ai_url_input = QLineEdit(game_data.get('ai_url', ''))
        self.ai_url_input.setPlaceholderText("https://chatgpt.com/...")
        layout.addRow("Ссылка на ИИ-чат:", self.ai_url_input)

        self.steam_input = QLineEdit(game_data.get('steam_id', ''))
        self.steam_input.setPlaceholderText("Например: 108600")
        layout.addRow("Steam ID:", self.steam_input)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("💾 Сохранить изменения")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

class AddEpisodeDialog(QDialog):
    def __init__(self, parent, games, current_game_id, config): # <-- Добавили config
        super().__init__(parent)
        self.config = config # <-- Сохранили
        self.setWindowTitle(f"{_('title_add_episode')} (MKV -> MP4)")
        self.resize(500, 200)

        # Выбираем QFormLayout — он идеально подходит для окон с настройками (Метка: Поле ввода)
        layout = QFormLayout(self)

        # 1. Исходный файл
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        file_btn = QPushButton("Выбрать файл .mkv")
        file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(file_btn)
        layout.addRow(_("lbl_source_file"), file_layout)

        # 2. Выбор игры (копируем список из главного окна)
        self.game_selector = QComboBox()
        # Также добавляем ai_url в распаковку
        for game_id, name, folder_path, ai_url, steam_id in games:
            self.game_selector.addItem(name, userData={'id': game_id, 'path': folder_path})
            # Сразу выбираем ту игру, которая была открыта в главном окне
            if game_id == current_game_id:
                self.game_selector.setCurrentIndex(self.game_selector.count() - 1)
        
        layout.addRow(_("lbl_game"), self.game_selector)

        # 3. Номер эпизода (числовое поле)
        self.ep_spinbox = QSpinBox()
        self.ep_spinbox.setMinimum(1)
        self.ep_spinbox.setMaximum(9999)
        layout.addRow(_("lbl_episode_number"), self.ep_spinbox)
        
        # --- НОВОЕ: Подключаем автоопределение эпизода ---
        self.game_selector.currentIndexChanged.connect(self.update_episode_number)
        # Вызываем один раз при открытии окна
        self.update_episode_number()

        # --- НОВОЕ: Чекбокс действия ---
        self.convert_checkbox = QCheckBox(_("lbl_push_video_over_ffmpeg"))
        self.convert_checkbox.setChecked(True) # По умолчанию включено
        layout.addRow(f"{_("lbl_action")}:", self.convert_checkbox)
        # -------------------------------

        # 4. Кнопки Ок/Отмена
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton(_("btn_add_and_convert"))
        self.add_btn.clicked.connect(self.accept) # Закрывает диалог с кодом "ОК"
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject) # Закрывает диалог с кодом "Отмена"
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def select_file(self):
        start_dir = self.config.get("recordings_folder", "") # <-- Берем папку
        file, ignored = QFileDialog.getOpenFileName(self, "Выберите исходное видео", start_dir, "Видеофайлы (*.mkv *.mp4 *.avi)")
        if file:
            self.file_input.setText(file)
            if file.lower().endswith('.mp4'):
                self.convert_checkbox.setChecked(False)
            else:
                self.convert_checkbox.setChecked(True)

    def update_episode_number(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1:
            return
            
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        
        # Получаем все эпизоды для этой игры из базы
        episodes = get_episodes(game_id)
        if episodes:
            # episodes это список кортежей: (id, number, file_size, duration)
            # Достаем максимальный номер и прибавляем 1
            max_ep = max(ep[1] for ep in episodes)
            self.ep_spinbox.setValue(max_ep + 1)
        else:
            # Если эпизодов нет, предлагаем начать с 1
            self.ep_spinbox.setValue(1)

class CompressDialog(QDialog):
    def __init__(self, parent, config): # <-- Добавили config
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Сжатие видео (Transcoding)")
        self.resize(500, 250)
        
        layout = QFormLayout(self)
        self.filepath = ""
        self.duration_sec = 0.0 # Сохраним секунды для расчета размера

        # 1. Выбор файла
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setReadOnly(True)
        file_btn = QPushButton("Выбрать видео")
        file_btn.clicked.connect(self.select_file)
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(file_btn)
        layout.addRow("Исходный файл:", file_layout)

        # 2. Информация о файле
        self.info_label = QLabel("Выберите файл для анализа...")
        layout.addRow("Информация:", self.info_label)

        # 3. Выбор кодека
        self.codec_selector = QComboBox()
        self.codec_selector.addItem("CPU (Обычный H.264)", userData="libx264")
        self.codec_selector.addItem("AMD (H.264)", userData="h264_amf")
        self.codec_selector.addItem("NVIDIA (H.264)", userData="h264_nvenc")
        self.codec_selector.addItem("AMD (HEVC / H.265)", userData="hevc_amf")
        self.codec_selector.addItem("NVIDIA (HEVC / H.265)", userData="hevc_nvenc")
        
        # Ставим AMD HEVC по умолчанию (это индекс 3 в списке)
        self.codec_selector.setCurrentIndex(3)
        layout.addRow("Кодек видео:", self.codec_selector)

        # 3. Выбор битрейта
        self.bitrate_selector = QComboBox()
        self.bitrate_selector.addItems(["10", "15", "20", "25", "30", "40", "50"])
        self.bitrate_selector.setCurrentText("15") # По умолчанию 15 Mbps
        self.bitrate_selector.currentTextChanged.connect(self.update_estimate)
        
        # Добавим подпись "Mbps" для красоты
        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(self.bitrate_selector)
        bitrate_layout.addWidget(QLabel("Mbps (Мбит/с)"))
        layout.addRow("Целевой битрейт видео:", bitrate_layout)

        # 4. Прогноз размера
        self.estimate_label = QLabel("Ожидаемый вес: 0 MB")
        self.estimate_label.setStyleSheet("font-weight: bold; color: #2e8b57;") # Сделаем зеленым
        layout.addRow("Прогноз:", self.estimate_label)

        # 5. Кнопки
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Сжать видео")
        self.start_btn.setEnabled(False) # Выключена, пока не выбран файл
        self.start_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

    def select_file(self):
        start_dir = self.config.get("recordings_folder", "") # <-- Берем папку
        file, ignored = QFileDialog.getOpenFileName(self, _("dlg_select_source_video"), "", f"{_('filter_video_files')} (*.mkv *.mp4 *.avi)")
        if file:
            self.filepath = file
            self.file_input.setText(file)
            self.analyze_file()
            self.start_btn.setEnabled(True)

    def analyze_file(self):
        # Получаем размер
        size_bytes = os.path.getsize(self.filepath)
        size_mb = size_bytes / (1024 * 1024)
        
        # Получаем длительность в секундах через ffprobe
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                 '-of', 'default=noprint_wrappers=1:nokey=1', self.filepath],
                stdout=subprocess.PIPE, text=True, creationflags=0x08000000
            )
            self.duration_sec = float(result.stdout.strip())
            
            # Переводим в HH:MM:SS для отображения
            m, s = divmod(int(self.duration_sec), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h:02d}:{m:02d}:{s:02d}"
            
            self.info_label.setText(f"{_('lbl_size')}: {size_mb:.2f} MB | {_('lbl_duration')}: {dur_str}")
            self.update_estimate()
        except Exception as e:
            self.info_label.setText(_("msg_file_read_error"))

    def update_estimate(self):
        if self.duration_sec > 0:
            # Формула: Битрейт (Мбит/с) * Длительность (с) / 8 = Мегабайты
            # Плюс накидываем аудио (например 192 kbps) и контейнер ~ 5%
            bitrate_mbps = float(self.bitrate_selector.currentText())
            audio_bitrate_mbps = 0.192 
            
            total_size_mb = ((bitrate_mbps + audio_bitrate_mbps) * self.duration_sec) / 8
            self.estimate_label.setText(f"{_('lbl_maybe_weight')}: ~{total_size_mb:.2f} MB")

class CalendarDialog(QDialog):
    def __init__(self, parent, current_date_str=""):
        super().__init__(parent)
        self.setWindowTitle(_("lbl_publishing_date"))
        self.resize(350, 250)
        layout = QVBoxLayout(self)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        
        # Если дата уже была, выделяем её в календаре
        if current_date_str and current_date_str != _("lbl_not_set"):
            try:
                d = QDate.fromString(current_date_str, "dd.MM.yyyy")
                if d.isValid():
                    self.calendar.setSelectedDate(d)
            except:
                pass
        
        layout.addWidget(self.calendar)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton(_("btn_save"))
        save_btn.clicked.connect(self.accept)
        clear_btn = QPushButton(_("btn_clear"))
        clear_btn.clicked.connect(self.clear_date)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(self.reject)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(clear_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        self.selected_date_str = ""

    def clear_date(self):
        self.selected_date_str = ""
        self.done(QDialog.DialogCode.Accepted)

    def accept(self):
        self.selected_date_str = self.calendar.selectedDate().toString("dd.MM.yyyy")
        super().accept()

class ShortsManagerDialog(QDialog):
    def __init__(self, parent, ep_id, ep_number, ep_folder, game_name, db_size, db_duration, ai_url, config, hostings):
        super().__init__(parent)
        self.ep_id = ep_id
        self.ep_number = ep_number
        self.ep_folder = ep_folder
        self.shorts_folder = os.path.join(ep_folder, "shorts")
        self.game_name = game_name
        self.ai_url = ai_url
        self.config = config
        self.hostings = hostings

        self.setWindowTitle(f"{_('title_shorts_manager')}: {game_name} - Эпизод {ep_number}")
        self.resize(950, 500)
        layout = QVBoxLayout(self)

        # --- ВЕРХНЯЯ ИНФО-ПАНЕЛЬ ---
        info_group = QWidget()
        info_layout = QVBoxLayout(info_group)
        
        title_lbl = QLabel(f"<b>{game_name} - {_('lbl_episode')} {ep_number}</b>")
        title_lbl.setStyleSheet("font-size: 16px;")
        stats_lbl = QLabel(f"{_('lbl_source')}: {db_size} | {db_duration}")
        
        btn_layout = QHBoxLayout()
        play_btn = QPushButton(f"▶ {_('lbl_source_video')}")
        play_btn.clicked.connect(self.play_original)
        
        folder_btn = QPushButton(f"📁 {_('lbl_episode_folder')}")
        folder_btn.clicked.connect(lambda: os.startfile(self.ep_folder) if os.path.exists(self.ep_folder) else None)
        
        editor_btn = QPushButton(f"🎬 {_('lbl_videoeditor')}")
        editor_btn.setToolTip(_("tooltip_run_videoeditor"))
        editor_btn.clicked.connect(self.launch_editor)
        
        ai_btn = QPushButton(_("lbl_ai_chat"))
        ai_btn.clicked.connect(lambda: webbrowser.open(self.ai_url) if self.ai_url else QMessageBox.warning(self, _("status_error"), _("msg_ai_link_not_set")))

        btn_layout.addWidget(play_btn)
        btn_layout.addWidget(folder_btn)
        btn_layout.addWidget(editor_btn)
        btn_layout.addWidget(ai_btn)
        
        info_layout.addWidget(title_lbl)
        info_layout.addWidget(stats_lbl)
        info_layout.addLayout(btn_layout)
        layout.addWidget(info_group)

        # --- ТАБЛИЦА ШОРТСОВ ---
        self.table = QTableWidget(0, 6 + len(self.hostings))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        layout.addWidget(self.table)

        # --- ПАНЕЛЬ ДОБАВЛЕНИЯ ---
        add_btn = QPushButton(f"+ {_('lbl_add_shorts')}")
        add_btn.setStyleSheet("padding: 10px; font-weight: bold;")
        add_btn.clicked.connect(self.add_short)
        layout.addWidget(add_btn)

        self.update_table()

    def launch_editor(self):
        editor_path = self.config.get("video_editor_path", "")
        if os.path.exists(editor_path):
            subprocess.Popen([editor_path])
        else:
            QMessageBox.warning(self, _("status_error"), _("msg_videoeditor_path_not_set"))

    def play_original(self):
        if not os.path.exists(self.ep_folder): return
        for f in os.listdir(self.ep_folder):
            if f.endswith(('.mp4', '.mkv', '.avi')) and "shorts" not in f.lower():
                os.startfile(os.path.join(self.ep_folder, f))
                return
        QMessageBox.warning(self, _("status_error"), _("msg_episode_file_not_found"))

    def update_table(self):
        shorts = get_shorts(self.ep_id)
        self.table.clearContents()
        self.table.setRowCount(len(shorts))
        
        headers = [_("col_name"), _("col_size"), _("col_time"), _("col_media"), _("col_tags"), _("col_publish_date")] + [h[2] for h in self.hostings]
        self.table.setHorizontalHeaderLabels(headers)
        
        for row, s in enumerate(shorts):
            s_id, s_num, s_size, s_dur, s_title, s_tags, s_pub = s
            display_title = s_title if s_title else f"Shorts_{s_num}"
            
            title_item = QTableWidgetItem(display_title)
            title_item.setData(Qt.ItemDataRole.UserRole, s_id)
            self.table.setItem(row, 0, title_item)
            self.table.setItem(row, 1, QTableWidgetItem(s_size))
            self.table.setItem(row, 2, QTableWidgetItem(s_dur))
            
            # Медиа-кнопки
            media_w = QWidget()
            m_lay = QHBoxLayout(media_w)
            m_lay.setContentsMargins(2,2,2,2)
            f_btn = QPushButton("📁")
            f_btn.setFixedWidth(30)
            f_btn.clicked.connect(lambda ch, sid=s_id: os.startfile(self.shorts_folder) if os.path.exists(self.shorts_folder) else None)
            p_btn = QPushButton("▶")
            p_btn.setFixedWidth(30)
            p_btn.clicked.connect(lambda ch, sid=s_id, num=s_num: self.play_short(num))
            m_lay.addWidget(f_btn)
            m_lay.addWidget(p_btn)
            self.table.setCellWidget(row, 3, media_w)
            
            # Теги
            tags_item = QTableWidgetItem(s_tags if s_tags else _("lbl_add_tags"))
            if not s_tags: tags_item.setBackground(QColor("#ffcccb"))
            self.table.setItem(row, 4, tags_item)
            
            self.table.setItem(row, 5, QTableWidgetItem(s_pub if s_pub else _("lbl_not_set")))
            
            # Хостинги
            uploads = {int(u[0]): u[2] for u in get_short_uploads(s_id)}
            for col_off, (h_id, ignored, h_name) in enumerate(self.hostings):
                hw = QWidget()
                hl = QHBoxLayout(hw)
                hl.setContentsMargins(2,2,2,2)
                
                cb = QCheckBox()
                cb.setChecked(h_id in uploads)
                cb.toggled.connect(lambda ch, sid=s_id, hid=h_id: update_short_upload_status(sid, hid, int(ch)))
                
                url = next((u[2] for u in get_short_uploads(s_id) if u[0] == h_id), "")
                link_btn = QPushButton("🌐" if url else "✏️")
                link_btn.setFixedWidth(30)
                if url: link_btn.setStyleSheet("background-color: #add8e6;")
                
                link_btn.clicked.connect(lambda ch, sid=s_id, hid=h_id, hn=h_name, u=url: webbrowser.open(u) if u else self.edit_url(sid, hid, hn))
                link_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                link_btn.customContextMenuRequested.connect(lambda pos, sid=s_id, hid=h_id, hn=h_name: self.edit_url(sid, hid, hn))
                
                hl.addWidget(cb)
                hl.addWidget(link_btn)
                self.table.setCellWidget(row, 6 + col_off, hw)

    def play_short(self, s_num):
        if not os.path.exists(self.shorts_folder): return
        expected = f"Short {s_num}"
        for f in os.listdir(self.shorts_folder):
            if expected in f and f.endswith(('.mp4', '.mkv')):
                os.startfile(os.path.join(self.shorts_folder, f))
                return
        QMessageBox.warning(self, _("status_error"), _("msg_short_file_not_found"))

    def add_short(self):
        start_dir = self.config.get("renders_folder", "")
        file, ignored = QFileDialog.getOpenFileName(self, _("lbl_select_short"), start_dir, f"{_('lbl_video_files')} (*.mp4 *.mkv)")
        if not file: return
        
        os.makedirs(self.shorts_folder, exist_ok=True)
        shorts = get_shorts(self.ep_id)
        next_num = max([s[1] for s in shorts] + [0]) + 1
        
        filename, ext = os.path.splitext(file)
        out_name = f"{self.game_name} - Ep.{self.ep_number} - Short {next_num}{ext}"
        out_path = os.path.join(self.shorts_folder, out_name)
        
        norm_in = os.path.normpath(file)
        norm_out = os.path.normpath(out_path)
        
        if norm_in != norm_out:
            try:
                shutil.move(norm_in, norm_out)
            except Exception as e:
                QMessageBox.critical(self, _("status_error"), f"{_('lbl_video_convert_error')}:\n{e}")
                return
        
        # Запрашиваем размер и время через родительское окно
        size_str = self.parent().get_format_size(os.path.getsize(norm_out))
        dur_str = self.parent().get_video_duration(norm_out)
        
        add_short_to_db(self.ep_id, next_num, size_str, dur_str)
        self.update_table()
        self.parent().update_table() # Обновляем счетчик в главной таблице

    def on_cell_double_clicked(self, row, column):
        s_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        if column == 0:
            cur = self.table.item(row, 0).text()
            if cur.startswith("Shorts_"): cur = ""
            new_t, ok = QInputDialog.getText(self, _("lbl_name"), _("lbl_own_name"), QLineEdit.EchoMode.Normal, cur)
            if ok: update_short_field(s_id, 'custom_title', new_t.strip())
                
        elif column == 4:
            cur = self.table.item(row, 4).text()
            if cur == "Добавить теги": cur = ""
            new_t, ok = QInputDialog.getText(self, _("lbl_tags"), _("lbl_enter_tags"), QLineEdit.EchoMode.Normal, cur)
            if ok: update_short_field(s_id, 'tags', new_t.strip())
                
        elif column == 5:
            cur = self.table.item(row, 5).text()
            dialog = CalendarDialog(self, cur)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                update_short_field(s_id, 'publish_date', dialog.selected_date_str)
                
        self.update_table()

    def edit_url(self, s_id, h_id, h_name):
        url = next((u[2] for u in get_short_uploads(s_id) if u[0] == h_id), "")
        new_u, ok = QInputDialog.getText(self, f"{_('lbl_link')}: {h_name}", f"{_('lbl_enter_link')}:", QLineEdit.EchoMode.Normal, url)
        if ok:
            update_short_url(s_id, h_id, new_u.strip())
            self.update_table()

class AboutDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("О программе")
        self.setFixedSize(450, 250)
        
        layout = QVBoxLayout(self)
        
        # Основной текст с поддержкой HTML
        info_label = QLabel()
        info_label.setTextFormat(Qt.TextFormat.RichText)
        info_label.setOpenExternalLinks(True) # ВАЖНО: Разрешает кликать по ссылкам и открывать браузер
        info_label.setWordWrap(True)
        
        text = f"""
        <h2 style='text-align: center; color: #2c3e50;'>LetsPlayManager v{APP_VERSION}</h2>
        <p style='text-align: center;'>Умный инструмент для наведения порядка в исходниках и управления публикациями.</p>
        <hr>
        <p><b>Основные возможности:</b><br>
        Автоматизация перепаковки, управление метаданными и шортсами, планирование публикаций и интеграция с видеоредакторами.</p>
        <p><b>Следить за обновлениями:</b><br>
        🐙 <a href='https://github.com/zurisar/letsplaymanager' style='color: #2980b9;'>Исходный код на GitHub</a><br>
        🟦 <a href='https://vk.ru/zarubagames' style='color: #2980b9;'>Официальное сообщество VK</a></p>
        <br>
        <p style='text-align: center; font-size: 10px; color: gray;'>Разработано с душой для создателей контента.</p>
        """
        
        info_label.setText(text)
        layout.addWidget(info_label)
        
        # Кнопка закрытия по центру
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("Закрыть")
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)

class LetsPlayManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()

        # ЗАГРУЖАЕМ ЯЗЫК
        load_language(self.config.get("language", "ru_ru"))
        
        # Настройки самого окна
        self.setWindowTitle(_("app_title"))
        self.resize(950, 600)

        # Центральный виджет (основа окна)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный вертикальный слой (все элементы будут идти сверху вниз)
        main_layout = QVBoxLayout(central_widget)

        # --- 1. Верхняя панель (Выбор игры) ---
        # Горизонтальный слой (элементы идут слева направо)
        top_panel = QHBoxLayout()

        top_panel.addWidget(QLabel(_("lbl_select_game")))

        # Выпадающий список (теперь без заглушек)
        self.game_selector = QComboBox()
        self.game_selector.currentIndexChanged.connect(self.update_table)
        #self.game_selector.resize(600, 50)
        self.game_selector.setMinimumWidth(600) # Переключить на этот вариант если размер будет уезжать
        top_panel.addWidget(self.game_selector)

        self.add_game_btn = QPushButton(_("btn_add_game"))
        # Привязываем нажатие кнопки к нашей новой функции
        self.add_game_btn.clicked.connect(self.add_new_game) 
        top_panel.addWidget(self.add_game_btn)

        # --- НОВАЯ КНОПКА РЕДАКТИРОВАНИЯ ---
        self.edit_game_btn = QPushButton("✏ Редактировать")
        self.edit_game_btn.clicked.connect(self.edit_current_game)
        top_panel.addWidget(self.edit_game_btn)
        # -----------------------------------

        # --- НОВАЯ КНОПКА УДАЛЕНИЯ ---
        self.delete_game_btn = QPushButton("🗑 Удалить игру")
        self.delete_game_btn.setStyleSheet("color: #c0392b; font-weight: bold;") # Сделаем её красной для привлечения внимания
        self.delete_game_btn.clicked.connect(self.delete_current_game)
        top_panel.addWidget(self.delete_game_btn)
        # -----------------------------

        # Кнопка открытия настроек
        self.settings_btn = QPushButton(_("btn_settings"))
        self.settings_btn.clicked.connect(self.open_settings)
        top_panel.addWidget(self.settings_btn)

        self.about_btn = QPushButton(_("btn_about"))
        self.about_btn.clicked.connect(self.open_about)

        # Пружина, которая прижмет все элементы панели к левому краю
        top_panel.addStretch() 

        # Добавляем верхнюю панель в главный вертикальный слой
        main_layout.addLayout(top_panel)

        # --- ПАНЕЛЬ ИНСТРУМЕНТОВ ТЕКУЩЕЙ ИГРЫ ---
        self.game_tools_panel = QHBoxLayout()
        self.game_tools_panel.setContentsMargins(0, 0, 0, 10) # Отступ снизу
        
        self.ai_chat_btn = QPushButton(_("lbl_ai_chat"))
        self.ai_chat_btn.setFixedWidth(200)
        self.ai_chat_btn.clicked.connect(self.handle_ai_btn_click)
        self.steam_store_btn = QPushButton("🌐 Steam")
        self.steam_store_btn.clicked.connect(self.open_steam_store)
        self.steam_store_btn.setVisible(False) # Скрываем по умолчанию
        
        self.steam_play_btn = QPushButton(f"🎮 {_('btn_play')}")
        self.steam_play_btn.clicked.connect(self.play_steam_game)
        self.steam_play_btn.setVisible(False) # Скрываем по умолчанию

        self.game_tools_panel.addWidget(self.ai_chat_btn)
        self.game_tools_panel.addWidget(self.steam_store_btn)
        self.game_tools_panel.addWidget(self.steam_play_btn)
        
        self.game_tools_panel.addStretch() # Прижимаем кнопку влево
        main_layout.addLayout(self.game_tools_panel)

        # --- 2. Центральная часть (Таблица эпизодов) ---
        # 0 строк (пока пустая), 7 столбцов
        self.table = QTableWidget(0, 7)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers) # <--- БЛОКИРУЕМ СТАНДАРТНОЕ РЕДАКТИРОВАНИЕ
        self.table.setHorizontalHeaderLabels([
            _("col_episode"), _("col_size"), _("col_time"), 
            _("col_desc"), _("col_preview"), "YouTube", "RuTube"
        ])

        # Подключаем двойной клик по ячейке для редактирования кастомного названия эпизода (Пункт 5)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        # --- НОВОЕ: Включаем ПКМ-меню ---
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        
        # Красиво растягиваем столбцы по ширине окна
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        main_layout.addWidget(self.table)

        # --- 3. Нижняя панель (Управление) ---
        bottom_panel = QHBoxLayout()
        
        self.add_episode_btn = QPushButton(_("btn_add_episode"))
        self.add_episode_btn.clicked.connect(self.show_add_episode_dialog)
        self.render_btn = QPushButton(_("btn_compress"))
        self.render_btn.clicked.connect(self.show_compress_dialog)

        bottom_panel.addWidget(self.add_episode_btn)
        bottom_panel.addWidget(self.render_btn)

        main_layout.addLayout(bottom_panel)

        # Загружаем игры при старте
        self.load_games()

        # Проверка первого запуска (если папки не указаны)
        if not self.config.get("renders_folder") or not self.config.get("recordings_folder"):
            QMessageBox.information(self, "Настройка", "Пожалуйста, укажите базовые папки для записей и рендеров.")
            self.open_settings()

    def edit_current_game(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_name = self.game_selector.currentText()
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        folder = game_data['path']
        old_steam_id = game_data.get('steam_id', '')
        
        dialog = EditGameDialog(self, game_name, game_data)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_name = dialog.name_input.text().strip()
            new_ai = dialog.ai_url_input.text().strip()
            new_steam = dialog.steam_input.text().strip()
            
            if not new_name:
                QMessageBox.warning(self, "Ошибка", "Название игры не может быть пустым.")
                return
                
            # Если ввели/изменили Steam ID - скачиваем капсулу
            if new_steam and new_steam != old_steam_id:
                urls_to_try = [
                    f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{new_steam}/header.jpg",
                    f"https://cdn.akamai.steamstatic.com/steam/apps/{new_steam}/header.jpg"
                ]
                import requests
                for img_url in urls_to_try:
                    try:
                        response = requests.get(img_url, timeout=5)
                        if response.status_code == 200:
                            img_path = os.path.join(folder, "steam_capsule.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                            logging.info(f"Новая обложка Steam сохранена: {img_path}")
                            break
                    except Exception as e:
                        logging.error(f"Не удалось скачать обложку Steam: {e}")
            
            # Обновляем БД
            update_game(game_id, new_name, new_ai, new_steam)
            
            # Перезагружаем список игр и возвращаем фокус на ту же игру
            self.load_games()
            
            # Ищем нашу игру по ID, чтобы вернуть на нее выпадающий список
            for i in range(self.game_selector.count()):
                if self.game_selector.itemData(i)['id'] == game_id:
                    self.game_selector.setCurrentIndex(i)
                    break

    def delete_current_game(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_name = self.game_selector.currentText()
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        game_folder = game_data['path']
        
        # 1. Запрашиваем подтверждение вводом названия
        msg = (f"<b>ВНИМАНИЕ!</b> Это действие безвозвратно удалит:<br>"
               f"- Игру из базы данных<br>"
               f"- Все связанные эпизоды и шортсы<br>"
               f"- <b>Папку с игрой и всеми видео на диске</b><br><br>"
               f"Для подтверждения введите точное название игры: <i>{game_name}</i>")
               
        text, ok = QInputDialog.getText(self, "Удаление игры", msg, QLineEdit.EchoMode.Normal, "")
        
        if ok:
            if text.strip() == game_name:
                import shutil # На всякий случай импортируем прямо здесь
                
                # 2. Пытаемся физически удалить папку с диска
                if os.path.exists(game_folder):
                    try:
                        shutil.rmtree(game_folder)
                        logging.info(f"Папка игры удалена: {game_folder}")
                    except Exception as e:
                        QMessageBox.critical(self, "Ошибка", f"Не удалось удалить папку с диска.\nУбедитесь, что файлы не открыты в видеоредакторе или плеере.\n\n{e}")
                        return # Если не удалилась папка, прерываем удаление, чтобы не сломать логику
                
                # 3. Чистим базу данных
                delete_game_full(game_id)
                logging.info(f"Игра '{game_name}' удалена из БД.")
                
                QMessageBox.information(self, "Успех", f"Игра '{game_name}' полностью удалена!")
                
                # 4. Обновляем интерфейс
                self.load_games()
            else:
                QMessageBox.warning(self, "Отмена", "Название введено неверно. Удаление отменено.")

    def open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def open_url_dialog(self, episode_id, hosting_id, hosting_name):
        """Всплывающее окно для ввода ссылки на видео (Пункт 7)"""
        current_url = get_upload_url(episode_id, hosting_id)
        url, ok = QInputDialog.getText(
            self, 
            f"{_('lbl_video_url')} — {hosting_name}", 
            _("lbl_enter_video_url"), 
            QLineEdit.EchoMode.Normal, 
            current_url
        )
        if ok:
            toggle_upload(episode_id, hosting_id, True, url.strip())
            self.update_table()

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
            
        row = item.row()
        ep_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        
        # Данные для пути
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        game_data = self.game_selector.itemData(current_index)
        ep_number = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)
        ep_folder = os.path.join(game_data['path'], f"ep{ep_number}")

        menu = QMenu(self)
        refresh_action = menu.addAction("🔄 Обновить данные видеофайла")
        date_action = menu.addAction("📅 Изменить дату публикации")
        menu.addSeparator() # Разделитель для безопасности
        delete_action = menu.addAction("🗑️ Удалить папку эпизода (Очистка)") # <--- НОВАЯ КНОПКА
        
        # Показываем меню ровно в месте клика
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == refresh_action:
            self.refresh_episode_data(ep_id, ep_folder)
        elif action == date_action:
            self.edit_publish_date(ep_id, row)
        elif action == delete_action: # <--- ОБРАБОТЧИК КЛИКА
            self.delete_episode_folder(ep_id, ep_folder)

    def refresh_episode_data(self, ep_id, ep_folder):
        if not os.path.exists(ep_folder):
            QMessageBox.warning(self, "Ошибка", "Папка эпизода не найдена на диске.")
            return
        
        video_file = None
        for file in os.listdir(ep_folder):
            if file.endswith(('.mkv', '.mp4')):
                video_file = os.path.join(ep_folder, file)
                if file.endswith('.mp4'): break
        
        if video_file:
            size_bytes = os.path.getsize(video_file)
            size_text = self.get_format_size(size_bytes)
            duration_text = self.get_video_duration(video_file)
            update_episode_metadata(ep_id, size_text, duration_text)
            self.update_table()
            QMessageBox.information(self, "Готово", f"Данные файла успешно обновлены!\nВес: {size_text}\nВремя: {duration_text}")
        else:
            QMessageBox.warning(self, "Ошибка", "Не удалось найти видеофайл в папке эпизода.")

    def edit_publish_date(self, ep_id, row):
        current_date = self.table.item(row, 6).text()
        dialog = CalendarDialog(self, current_date)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_episode_publish_date(ep_id, dialog.selected_date_str)
            self.update_table()

    def delete_episode_folder(self, ep_id, ep_folder):
        # Проверяем, существует ли папка вообще
        if not os.path.exists(ep_folder):
            QMessageBox.information(self, "Информация", "Папка уже удалена с диска.")
            mark_episode_deleted(ep_id)
            self.update_table()
            return

        # Запрашиваем подтверждение
        reply = QMessageBox.question(
            self, "Подтверждение очистки", 
            f"Вы уверены, что хотите безвозвратно удалить папку:\n{ep_folder}\nсо всеми тяжелыми исходниками?\n\nЗапись об эпизоде останется в таблице (окрасится в голубой).", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(ep_folder) # Безвозвратно удаляем папку со всем содержимым
                mark_episode_deleted(ep_id) # Обновляем БД
                self.update_table() # Перерисовываем таблицу (строка станет голубой)
                QMessageBox.information(self, "Успех", "Папка эпизода успешно удалена.")
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить папку:\n{e}")

    def open_url_dialog(self, ep_id, host_id, host_name):
        current_url = get_upload_url(ep_id, host_id)
        new_url, ok = QInputDialog.getText(
            self, f"Ссылка: {host_name}",
            "Введите ссылку на опубликованное видео:",
            QLineEdit.EchoMode.Normal, current_url or ""
        )
        if ok:
            update_upload_url(ep_id, host_id, new_url.strip())
            self.update_table()

    def retranslate_ui(self):
        # Обновляем заголовок окна
        self.setWindowTitle(_("app_title"))
        
        # Обновляем кнопки
        self.settings_btn.setText(_("btn_settings"))
        self.add_game_btn.setText(_("btn_add_game"))
        self.add_episode_btn.setText(_("btn_add_episode"))
        self.render_btn.setText(_("btn_compress"))
        self.delete_old_btn.setText(_("btn_delete_old"))
        
        # Обновляем заголовки таблицы
        self.table.setHorizontalHeaderLabels([
            _("col_episode"), 
            _("col_size"), 
            _("col_time"), 
            _("col_desc"), 
            _("col_preview"), 
            "YouTube", "RuTube"
        ])

    def open_settings(self):
        dialog = SettingsDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:

            # Забираем язык (через currentData получаем "ru_ru" или "en_us")
            self.config["language"] = dialog.lang_selector.currentData()

            # Если нажали "Сохранить", обновляем словарь
            self.config["recordings_folder"] = dialog.recordings_input.text()
            self.config["renders_folder"] = dialog.renders_input.text()
            self.config["notepad_path"] = dialog.editor_input.text()
            self.config["gimp_path"] = dialog.gimp_input.text()
            self.config["desc_name"] = dialog.desc_input.text()
            self.config["preview_name"] = dialog.prev_input.text()
            
            # Сохраняем в файл json
            save_config(self.config)

            # ЗАГРУЖАЕМ НОВЫЙ СЛОВАРЬ В ПАМЯТЬ
            load_language(self.config["language"])

            # МГНОВЕННО ОБНОВЛЯЕМ ИНТЕРФЕЙС
            self.retranslate_ui()
            
            # Перерисовываем таблицу, чтобы новые имена файлов применились
            self.update_table()

    def show_compress_dialog(self):
        dialog = CompressDialog(self, self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            input_file = dialog.filepath
            # Забираем кодек и число битрейта
            codec = dialog.codec_selector.currentData()
            bitrate_num = dialog.bitrate_selector.currentText()
            
            bitrate = bitrate_num + "M"
            # Буфер обычно делают в 1-2 раза больше битрейта для стабильности
            bufsize = str(int(bitrate_num) * 2) + "M" 
            
            directory, filename_with_ext = os.path.split(input_file)
            filename_no_ext, ext = os.path.splitext(filename_with_ext)
            out_filename = f"{filename_no_ext} (lowbitrate {bitrate}).mp4"
            output_file = os.path.join(directory, out_filename)

            # Обновленная команда с жесткими рамками для видеокарты
            cmd = ['ffmpeg', '-y', '-i', input_file, 
                   '-c:v', codec, 
                   '-b:v', bitrate, 
                   '-maxrate', bitrate, 
                   '-bufsize', bufsize,
                   '-c:a', 'aac', '-b:a', '192k', 
                   output_file]
            
            # Запускаем нашего воркера и показываем уже готовое окно логов
            self.worker = FFmpegWorker(cmd)
            self.progress_dialog = ProgressDialog(self)
            
            self.worker.progress.connect(self.progress_dialog.append_log)
            # Для сжатия можно использовать тот же обработчик on_ffmpeg_finished
            self.worker.finished.connect(self.on_ffmpeg_finished)
            
            self.worker.start()
            self.progress_dialog.exec()

    def show_add_episode_dialog(self):
        # Достаем список игр и текущую игру, чтобы передать в диалог
        games = get_games()
        current_index = self.game_selector.currentIndex()
        if current_index == -1:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_add_game_first"))
            return
            
        current_game_data = self.game_selector.itemData(current_index)
        current_game_id = current_game_data['id']

        # Создаем и показываем наше окно
        dialog = AddEpisodeDialog(self, games, current_game_id, self.config)
        
        # Если пользователь нажал "Добавить и Конвертировать"
        if dialog.exec() == QDialog.DialogCode.Accepted:
            input_file = dialog.file_input.text()
            if not input_file:
                QMessageBox.warning(self, _("msg_title_error"), _("msg_no_source_file_selected"))
                return
                
            # Собираем данные
            game_data = dialog.game_selector.itemData(dialog.game_selector.currentIndex())
            game_name = dialog.game_selector.currentText()
            ep_number = dialog.ep_spinbox.value()
            base_folder = game_data['path']
            do_convert = dialog.convert_checkbox.isChecked() # <--- Считываем галочку
            
            # Формируем папку и выходной файл
            ep_folder = os.path.join(base_folder, f"ep{ep_number}")
            os.makedirs(ep_folder, exist_ok=True) # Создаем папку epX, если её нет

            # Определяем расширение. Если не конвертируем, сохраняем оригинальное
            _, ext = os.path.splitext(input_file)
            if do_convert:
                ext = '.mp4' # Принудительно MP4, если идет перепаковка
            
            # Имя выходного файла: Game Name - Ep.2.mp4
            out_filename = f"{game_name} - Ep.{ep_number}.mp4"
            output_file = os.path.join(ep_folder, out_filename)

            # НОВАЯ ЛОГИКА: Решаем, как обработать файл
            if do_convert:
                # Старый добрый FFmpeg (Remux)
                cmd = ['ffmpeg', '-y', '-i', input_file, '-c', 'copy', output_file]
                
                self.worker = FFmpegWorker(cmd)
                self.progress_dialog = ProgressDialog(self)
                self.worker.progress.connect(self.progress_dialog.append_log)
                self.worker.finished.connect(self.on_ffmpeg_finished)
                
                self.worker.start()
                self.progress_dialog.exec()
            else:
                # Простое перемещение / переименование файла
                norm_input = os.path.normpath(input_file)
                norm_output = os.path.normpath(output_file)
                
                if norm_input != norm_output:
                    try:
                        shutil.move(norm_input, norm_output)
                        QMessageBox.information(self, _("msg_title_success"), f"{_('lbl_video_convert_success')}\n{out_filename}")
                    except Exception as e:
                        QMessageBox.critical(self, _("msg_title_error"), f"{_('lbl_video_convert_error')}\n{e}")
                else:
                    QMessageBox.information(self, _("msg_title_done"), _("lbl_video_convert_exist"))
                
                self.update_table() # Сразу обновляем таблицу

    def on_ffmpeg_finished(self, success, message):
        # Закрываем окно с логами, когда воркер закончил
        self.progress_dialog.accept() 
        
        if success:
            QMessageBox.information(self, _("msg_title_success"), _("msg_video_added_and_remuxed"))
            self.update_table() 
        else:
            QMessageBox.critical(self, _("msg_title_conversion_error"), f"{_('msg_error_occurred')}:\n{message}")

# Загрузка игр из БД в выпадающий список
    def load_games(self):
        self.game_selector.blockSignals(True)
        self.game_selector.clear()
        games = get_games()
        # Добавляем ai_url в распаковку и в userData
        for game_id, name, folder_path, ai_url, steam_id in games:
            self.game_selector.addItem(name, userData={'id': game_id, 'path': folder_path, 'ai_url': ai_url, 'steam_id': steam_id})
        self.game_selector.blockSignals(False)
        
        if self.game_selector.count() > 0:
            self.update_table()

    # Функция добавления новой игры
    def add_new_game(self):
        dialog = AddGameDialog(self, self.config)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            name = dialog.name_input.text().strip()
            folder = dialog.folder_input.text().strip()
            ai_url = dialog.ai_url_input.text().strip()
            steam_id = dialog.steam_input.text().strip() # <--- Достаем Steam ID
            
            if not name or not folder:
                QMessageBox.warning(self, _("status_error"), _("msg_name_folder_game_need"))
                return
                
            # Если папки еще нет на диске — создаем её автоматически
            if not os.path.exists(folder):
                try:
                    os.makedirs(folder)
                    logging.info(f"Создана новая папка для игры: {folder}")
                except Exception as e:
                    QMessageBox.critical(self, _("status_error"), f"{_('msg_cant_create_folder')}\n{e}")
                    return
            
            # --- НОВОЕ: Скачиваем капсулу из Steam (с проверкой двух URL) ---
            if steam_id:
                urls_to_try = [
                    f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{steam_id}/header.jpg",
                    f"https://cdn.akamai.steamstatic.com/steam/apps/{steam_id}/header.jpg"
                ]
                
                import requests
                for img_url in urls_to_try:
                    try:
                        response = requests.get(img_url, timeout=5)
                        if response.status_code == 200:
                            img_path = os.path.join(folder, "steam_capsule.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(response.content)
                            logging.info(f"Обложка Steam сохранена: {img_path}")
                            break # Успешно скачали, выходим из цикла
                    except Exception as e:
                        logging.error(f"Ошибка при попытке скачать по ссылке {img_url}: {e}")
            
            # Сохраняем в БД с новыми параметрами
            add_game(name, folder, ai_url=ai_url, steam_id=steam_id) # <--- Передаем steam_id
            
            self.load_games()
            self.game_selector.setCurrentIndex(self.game_selector.count() - 1)

    def on_cell_double_clicked(self, row, column):
        # Столбец 0: Редактирование кастомного названия эпизода
        if column == 0:
            item = self.table.item(row, 0)
            if not item:
                return
            
            ep_id = item.data(Qt.ItemDataRole.UserRole)
            current_title = item.data(Qt.ItemDataRole.UserRole + 1) or ""
            ep_number = item.data(Qt.ItemDataRole.UserRole + 2)

            new_title, ok = QInputDialog.getText(
                self, 
                _("lbl_episode_title", _("lbl_episode_title")), 
                f"{_('lbl_enter_episode_title')} {ep_number}:", 
                QLineEdit.EchoMode.Normal, 
                current_title
            )
            
            if ok:
                update_episode_title(ep_id, new_title.strip())
                self.update_table()

        # Столбец 6: Редактирование даты публикации
        elif column == 6:
            ep_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.edit_publish_date(ep_id, row) # <--- Вызываем наш новый виджет!

    def handle_ai_btn_click(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1:
            return
        
        game_data = self.game_selector.itemData(current_index)
        ai_url = game_data.get('ai_url', '')
        
        if ai_url:
            # Открываем чат в браузере
            webbrowser.open(ai_url)
        else:
            # Если ссылки нет, предлагаем её добавить
            url, ok = QInputDialog.getText(
                self, _("title_ai_chat_add"), 
                _("lbl_ai_chat_enter_link_to_dialogue"), 
                QLineEdit.EchoMode.Normal
            )
            if ok and url.strip():
                update_game_ai_url(game_data['id'], url.strip())
                # Мгновенно обновляем данные текущей игры в памяти
                game_data['ai_url'] = url.strip()
                self.game_selector.setItemData(current_index, game_data)
                self.update_table() # Обновит цвет кнопки

    def update_table(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1:
            return
            
        self.ai_chat_btn.setVisible(True)
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        folder_path = game_data['path']
        ai_url = game_data.get('ai_url', '')

        # Подсветка кнопки ИИ
        if ai_url:
            self.ai_chat_btn.setText(_("lbl_ai_chat_open"))
            self.ai_chat_btn.setStyleSheet("background-color: #add8e6; font-weight: bold;") # Голубая
        else:
            self.ai_chat_btn.setText(_("lbl_ai_chat_add"))
            self.ai_chat_btn.setStyleSheet("") # Обычный цвет

        # --- ПОКАЗЫВАЕМ ИЛИ СКРЫВАЕМ КНОПКИ STEAM ЗДЕСЬ ---
        steam_id = game_data.get('steam_id', '')
        self.steam_store_btn.setVisible(bool(steam_id))
        self.steam_play_btn.setVisible(bool(steam_id))
        # ---------------------------------------------------

        hostings = get_videohostings() 
        
        # Добавили новую колонку "Медиа" (Индекс 3)
        headers = [
            _("col_episode"), _("col_size"), _("col_time"), _("col_media"), 
            _("col_desc"), _("col_preview"), _("col_publish_date"), _("col_shorts")
        ]
        for h_id, h_key, h_display_name in hostings:
            headers.append(h_display_name)

        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        if os.path.exists(folder_path):
            for item in os.listdir(folder_path):
                full_path = os.path.join(folder_path, item)
                if os.path.isdir(full_path) and item.startswith("ep"):
                    match = re.search(r'\d+', item)
                    if match:
                        ep_number = int(match.group())
                        add_episode_if_not_exists(game_id, ep_number)

        episodes = get_episodes(game_id)

        # --- ДОБАВЛЯЕМ ЭТУ СТРОКУ ---
        self.table.clearContents() # Жестко стираем все старые ячейки перед отрисовкой новых
        # ----------------------------

        self.table.setRowCount(len(episodes))

        for row_idx, ep in enumerate(episodes):
            ep_id, ep_number, ep_title, db_size, db_duration, pub_date, shorts_count = ep
            ep_folder = os.path.join(folder_path, f"ep{ep_number}")
            folder_exists = os.path.exists(ep_folder)

            display_ep_text = f"{_('lbl_episode')} {ep_number}"
            if ep_title:
                display_ep_text += f" {ep_title}"
                
            ep_item = QTableWidgetItem(display_ep_text)
            ep_item.setData(Qt.ItemDataRole.UserRole, ep_id)
            ep_item.setData(Qt.ItemDataRole.UserRole + 1, ep_title)
            ep_item.setData(Qt.ItemDataRole.UserRole + 2, ep_number)

            if not folder_exists:
                ep_item.setBackground(QColor("#add8e6"))
                ep_item.setToolTip(_("tooltip_sources_deleted_from_disk"))
            self.table.setItem(row_idx, 0, ep_item)

            if folder_exists:
                video_file = None
                for file in os.listdir(ep_folder):
                    if file.endswith(('.mkv', '.mp4')):
                        video_file = os.path.join(ep_folder, file)
                        if file.endswith('.mp4'):
                            break

                size_text = "..."
                duration_text = "..."

                if video_file:
                    if db_size != '0' and db_duration != '0':
                        size_text = db_size
                        duration_text = db_duration
                    else:
                        size_bytes = os.path.getsize(video_file)
                        size_text = self.get_format_size(size_bytes)
                        duration_text = self.get_video_duration(video_file)
                        update_episode_metadata(ep_id, size_text, duration_text)
                else:
                    size_text = "Нет файла"
                    duration_text = "-"

                self.table.setItem(row_idx, 1, QTableWidgetItem(size_text)) 
                self.table.setItem(row_idx, 2, QTableWidgetItem(duration_text))

                # --- НОВАЯ СЕКЦИЯ: МЕДИАКНОПКИ (Папка и Видео) ---
                media_widget = QWidget()
                media_layout = QHBoxLayout(media_widget)
                media_layout.setContentsMargins(4, 2, 4, 2)
                
                folder_btn = QPushButton("📁")
                folder_btn.setToolTip(_("tooltip_open_episode_folder"))
                folder_btn.setFixedWidth(30)
                folder_btn.clicked.connect(lambda checked, p=ep_folder: os.startfile(p))
                
                play_btn = QPushButton("▶️")
                play_btn.setToolTip(_("tooltip_watch_video"))
                play_btn.setFixedWidth(30)
                if video_file:
                    play_btn.clicked.connect(lambda checked, p=video_file: os.startfile(p))
                else:
                    play_btn.setEnabled(False) # Выключаем кнопку, если видео нет
                    
                media_layout.addWidget(folder_btn)
                media_layout.addWidget(play_btn)
                media_layout.addStretch()
                self.table.setCellWidget(row_idx, 3, media_widget) # Теперь это индекс 3

                # --- БЛОК ОПИСАНИЯ И ПРЕВЬЮ (Теперь индексы 4 и 5) ---
                desc_name = self.config.get("desc_name", "desc.txt")
                prev_name = self.config.get("preview_name", "preview.jpg")
                
                desc_path = os.path.join(ep_folder, desc_name)
                prev_path = os.path.join(ep_folder, prev_name)

                # Описание (Кнопка с иконкой)
                desc_exists = os.path.exists(desc_path)
                desc_empty = desc_exists and os.path.getsize(desc_path) == 0

                desc_btn = QPushButton("📝")
                desc_btn.setToolTip(f"{_('tooltip_description')} ({desc_name})")
                if not desc_exists:
                    desc_btn.setStyleSheet("background-color: lightcoral; font-size: 14px;")
                elif desc_empty:
                    desc_btn.setStyleSheet("background-color: #ffd700; font-size: 14px;")
                else:
                    desc_btn.setStyleSheet("background-color: lightgreen; font-size: 14px;")
                    
                desc_btn.clicked.connect(lambda checked, p=desc_path: self.open_notepad(p))
                self.table.setCellWidget(row_idx, 4, desc_btn)

                # Превью (Кнопка с иконкой)
                prev_exists = os.path.exists(prev_path)
                prev_empty = prev_exists and os.path.getsize(prev_path) < 1024 

                prev_btn = QPushButton("🖼️")
                prev_btn.setToolTip(f"{_('tooltip_preview')} ({prev_name})")
                if not prev_exists:
                    prev_btn.setStyleSheet("background-color: lightcoral; font-size: 14px;")
                elif prev_empty:
                    prev_btn.setStyleSheet("background-color: #ffd700; font-size: 14px;")
                else:
                    prev_btn.setStyleSheet("background-color: lightgreen; font-size: 14px;")
                    
                prev_btn.clicked.connect(lambda checked, p=prev_path: self.open_gimp(p))
                self.table.setCellWidget(row_idx, 5, prev_btn)

                pub_item = QTableWidgetItem(pub_date if pub_date else "Не задана")
                if not folder_exists:
                    pub_item.setBackground(QColor("#add8e6"))
                self.table.setItem(row_idx, 6, pub_item)

                # --- КОЛОНКА ШОРТСОВ ---
                shorts_btn = QPushButton()
                if shorts_count > 0:
                    shorts_btn.setText(f"Шортсов: {shorts_count}")
                    shorts_btn.setStyleSheet("background-color: #90ee90; color: black;") # Зеленый индикатор
                else:
                    shorts_btn.setText("+ Добавить")
                
                # Привязываем вызов менеджера
                shorts_btn.clicked.connect(lambda checked, e=ep_id, n=ep_number: self.open_shorts_manager(e, n))

                self.table.setCellWidget(row_idx, 7, shorts_btn) # Ставим кнопку в 7-й столбец

            else:
                # Создаем элементы
                size_item = QTableWidgetItem(db_size if db_size and db_size != '0' else _("lbl_deleted"))
                dur_item = QTableWidgetItem(db_duration if db_duration and db_duration != '0' else "-")
                media_item = QTableWidgetItem("-")
                desc_item = QTableWidgetItem(_("lbl_deleted"))
                prev_item = QTableWidgetItem(_("lbl_deleted"))
                
                # ДОБАВЛЕНО: Создаем элемент даты для удаленных папок
                pub_item = QTableWidgetItem(pub_date if pub_date else _("lbl_not_set"))

                shorts_item  = QTableWidgetItem("-")

                # Красим их ВСЕ в голубой
                for it in (size_item, dur_item, media_item, desc_item, prev_item, pub_item, shorts_item):
                    it.setBackground(QColor("#add8e6"))

                self.table.setItem(row_idx, 1, size_item)
                self.table.setItem(row_idx, 2, dur_item)
                self.table.setItem(row_idx, 3, media_item)
                self.table.setItem(row_idx, 4, desc_item)
                self.table.setItem(row_idx, 5, prev_item)
                self.table.setItem(row_idx, 6, pub_item) # <--- ОБЯЗАТЕЛЬНО ПЕРЕЗАПИСЫВАЕМ СТОЛБЕЦ 6      
                self.table.setItem(row_idx, 7, shorts_item)
            
            # --- ДИНАМИЧЕСКИЕ СТОЛБЦЫ И ССЫЛКИ (Индексы сместились на 8 + col_offset) ---
            uploads = get_uploads(ep_id) 
            
            for col_offset, (h_id, h_key, h_display_name) in enumerate(hostings):
                cell_widget = QWidget()
                cell_layout = QHBoxLayout(cell_widget)
                cell_layout.setContentsMargins(4, 2, 4, 2)
                
                # Галочка
                cb = QCheckBox()
                cb.setToolTip(_("tooltip_video_uploaded"))
                cb.setChecked(h_id in uploads)
                cb.toggled.connect(lambda checked, e=ep_id, h=h_id: toggle_upload(e, h, checked))
                
                # Единая умная кнопка ссылки
                current_url = get_upload_url(ep_id, h_id)
                link_btn = QPushButton()
                link_btn.setFixedWidth(35)

                if current_url:
                    link_btn.setText("🌐")
                    link_btn.setStyleSheet("background-color: #add8e6;") # Голубой цвет, если есть
                    link_btn.setToolTip(f"{_('tooltip_watch_on')} {h_display_name}\n{_("lbl_open_change")}")
                    link_btn.clicked.connect(lambda checked, url=current_url: webbrowser.open(url))
                else:
                    link_btn.setText("✏️")
                    link_btn.setToolTip(f"{_('tooltip_enter_change_link')} {h_display_name}")
                    link_btn.clicked.connect(lambda checked, e=ep_id, h=h_id, name=h_display_name: self.open_url_dialog(e, h, name))
                
                # ПКМ по самой кнопке всегда открывает окно редактирования ссылки
                link_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                link_btn.customContextMenuRequested.connect(lambda pos, e=ep_id, h=h_id, name=h_display_name: self.open_url_dialog(e, h, name))
                
                cell_layout.addWidget(cb)
                cell_layout.addWidget(link_btn)
                cell_layout.addStretch()
                
                self.table.setCellWidget(row_idx, 8 + col_offset, cell_widget)

    def open_notepad(self, file_path):
        if not os.path.exists(file_path):
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("")
        
        # Достаем путь из конфига (по умолчанию 'notepad.exe')
        editor = self.config.get("notepad_path", "notepad.exe")
        
        try:
            # Если поле пустое, fallback на стандартное приложение Windows
            if not editor.strip():
                os.startfile(file_path)
            else:
                # Запускаем выбранный редактор и передаем ему файл
                subprocess.Popen([editor, file_path])
        except Exception as e:
            logging.error(f"{_('log_failed_to_open_editor')}: {e}")
            
        self.update_table()

    def open_gimp(self, file_path):
        gimp_path = self.config.get("gimp_path", "").strip()
        
        # Если путь к графическому редактору не указан
        if not gimp_path:
            if os.path.exists(file_path):
                os.startfile(file_path) # Откроет стандартным просмотрщиком фото
            else:
                # Если картинки нет, откроем папку эпизода
                os.startfile(os.path.dirname(file_path)) 
            return
            
        # Если редактор (GIMP, Photoshop) указан
        try:
            if os.path.exists(file_path):
                subprocess.Popen([gimp_path, file_path])
            else:
                # Если файла нет, просто запускаем редактор
                subprocess.Popen([gimp_path])
        except Exception as e:
            logging.error(f"{_('log_failed_to_start_gimp')}: {e}")

    def get_format_size(self, size_bytes):
        if size_bytes == 0:
            return "0 B"
        # Массив суффиксов
        size_name = ("B", "KB", "MB", "GB", "TB")
        # Высчитываем порядок (0 для B, 1 для KB, 2 для MB и т.д.)
        i = int(math.floor(math.log(size_bytes, 1024)))
        p = math.pow(1024, i)
        s = round(size_bytes / p, 2)
        return f"{s} {size_name[i]}"

    def get_video_duration(self, filepath):
        try:
            # Запускаем ffprobe (он идет в комплекте с ffmpeg)
            # creationflags=0x08000000 скрывает всплывающее черное окно консоли в Windows
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 
                 'format=duration', '-of', 
                 'default=noprint_wrappers=1:nokey=1', filepath],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=0x08000000
            )
            # Получаем время в секундах (float)
            seconds = float(result.stdout.strip())
            
            # Конвертируем в HH:MM:SS
            m, s = divmod(int(seconds), 60)
            h, m = divmod(m, 60)
            if h > 0:
                return f"{h:02d}:{m:02d}:{s:02d}"
            else:
                return f"{m:02d}:{s:02d}"
        except Exception as e:
            # Если ffprobe не найден или файл сломан
            return _("status_error")
        
    def open_shorts_manager(self, ep_id, ep_number):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_data = self.game_selector.itemData(current_index)
        game_name = self.game_selector.currentText()
        ep_folder = os.path.join(game_data['path'], f"ep{ep_number}")
        ai_url = game_data.get('ai_url', '')

        # Получаем размер и длительность эпизода из базы
        episodes = get_episodes(game_data['id'])
        ep = next((e for e in episodes if e[0] == ep_id), None)
        if not ep: return
        db_size, db_dur = ep[3], ep[4]

        dialog = ShortsManagerDialog(self, ep_id, ep_number, ep_folder, game_name, db_size, db_dur, ai_url, self.config, get_videohostings())
        dialog.exec()
        
        # Когда окно закроется, обновляем главную таблицу (чтобы кнопка "+ Добавить" сменилась на счетчик)
        self.update_table()

    def open_steam_store(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        steam_id = self.game_selector.itemData(current_index).get('steam_id', '')
        if steam_id:
            webbrowser.open(f"https://store.steampowered.com/app/{steam_id}")

    def play_steam_game(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        steam_id = self.game_selector.itemData(current_index).get('steam_id', '')
        if steam_id:
            # Магия протокола steam:// - запускает игру напрямую без браузера
            webbrowser.open(f"steam://rungameid/{steam_id}")

if __name__ == "__main__":
    # На всякий случай проверяем БД перед стартом
    init_db()

    # Запуск приложения
    app = QApplication(sys.argv)
    
    # Применяем современный стиль, чтобы окно выглядело аккуратно
    app.setStyle("Fusion")

    window = LetsPlayManager()
    window.show()

    sys.exit(app.exec())