import os
import subprocess
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import BASE_DIR, _

def get_tool_path(tool_name):
    """Возвращает путь к локальному ffmpeg/ffprobe, либо fallback на системный"""
    local_path = os.path.join(BASE_DIR, 'bin', f"{tool_name}.exe")
    if os.path.exists(local_path):
        return local_path
    return tool_name

class FFmpegWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd

    def run(self):
        try:
            process = subprocess.Popen(
                self.cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True,
                encoding='utf-8',
                errors='ignore',
                creationflags=0x08000000
            )
            
            for line in process.stdout:
                self.progress.emit(line.strip())
            
            process.wait()
            
            if process.returncode == 0:
                self.finished.emit(True, _("status_done"))
            else:
                self.finished.emit(False, _("status_conversion_error"))
        except Exception as e:
            self.finished.emit(False, str(e))