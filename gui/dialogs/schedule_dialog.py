import os
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QPushButton, QLabel)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont

from core.config import _
from database import (get_all_episodes_for_schedule, get_all_shorts_for_schedule, 
                      update_episode_publish_date, update_short_field, get_episode_metadata)
from gui.dialogs.calendar_dialog import CalendarDialog

class ScheduleDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle(_("title_schedule_dialog"))
        self.resize(750, 500)
        self.config = config
        
        layout = QVBoxLayout(self)
        
        # Инструкция для пользователя
        help_lbl = QLabel(f"<i>{_('lbl_schedule_help')}</i>")
        layout.addWidget(help_lbl)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([_("col_game"), _("col_episode_short"), _("col_publish_date"), _("col_readiness")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        # --- НОВЫЕ СТРОКИ ---
        # Выделяем сразу всю строку целиком, а не одну ячейку
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        # Отслеживаем обычный клик для массового выделения
        self.table.cellClicked.connect(self.on_cell_clicked)
        # --------------------
        
        # Подключаем двойной клик для редактирования даты
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        
        layout.addWidget(self.table)
        
        close_btn = QPushButton(_("btn_close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.load_data()
        
    def load_data(self):
        episodes = get_all_episodes_for_schedule()
        shorts = get_all_shorts_for_schedule()
        
        prev_name = self.config.get("preview_name", "preview.jpg")
        
        combined_list = []
        
        # Обработка эпизодов
        for ep_id, game_name, folder_path, ep_num, title, pub_date in episodes:
            ep_folder = os.path.join(folder_path, f"ep{ep_num}")
            prev_path = os.path.join(ep_folder, prev_name)
            
            # Получаем метаданные из БД вместо файла
            ep_meta = get_episode_metadata(ep_id)
            has_desc = bool(ep_meta[1].strip()) # Индекс 1 отвечает за описание эпизода
            
            # Превью по-прежнему проверяем как файл на диске
            has_prev = os.path.exists(prev_path) and os.path.getsize(prev_path) > 1024
            
            is_ready = "✅" if (has_desc and has_prev) else "❌"
            display_title = f"Ep. {ep_num} {title}".strip()
            
            combined_list.append({
                "type": "episode",
                "id": ep_id,
                "game": game_name,
                "title": display_title,
                "date_str": pub_date,
                "ready": is_ready
            })
            
        # Обработка шортсов
        for short_id, game_name, ep_num, short_num, custom_title, pub_date in shorts:
            display_title = f"Ep. {ep_num} - " + (custom_title if custom_title else f"Shorts {short_num}")
            
            combined_list.append({
                "type": "short",
                "id": short_id,
                "game": game_name,
                "title": display_title,
                "date_str": pub_date,
                "ready": "-" 
            })
            
        # Сортировка: пустые даты кидаем в самый верх (минимальное время)
        def parse_date(item):
            if not item["date_str"]:
                return datetime.min
            try:
                return datetime.strptime(item["date_str"], "%d.%m.%Y")
            except ValueError:
                return datetime.min
                
        combined_list.sort(key=parse_date)
        
        # Заполнение таблицы
        self.table.setRowCount(len(combined_list))
        # Получаем сегодняшнюю дату (только день, без времени)
        today = datetime.now().date()
        
        # Заполнение таблицы
        self.table.setRowCount(len(combined_list))
        for row, item in enumerate(combined_list):
            
            # 1. Создаем элементы ячеек
            game_item = QTableWidgetItem(item["game"])
            title_item = QTableWidgetItem(item["title"])
            
            display_date = item["date_str"] if item["date_str"] else "Не задана"
            date_item = QTableWidgetItem(display_date)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            date_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            date_item.setData(Qt.ItemDataRole.UserRole + 1, item["type"])
            
            ready_item = QTableWidgetItem(item["ready"])
            ready_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # 2. Логика раскраски и шрифтов
            if item["date_str"]:
                try:
                    # Парсим дату публикации
                    pub_date = datetime.strptime(item["date_str"], "%d.%m.%Y").date()
                    
                    # Проходимся по всем ячейкам текущей строки, чтобы применить стиль
                    for cell_item in (game_item, title_item, date_item, ready_item):
                        if pub_date < today:
                            # Прошлое — Голубой
                            cell_item.setBackground(QColor("#add8e6"))
                        elif pub_date > today:
                            # Будущее — Желтый (светло-желтый для читаемости)
                            cell_item.setBackground(QColor("#ffffe0"))
                        elif pub_date == today:
                            # Сегодня — Жирный шрифт
                            font = cell_item.font()
                            font.setBold(True)
                            cell_item.setFont(font)
                            # Можно добавить легкий зеленый фон для сегодня, если захочешь:
                            # cell_item.setBackground(QColor("#e0ffe0"))
                            
                except ValueError:
                    pass # На случай сбоя парсинга оставляем ячейки стандартными
            else:
                # Если дата не задана — красим саму надпись в серый
                date_item.setForeground(Qt.GlobalColor.gray)
                
            # 3. Вставляем элементы в таблицу
            self.table.setItem(row, 0, game_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, date_item)
            self.table.setItem(row, 3, ready_item)

    def on_cell_clicked(self, row, column):
        # Если кликнули по первому столбцу (Название игры)
        if column == 0:
            target_game = self.table.item(row, 0).text()
            
            # Временно блокируем сигналы, чтобы выделение не вызывало лишних срабатываний
            self.table.blockSignals(True)
            self.table.clearSelection()
            
            # Проходим по всем строкам и ищем совпадения
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).text() == target_game:
                    # Программно выделяем все ячейки в подходящей строке
                    for c in range(self.table.columnCount()):
                        item = self.table.item(r, c)
                        if item:
                            item.setSelected(True)
                            
            self.table.blockSignals(False)

    def on_cell_double_clicked(self, row, column):
        # Реагируем только на клик по столбцу с датой (индекс 2)
        if column == 2:
            item = self.table.item(row, column)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            
            current_date = item.text()
            if current_date == _("lbl_not_set"):
                current_date = ""

            dialog = CalendarDialog(self, current_date)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_date = dialog.selected_date_str
                
                # Обновляем в базе данных
                if item_type == "episode":
                    update_episode_publish_date(item_id, new_date)
                elif item_type == "short":
                    update_short_field(item_id, 'publish_date', new_date)
                
                # Перезагружаем календарь
                self.load_data()
                
                # Обновляем главную таблицу под окном, чтобы там тоже появилась дата
                if hasattr(self.parent(), "update_table"):
                    self.parent().update_table()