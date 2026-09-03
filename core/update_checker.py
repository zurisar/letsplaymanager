import logging
import requests
import re
from PyQt6.QtCore import QThread, pyqtSignal
from core.config import APP_VERSION

class UpdateCheckerThread(QThread):
    update_available = pyqtSignal(str, str)

    def run(self):
        try:
            url = "https://api.github.com/repos/zurisar/letsplaymanager/releases"
            
            headers = {
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "LetsPlayManager-UpdateChecker"
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code == 200:
                releases = response.json()
                if releases and isinstance(releases, list):
                    latest_data = releases[0]
                    
                    latest_version = latest_data.get("tag_name", "").replace("v", "")
                    release_url = latest_data.get("html_url", "")
                    
                    if self.is_newer_version(APP_VERSION, latest_version):
                        self.update_available.emit(latest_version, release_url)
            elif response.status_code == 403:
                # Читаем текст ошибки напрямую, чтобы подтвердить Rate Limit
                logging.warning(f"GitHub API 403 Forbidden. Ответ сервера: {response.text}")
            else:
                logging.warning(f"GitHub API вернул статус: {response.status_code}")
                    
        except Exception as e:
            logging.warning(f"Не удалось проверить обновления: {e}")

    def is_newer_version(self, current, latest):
        """
        Умное сравнение версий. Вытаскивает только числа (0.5.1-alpha -> [0, 5, 1]).
        """
        def parse_version(v):
            # Находим все числа в строке, игнорируя текст (alpha, beta, rc и т.д.)
            return [int(x) for x in re.findall(r'\d+', v)]
        
        return parse_version(latest) > parse_version(current)