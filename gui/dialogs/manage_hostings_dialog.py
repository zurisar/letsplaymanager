import re
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QHBoxLayout, QLineEdit, QPushButton, QMessageBox)
from PyQt6.QtCore import Qt

from core.config import _
from database import get_videohostings, add_videohosting, delete_videohosting

class ManageHostingsDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(_("title_manage_hostings", "Управление видеохостингами"))
        self.resize(450, 300)
        
        layout = QVBoxLayout(self)
        
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([f"{_('lbl_key')} (system)", _("lbl_displayname")])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)
        
        self.load_data()
        
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