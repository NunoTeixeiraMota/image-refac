import io
import zipfile
import shutil
import threading
import time
from pathlib import Path


UPLOAD_DIR = Path(__file__).resolve().parent.parent / 'uploads'
CONVERSION_DIR = Path(__file__).resolve().parent.parent / 'conversions'
SESSION_MAX_AGE = 3600  # 1 hour


def ensure_dirs():
    UPLOAD_DIR.mkdir(exist_ok=True)
    CONVERSION_DIR.mkdir(exist_ok=True)


def session_upload_dir(session_id):
    p = UPLOAD_DIR / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def session_conversion_dir(session_id):
    p = CONVERSION_DIR / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def create_zip_in_memory(directory):
    """Create a ZIP archive of all files in directory, returned as bytes."""
    buf = io.BytesIO()
    directory = Path(directory)
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fpath in directory.iterdir():
            if fpath.is_file():
                zf.write(fpath, fpath.name)
    buf.seek(0)
    return buf


def cleanup_old_sessions():
    """Remove session folders older than SESSION_MAX_AGE."""
    now = time.time()
    for base in (UPLOAD_DIR, CONVERSION_DIR):
        if not base.exists():
            continue
        for folder in base.iterdir():
            if not folder.is_dir():
                continue
            try:
                age = now - folder.stat().st_mtime
                if age > SESSION_MAX_AGE:
                    shutil.rmtree(folder, ignore_errors=True)
            except Exception:
                pass


def start_cleanup_thread(interval=300):
    """Run cleanup every `interval` seconds in a daemon thread."""
    def _loop():
        while True:
            cleanup_old_sessions()
            time.sleep(interval)

    t = threading.Thread(target=_loop, daemon=True)
    t.start()
