"""File path and modification-time tracking."""
import os


class FileService:
    """Tracks the current file path and modification time."""

    def __init__(self):
        self.current_file = None
        self.current_file_mtime = None

    def set_current_file(self, path: str | None) -> None:
        self.current_file = path
        self.refresh_mtime()

    def refresh_mtime(self) -> None:
        try:
            self.current_file_mtime = (
                os.path.getmtime(self.current_file)
                if self.current_file and os.path.exists(self.current_file)
                else None
            )
        except OSError:
            self.current_file_mtime = None

    def check_external_change(self) -> bool:
        if not self.current_file or not os.path.exists(self.current_file):
            return False
        try:
            return os.path.getmtime(self.current_file) != self.current_file_mtime
        except OSError:
            return False

    @property
    def basename(self) -> str:
        return os.path.basename(self.current_file) if self.current_file else ""
