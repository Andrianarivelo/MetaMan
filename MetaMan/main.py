import os
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QFileDialog, QMessageBox, QLabel
)

from .config import APP_TITLE, WINDOW_GEOMETRY
from .state import AppState
from .tabs.navigation_tab import NavigationTab
from .tabs.recording_tab import RecordingTab
from .tabs.preprocessing_tab import PreprocessingTab
from .services.server_sync import sync_project_to_server
from .services.search_service import search_in_project
from .io_ops import load_session_metadata, save_session_triplet

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(*WINDOW_GEOMETRY)
        self.state = AppState()
        self._build_ui()

    def _build_ui(self):
        cw = QWidget(); self.setCentralWidget(cw)
        root = QVBoxLayout(cw)

        self.tabs = QTabWidget()
        self.nav_tab = NavigationTab(self.state, on_load_session=self._load_session_everywhere)
        self.rec_tab = RecordingTab(self.state)
        self.pre_tab = PreprocessingTab(self.state)
        self.tabs.addTab(self.nav_tab, "Navigation")
        self.tabs.addTab(self.rec_tab, "Recording")
        self.tabs.addTab(self.pre_tab, "Preprocessing")
        root.addWidget(self.tabs, 1)

        # bottom bar
        bar = QHBoxLayout()
        b_copy = QPushButton("Copy project to server…"); b_copy.clicked.connect(self._copy_to_server); bar.addWidget(b_copy)
        b_search = QPushButton("Search…"); b_search.clicked.connect(self._search); bar.addWidget(b_search)
        b_animal = QPushButton("Generate animal summary CSV…"); b_animal.clicked.connect(self._animal_summary); bar.addWidget(b_animal)
        bar.addStretch(1)
        self.lbl_status = QLabel(""); bar.addWidget(self.lbl_status)
        root.addLayout(bar)

    def _load_session_everywhere(self, session_path: str):
        self.rec_tab.load_session(session_path)
        self.pre_tab._load_from_session(session_path)

    def _copy_to_server(self):
        proj = self.state.current_project
        if not proj:
            QMessageBox.warning(self, "No project", "Select or load a session first.")
            return
        project_dir = os.path.join(self.state.settings.raw_root, proj)
        if not os.path.isdir(project_dir):
            QMessageBox.critical(self, "Missing", f"Project folder not found:\n{project_dir}")
            return
        default_server = self.state.settings.get_server_root_for_project(proj)
        server_dir = QFileDialog.getExistingDirectory(self, "Choose server root", default_server or "")
        if not server_dir:
            return
        self.state.settings.put_server_root_for_project(proj, server_dir)

        # stream progress to Recording log
        def log(s: str): self.rec_tab.logger.log(s)

        from time import time
        start = time()
        # run synchronously? better not block. but we promised to perform tasks now; still, threading is ok here for UI.
        from ..utils import run_in_thread
        def work():
            sync_project_to_server(project_dir, server_dir, log)
            dt = max(time() - start, 1e-6)
            log(f"Project copy finished in {dt:.1f}s.")
            # annotate server paths in current session
            sess_path = self.state.current_session_path
            if not sess_path:
                return
            meta = load_session_metadata(sess_path) or {}
            proj_name = proj
            animal = meta.get("Animal",""); session = meta.get("Session","")
            server_project = os.path.join(server_dir, proj_name)
            session_dir = os.path.join(self.state.settings.raw_root, proj_name, animal, session)
            for item in meta.get("file_list", []):
                spath = item["path"].replace(session_dir, os.path.join(server_project, animal, session))
                item["server_path"] = spath if os.path.exists(spath) else ""
            save_session_triplet(sess_path, meta, logger=log)

        run_in_thread(work)

    def _search(self):
        proj = self.state.current_project
        if not proj:
            QMessageBox.warning(self, "No project", "Select or load a session first.")
            return
        from PySide6.QtWidgets import QInputDialog
        text, ok = QInputDialog.getText(self, "Search", "Enter text:")
        if not ok or not text:
            return
        project_dir = os.path.join(self.state.settings.raw_root, proj)
        hits = search_in_project(project_dir, text)
        if not hits:
            QMessageBox.information(self, "Search", "No matches.")
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox
        dlg = QDialog(self); dlg.setWindowTitle("Search results"); lay = QVBoxLayout(dlg)
        txt = QTextEdit(); txt.setReadOnly(True); lay.addWidget(txt)
        txt.setPlainText("\n\n".join([f"{i+1}. {h['path']}\n  {h['key']}: {h['value']}" for i,h in enumerate(hits[:200])]))
        btns = QDialogButtonBox(QDialogButtonBox.Close); btns.rejected.connect(dlg.reject); btns.accepted.connect(dlg.accept); lay.addWidget(btns)
        dlg.exec()

    def _animal_summary(self):
        proj = self.state.current_project
        animal = self.state.current_animal
        if not (proj and animal):
            QMessageBox.warning(self, "Choose animal", "Select an animal in Navigation first.")
            return
        rows = []
        import json, pandas as pd
        animal_dir = os.path.join(self.state.settings.raw_root, proj, animal)
        for sess in sorted([d for d in os.listdir(animal_dir) if os.path.isdir(os.path.join(animal_dir, d))]):
            smeta = os.path.join(animal_dir, sess, "metadata.json")
            if os.path.exists(smeta):
                try:
                    data = json.loads(open(smeta, "r", encoding="utf-8").read())
                    row = {
                        "Project": proj,
                        "Animal": animal,
                        "Session": sess,
                        "DateTime": data.get("DateTime",""),
                        "Recording": data.get("Recording",""),
                        "Experiment": data.get("Experiment",""),
                        "Experimenter": data.get("Experimenter",""),
                        "Condition": data.get("Condition",""),
                        "Comments": data.get("Comments",""),
                    }
                    rows.append(row)
                except Exception:
                    pass
        if not rows:
            QMessageBox.information(self, "No data", "No metadata found for this animal.")
            return
        df = pd.DataFrame(rows)
        path, _ = QFileDialog.getSaveFileName(self, "Save CSV", f"{animal}_summary.csv", "CSV (*.csv)")
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        df.to_csv(path, index=False)
        QMessageBox.information(self, "Saved", f"Animal summary saved:\n{path}")

def launch():
    app = QApplication([])
    win = MainWindow()
    win.show()
    app.exec()
