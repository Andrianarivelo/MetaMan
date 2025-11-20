import json
import os
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QListWidget, QFileDialog, QMessageBox, QTableWidget, QTableWidgetItem,
    QSplitter
)

from ..state import AppState
from ..models import SessionMetadata
from ..services.file_scanner import scan_file_list
from ..io_ops import save_session_triplet, load_session_metadata
from ..utils import LogEmitter, run_in_thread

def dict_to_table(tbl: QTableWidget, data: Dict):
    tbl.setRowCount(0)
    for k, v in data.items():
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setItem(r, 0, QTableWidgetItem(str(k)))
        tbl.setItem(r, 1, QTableWidgetItem(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v)))

def table_to_dict(tbl: QTableWidget) -> Dict[str, str]:
    out = {}
    for r in range(tbl.rowCount()):
        k = (tbl.item(r, 0).text() if tbl.item(r, 0) else "").strip()
        if not k:
            continue
        v = tbl.item(r, 1).text() if tbl.item(r, 1) else ""
        out[k] = v
    return out

class RecordingTab(QWidget):
    """
    Layout update:
      - Main horizontal QSplitter: LEFT = metadata editor; RIGHT = (small) trial panel + log.
      - LEFT has its own vertical splitter: top = editable table + controls; bottom = JSON preview.
      - RIGHT has its own vertical splitter: top = trial controls/list; bottom = log.
      - All panels resizable.
    """
    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.meta: Dict = {}
        self._build_ui()
        if self.app_state.current_session_path and os.path.isdir(self.app_state.current_session_path):
            self.load_session(self.app_state.current_session_path)

    def _build_ui(self):
        root = QHBoxLayout(self)

        # Main horizontal splitter
        main_split = QSplitter(Qt.Horizontal)
        root.addWidget(main_split)

        # ----- LEFT: metadata editor side (own vertical splitter) -----
        left_panel = QWidget()
        left_vbox = QVBoxLayout(left_panel)

        # Controls row 1: root + new recording
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Root dir:"))
        self.ed_root = QLineEdit(self.app_state.settings.raw_root); row1.addWidget(self.ed_root, 1)
        b_browse = QPushButton("Browse…"); b_browse.clicked.connect(self._choose_root); row1.addWidget(b_browse)
        b_new = QPushButton("New recording"); b_new.clicked.connect(self.new_recording); row1.addWidget(b_new)
        left_vbox.addLayout(row1)

        # Controls row 2: project/animal/session
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Project")); self.ed_proj = QLineEdit(); row2.addWidget(self.ed_proj)
        row2.addWidget(QLabel("Animal")); self.ed_animal = QLineEdit(); row2.addWidget(self.ed_animal)
        row2.addWidget(QLabel("Session")); self.ed_session = QLineEdit(); row2.addWidget(self.ed_session)
        left_vbox.addLayout(row2)

        # Editable table for metadata
        self.tbl_meta = QTableWidget(0, 2)
        self.tbl_meta.setHorizontalHeaderLabels(["Key", "Value"])
        self.tbl_meta.horizontalHeader().setStretchLastSection(True)

        # Buttons under table
        tbl_btns = QHBoxLayout()
        b_add_row = QPushButton("Add row"); b_add_row.clicked.connect(self._add_meta_row); tbl_btns.addWidget(b_add_row)
        b_rm_row = QPushButton("Remove selected"); b_rm_row.clicked.connect(self._rm_meta_row); tbl_btns.addWidget(b_rm_row)
        b_apply = QPushButton("Apply table → metadata"); b_apply.clicked.connect(self._apply_table_to_meta); tbl_btns.addWidget(b_apply)

        # Comments quick-save
        b_save_all = QPushButton("Save metadata (JSON/CSV/H5)"); b_save_all.clicked.connect(self._save_all)
        tbl_btns.addWidget(b_save_all)

        # Build the left vertical splitter
        left_split = QSplitter(Qt.Vertical)
        # Top widget holds table + its controls
        left_top = QWidget(); lt_layout = QVBoxLayout(left_top)
        lt_layout.addWidget(self.tbl_meta, 1)
        lt_layout.addLayout(tbl_btns)
        left_split.addWidget(left_top)

        # Bottom: JSON preview
        left_bottom = QWidget(); lb_layout = QVBoxLayout(left_bottom)
        lb_layout.addWidget(QLabel("metadata.json (preview)"))
        self.txt_preview = QTextEdit(); self.txt_preview.setReadOnly(True)
        mono = QFont("Consolas" if os.name == "nt" else "Monospace"); mono.setStyleHint(QFont.Monospace)
        self.txt_preview.setFont(mono)
        lb_layout.addWidget(self.txt_preview, 1)
        left_split.addWidget(left_bottom)

        left_split.setSizes([600, 300])
        left_vbox.addWidget(left_split, 1)

        main_split.addWidget(left_panel)

        # ----- RIGHT: small trial panel + log (own vertical splitter) -----
        right_panel = QWidget()
        right_vbox = QVBoxLayout(right_panel)

        # Top trial panel (compact)
        trial_top = QWidget(); t_layout = QVBoxLayout(trial_top)

        # Trial controls
        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Trial #")); self.ed_trial = QLineEdit(); self.ed_trial.setFixedWidth(60); row3.addWidget(self.ed_trial)
        row3.addWidget(QLabel("Type")); self.ed_trial_type = QLineEdit(); row3.addWidget(self.ed_trial_type, 1)
        b_add_trial = QPushButton("Add trial info"); b_add_trial.clicked.connect(self._add_trial_info); row3.addWidget(b_add_trial)
        b_update = QPushButton("Update file list"); b_update.clicked.connect(self.update_file_list); row3.addWidget(b_update)
        t_layout.addLayout(row3)

        # Comments quick row (kept here for convenience)
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Comments")); self.ed_comments = QLineEdit(); row4.addWidget(self.ed_comments, 1)
        b_save_comments = QPushButton("Save comments"); b_save_comments.clicked.connect(self._save_comments); row4.addWidget(b_save_comments)
        t_layout.addLayout(row4)

        # Trial list (small)
        t_layout.addWidget(QLabel("Trial info"))
        self.list_trials = QListWidget(); t_layout.addWidget(self.list_trials, 1)

        # Build right vertical splitter: top = trial panel, bottom = log
        right_split = QSplitter(Qt.Vertical)
        right_split.addWidget(trial_top)

        # Log area
        log_widget = QWidget(); lw = QVBoxLayout(log_widget)
        lw.addWidget(QLabel("Log"))
        self.txt_log = QTextEdit(); self.txt_log.setReadOnly(True)
        lw.addWidget(self.txt_log, 1)
        self.logger = LogEmitter(self.txt_log)
        right_split.addWidget(log_widget)
        right_split.setSizes([300, 300])

        right_vbox.addWidget(right_split, 1)

        main_split.addWidget(right_panel)
        # Make trial side small by default
        main_split.setSizes([900, 350])

    # ---------------- helpers ----------------

    def _choose_root(self):
        d = QFileDialog.getExistingDirectory(self, "Choose root directory", self.ed_root.text() or "")
        if d:
            self.ed_root.setText(d)
            self.app_state.settings.raw_root = d

    def _session_dir(self) -> str:
        return os.path.join(self.ed_root.text(), self.ed_proj.text(), self.ed_animal.text(), self.ed_session.text())

    def _refresh_preview(self):
        self.txt_preview.setPlainText(json.dumps(self.meta, indent=2, ensure_ascii=False))
        dict_to_table(self.tbl_meta, self.meta)

    # ---------------- external ----------------

    def load_session(self, session_dir: str):
        meta = load_session_metadata(session_dir) or {}
        if not meta:
            project = os.path.basename(os.path.dirname(os.path.dirname(session_dir)))
            animal = os.path.basename(os.path.dirname(session_dir))
            session = os.path.basename(session_dir)
            meta = SessionMetadata.new(project, animal, session, self.ed_root.text()).data
        self.meta = meta
        # fill fields
        self.ed_root.setText(meta.get("RootDir", self.app_state.settings.raw_root))
        self.ed_proj.setText(meta.get("Project", ""))
        self.ed_animal.setText(meta.get("Animal", ""))
        self.ed_session.setText(meta.get("Session", ""))
        self.ed_comments.setText(meta.get("Comments", ""))
        self.list_trials.clear()
        for k, v in (meta.get("trial_info") or {}).items():
            self.list_trials.addItem(f"Trial {k}: {v}")
        self.app_state.setCurrent = getattr(self.app_state, "set_current")  # safety for older code
        self.app_state.set_current(project=meta.get("Project", ""), animal=meta.get("Animal", ""),
                                   session=meta.get("Session", ""), session_path=session_dir)
        self._refresh_preview()
        self.logger.log(f"Loaded session: {session_dir}")

    # ---------------- actions ----------------

    def new_recording(self):
        root = self.ed_root.text().strip()
        project = self.ed_proj.text().strip()
        animal = self.ed_animal.text().strip()
        session = self.ed_session.text().strip()
        if not (root and project and animal and session):
            QMessageBox.warning(self, "Missing fields", "Fill Project, Animal, Session.")
            return
        # ensure dirs
        project_dir = os.path.join(root, project)
        animal_dir = os.path.join(project_dir, animal)
        session_dir = os.path.join(animal_dir, session)
        for d in (project_dir, animal_dir, session_dir):
            os.makedirs(d, exist_ok=True)
        meta = SessionMetadata.new(project, animal, session, root).data
        self.meta = meta
        save_session_triplet(session_dir, self.meta, logger=self.logger.log)
        self.load_session(session_dir)

    def update_file_list(self):
        session_dir = self._session_dir()
        if not os.path.isdir(session_dir):
            QMessageBox.critical(self, "Not found", f"Session directory not found:\n{session_dir}")
            return

        def work():
            file_list = scan_file_list(session_dir)
            self.meta["file_list"] = file_list
            save_session_triplet(session_dir, self.meta, logger=self.logger.log)
            # annotate server presence if server root known
            srv_root = self.app_state.settings.get_server_root_for_project(self.meta.get("Project", ""))
            if srv_root and os.path.isdir(srv_root):
                proj = self.meta.get("Project", "")
                animal = self.meta.get("Animal", "")
                session = self.meta.get("Session", "")
                server_proj = os.path.join(srv_root, proj)
                for item in self.meta["file_list"]:
                    spath = item["path"].replace(session_dir, os.path.join(server_proj, animal, session))
                    item["server_path"] = spath if os.path.exists(spath) else ""
                save_session_triplet(session_dir, self.meta, logger=self.logger.log)
                self.logger.log("Server presence annotated in metadata.")
            self._refresh_preview()
            self.logger.log("File list updated.")

        run_in_thread(work)

    def _add_trial_info(self):
        t = self.ed_trial.text().strip()
        tt = self.ed_trial_type.text().strip()
        if not t:
            QMessageBox.warning(self, "Trial", "Enter trial number.")
            return
        self.meta.setdefault("trial_info", {})[str(int(t))] = tt
        self.list_trials.addItem(f"Trial {t}: {tt}")
        save_session_triplet(self._session_dir(), self.meta, logger=self.logger.log)
        self._refresh_preview()

    def _save_comments(self):
        self.meta["Comments"] = self.ed_comments.text()
        save_session_triplet(self._session_dir(), self.meta, logger=self.logger.log)
        self._refresh_preview()

    def _save_all(self):
        save_session_triplet(self._session_dir(), self.meta, logger=self.logger.log)
        self._refresh_preview()

    # ---------------- metadata table controls ----------------

    def _add_meta_row(self):
        r = self.tbl_meta.rowCount()
        self.tbl_meta.insertRow(r)
        self.tbl_meta.setItem(r, 0, QTableWidgetItem(""))
        self.tbl_meta.setItem(r, 1, QTableWidgetItem(""))

    def _rm_meta_row(self):
        rows = sorted({i.row() for i in self.tbl_meta.selectedIndexes()}, reverse=True)
        for r in rows:
            self.tbl_meta.removeRow(r)

    def _apply_table_to_meta(self):
        """Push changes from table into self.meta, parsing JSON for lists/dicts and numbers when possible."""
        flat = table_to_dict(self.tbl_meta)
        new_meta: Dict[str, Any] = {}
        for k, v in flat.items():
            # try JSON (for dict/list/numbers/bools/null)
            try:
                new_meta[k] = json.loads(v)
                continue
            except Exception:
                pass
            # try int/float
            try:
                if "." in v:
                    new_meta[k] = float(v)
                else:
                    new_meta[k] = int(v)
                continue
            except Exception:
                pass
            new_meta[k] = v
        self.meta = new_meta
        save_session_triplet(self._session_dir(), self.meta, logger=self.logger.log)
        self._refresh_preview()
