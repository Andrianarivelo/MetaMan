import json
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QListWidget, QTextEdit, QComboBox, QMessageBox, QFileDialog, QSplitter,
    QTableWidget, QTableWidgetItem, QInputDialog
)

from ..state import AppState
from ..io_ops import save_session_triplet, load_session_metadata

# Step menus (kept as requested)
NPX_STEPS = ["spike_sorting", "curation", "histology", "time_sync", "dlc", "add_new_step"]
FIBER_STEPS = ["artefact_removal", "delta_F/F", "time_sync", "dlc", "add_new_step"]
BEHAV_STEPS = ["manual_scoring", "DLC", "lisbet", "dlc", "add_new_step"]


def dict_to_table(tbl: QTableWidget, data: Dict[str, Any]):
    tbl.setRowCount(0)
    for k, v in data.items():
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setItem(r, 0, QTableWidgetItem(str(k)))
        if isinstance(v, (dict, list)):
            tbl.setItem(r, 1, QTableWidgetItem(json.dumps(v, ensure_ascii=False)))
        else:
            tbl.setItem(r, 1, QTableWidgetItem("" if v is None else str(v)))
    tbl.resizeColumnsToContents()


class PreprocessingTab(QWidget):
    """
    Three-pane layout using a horizontal splitter:
      LEFT   : Steps list & controls
      CENTER : Parameters/Comments + Import params + Results folder
      RIGHT  : Session Info (read-only key/value table)

    - 'add_new_step' lets the user name a custom step.
    - 'Import params (CSV/JSON)' loads that file into the selected step's params.
    - 'Results folder' lets you store a path per step as 'results_dir'.
    """

    def __init__(self, app_state: AppState):
        super().__init__()
        self.app_state = app_state
        self.meta: Dict[str, Any] = {}
        self._build_ui()
        if self.app_state.current_session_path:
            self._load_from_session(self.app_state.current_session_path)

    # ------------------------ UI ------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Top bar: processed root + create folder (kept behavior)
        row = QHBoxLayout()
        row.addWidget(QLabel("Processed root:"))
        self.ed_proc_root = QLineEdit(self.app_state.settings.processed_root)
        row.addWidget(self.ed_proc_root, 1)
        b_create = QPushButton("Create folder")
        b_create.clicked.connect(self._create_processed_folder)
        row.addWidget(b_create)
        b_new = QPushButton("New preprocessing")
        b_new.clicked.connect(self._create_processed_folder)  # alias
        row.addWidget(b_new)
        root.addLayout(row)

        # Middle: 3 panels in a splitter
        split = QSplitter(Qt.Horizontal)
        root.addWidget(split, 1)

        # LEFT: steps & actions
        left = QWidget(); l = QVBoxLayout(left)
        l.addWidget(QLabel("Steps"))
        self.steps = QListWidget(); l.addWidget(self.steps, 1)
        rowL = QHBoxLayout()
        self.cb_step = QComboBox(); self.cb_step.addItems(BEHAV_STEPS); rowL.addWidget(self.cb_step)
        b_add = QPushButton("Add step"); b_add.clicked.connect(self._add_step); rowL.addWidget(b_add)
        b_done = QPushButton("Completed"); b_done.clicked.connect(self._mark_completed); rowL.addWidget(b_done)
        b_remove = QPushButton("Remove step"); b_remove.clicked.connect(self._remove_step); rowL.addWidget(b_remove)
        l.addLayout(rowL)
        split.addWidget(left)

        # CENTER: params/comments + import + results dir
        center = QWidget(); c = QVBoxLayout(center)

        # Params
        c.addWidget(QLabel("Parameters (JSON)"))
        self.txt_params = QTextEdit()
        c.addWidget(self.txt_params, 1)

        rowP = QHBoxLayout()
        b_save_params = QPushButton("Add/Update parameters"); b_save_params.clicked.connect(self._save_params)
        rowP.addWidget(b_save_params)
        b_import = QPushButton("Import params (CSV/JSON)"); b_import.clicked.connect(self._import_params_for_step)
        rowP.addWidget(b_import)
        c.addLayout(rowP)

        # Results folder selector per step
        c.addWidget(QLabel("Results folder (for this step)"))
        rowR = QHBoxLayout()
        self.ed_results_dir = QLineEdit()
        rowR.addWidget(self.ed_results_dir, 1)
        b_browse_results = QPushButton("Choose…"); b_browse_results.clicked.connect(self._select_results_dir)
        rowR.addWidget(b_browse_results)
        b_apply_results = QPushButton("Save results folder"); b_apply_results.clicked.connect(self._apply_results_dir)
        rowR.addWidget(b_apply_results)
        c.addLayout(rowR)

        # Comments
        c.addWidget(QLabel("Comments"))
        self.txt_comments = QTextEdit()
        c.addWidget(self.txt_comments, 1)
        b_save_comment = QPushButton("Save comment"); b_save_comment.clicked.connect(self._save_comment)
        c.addWidget(b_save_comment)

        split.addWidget(center)

        # RIGHT: session info panel (read-only)
        right = QWidget(); r = QVBoxLayout(right)
        r.addWidget(QLabel("Loaded Session Info"))
        self.tbl_session_info = QTableWidget(0, 2)
        self.tbl_session_info.setHorizontalHeaderLabels(["Key", "Value"])
        self.tbl_session_info.horizontalHeader().setStretchLastSection(True)
        r.addWidget(self.tbl_session_info, 1)
        split.addWidget(right)

        split.setSizes([350, 600, 450])

        # Hook step selection
        self.steps.currentRowChanged.connect(self._update_param_comment)

    # ------------------------ Session load / step menu ------------------------

    def _determine_step_choices(self) -> List[str]:
        rec = (self.meta.get("Recording") or "").lower()
        if "npx" in rec or "neuro" in rec:
            return NPX_STEPS
        if "fiber" in rec:
            return FIBER_STEPS
        return BEHAV_STEPS

    def _load_from_session(self, session_dir: str):
        self.meta = load_session_metadata(session_dir) or {}
        self._refresh_steps()
        # update choices
        self.cb_step.clear()
        self.cb_step.addItems(self._determine_step_choices())
        # refresh session info panel
        dict_to_table(self.tbl_session_info, self.meta)

    def _refresh_steps(self):
        self.steps.clear()
        for s in self.meta.get("preprocessing", []):
            name = s.get("name", "")
            status = s.get("status", "")
            self.steps.addItem(f"{name} [{status}]")

    def _current_step(self) -> Optional[Dict[str, Any]]:
        row = self.steps.currentRow()
        if row < 0:
            return None
        # robust match by name inside brackets
        text = self.steps.item(row).text()
        name = text.split(" [", 1)[0]
        for s in self.meta.get("preprocessing", []):
            if s.get("name") == name:
                return s
        return None

    # ------------------------ Top controls ------------------------

    def _create_processed_folder(self):
        """Create processed folder structure and copy current metadata triplet."""
        proj = self.meta.get("Project", "")
        animal = self.meta.get("Animal", "")
        session = self.meta.get("Session", "")
        root = self.ed_proc_root.text().strip()
        if not (proj and animal and session and root):
            QMessageBox.warning(self, "Missing", "Missing processed root or session info.")
            return
        session_proc = os.path.join(root, proj, animal, session)
        os.makedirs(session_proc, exist_ok=True)
        save_session_triplet(session_proc, self.meta)
        self.app_state.settings.processed_root = root
        QMessageBox.information(self, "Created", f"Processed session created:\n{session_proc}")

    # ------------------------ Step actions ------------------------

    def _add_step(self):
        choice = self.cb_step.currentText().strip()
        if not choice:
            return
        if choice == "add_new_step":
            name, ok = QInputDialog.getText(self, "New step", "Step name:")
            if not ok or not name.strip():
                return
            step_name = name.strip()
        else:
            step_name = choice

        # Avoid duplicates with same name
        for s in self.meta.get("preprocessing", []):
            if s.get("name") == step_name:
                QMessageBox.information(self, "Exists", f"Step '{step_name}' already exists.")
                return

        step = {"name": step_name, "params": {}, "comments": "", "status": "in_progress"}
        self.meta.setdefault("preprocessing", []).append(step)
        save_session_triplet(self.app_state.current_session_path, self.meta)
        self._refresh_steps()
        # select newly added
        self.steps.setCurrentRow(self.steps.count() - 1)

    def _remove_step(self):
        cur = self._current_step()
        if not cur:
            return
        name = cur.get("name", "")
        steps = self.meta.get("preprocessing", [])
        steps = [s for s in steps if s.get("name") != name]
        self.meta["preprocessing"] = steps
        save_session_triplet(self.app_state.current_session_path, self.meta)
        self._refresh_steps()
        self.txt_params.clear()
        self.txt_comments.clear()
        self.ed_results_dir.clear()

    def _mark_completed(self):
        cur = self._current_step()
        if not cur:
            return
        cur["status"] = "completed"
        save_session_triplet(self.app_state.current_session_path, self.meta)
        self._refresh_steps()

    def _update_param_comment(self):
        cur = self._current_step()
        if not cur:
            return
        # Update center widgets from selected step
        self.txt_params.setText(json.dumps(cur.get("params", {}), indent=2))
        self.txt_comments.setText(cur.get("comments", ""))
        self.ed_results_dir.setText(cur.get("results_dir", ""))

    # ------------------------ Params & comments ------------------------

    def _save_params(self):
        cur = self._current_step()
        if not cur:
            return
        try:
            params = json.loads(self.txt_params.toPlainText() or "{}")
        except Exception as e:
            QMessageBox.critical(self, "JSON error", str(e))
            return
        cur["params"] = params
        save_session_triplet(self.app_state.current_session_path, self.meta)

    def _save_comment(self):
        cur = self._current_step()
        if not cur:
            return
        txt = self.txt_comments.toPlainText().strip()
        cur["comments"] = txt
        save_session_triplet(self.app_state.current_session_path, self.meta)

    # ------------------------ Import params (CSV/JSON) ------------------------

    def _import_params_for_step(self):
        """
        Load params for the selected step:
          - JSON: expect a dict (stored as-is) OR a list (stored as-is).
          - CSV : preferred formats:
                * two-column ['key','value'] (case-insensitive)
                * a single-row table -> dict of {col: value}
                * multi-row table -> list of row dicts
        """
        cur = self._current_step()
        if not cur:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Choose CSV/JSON", "", "Tables (*.csv *.json);;All files (*)")
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        try:
            if ext == ".json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cur["params"] = data
            elif ext == ".csv":
                import pandas as pd
                # try robust encodings
                df = None
                for enc in ["utf-8-sig", "utf-16", "utf-16le", "utf-16be", "latin-1", "cp1252"]:
                    try:
                        df = pd.read_csv(path, encoding=enc, sep=None, engine="python")
                        break
                    except Exception:
                        continue
                if df is None:
                    df = pd.read_csv(path)  # let it error if truly unreadable

                cols_lower = {str(c).strip().lower(): c for c in df.columns}
                if "key" in cols_lower and "value" in cols_lower:
                    kcol, vcol = cols_lower["key"], cols_lower["value"]
                    params = {}
                    for _, row in df.iterrows():
                        k = str(row.get(kcol, "")).strip()
                        if not k:
                            continue
                        v = row.get(vcol, "")
                        # try JSON parsing per-cell for structured values
                        try:
                            v = json.loads(v)
                        except Exception:
                            v = "" if (isinstance(v, float) and v != v) else v
                        params[k] = v
                    cur["params"] = params
                else:
                    # if single-row -> dict; else list of dicts
                    if len(df) == 1:
                        rec = df.iloc[0].to_dict()
                        # convert NaN → ""
                        for k, v in rec.items():
                            if isinstance(v, float) and v != v:
                                rec[k] = ""
                        cur["params"] = rec
                    else:
                        records = df.to_dict(orient="records")
                        for rec in records:
                            for k, v in list(rec.items()):
                                if isinstance(v, float) and v != v:
                                    rec[k] = ""
                        cur["params"] = records
            else:
                QMessageBox.warning(self, "Format", "Please choose a .csv or .json file.")
                return
        except Exception as e:
            QMessageBox.critical(self, "Import error", f"Could not import params:\n{e}")
            return

        # Reflect in UI and save
        self.txt_params.setText(json.dumps(cur.get("params", {}), indent=2))
        save_session_triplet(self.app_state.current_session_path, self.meta)

    # ------------------------ Results folder per step ------------------------

    def _select_results_dir(self):
        cur = self._current_step()
        if not cur:
            return
        d = QFileDialog.getExistingDirectory(self, "Choose results folder", self.ed_results_dir.text() or "")
        if not d:
            return
        self.ed_results_dir.setText(d)

    def _apply_results_dir(self):
        cur = self._current_step()
        if not cur:
            return
        cur["results_dir"] = self.ed_results_dir.text().strip()
        save_session_triplet(self.app_state.current_session_path, self.meta)
