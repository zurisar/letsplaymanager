import shutil
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
import database as db

VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.ts'}


class DeleteMode(Enum):
    VIDEO_ONLY = auto()      # Снести тяжелые видео серии, оставить превью/заметки/шортсы и запись в БД
    ARCHIVE_FOLDER = auto()  # Снести всю папку epX вместе с шортсами, в БД поставить sources_deleted = 1
    HARD_EPISODE = auto()    # Снести папку epX + полностью вычистить эпизод и его шортсы из БД
    FULL_GAME = auto()       # Выжечь папку игры целиком + каскадно снести всё из БД


@dataclass
class DeletionReport:
    target_path_exists: bool = True
    unpublished_episodes: int = 0
    unpublished_shorts: int = 0
    untracked_shorts_files: int = 0  # Лишние видео в папке shorts, которых нет в БД

    @property
    def has_risks(self) -> bool:
        return (
            self.unpublished_episodes > 0
            or self.unpublished_shorts > 0
            or self.untracked_shorts_files > 0
        )


class DeletionManager:
    @staticmethod
    def _find_shorts_dir(ep_path: Path) -> Path | None:
        """Ищет подпапку shorts (или short) внутри папки эпизода без учета регистра."""
        if not ep_path.exists():
            return None
        for sub in ('shorts', 'short'):
            candidate = ep_path / sub
            if candidate.is_dir():
                return candidate
        return None

    @classmethod
    def inspect_episode(cls, ep_id: int, ep_folder: str | Path) -> DeletionReport:
        report = DeletionReport()
        ep_path = Path(ep_folder)
        report.target_path_exists = ep_path.exists()

        # 1. Выложена ли сама серия хотя бы на один хостинг
        if not db.get_uploads(ep_id):
            report.unpublished_episodes = 1

        # 2. Проверяем статус публикации шортсов в БД
        shorts_in_db = db.get_shorts(ep_id)
        for sh in shorts_in_db:
            sh_uploads = db.get_short_uploads(sh[0])
            # В update_short_upload_status запись создается при status=1, но на всякий случай проверяем наличие строки
            if not sh_uploads:
                report.unpublished_shorts += 1

        # 3. Сверяем количество видеофайлов в папке shorts с тем, что записано в БД
        sh_dir = cls._find_shorts_dir(ep_path)
        if sh_dir:
            disk_videos = [
                f for f in sh_dir.iterdir()
                if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
            ]
            diff = len(disk_videos) - len(shorts_in_db)
            if diff > 0:
                report.untracked_shorts_files = diff

        return report

    @classmethod
    def inspect_game(cls, game_id: int, game_folder: str | Path) -> DeletionReport:
        """Префлайт перед сносом всей игры: агрегирует риски по всем живым сериям."""
        report = DeletionReport()
        game_path = Path(game_folder)
        report.target_path_exists = game_path.exists()

        episodes = db.get_episodes(game_id)  # [(id, number, ...), ...]
        for ep in episodes:
            ep_id, ep_num = ep[0], ep[1]
            ep_subreport = cls.inspect_episode(ep_id, game_path / f"ep{ep_num}")
            report.unpublished_episodes += ep_subreport.unpublished_episodes
            report.unpublished_shorts += ep_subreport.unpublished_shorts
            report.untracked_shorts_files += ep_subreport.untracked_shorts_files

        return report

    @staticmethod
    def execute_episode(ep_id: int, ep_folder: str | Path, mode: DeleteMode) -> None:
        ep_path = Path(ep_folder)

        if mode == DeleteMode.VIDEO_ONLY:
            # iterdir() не заходит в подпапку shorts, поэтому рендеры шортсов, превью и txt остаются целыми
            if ep_path.exists():
                for item in ep_path.iterdir():
                    if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS:
                        item.unlink(missing_ok=True)
            db.mark_episode_deleted(ep_id)

        elif mode == DeleteMode.ARCHIVE_FOLDER:
            if ep_path.exists():
                shutil.rmtree(ep_path)
            db.mark_episode_deleted(ep_id)

        elif mode == DeleteMode.HARD_EPISODE:
            if ep_path.exists():
                shutil.rmtree(ep_path)
            db.delete_episode_from_db(ep_id)

    @staticmethod
    def execute_game(game_id: int, game_folder: str | Path, keep_shorts: bool = False) -> None:
        """Удаление игры: либо полное выжигание, либо архивация с сохранением папок shorts."""
        game_path = Path(game_folder)

        if keep_shorts:
            episodes = db.get_episodes(game_id)
            for ep in episodes:
                ep_id, ep_num = ep[0], ep[1]
                ep_path = game_path / f"ep{ep_num}"
                
                if ep_path.exists():
                    for item in ep_path.iterdir():
                        # Оставляем живой только папку с шортсами
                        if item.name.lower() not in ('shorts', 'short'):
                            if item.is_dir():
                                shutil.rmtree(item)
                            else:
                                item.unlink(missing_ok=True)
                
                db.mark_episode_deleted(ep_id)
        else:
            if game_path.exists():
                shutil.rmtree(game_path)
            db.delete_game_full(game_id)