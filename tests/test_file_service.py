import os
import tempfile

from bitmap_designer.services.file_service import FileService


class TestFileService:
    def test_initial_state(self):
        fs = FileService()
        assert fs.current_file is None
        assert fs.current_file_mtime is None
        assert fs.basename == ""

    def test_set_current_file(self):
        fs = FileService()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            fs.set_current_file(path)
            assert fs.current_file == path
            assert fs.current_file_mtime is not None
            assert fs.basename == os.path.basename(path)
        finally:
            os.unlink(path)

    def test_set_current_file_none(self):
        fs = FileService()
        fs.set_current_file(None)
        assert fs.current_file is None
        assert fs.current_file_mtime is None

    def test_refresh_mtime(self):
        fs = FileService()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            fs.set_current_file(path)
            orig_mtime = fs.current_file_mtime
            fs.refresh_mtime()
            assert fs.current_file_mtime == orig_mtime
        finally:
            os.unlink(path)

    def test_check_external_change_no_file(self):
        fs = FileService()
        assert fs.check_external_change() is False

    def test_check_external_change_no_change(self):
        fs = FileService()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            fs.set_current_file(path)
            assert fs.check_external_change() is False
        finally:
            os.unlink(path)

    def test_check_external_change_detected(self):
        fs = FileService()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            f.write(b"{}")
            path = f.name
        try:
            fs.set_current_file(path)
            fs.refresh_mtime()
            os.utime(path, (0, 0))
            assert fs.check_external_change() is True
        finally:
            os.unlink(path)

    def test_basename_with_path(self):
        fs = FileService()
        fs.set_current_file("/some/dir/file.json")
        assert fs.basename == "file.json"

    def test_basename_none(self):
        fs = FileService()
        assert fs.basename == ""
