import os
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QFileDialog, QWidget, QTimeEdit, QScrollArea)
from PyQt6.QtCore import QTime, Qt
from core.config import _
from core.ffmpeg_worker import FFmpegWorker, get_tool_path
from gui.dialogs.progress_dialog import ProgressDialog

class CutRowWidget(QWidget):
    """Виджет одной строки для нарезки"""
    def __init__(self, index, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Порядковый номер
        self.lbl_index = QLabel(f"{index}.")
        self.lbl_index.setFixedWidth(20)
        layout.addWidget(self.lbl_index)
        
        # Время начала
        layout.addWidget(QLabel("Старт:"))
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("HH:mm:ss")
        layout.addWidget(self.time_start)
        
        # Продолжительность
        layout.addWidget(QLabel("Длительность:"))
        self.time_duration = QTimeEdit()
        self.time_duration.setDisplayFormat("HH:mm:ss")
        self.time_duration.setTime(QTime(0, 1, 0)) # По умолчанию 1 минута
        layout.addWidget(self.time_duration)
        
        # Кнопки быстрого добавления времени к длительности
        btn_add_15 = QPushButton("+15s")
        btn_add_15.clicked.connect(lambda: self.add_seconds_to_duration(15))
        layout.addWidget(btn_add_15)
        
        btn_add_30 = QPushButton("+30s")
        btn_add_30.clicked.connect(lambda: self.add_seconds_to_duration(30))
        layout.addWidget(btn_add_30)
        
        btn_add_60 = QPushButton("+1m")
        btn_add_60.clicked.connect(lambda: self.add_seconds_to_duration(60))
        layout.addWidget(btn_add_60)
        
        layout.addStretch()

    def add_seconds_to_duration(self, secs):
        current_time = self.time_duration.time()
        # addSecs возвращает новый объект QTime
        new_time = current_time.addSecs(secs)
        self.time_duration.setTime(new_time)
        
    def get_data(self):
        return {
            "start": self.time_start.time().toString("HH:mm:ss"),
            "duration": self.time_duration.time().toString("HH:mm:ss")
        }

class ShortsCutterDialog(QDialog):
    def __init__(self, parent, source_file=""):
        super().__init__(parent)
        self.setWindowTitle("Нарезка на шортсы")
        self.resize(800, 400)
        
        self.main_layout = QVBoxLayout(self)
        
        # --- ВЫБОР ФАЙЛА ---
        file_layout = QHBoxLayout()
        self.file_input = QLineEdit(source_file)
        self.file_input.setReadOnly(True)
        btn_browse = QPushButton("Обзор")
        btn_browse.clicked.connect(self.browse_file)
        
        file_layout.addWidget(QLabel("Исходник:"))
        file_layout.addWidget(self.file_input)
        file_layout.addWidget(btn_browse)
        self.main_layout.addLayout(file_layout)
        
        # --- ПАНЕЛЬ УПРАВЛЕНИЯ СТРОКАМИ ---
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Фрагменты:"))
        
        btn_add = QPushButton("➕ Добавить")
        btn_add.clicked.connect(self.add_row)
        ctrl_layout.addWidget(btn_add)
        
        btn_remove = QPushButton("➖ Убрать")
        btn_remove.clicked.connect(self.remove_row)
        ctrl_layout.addWidget(btn_remove)
        
        ctrl_layout.addStretch()
        self.main_layout.addLayout(ctrl_layout)
        
        # --- СПИСОК ОТРЕЗКОВ (В ScrollArea на случай если их будет много) ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.rows_container = QWidget()
        self.rows_layout = QVBoxLayout(self.rows_container)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.rows_container)
        
        self.main_layout.addWidget(self.scroll_area)
        
        # --- НИЖНИЕ КНОПКИ ---
        btn_layout = QHBoxLayout()
        self.btn_cut = QPushButton("✂️ Нарезать")
        self.btn_cut.setStyleSheet("background-color: #90ee90; font-weight: bold; padding: 8px;")
        self.btn_cut.clicked.connect(self.start_cutting)
        
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.btn_cut)
        btn_layout.addWidget(btn_cancel)
        self.main_layout.addLayout(btn_layout)
        
        self.rows = []
        self.queue = []
        
        # Добавляем первую строку по умолчанию
        self.add_row()

    def browse_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите исходное видео", "", "Видеофайлы (*.mkv *.mp4 *.avi)")
        if file:
            self.file_input.setText(file)

    def add_row(self):
        index = len(self.rows) + 1
        row_widget = CutRowWidget(index)
        self.rows.append(row_widget)
        self.rows_layout.addWidget(row_widget)

    def remove_row(self):
        if len(self.rows) > 1: # Оставляем минимум одну строку
            row_widget = self.rows.pop()
            self.rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()

    def start_cutting(self):
        input_file = self.file_input.text().strip()
        if not input_file or not os.path.exists(input_file):
            return
            
        base_dir = os.path.dirname(input_file)
        shorts_dir = os.path.join(base_dir, "shorts")
        os.makedirs(shorts_dir, exist_ok=True)
        
        filename_no_ext, ext = os.path.splitext(os.path.basename(input_file))
        
        self.queue = []
        for i, row in enumerate(self.rows):
            data = row.get_data()
            if data["duration"] == "00:00:00":
                continue # Пропускаем пустые отрезки
                
            out_name = f"{filename_no_ext} - Cut {i+1}.mp4"
            out_path = os.path.join(shorts_dir, out_name)
            
            # -ss ставим ПЕРЕД -i для мгновенного позиционирования
            cmd = [
                get_tool_path('ffmpeg'), '-y', 
                '-ss', data["start"], 
                '-i', input_file, 
                '-t', data["duration"], 
                '-c', 'copy', 
                out_path
            ]
            self.queue.append((cmd, out_name))
            
        if not self.queue:
            return

        # Открываем окно прогресса и запускаем первый процесс
        self.progress_dialog = ProgressDialog(self)
        self.process_next_in_queue()
        self.progress_dialog.exec()
        
    def process_next_in_queue(self):
        if not self.queue:
            self.progress_dialog.append_log("\n✅ Все фрагменты успешно нарезаны!")
            return
            
        cmd, out_name = self.queue.pop(0)
        self.progress_dialog.append_log(f"\n--- Нарезка фрагмента: {out_name} ---\n")
        
        self.worker = FFmpegWorker(cmd)
        self.worker.progress.connect(self.progress_dialog.append_log)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.start()

    def on_worker_finished(self, success, message):
        if not success:
            self.progress_dialog.append_log(f"\n❌ Ошибка: {message}")
        # Запускаем следующий кусок как только закончили текущий
        self.process_next_in_queue()