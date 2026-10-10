import os
from datetime import datetime
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QPushButton, QLabel, QCalendarWidget, QHBoxLayout)
from PyQt6.QtCore import Qt, QDate, QItemSelectionModel
from PyQt6.QtGui import QTextCharFormat, QFont, QPen, QColor

from core.config import _, get_color
from database import (get_all_episodes_for_schedule, get_all_shorts_for_schedule, 
                      update_episode_publish_date, update_short_field, get_episode_metadata)
from gui.dialogs.calendar_dialog import CalendarDialog
from gui.dialogs.assign_episode_dialog import AssignEpisodeDialog


def _parse_schedule_date(item):
    """Сортировка: элементы без даты уходят в самый верх списка."""
    date_str = item.get("date_str")
    if not date_str:
        return datetime.min
    try:
        return datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        return datetime.min


class ScheduleDialog(QDialog):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.setWindowTitle(_("title_schedule_dialog"))
        self.resize(1180, 520)
        self.config = config
        self.unassigned_items = []
        
        layout = QVBoxLayout(self)
        
        help_lbl = QLabel(f"<i>{_('lbl_schedule_help')}</i>")
        layout.addWidget(help_lbl)
        
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            _("col_game"), 
            _("col_episode_short"), 
            _("col_publish_date"), 
            _("col_readiness")
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.selected_game_name = None
        self.cached_items = []
        
        table_and_calendar_layout = QHBoxLayout()
        table_and_calendar_layout.addWidget(self.table, stretch=1)
        
        self.reference_calendar = QCalendarWidget()
        self.reference_calendar.setGridVisible(True)
        self.reference_calendar.setFixedWidth(340)
        self.reference_calendar.setSelectionMode(QCalendarWidget.SelectionMode.SingleSelection)
        self.reference_calendar.activated.connect(self.on_calendar_date_activated)
        
        table_and_calendar_layout.addWidget(self.reference_calendar, stretch=0)
        layout.addLayout(table_and_calendar_layout)
        
        close_btn = QPushButton(_("btn_close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.load_data()

    def update_calendar_highlights(self, items):
        """Подсветка календаря: шортсы не триггерят красный статус, проверяются только серии."""
        self.reference_calendar.setDateTextFormat(QDate(), QTextCharFormat())
        
        current_theme = self.config.get("theme", "dark")
        color_ready = get_color("cal_ready", current_theme)
        color_not_ready = get_color("cal_not_ready", current_theme)
        
        episodes_by_date = {}
        dates_with_only_shorts = set()
        
        for it in items:
            d_str = it.get("date_str")
            if not d_str:
                continue
                
            if it["type"] == "episode":
                episodes_by_date.setdefault(d_str, []).append(it["ready"] == "✅")
            elif it["type"] == "short":
                dates_with_only_shorts.add(d_str)

        all_dates = set(episodes_by_date.keys()) | dates_with_only_shorts

        for d_str in all_dates:
            try:
                dt = datetime.strptime(d_str, "%d.%m.%Y")
                qdate = QDate(dt.year, dt.month, dt.day)
                
                ep_statuses = episodes_by_date.get(d_str)
                all_ready = all(ep_statuses) if ep_statuses is not None else True
                bg_color = color_ready if all_ready else color_not_ready
                
                fmt = QTextCharFormat()
                fmt.setBackground(bg_color)
                fmt.setForeground(Qt.GlobalColor.white if current_theme == "dark" else Qt.GlobalColor.black)
                
                self.reference_calendar.setDateTextFormat(qdate, fmt)
            except ValueError:
                continue

    def on_calendar_date_activated(self, qdate):
        """Дабл-клик/Enter по дате календаря: выбор и привязка нераспределенной серии."""
        if not self.unassigned_items:
            return
            
        target_date_str = qdate.toString("dd.MM.yyyy")
        dlg = AssignEpisodeDialog(self, self.unassigned_items, target_date_str)
        if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_item:
            target = dlg.selected_item
            
            if target["type"] == "episode":
                update_episode_publish_date(target["id"], target_date_str)
            elif target["type"] == "short":
                update_short_field(target["id"], 'publish_date', target_date_str)
                
            self.load_data()
            if hasattr(self.parent(), "update_table"):
                self.parent().update_table()

    def load_data(self):
        episodes = get_all_episodes_for_schedule()
        shorts = get_all_shorts_for_schedule()
        prev_name = self.config.get("preview_name", "preview.jpg")
        
        combined_list = []
        current_theme = self.config.get("theme", "dark")
        past_bg = get_color("past_date", current_theme)
        future_bg = get_color("future_date", current_theme)

        self.cached_items = combined_list
        self.update_calendar_highlights(combined_list)
        if self.selected_game_name:
            self.highlight_selected_game_dates(self.selected_game_name)
        
        # Гарантируем контрастный шрифт под тему, игнорируя системные артефакты стилей
        text_color = Qt.GlobalColor.white if current_theme == "dark" else Qt.GlobalColor.black
        
        for ep_id, game_name, folder_path, ep_num, title, pub_date in episodes:
            ep_folder = os.path.join(folder_path, f"ep{ep_num}")
            prev_path = os.path.join(ep_folder, prev_name)
            
            # ep_meta: (title, desc, timecodes, tags)
            ep_meta = get_episode_metadata(ep_id)
            meta_title = ep_meta[0] if ep_meta and len(ep_meta) > 0 else ""
            has_desc = bool(ep_meta[1].strip()) if ep_meta and len(ep_meta) > 1 else False
            has_prev = os.path.exists(prev_path) and os.path.getsize(prev_path) > 1024
            
            is_ready = "✅" if (has_desc and has_prev) else "❌"
            
            # Приоритет: кастомный заголовок из метаданных, затем title из селекта эпизода
            resolved_title = (meta_title or title or "").strip()
            display_title = f"Ep. {ep_num} {resolved_title}".strip()
            
            combined_list.append({
                "type": "episode",
                "id": ep_id,
                "game": game_name,
                "title": display_title,
                "date_str": pub_date,
                "ready": is_ready
            })
            
        for short_id, game_name, ep_num, short_num, custom_title, pub_date in shorts:
            display_title = f"Ep. {ep_num} — " + (custom_title if custom_title else f"Shorts {short_num}")
            combined_list.append({
                "type": "short",
                "id": short_id,
                "game": game_name,
                "title": display_title,
                "date_str": pub_date,
                "ready": "-" 
            })
            
        self.unassigned_items = [it for it in combined_list if not it["date_str"]]
        combined_list.sort(key=_parse_schedule_date)
        
        self.table.setRowCount(len(combined_list))
        today = datetime.now().date()
        
        for row, item in enumerate(combined_list):
            game_item = QTableWidgetItem(item["game"])
            title_item = QTableWidgetItem(item["title"])
            
            display_date = item["date_str"] if item["date_str"] else _("lbl_not_set", "Не задана")
            date_item = QTableWidgetItem(display_date)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            date_item.setData(Qt.ItemDataRole.UserRole, item["id"])
            date_item.setData(Qt.ItemDataRole.UserRole + 1, item["type"])
            
            ready_item = QTableWidgetItem(item["ready"])
            ready_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            for cell in (game_item, title_item, date_item, ready_item):
                cell.setForeground(text_color)
            
            if item["date_str"]:
                try:
                    pub_date = datetime.strptime(item["date_str"], "%d.%m.%Y").date()
                    for cell_item in (game_item, title_item, date_item, ready_item):
                        if pub_date < today:
                            cell_item.setBackground(past_bg)
                        elif pub_date > today:
                            cell_item.setBackground(future_bg)
                        elif pub_date == today:
                            font = cell_item.font()
                            font.setBold(True)
                            cell_item.setFont(font)
                except ValueError:
                    pass
            else:
                date_item.setForeground(Qt.GlobalColor.gray)
                
            self.table.setItem(row, 0, game_item)
            self.table.setItem(row, 1, title_item)
            self.table.setItem(row, 2, date_item)
            self.table.setItem(row, 3, ready_item)

        self.update_calendar_highlights(combined_list)

    def on_cell_clicked(self, row, column):
        target_item = self.table.item(row, 0)
        if not target_item:
            return
        target_game = target_item.text().strip()

        sel_model = self.table.selectionModel()

        # Тоггл: если кликнули по уже выбранной игре — сбрасываем всё
        if self.selected_game_name == target_game:
            self.table.blockSignals(True)
            sel_model.clearSelection()
            self.table.blockSignals(False)
            
            self.selected_game_name = None
            self.highlight_selected_game_dates(None)
            return

        # Иначе выбираем все строки кликнутой игры
        self.selected_game_name = target_game
        self.table.blockSignals(True)
        sel_model.clearSelection()

        for r in range(self.table.rowCount()):
            game_cell = self.table.item(r, 0)
            if game_cell and game_cell.text().strip() == target_game:
                idx = self.table.model().index(r, 0)
                sel_model.select(
                    idx, 
                    QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
                )

        self.table.blockSignals(False)
        
        # Подсвечиваем даты релизов этой игры в календаре
        self.highlight_selected_game_dates(target_game)

    def on_cell_double_clicked(self, row, column):
        if column == 2:
            item = self.table.item(row, column)
            item_id = item.data(Qt.ItemDataRole.UserRole)
            item_type = item.data(Qt.ItemDataRole.UserRole + 1)
            
            current_date = item.text()
            if current_date == _("lbl_not_set", "Не задана"):
                current_date = ""

            dialog = CalendarDialog(self, current_date)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_date = dialog.selected_date_str
                if item_type == "episode":
                    update_episode_publish_date(item_id, new_date)
                elif item_type == "short":
                    update_short_field(item_id, 'publish_date', new_date)
                
                self.load_data()
                if hasattr(self.parent(), "update_table"):
                    self.parent().update_table()

    def highlight_selected_game_dates(self, game_name=None):
        """Накладывает акцент на даты релизов конкретной игры поверх базовой раскраски"""
        # Сначала восстанавливаем базовую подсветку готовности
        self.update_calendar_highlights(self.cached_items)
        
        if not game_name:
            return

        current_theme = self.config.get("theme", "dark")
        # Рамка и цвет для выбранных дат (яркий бирюзовый/голубой)
        accent_color = QColor("#00bcd4") if current_theme == "dark" else QColor("#0288d1")

        for it in self.cached_items:
            if it.get("game") == game_name and it.get("date_str"):
                try:
                    dt = datetime.strptime(it["date_str"], "%d.%m.%Y")
                    qdate = QDate(dt.year, dt.month, dt.day)
                    
                    # Забираем уже существующий формат (с цветом готовности)
                    fmt = self.reference_calendar.dateTextFormat(qdate)
                    fmt.setFontWeight(QFont.Weight.ExtraBold)
                    fmt.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
                    fmt.setUnderlineColor(accent_color)
                    
                    self.reference_calendar.setDateTextFormat(qdate, fmt)
                except ValueError:
                    continue