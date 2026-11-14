import os
import sys
import tempfile
from pathlib import Path


_TEST_APP_DATA = tempfile.TemporaryDirectory(prefix="tianxin-app-test-")
os.environ["TASK_CENTER_DATABASE_URL"] = (
    f"sqlite:///{Path(_TEST_APP_DATA.name) / 'unstarted-app.sqlite3'}"
)

BACKEND_ROOT = Path(__file__).resolve().parents[1] / "src" / "backend"
sys.path.insert(0, str(BACKEND_ROOT))
