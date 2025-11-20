import json
from typing import Dict, Optional
from .config import SETTINGS_FILE, DEFAULT_RAW_ROOT, DEFAULT_PROCESSED_ROOT

class AppSettings:
    def __init__(self):
        self._data: Dict = {
            "raw_root": DEFAULT_RAW_ROOT,
            "processed_root": DEFAULT_PROCESSED_ROOT,
            "last_opened_project": "",
            "last_opened_session_path": "",
            "server_roots_by_project": {},  # {project: server_root}
        }
        self.load()

    def load(self):
        try:
            if SETTINGS_FILE.exists():
                self._data.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass

    def save(self):
        try:
            SETTINGS_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        except Exception:
            pass

    @property
    def raw_root(self) -> str:
        return self._data.get("raw_root") or DEFAULT_RAW_ROOT

    @raw_root.setter
    def raw_root(self, v: str):
        self._data["raw_root"] = v
        self.save()

    @property
    def processed_root(self) -> str:
        return self._data.get("processed_root") or DEFAULT_PROCESSED_ROOT

    @processed_root.setter
    def processed_root(self, v: str):
        self._data["processed_root"] = v
        self.save()

    def get_server_root_for_project(self, project: str) -> str:
        return (self._data.get("server_roots_by_project") or {}).get(project, "")

    def put_server_root_for_project(self, project: str, server_root: str):
        d = self._data.setdefault("server_roots_by_project", {})
        d[project] = server_root
        self.save()

    @property
    def last_opened_project(self) -> str:
        return self._data.get("last_opened_project", "")

    @last_opened_project.setter
    def last_opened_project(self, v: str):
        self._data["last_opened_project"] = v
        self.save()

    @property
    def last_opened_session_path(self) -> str:
        return self._data.get("last_opened_session_path", "")

    @last_opened_session_path.setter
    def last_opened_session_path(self, v: str):
        self._data["last_opened_session_path"] = v
        self.save()


class AppState:
    def __init__(self):
        self.settings = AppSettings()
        self.current_project: str = self.settings.last_opened_project or ""
        self.current_animal: str = ""
        self.current_session: str = ""
        self.current_session_path: str = self.settings.last_opened_session_path or ""

    def set_current(self, project: Optional[str]=None, animal: Optional[str]=None,
                    session: Optional[str]=None, session_path: Optional[str]=None):
        if project is not None:
            self.current_project = project
            self.settings.last_opened_project = project
        if animal is not None:
            self.current_animal = animal
        if session is not None:
            self.current_session = session
        if session_path is not None:
            self.current_session_path = session_path
            self.settings.last_opened_session_path = session_path
