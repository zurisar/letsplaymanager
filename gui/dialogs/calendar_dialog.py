from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QCalendarWidget
from PyQt6.QtCore import QDate
from core.config import _

class CalendarDialog(QDialog):
    def __init__(self, parent, current_date_str=""):
        super().__init__(parent)
        self.setWindowTitle(_("lbl_publishing_date"))
        self.resize(350, 250)
        layout = QVBoxLayout(self)

        self.calendar = QCalendarWidget()
        self.calendar.setGridVisible(True)
        
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