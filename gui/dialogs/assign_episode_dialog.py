from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QLabel, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox

class AssignEpisodeDialog(QDialog):
    """Выбор серии/шортса из нераспределенных для назначения на дату"""
    def __init__(self, parent, unassigned_items, target_date_str):
        super().__init__(parent)
        self.setWindowTitle(f"{_('title_assign_episode', 'Назначить выпуск')} — {target_date_str}")
        self.resize(500, 350)
        self.selected_item = None
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{_('lbl_choose_episode_for_date', 'Выберите серию без даты для выпуска:')} <b>{target_date_str}</b>"))
        
        self.list_widget = QListWidget()
        for item in unassigned_items:
            prefix = "[Шортс]" if item["type"] == "short" else "[Серия]"
            list_item = QListWidgetItem(f"{prefix} {item['game']} — {item['title']}")
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.list_widget.addItem(list_item)
            
        self.list_widget.itemDoubleClicked.connect(self._on_item_chosen)
        layout.addWidget(self.list_widget)
        
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._on_item_chosen)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_item_chosen(self):
        curr = self.list_widget.currentItem()
        if curr:
            self.selected_item = curr.data(Qt.ItemDataRole.UserRole)
            self.accept()