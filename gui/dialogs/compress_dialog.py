import os
import subprocess
from PyQt6.QtWidgets import (QDialog, QFormLayout, QHBoxLayout, QLineEdit, 
                             QPushButton, QFileDialog, QLabel, QComboBox, QSpinBox)
from core.config import _

class CompressDialog(QDialog):
    def __init__(self, parent, config): 
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("Сжатие видео (Transcoding)")
        self.resize(550, 380)
        
        layout = QFormLayout(self)
        self.filepath = ""
        self.duration_sec = 0.0 

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

        # 3. Выбор профиля
        self.profile_selector = QComboBox()
        self.profile_selector.addItem("⚙️ Ручная настройка", userData="manual")
        self.profile_selector.addItem("🚀 Черновик / Быстрый экспорт (H.264, 8 Mbps)", userData="draft")
        self.profile_selector.addItem("🎬 YouTube 1080p Optimal (H.264, 15 Mbps, 60fps)", userData="youtube")
        self.profile_selector.addItem("📦 Архив для монтажа / Vegas (HEVC, 30 Mbps, GOP 30)", userData="archive")
        self.profile_selector.currentIndexChanged.connect(self.on_profile_changed)
        layout.addRow("Профиль:", self.profile_selector)

        # 4. Выбор кодека
        self.codec_selector = QComboBox()
        self.codec_selector.addItem("CPU (Обычный H.264)", userData="libx264")
        self.codec_selector.addItem("AMD (H.264)", userData="h264_amf")
        self.codec_selector.addItem("NVIDIA (H.264)", userData="h264_nvenc")
        self.codec_selector.addItem("AMD (HEVC / H.265)", userData="hevc_amf")
        self.codec_selector.addItem("NVIDIA (HEVC / H.265)", userData="hevc_nvenc")
        self.codec_selector.setCurrentIndex(3)
        layout.addRow("Кодек видео:", self.codec_selector)

        # 5. Целевой битрейт
        self.bitrate_selector = QComboBox()
        self.bitrate_selector.addItems(["5", "8", "10", "15", "20", "25", "30", "40", "50"])
        self.bitrate_selector.setCurrentText("15") 
        self.bitrate_selector.currentTextChanged.connect(self.update_estimate)
        
        bitrate_layout = QHBoxLayout()
        bitrate_layout.addWidget(self.bitrate_selector)
        bitrate_layout.addWidget(QLabel("Mbps (Мбит/с)"))
        layout.addRow("Целевой битрейт:", bitrate_layout)

        # 6. FPS (Кадры в секунду)
        self.fps_selector = QComboBox()
        self.fps_selector.addItem("Оригинал (не менять)", userData="original")
        self.fps_selector.addItem("30 fps", userData="30")
        self.fps_selector.addItem("60 fps", userData="60")
        layout.addRow("Частота кадров (FPS):", self.fps_selector)

        # 7. Прогноз размера
        self.estimate_label = QLabel("Ожидаемый вес: 0 MB")
        self.estimate_label.setStyleSheet("font-weight: bold; color: #2e8b57;") 
        layout.addRow("Прогноз:", self.estimate_label)

        # 8. Кнопки
        btn_layout = QHBoxLayout()
        self.start_btn = QPushButton("Сжать видео")
        self.start_btn.setEnabled(False) 
        self.start_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.start_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addRow(btn_layout)

        # Инициализируем состояние интерфейса (по умолчанию стоит ручной или первый профиль)
        self.on_profile_changed()

    def select_file(self):
        start_dir = self.config.get("recordings_folder", "") 
        file, ignored = QFileDialog.getOpenFileName(self, _("dlg_select_source_video"), "", f"{_('filter_video_files')} (*.mkv *.mp4 *.avi)")
        if file:
            self.filepath = file
            self.file_input.setText(file)
            self.analyze_file()
            self.start_btn.setEnabled(True)

    def analyze_file(self):
        size_bytes = os.path.getsize(self.filepath)
        size_mb = size_bytes / (1024 * 1024)
        
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                 '-of', 'default=noprint_wrappers=1:nokey=1', self.filepath],
                stdout=subprocess.PIPE, text=True, creationflags=0x08000000
            )
            self.duration_sec = float(result.stdout.strip())
            
            m, s = divmod(int(self.duration_sec), 60)
            h, m = divmod(m, 60)
            dur_str = f"{h:02d}:{m:02d}:{s:02d}"
            
            self.info_label.setText(f"{_('lbl_size')}: {size_mb:.2f} MB | {_('lbl_duration')}: {dur_str}")
            self.update_estimate()
        except Exception as e:
            self.info_label.setText(_("msg_file_read_error"))

    def update_estimate(self):
        if self.duration_sec > 0:
            try:
                bitrate_mbps = float(self.bitrate_selector.currentText())
            except ValueError:
                bitrate_mbps = 15.0
            
            audio_bitrate_mbps = 0.192 
            total_size_mb = ((bitrate_mbps + audio_bitrate_mbps) * self.duration_sec) / 8
            self.estimate_label.setText(f"{_('lbl_maybe_weight')}: ~{total_size_mb:.2f} MB")

    def on_profile_changed(self):
        profile = self.profile_selector.currentData()
        
        if profile == "manual":
            # Разблокируем ручное управление
            self.codec_selector.setEnabled(True)
            self.bitrate_selector.setEnabled(True)
            self.fps_selector.setEnabled(True)
        else:
            # Блокируем поля, так как они управляются профилем
            self.codec_selector.setEnabled(False)
            self.bitrate_selector.setEnabled(False)
            self.fps_selector.setEnabled(False)
            
            # Автоматически задаем параметры в зависимости от профиля
            if profile == "draft":
                # Ищем индекс h264_amf или libx264
                self.codec_selector.setCurrentIndex(1) # h264_amf
                self.bitrate_selector.setCurrentText("8")
                self.fps_selector.setCurrentIndex(1) # 30 fps для скорости
            elif profile == "youtube":
                self.codec_selector.setCurrentIndex(1) # h264_amf
                self.bitrate_selector.setCurrentText("15")
                self.fps_selector.setCurrentIndex(2) # 60 fps
            elif profile == "archive":
                self.codec_selector.setCurrentIndex(3) # hevc_amf
                self.bitrate_selector.setCurrentText("30")
                self.fps_selector.setCurrentIndex(0) # Оригинал