import sys
import logging
import os
import re
import shutil
import webbrowser
import math
import subprocess
import webbrowser

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QPushButton, QTableWidget, QTableWidgetItem,
                             QComboBox, QLabel, QHeaderView, QInputDialog, 
                             QLineEdit, QMessageBox, QMenu, QDialog, QCheckBox,
                             QMenu, QMenuBar, QApplication)
from PyQt6.QtGui import (QColor, QAction, QIcon)

# --- НАШИ МОДУЛИ ---
from core.config import _, load_config, save_config, load_language, APP_VERSION, BASE_DIR
from core.ffmpeg_worker import FFmpegWorker, get_tool_path
from core.update_checker import UpdateCheckerThread

from database import (add_game, get_games, add_episode_if_not_exists, 
                      get_episodes, get_uploads, toggle_upload, update_episode_metadata,
                      get_videohostings, update_episode_title, get_upload_url,
                      update_game_ai_url, update_episode_publish_date, update_upload_url, 
                      mark_episode_deleted, delete_game_full, update_game, check_unpublished_shorts,
                      is_game_archived, update_episode_metadata_full, get_episode_metadata,
                      get_game_playlists, update_game_playlists)

# --- ОКНА (ДИАЛОГИ) ---
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.progress_dialog import ProgressDialog
from gui.dialogs.calendar_dialog import CalendarDialog
from gui.dialogs.game_dialog import GameDialog
from gui.dialogs.add_episode_dialog import AddEpisodeDialog
from gui.dialogs.compress_dialog import CompressDialog
from gui.shorts_manager import ShortsManagerDialog
from gui.dialogs.shorts_cutter_dialog import ShortsCutterDialog
from gui.dialogs.schedule_dialog import ScheduleDialog
from gui.dialogs.select_episode_dialog import SelectEpisodeDialog
from gui.dialogs.profile_settings_dialog import ProfileSettingsDialog
from gui.dialogs.episode_metadata_dialog import EpisodeMetadataDialog
from core.profile_manager import ProfileManager

class LetsPlayManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()

        # --- ИНИЦИАЛИЗАЦИЯ МЕНЕДЖЕРА ПРОФИЛЕЙ ---
        self.pm = ProfileManager()

        # ЗАГРУЖАЕМ ЯЗЫК
        load_language(self.config.get("language", "ru_ru"))
        
        # Настройки самого окна
        self.setWindowTitle(_("app_title"))
        self.resize(1280, 720)

        icon_path = os.path.join(BASE_DIR, "assets", "icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # Центральный виджет (основа окна)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Главный вертикальный слой (все элементы будут идти сверху вниз)
        main_layout = QVBoxLayout(central_widget)

        # Инициализируем верхнее меню
        self.setup_menu()

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
        self.edit_game_btn = QPushButton(f"✏ {_('btn_edit')}")
        self.edit_game_btn.clicked.connect(self.edit_current_game)
        top_panel.addWidget(self.edit_game_btn)
        # -----------------------------------

        # --- НОВАЯ КНОПКА УДАЛЕНИЯ ---
        self.delete_game_btn = QPushButton(f"🗑 {_('btn_delete_game')}")
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
        top_panel.addWidget(self.about_btn)

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

        self.schedule_btn = QPushButton(f"📅 {_('btn_publish_calendar')}")
        self.schedule_btn.setFixedWidth(200)
        self.schedule_btn.clicked.connect(self.open_schedule)

        self.steam_store_btn = QPushButton("🌐 Steam")
        self.steam_store_btn.clicked.connect(self.open_steam_store)
        self.steam_store_btn.setVisible(False) # Скрываем по умолчанию
        
        self.steam_play_btn = QPushButton(f"🎮 {_('btn_play')}")
        self.steam_play_btn.clicked.connect(self.play_steam_game)
        self.steam_play_btn.setVisible(False) # Скрываем по умолчанию

        self.game_tools_panel.addWidget(self.ai_chat_btn)
        self.game_tools_panel.addWidget(self.schedule_btn)
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
            QMessageBox.information(self, _("msg_settings"), _("msg_choose_base_dirs"))
            self.open_settings()

        # --- ПРОВЕРКА ОБНОВЛЕНИЙ ---
        self.update_checker = UpdateCheckerThread()
        self.update_checker.update_available.connect(self.show_update_notification)
        self.update_checker.start()

    def setup_menu(self):
        # Используем встроенный метод QMainWindow для создания меню
        self.menu_bar = self.menuBar()
        
        # --- 1. Меню "Игра" ---
        game_menu = self.menu_bar.addMenu(_("menu_game"))
        
        add_game_act = QAction(_("menu_add_game"), self)
        add_game_act.triggered.connect(self.add_new_game) # Привязываем к существующему методу
        game_menu.addAction(add_game_act)
        
        edit_game_act = QAction(_("menu_edit_game"), self)
        # Если у тебя есть метод редактирования, замени None на self.edit_game
        edit_game_act.triggered.connect(self.edit_current_game) 
        game_menu.addAction(edit_game_act)
        
        game_menu.addSeparator() # Визуальный разделитель
        
        delete_game_act = QAction(_("menu_delete_game"), self)
        delete_game_act.triggered.connect(self.delete_current_game)
        game_menu.addAction(delete_game_act)

        # --- 2. Меню "Видео" ---
        video_menu = self.menu_bar.addMenu(_("menu_video"))
        
        add_ep_act = QAction(_("menu_add_episode"), self)
        add_ep_act.triggered.connect(self.show_add_episode_dialog)
        video_menu.addAction(add_ep_act)

        # --- 3. Меню "Шортсы" ---
        shorts_menu = self.menu_bar.addMenu(_("menu_shorts"))
        
        shorts_manager_act = QAction(_("menu_shorts_manager"), self)
        shorts_manager_act.triggered.connect(self.open_shorts_manager) # Твой метод вызова менеджера
        shorts_menu.addAction(shorts_manager_act)

        # --- 4. Меню "Инструменты" ---
        tools_menu = self.menu_bar.addMenu(_("menu_tools"))
        
        transcoder_act = QAction(_("menu_transcoder"), self)
        transcoder_act.triggered.connect(self.show_compress_dialog) # Метод вызова транскодера
        tools_menu.addAction(transcoder_act)
        
        schedule_act = QAction(_("menu_publish_calendar"), self)
        schedule_act.triggered.connect(self.open_schedule)
        tools_menu.addAction(schedule_act)

        # --- 5. Меню "Настройки" ---
        settings_menu = self.menu_bar.addMenu(_("menu_settings"))
        
        app_settings_act = QAction(_("menu_app_settings"), self)
        app_settings_act.triggered.connect(self.open_settings) # Если есть окно настроек
        settings_menu.addAction(app_settings_act)
        
        profile_settings_act = QAction(_("menu_profile_manager"), self)
        profile_settings_act.triggered.connect(self.open_profile_settings) # Будущий метод
        settings_menu.addAction(profile_settings_act)

        # --- 6. Меню "О программе" ---
        about_menu = self.menu_bar.addMenu(_("menu_about"))
        
        about_act = QAction(_("menu_about"), self)
        about_act.triggered.connect(self.open_about)
        about_menu.addAction(about_act)
        
        about_menu.addSeparator()
        
        github_act = QAction("GitHub", self)
        github_act.triggered.connect(lambda: webbrowser.open("https://github.com/zurisar/letsplaymanager"))
        about_menu.addAction(github_act)
        
        vk_act = QAction(_("menu_vk_group"), self)
        # Замени ссылку на свою реальную группу VK
        vk_act.triggered.connect(lambda: webbrowser.open("https://vk.ru/zarubagames")) 
        about_menu.addAction(vk_act)

    def open_schedule(self):
        dialog = ScheduleDialog(self, self.config)
        dialog.exec()
    
    def edit_current_game(self):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_name = self.game_selector.currentText()
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        folder = game_data['path']
        old_steam_id = game_data.get('steam_id', '')
        
        # --- ВЫЗЫВАЕМ НОВЫЙ ОБЪЕДИНЕННЫЙ ДИАЛОГ ---
        from gui.dialogs.game_dialog import GameDialog 
        dialog = GameDialog(self, self.config, game_name=game_name, game_data=game_data)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕТОД СБОРА ДАННЫХ ---
            data = dialog.get_data()
            
            new_name = data.get('name', '').strip()
            new_ai = data.get('ai_url', '').strip()
            new_steam = data.get('steam_id', '').strip()
            
            # Извлекаем новые метаданные для шаблонов
            desc_template = data.get("desc_template", "")
            default_tags = data.get("default_tags", "")
            
            if not new_name:
                QMessageBox.warning(self, _("msg_title_error"), _("msg_game_name_cannot_be_empty"))
                return
                
            # Если ввели/изменили Steam ID - скачиваем капсулу
            if new_steam and new_steam != old_steam_id:
                # --- Скачиваем капсулу через Steam API ---
                import requests
                api_url = f"https://store.steampowered.com/api/appdetails?appids={new_steam}"
                try:
                    # Сначала получаем JSON от Steam
                    response = requests.get(api_url, timeout=5).json()
                    
                    # Проверяем, что игра найдена и запрос успешен
                    if response and str(new_steam) in response and response[str(new_steam)].get("success"):
                        # Достаем актуальную ссылку на картинку
                        img_url = response[str(new_steam)]["data"]["header_image"]
                        
                        # Скачиваем саму картинку
                        img_resp = requests.get(img_url, timeout=5)
                        if img_resp.status_code == 200:
                            img_path = os.path.join(folder, "steam_capsule.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(img_resp.content)
                            logging.info(f"Обложка Steam успешно скачана через API: {img_path}")
                    else:
                        logging.warning(f"Steam API не нашел игру с ID {new_steam}")
                except Exception as e:
                    logging.error(f"Ошибка при работе со Steam API: {e}")
            
            # Обновляем БД с учетом новых полей шаблонов
            update_game(
                game_id=game_id, 
                name=new_name, 
                ai_url=new_ai, 
                steam_id=new_steam,
                desc_template=data.get("desc_template", ""),
                default_tags=data.get("default_tags", "")
            )
            update_game_playlists(game_id, data.get("playlists", {}))
            
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
        
        game_name = self.game_selector.currentText().replace(" (S)", "") # Убираем маркер для сравнения
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        game_folder = game_data['path']
        
        unpublished_shorts = check_unpublished_shorts(game_id)

        # Создаем кастомный диалог прямо здесь
        dialog = QDialog(self)
        dialog.setWindowTitle(_("title_delete_game"))
        layout = QVBoxLayout(dialog)

        msg = (f"<b>{_('lbl_warnin')}</b> {_('msg_delete_warning_1')}<br>"
               f"- <b>{_('msg_delete_warning_2')}</b><br><br>"
               f"{_('msg_delete_warning_3')} <i>{game_name}</i>")
               
        if unpublished_shorts > 0:
            msg += f"<br><br><span style='color:#c0392b;'><b>{_('msg_found')} {unpublished_shorts} {_('msg_unpublished_shorts')}!</b></span>"

        info_label = QLabel(msg)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        name_input = QLineEdit()
        layout.addWidget(name_input)

        keep_shorts_cb = QCheckBox(_("lbl_stay_game_only_for_shorts"))
        keep_shorts_cb.setChecked(unpublished_shorts > 0)
        if unpublished_shorts == 0:
            keep_shorts_cb.hide() # Прячем галочку, если шортсов нет
        layout.addWidget(keep_shorts_cb)

        btn_layout = QHBoxLayout()
        del_btn = QPushButton(_("btn_delete"))
        del_btn.setStyleSheet("background-color: lightcoral;")
        del_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton(_("btn_cancel"))
        cancel_btn.clicked.connect(dialog.reject)

        btn_layout.addWidget(del_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            if name_input.text().strip() == game_name:
                keep_shorts = keep_shorts_cb.isChecked()
                
                if keep_shorts and unpublished_shorts > 0:
                    # ЧАСТИЧНОЕ УДАЛЕНИЕ (Архивация)
                    episodes = get_episodes(game_id)
                    for ep in episodes:
                        ep_id, ep_number = ep[0], ep[1]
                        ep_folder = os.path.join(game_folder, f"ep{ep_number}")
                        
                        if os.path.exists(ep_folder):
                            # Удаляем всё, КРОМЕ папки shorts
                            for item in os.listdir(ep_folder):
                                if item.lower() != "shorts":
                                    item_path = os.path.join(ep_folder, item)
                                    try:
                                        if os.path.isdir(item_path):
                                            shutil.rmtree(item_path)
                                        else:
                                            os.remove(item_path)
                                    except Exception as e:
                                        logging.error(f"{_('msg_cant_delete')} {item_path}: {e}")
                            
                            # Помечаем эпизод как удаленный в БД
                            mark_episode_deleted(ep_id)
                            
                    QMessageBox.information(self, _("msg_title_success"), f"{_('msg_source_deleted_shorts_saved')}\n{_('msg_game_moved_to_archive')}")
                else:
                    # ПОЛНОЕ УДАЛЕНИЕ
                    if os.path.exists(game_folder):
                        try:
                            shutil.rmtree(game_folder)
                            logging.info(f"{_('msg_game_folder_deleted')}: {game_folder}")
                        except Exception as e:
                            QMessageBox.critical(self, _("msg_title_error"), f"{_('msg_cant_delete_folder_from_disk')}\n{_('msg_check_files_may_be_open')}\n\n{e}")
                            return 
                    
                    delete_game_full(game_id)
                    logging.info(f"{_('msg_game')} '{game_name}' {_('msg_game_deleted_from_DB')}")
                    QMessageBox.information(self, _("msg_title_success"), f"{_('msg_game')} '{game_name}' {_('msg_game_deleted_full')}")
                
                self.load_games()
            else:
                QMessageBox.warning(self, _('msg_cancel'), _('msg_name_error_game_not_delete'))

    def open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def show_update_notification(self, latest_version, url):
        reply = QMessageBox.information(
            self, 
            _('msg_update_avaliable'), 
            f"{_('msg_update_new_version_release')} LetsPlayManager: <b>v{latest_version}</b>\n\n"
            f"{_('msg_update_current_version')}: v{APP_VERSION}\n\n"
            f"{_('msg_update_want_to_update')}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            webbrowser.open(url)

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
        game_name = self.game_selector.currentText() # <-- Название игры для шаблона заголовка
        ep_number = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)
        ep_folder = os.path.join(game_data['path'], f"ep{ep_number}")

        menu = QMenu(self)
        
        # --- НОВЫЙ ПУНКТ МЕНЮ ---
        meta_action = menu.addAction(f"📝 {_('menu_meta_templates')}")
        # Добавляем действие копирования названия
        copy_title_action = menu.addAction(f"📋 {_('menu_copy_title', 'Копировать название')}")
        copy_menu = menu.addMenu(f"📋 {_('menu_copy_desc_for')}")
        hostings = get_videohostings()
        
        copy_actions = {}
        for h_id, h_key, h_name in hostings:
            action = copy_menu.addAction(h_name)
            copy_actions[action] = h_key # Связываем QAction с ключом хостинга (youtube, rutube и тд)
            
        menu.addSeparator()
        
        refresh_action = menu.addAction(f"🔄 {_('menu_refresh_video_data')}")
        date_action = menu.addAction(f"📅 {_('menu_change_publish_date')}")
        cut_shorts_action = menu.addAction(f"✂️ {_('menu_cut_shorts')}")
        menu.addSeparator() # Разделитель для безопасности
        delete_action = menu.addAction(f"🗑️ {_('menu_delete_episode_folder')}")
        
        # Показываем меню ровно в месте клика
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        # Обработчики действий
        if action == meta_action:
            self.open_metadata_dialog(ep_id, ep_number)
            logging.info(f"Метаданные для эпизода {ep_number} успешно сохранены в БД.")
        elif action == copy_title_action: # <-- Обработка копирования названия
            self.copy_title_to_clipboard(ep_id, game_name, ep_number)
        elif action in copy_actions:
            hosting_key = copy_actions[action]
            self.copy_desc_to_clipboard(ep_id, hosting_key, game_name, ep_number, game_data)
        elif action == refresh_action:
            self.refresh_episode_data(ep_id, ep_folder)
        elif action == date_action:
            self.edit_publish_date(ep_id, row)
        elif action == cut_shorts_action:
            self.open_shorts_cutter(ep_folder)
        elif action == delete_action:
            self.delete_episode_folder(ep_id, ep_folder)

    def open_shorts_cutter(self, ep_folder):
        if not os.path.exists(ep_folder):
            QMessageBox.warning(self, _("msg_title_error"), _("msg_ep_folder_not_found"))
            return
            
        video_file = None
        for file in os.listdir(ep_folder):
            if file.endswith(('.mkv', '.mp4')):
                video_file = os.path.join(ep_folder, file)
                if file.endswith('.mp4'): break
                
        if video_file:
            dialog = ShortsCutterDialog(self, video_file)
            dialog.exec()
            self.update_table()
        else:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_source_video_not_found"))
    
    def refresh_episode_data(self, ep_id, ep_folder):
        if not os.path.exists(ep_folder):
            QMessageBox.warning(self, _("msg_title_error"), _("msg_ep_folder_not_found"))
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
            QMessageBox.information(self, _("msg_title_done"), f"{_('msg_data_updated')}\n{_('col_size')}: {size_text}\n{_('col_time')}: {duration_text}")
        else:
            QMessageBox.warning(self, _("msg_title_error"), _("msg_source_video_not_found"))

    def edit_publish_date(self, ep_id, row):
        current_date = self.table.item(row, 6).text()
        dialog = CalendarDialog(self, current_date)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_episode_publish_date(ep_id, dialog.selected_date_str)
            self.update_table()

    def delete_episode_folder(self, ep_id, ep_folder):
        # Проверяем, существует ли папка вообще
        if not os.path.exists(ep_folder):
            QMessageBox.information(self, _('msg_title_info'), _("msg_folder_already_deleted"))
            mark_episode_deleted(ep_id)
            self.update_table()
            return

        # Запрашиваем подтверждение
        reply = QMessageBox.question(
            self, _("title_confirm_clear"), 
            f"{_('msg_confirm_delete_folder')}:\n{ep_folder}\n{_('msg_confirm_delete_folder_2')}\n\n{_('msg_delete_folder_warning')}", 
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                shutil.rmtree(ep_folder) # Безвозвратно удаляем папку со всем содержимым
                mark_episode_deleted(ep_id) # Обновляем БД
                self.update_table() # Перерисовываем таблицу (строка станет голубой)
                QMessageBox.information(self, _("msg_title_success"), _("msg_folder_deleted_success"))
            except Exception as e:
                QMessageBox.critical(self, _("msg_title_error"), f"{_('msg_folder_delete_error')}:\n{e}")

    def open_url_dialog(self, ep_id, host_id, host_name):
        current_url = get_upload_url(ep_id, host_id)
        new_url, ok = QInputDialog.getText(
            self, f"{_('lbl_link')}: {host_name}",
            _('msg_enter_published_link'),
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
            self.config["notepad_path"] = dialog.text_editor_input.text()
            self.config["gimp_path"] = dialog.gimp_input.text()
            self.config["desc_name"] = dialog.desc_input.text()
            self.config["preview_name"] = dialog.prev_input.text()
            self.config["default_codec"] = dialog.codec_combo.currentData()
            
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
            cmd = [get_tool_path('ffmpeg'), '-y', '-i', input_file, 
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
            
            # Читаем индекс выбранного режима (0, 1 или 2)
            process_mode = dialog.process_mode_combo.currentIndex()

            # Определяем исходное расширение
            ignored, ext = os.path.splitext(input_file)
            ext_lower = ext.lower()

            # --- АВТОМАТИЧЕСКАЯ ЗАЩИТА ---
            # Если исходник MKV, а выбрано простое перемещение, принудительно ставим Remux
            if ext_lower == '.mkv' and process_mode == 0:
                process_mode = 1 
            # ------------------------------
            
            # ПРИНУДИТЕЛЬНО МЕНЯЕМ РАСШИРЕНИЕ ДО ГЕНЕРАЦИИ ИМЕНИ ФАЙЛА
            if process_mode > 0:
                ext = '.mp4'
            
            # Формируем папку и выходной файл уже с правильным расширением (.mp4 или исходным)
            ep_folder = os.path.join(base_folder, f"ep{ep_number}")
            os.makedirs(ep_folder, exist_ok=True)
            
            out_filename = f"{game_name} - Ep.{ep_number}{ext}"
            output_file = os.path.join(ep_folder, out_filename)

            if process_mode > 0:
                # Базовый Remux (смена контейнера на лету)
                if process_mode == 1:
                    cmd = [get_tool_path('ffmpeg'), '-y', '-i', input_file, '-c', 'copy', output_file]
                
                elif process_mode == 2:
                    # Читаем выбранный кодек из конфига (по умолчанию обычный процессорный H.264)
                    codec_choice = self.config.get("default_codec", "h264_cpu")
                    
                    # Словарь с настройками под каждый энкодер
                    encoders = {
                        "h264_cpu":   ['-c:v', 'libx264', '-preset', 'fast'],
                        "h264_nvenc": ['-c:v', 'h264_nvenc', '-preset', 'fast'],
                        "h264_amf":   ['-c:v', 'h264_amf', '-quality', 'speed'],
                        "hevc_nvenc": ['-c:v', 'hevc_nvenc', '-preset', 'fast'],
                        "hevc_amf":   ['-c:v', 'hevc_amf', '-quality', 'speed']
                    }
                    
                    # Получаем нужные флаги (с fallback на базовый h264, если что-то пошло не так)
                    video_flags = encoders.get(codec_choice, encoders["h264_cpu"])

                    # Собираем финальную команду
                    cmd = [get_tool_path('ffmpeg'), '-y', '-i', input_file]
                    cmd.extend(video_flags)
                    cmd.extend([
                        '-b:v', '30M',       
                        '-g', '30',          
                        '-c:a', 'aac', '-b:a', '320k', 
                        output_file
                    ])

                self.worker = FFmpegWorker(cmd)
                self.progress_dialog = ProgressDialog(self)
                self.worker.progress.connect(self.progress_dialog.append_log)
                self.worker.finished.connect(self.on_ffmpeg_finished)
                
                self.worker.start()
                self.progress_dialog.exec()
            else:
                # Только перемещение
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
                
                self.update_table()

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
        
        # Распаковываем все 8 полей, которые теперь возвращает get_games()
        for game_id, name, folder_path, ai_url, steam_id, desc_template, default_tags in games:
            display_name = name
            
            # Умная проверка: если исходников нет, но есть шортсы, ставим маркер (S)
            if is_game_archived(game_id) and check_unpublished_shorts(game_id) > 0:
                display_name = f"{name} (S)"

            playlists = get_game_playlists(game_id)
                
            # Добавляем новые текстовые шаблоны в словарь userData
            self.game_selector.addItem(display_name, userData={
                'id': game_id, 
                'path': folder_path, 
                'ai_url': ai_url, 
                'steam_id': steam_id,
                'desc_template': desc_template,
                'default_tags': default_tags,
                'playlists': playlists # Передаем словарь в userData
            })
            
        self.game_selector.blockSignals(False)
        
        if self.game_selector.count() > 0:
            self.update_table()

    # Функция добавления новой игры
    def add_new_game(self):
        # Если импорт GameDialog у тебя в начале файла, эту строку можно опустить
        from gui.dialogs.game_dialog import GameDialog 
        
        dialog = GameDialog(self, self.config)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # --- ИСПОЛЬЗУЕМ НОВЫЙ МЕТОД СБОРА ДАННЫХ ---
            data = dialog.get_data()
            
            name = data.get("name", "")
            folder = data.get("folder", "")
            ai_url = data.get("ai_url", "")
            steam_id = data.get("steam_id", "")
            
            # Извлекаем новые метаданные
            desc_template = data.get("desc_template", "")
            default_tags = data.get("default_tags", "")
            
            
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
            
            # --- Скачиваем капсулу через Steam API ---
            if steam_id:
                import requests
                api_url = f"https://store.steampowered.com/api/appdetails?appids={steam_id}"
                try:
                    # Сначала получаем JSON от Steam
                    response = requests.get(api_url, timeout=5).json()
                    
                    # Проверяем, что игра найдена и запрос успешен
                    if response and str(steam_id) in response and response[str(steam_id)].get("success"):
                        # Достаем актуальную ссылку на картинку
                        img_url = response[str(steam_id)]["data"]["header_image"]
                        
                        # Скачиваем саму картинку
                        img_resp = requests.get(img_url, timeout=5)
                        if img_resp.status_code == 200:
                            img_path = os.path.join(folder, "steam_capsule.jpg")
                            with open(img_path, 'wb') as f:
                                f.write(img_resp.content)
                            logging.info(f"Обложка Steam успешно скачана через API: {img_path}")
                    else:
                        logging.warning(f"Steam API не нашел игру с ID {steam_id}")
                except Exception as e:
                    logging.error(f"Ошибка при работе со Steam API: {e}")
            
            # Сохраняем в БД с новыми параметрами шаблонов
            new_game_id = add_game(
                name=name, 
                folder_path=folder, 
                ai_url=ai_url, 
                steam_id=steam_id,
                desc_template=data.get("desc_template", ""),
                default_tags=data.get("default_tags", "")
            ) 

            update_game_playlists(new_game_id, data.get("playlists", {}))
            
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

        # --- БЛОКИРОВКА АРХИВОВ ---
        if is_game_archived(game_id):
            self.add_episode_btn.setEnabled(False)
            self.add_episode_btn.setToolTip(_("tooltip_game_archived"))
        else:
            self.add_episode_btn.setEnabled(True)
            self.add_episode_btn.setToolTip("")
        # --

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
                    size_text = _("lbl_no_file")
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
                # Меняем дефолтное имя на notes.txt
                notes_name = self.config.get("desc_name", "notes.txt") 
                prev_name = self.config.get("preview_name", "preview.jpg")
                
                notes_path = os.path.join(ep_folder, notes_name)
                prev_path = os.path.join(ep_folder, prev_name)

                # Получаем метаданные из БД для проверки
                from database import get_episode_metadata
                ep_meta = get_episode_metadata(ep_id)
                has_desc = bool(ep_meta[1].strip()) # Проверяем, не пустое ли поле custom_desc

                # Контейнер для ячейки
                desc_widget = QWidget()
                desc_layout = QHBoxLayout(desc_widget)
                desc_layout.setContentsMargins(2, 2, 2, 2)
                desc_layout.setSpacing(5)

                # Кнопка 1: Метаданные (БД)
                btn_meta = QPushButton("📝")
                btn_meta.setToolTip(f"{_('tooltip_description')} (БД)")
                btn_meta.setFixedWidth(35)
                btn_meta.clicked.connect(lambda ch, eid=ep_id, enum=ep_number: self.open_metadata_dialog(eid, enum))

                # Кнопка 2: Заметки (Файл)
                btn_notes = QPushButton("🗒")
                btn_notes.setToolTip(f"{_('tooltip_description')} ({notes_name})")
                btn_notes.setFixedWidth(35)
                # Оставляем вызов старого метода open_notepad
                btn_notes.clicked.connect(lambda checked, p=notes_path: self.open_notepad(p))

                desc_layout.addWidget(btn_meta)
                desc_layout.addWidget(btn_notes)
                desc_layout.addStretch() # Сдвигаем кнопки влево

                # Индикация: светло-зеленый (описание есть), светло-красный (пусто)
                bg_color = "lightgreen" if has_desc else "lightcoral"
                desc_widget.setStyleSheet(f"""
                    QWidget {{ background-color: {bg_color}; }} 
                    QPushButton {{ background-color: white; font-size: 14px; border: 1px solid #ccc; border-radius: 3px; }}
                    QPushButton:hover {{ background-color: #f0f0f0; }}
                """)

                self.table.setCellWidget(row_idx, 4, desc_widget)

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

                pub_item = QTableWidgetItem(pub_date if pub_date else _("lbl_not_set"))
                if not folder_exists:
                    pub_item.setBackground(QColor("#add8e6"))
                self.table.setItem(row_idx, 6, pub_item)

                # --- КОЛОНКА ШОРТСОВ ---
                shorts_btn = QPushButton()
                if shorts_count > 0:
                    shorts_btn.setText(f"{_('lbl_shorts_count')}: {shorts_count}")
                    shorts_btn.setStyleSheet("background-color: #90ee90; color: black;") # Зеленый индикатор
                else:
                    shorts_btn.setText(f"+ {_('btn_add')}")
                
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
                [get_tool_path('ffprobe'), '-v', 'error', '-show_entries', 
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
        
    def open_shorts_manager(self, ep_id=None, ep_number=None):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_data = self.game_selector.itemData(current_index)
        
        # Перехватываем вызов из верхнего меню
        if isinstance(ep_id, bool) or ep_id is None:
            # Передаем ID текущей игры в диалог
            dialog = SelectEpisodeDialog(self, game_data['id'])
            if dialog.exec() == QDialog.DialogCode.Accepted:
                ep_id = dialog.selected_ep_id
                ep_number = dialog.selected_ep_number
            else:
                return # Отмена
                
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
        
        # Когда окно закроется, обновляем главную таблицу
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

    def open_profile_settings(self):
        # Нам нужен экземпляр ProfileManager для передачи в диалог
        dialog = ProfileSettingsDialog(self, self.pm)
        dialog.exec()

    def open_metadata_dialog(self, ep_id, ep_number):
        current_index = self.game_selector.currentIndex()
        if current_index == -1: return
        
        game_data = self.game_selector.itemData(current_index)
        game_name = self.game_selector.currentText()
        
        from gui.dialogs.episode_metadata_dialog import EpisodeMetadataDialog
        from database import get_episode_metadata, update_episode_metadata_full, get_videohostings
        
        ep_meta = get_episode_metadata(ep_id)
        active_profile_id = self.pm.data.get("last_used_profile", "default")
        profile_data = self.pm.data["profiles"].get(active_profile_id, {})
        
        raw_hostings = get_videohostings()
        hostings_list = [(h[1], h[2]) for h in raw_hostings]

        dialog = EpisodeMetadataDialog(
            self, 
            game_name=game_name, 
            ep_number=ep_number,
            game_data=game_data,
            profile_data=profile_data,
            episode_data=ep_meta,
            hostings=hostings_list
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            update_episode_metadata_full(
                ep_id, 
                data["custom_title"], 
                data["custom_desc"], 
                data["timecodes"], 
                data["custom_tags"]
            )
            # Перерисовываем таблицу, чтобы цвет ячейки мгновенно поменялся на зеленый
            self.update_table()
    
    def copy_desc_to_clipboard(self, ep_id, hosting_key, game_name, ep_number, game_data):
        from database import get_episode_metadata
        ep_meta = get_episode_metadata(ep_id)
        title, desc, timecodes, ep_tags = ep_meta
        
        # Получаем данные профиля
        active_profile_id = self.pm.data.get("last_used_profile", "default")
        profile_data = self.pm.data["profiles"].get(active_profile_id, {})
        
        # Получаем шаблоны игры
        game_desc = game_data.get("desc_template", "")
        game_tags = game_data.get("default_tags", "")
        
        # Получаем плейлист ИМЕННО для выбранного хостинга
        playlists = game_data.get("playlists", {})
        game_playlist = playlists.get(hosting_key, "")
        
        profile_links = profile_data.get("channel_links", "")
        profile_cta = profile_data.get("global_desc", "")
        
        # Склейка тегов
        all_tags = [t.strip() for t in f"{game_tags} {ep_tags}".replace(',', ' ').split() if t.strip()]
        unique_tags = " ".join(list(dict.fromkeys(all_tags))) 
        
        # Сборка финального текста
        parts = []
        if desc: parts.append(desc)
        if game_desc: parts.append(game_desc)
        if timecodes: parts.append(f"⏱️ {_('lbl_timecodes')}\n{timecodes}")
        
        links_part = []
        if game_playlist: links_part.append(f"{_('lbl_playlist')}: {game_playlist}")
        if profile_links: links_part.append(profile_links)
        if links_part: parts.append(f"🔗 {_('lbl_links')}:\n" + "\n".join(links_part))
        
        if profile_cta: parts.append(profile_cta)
        if unique_tags: parts.append(unique_tags)
        
        text_to_copy = "\n\n".join(parts)
        
        # Отправляем в буфер обмена
        QApplication.clipboard().setText(text_to_copy.strip())
        import logging
        logging.info(f"Описание для '{hosting_key}' успешно скопировано в буфер обмена.")

    def copy_title_to_clipboard(self, ep_id, game_name, ep_number):
        from database import get_episode_metadata
        ep_meta = get_episode_metadata(ep_id)
        
        # Безопасное извлечение названия (если данных еще нет)
        ep_title = ep_meta[0] if ep_meta else ""
        
        if ep_title:
            full_title = f"{ep_title} | {game_name} ({_('lbl_episode')} {ep_number})"
        else:
            full_title = f"{game_name} | {_('lbl_walkthrough', 'Прохождение')} ({_('lbl_episode')} {ep_number})"
            
        QApplication.clipboard().setText(full_title)
        
        import logging
        logging.info(f"Название эпизода {ep_number} успешно скопировано в буфер обмена.")

    def center_on_screen(self):
        screen = QApplication.primaryScreen()
        if screen:
            qr = self.frameGeometry()
            cp = screen.availableGeometry().center()
            qr.moveCenter(cp)
            self.move(qr.topLeft())