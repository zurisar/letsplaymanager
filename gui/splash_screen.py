from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, pyqtSignal, Qt

class FadeSplashScreen(QSplashScreen):
    # Сигнал, который мы отправим, когда картинка полностью исчезнет
    fade_finished = pyqtSignal()

    def __init__(self, image_path):
        pixmap = QPixmap(image_path)
        super().__init__(pixmap, Qt.WindowType.SplashScreen | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowOpacity(1.0)

    def fade_out(self, duration=500):
        """Плавное затухание прозрачности окна от 1.0 до 0.0"""
        self.anim = QPropertyAnimation(self, b"windowOpacity")
        self.anim.setDuration(duration)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        # InOutQuad дает мягкий, кинематографичный старт и финиш анимации
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuad) 
        self.anim.finished.connect(self.on_fade_finished)
        self.anim.start()

    def on_fade_finished(self):
        self.fade_finished.emit()
        self.close()