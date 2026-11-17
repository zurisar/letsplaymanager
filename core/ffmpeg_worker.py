import os
import shutil
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


class FileMoveWorker(QThread):
    progress = pyqtSignal(str)
    finished = pyqtSignal(bool, str)

    def __init__(self, src: str, dst: str):
        super().__init__()
        self.src = src
        self.dst = dst

    def run(self):
        try:
            total_size = os.path.getsize(self.src)
            self.progress.emit(f"Перемещение файла: {os.path.basename(self.src)}...")

            # Пробуем мгновенное перемещение в пределах одного тома
            try:
                os.replace(self.src, self.dst)
                self.progress.emit("Готово (мгновенный перенос на одном диске).")
                self.finished.emit(True, _("status_done"))
                return
            except OSError:
                # Файлы на разных дисках — копируем по чанкам с выводом прогресса
                pass

            chunk_size = 16 * 1024 * 1024  # 16 MB
            copied = 0
            last_reported_pct = -1

            with open(self.src, 'rb') as fsrc, open(self.dst, 'wb') as fdst:
                while True:
                    buf = fsrc.read(chunk_size)
                    if not buf:
                        break
                    fdst.write(buf)
                    copied += len(buf)
                    if total_size > 0:
                        pct = int(copied * 100 / total_size)
                        if pct >= last_reported_pct + 5 or pct == 100:
                            last_reported_pct = pct
                            copied_mb = copied / (1024 * 1024)
                            total_mb = total_size / (1024 * 1024)
                            self.progress.emit(f"Копирование: {pct}% ({copied_mb:.0f} / {total_mb:.0f} MB)")

            shutil.copystat(self.src, self.dst)
            os.remove(self.src)
            self.finished.emit(True, _("status_done"))
        except Exception as e:
            # Если копирование оборвалось, убираем битый недокопированный файл
            if os.path.exists(self.dst) and os.path.exists(self.src):
                try:
                    os.remove(self.dst)
                except OSError:
                    pass
            self.finished.emit(False, str(e))