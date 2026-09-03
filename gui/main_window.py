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
                             QLineEdit, QMessageBox, QMenu, QDialog, QCheckBox)
from PyQt6.QtGui import QColor

# --- НАШИ МОДУЛИ ---
from core.config import _, load_config, save_config, load_language, APP_VERSION
from core.ffmpeg_worker import FFmpegWorker, get_tool_path
from core.update_checker import UpdateCheckerThread

from database import (add_game, get_games, add_episode_if_not_exists, 
                      get_episodes, get_uploads, toggle_upload, update_episode_metadata,
                      get_videohostings, update_episode_title, get_upload_url,
                      update_game_ai_url, update_episode_publish_date, update_upload_url, 
                      mark_episode_deleted, delete_game_full, update_game, check_unpublished_shorts,
                      is_game_archived)

# --- ОКНА (ДИАЛОГИ) ---
from gui.dialogs.settings_dialog import SettingsDialog
from gui.dialogs.about_dialog import AboutDialog
from gui.dialogs.progress_dialog import ProgressDialog
from gui.dialogs.calendar_dialog import CalendarDialog
from gui.dialogs.add_game_dialog import AddGameDialog
from gui.dialogs.edit_game_dialog import EditGameDialog
from gui.dialogs.add_episode_dialog import AddEpisodeDialog
from gui.dialogs.compress_dialog import CompressDialog
from gui.shorts_manager import ShortsManagerDialog
from gui.dialogs.shorts_cutter_dialog import ShortsCutterDialog
from gui.dialogs.schedule_dialog import ScheduleDialog

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

        self.schedule_btn = QPushButton("📅 Календарь публикаций") # <--- НОВАЯ КНОПКА
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
            QMessageBox.information(self, "Настройка", "Пожалуйста, укажите базовые папки для записей и рендеров.")
            self.open_settings()

        # --- ПРОВЕРКА ОБНОВЛЕНИЙ ---
        self.update_checker = UpdateCheckerThread()
        self.update_checker.update_available.connect(self.show_update_notification)
        self.update_checker.start()

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
        
        game_name = self.game_selector.currentText().replace(" (S)", "") # Убираем маркер для сравнения
        game_data = self.game_selector.itemData(current_index)
        game_id = game_data['id']
        game_folder = game_data['path']
        
        unpublished_shorts = check_unpublished_shorts(game_id)

        # Создаем кастомный диалог прямо здесь
        dialog = QDialog(self)
        dialog.setWindowTitle("Удаление игры")
        layout = QVBoxLayout(dialog)

        msg = (f"<b>ВНИМАНИЕ!</b> Это действие удалит:<br>"
               f"- <b>Папки с исходниками эпизодов на диске</b><br><br>"
               f"Для подтверждения введите точное название игры: <i>{game_name}</i>")
               
        if unpublished_shorts > 0:
            msg += f"<br><br><span style='color:#c0392b;'><b>Найдено {unpublished_shorts} неопубликованных шортсов!</b></span>"

        info_label = QLabel(msg)
        info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(info_label)

        name_input = QLineEdit()
        layout.addWidget(name_input)

        keep_shorts_cb = QCheckBox("Оставить игру в менеджере ради шортсов (удалить только исходники)")
        keep_shorts_cb.setChecked(unpublished_shorts > 0)
        if unpublished_shorts == 0:
            keep_shorts_cb.hide() # Прячем галочку, если шортсов нет
        layout.addWidget(keep_shorts_cb)

        btn_layout = QHBoxLayout()
        del_btn = QPushButton("Удалить")
        del_btn.setStyleSheet("background-color: lightcoral;")
        del_btn.clicked.connect(dialog.accept)
        cancel_btn = QPushButton("Отмена")
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
                                        logging.error(f"Не удалось удалить {item_path}: {e}")
                            
                            # Помечаем эпизод как удаленный в БД
                            mark_episode_deleted(ep_id)
                            
                    QMessageBox.information(self, "Успех", "Исходники эпизодов удалены, шортсы сохранены.\nИгра переведена в режим архива.")
                else:
                    # ПОЛНОЕ УДАЛЕНИЕ
                    if os.path.exists(game_folder):
                        try:
                            shutil.rmtree(game_folder)
                            logging.info(f"Папка игры удалена: {game_folder}")
                        except Exception as e:
                            QMessageBox.critical(self, "Ошибка", f"Не удалось удалить папку с диска.\nУбедитесь, что файлы не открыты.\n\n{e}")
                            return 
                    
                    delete_game_full(game_id)
                    logging.info(f"Игра '{game_name}' удалена из БД.")
                    QMessageBox.information(self, "Успех", f"Игра '{game_name}' полностью удалена!")
                
                self.load_games()
            else:
                QMessageBox.warning(self, "Отмена", "Название введено неверно. Удаление отменено.")

    def open_about(self):
        dialog = AboutDialog(self)
        dialog.exec()

    def show_update_notification(self, latest_version, url):
        reply = QMessageBox.information(
            self, 
            "Доступно обновление", 
            f"Вышла новая версия LetsPlayManager: <b>v{latest_version}</b>\n\n"
            f"Текущая версия: v{APP_VERSION}\n\n"
            f"Хотите перейти на GitHub для скачивания?",
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
        ep_number = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole + 2)
        ep_folder = os.path.join(game_data['path'], f"ep{ep_number}")

        menu = QMenu(self)
        refresh_action = menu.addAction("🔄 Обновить данные видеофайла")
        date_action = menu.addAction("📅 Изменить дату публикации")
        cut_shorts_action = menu.addAction("✂️ Нарезать на шортсы")
        menu.addSeparator() # Разделитель для безопасности
        delete_action = menu.addAction("🗑️ Удалить папку эпизода (Очистка)") # <--- НОВАЯ КНОПКА
        
        # Показываем меню ровно в месте клика
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        
        if action == refresh_action:
            self.refresh_episode_data(ep_id, ep_folder)
        elif action == date_action:
            self.edit_publish_date(ep_id, row)
        elif action == cut_shorts_action:
            self.open_shorts_cutter(ep_folder)
        elif action == delete_action:
            self.delete_episode_folder(ep_id, ep_folder)

    def open_shorts_cutter(self, ep_folder):
        if not os.path.exists(ep_folder):
            QMessageBox.warning(self, "Ошибка", "Папка эпизода не найдена.")
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
            QMessageBox.warning(self, "Ошибка", "Исходное видео не найдено в папке эпизода.")
    
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
                cmd = [get_tool_path('ffmpeg'), '-y', '-i', input_file, '-c', 'copy', output_file]
                
                # Быстрый транскод под монтажку с помощью AMF (AMD)
                # Фиксируем GOP (-g 30) для плавного скраббинга на таймлайне
                #cmd = [
                #    get_tool_path('ffmpeg'), '-y', '-i', input_file, 
                #    '-c:v', 'hevc_amf', # Используем аппаратный HEVC
                #    '-quality', 'speed', # Приоритет скорости
                #    '-b:v', '30M',       # Сохраняем твои исходные 30 Mbps
                #    '-g', '30',          # Ключевой кадр каждую секунду (идеально для Вегаса)
                #    '-c:a', 'aac', '-b:a', '320k', 
                #    output_file
                #]

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
        for game_id, name, folder_path, ai_url, steam_id in games:
            display_name = name
            
            # Умная проверка: если исходников нет, но есть шортсы, ставим маркер (S)
            if is_game_archived(game_id) and check_unpublished_shorts(game_id) > 0:
                display_name = f"{name} (S)"
                
            self.game_selector.addItem(display_name, userData={'id': game_id, 'path': folder_path, 'ai_url': ai_url, 'steam_id': steam_id})
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

        # --- БЛОКИРОВКА АРХИВОВ ---
        if is_game_archived(game_id):
            self.add_episode_btn.setEnabled(False)
            self.add_episode_btn.setToolTip("Игра в архиве. Добавление новых эпизодов недоступно.")
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
