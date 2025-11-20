import os
import re
from typing import Dict, Any, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QTreeWidget, QTreeWidgetItem, QPushButton,
    QLabel, QFileDialog, QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem,
    QLineEdit, QSplitter
)

from ..state import AppState
from ..io_ops import (
    list_projects, load_project_info, save_project_info,
    load_animal_info, save_animal_info, load_session_metadata
)

# ---------------- CSV/XLS helpers (robust) ----------------

def _norm_header(s: str) -> str:
    """Lower, strip, remove BOM and non-alnum to normalize header names."""
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\ufeff", "")  # strip BOM
    s = s.strip().lower()
    return re.sub(r"[^a-z0-9]+", "", s)

def read_tabular_any(path: str):
    """
    Read CSV or Excel robustly.
    """
    import pandas as pd
    ext = os.path.splitext(path)[1].lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        try:
            return pd.read_excel(path, engine="openpyxl")
        except Exception:
            return pd.read_excel(path)
    encodings = ["utf-8-sig", "utf-16", "utf-16le", "utf-16be", "cp1252", "latin-1"]
    last_err = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, sep=None, engine="python")
        except Exception as e:
            last_err = e
    try:
        return pd.read_csv(path, encoding="latin-1")
    except Exception:
        if last_err:
            raise last_err
        raise

def ensure_id_header(df):
    """Try to promote a first non-empty row to header if no ID-like column is found."""
    def has_id(frame) -> bool:
        norms = [_norm_header(c) for c in frame.columns]
        wanted = {"id", "animalid", "animal_id", "mouseid", "subject", "subjectid"}
        if any(n in wanted for n in norms):
            return True
        return any(n.endswith("id") and len(n) >= 2 for n in norms)

    if has_id(df):
        return df

    if any(str(c).lower().startswith("unnamed") or isinstance(c, (int, float)) for c in df.columns):
        for ridx in range(min(5, len(df))):
            row_vals = list(df.iloc[ridx].astype(str))
            if sum((v.strip() != "" and v.lower() != "nan") for v in row_vals) >= 2:
                new_cols = [v.replace("\ufeff", "").strip() for v in row_vals]
                new_df = df.iloc[ridx + 1:].copy()
                new_df.columns = new_cols
                if has_id(new_df):
                    return new_df.reset_index(drop=True)
                break
    return df

def find_id_column_smart(df) -> Optional[str]:
    cmap = {_norm_header(str(c)): str(c) for c in df.columns}
    for key in ("id", "animalid", "animal_id", "mouseid", "subject", "subjectid"):
        if key in cmap:
            return cmap[key]
    for norm, orig in cmap.items():
        if norm.endswith("id") and len(norm) >= 2:
            return orig
    return None

# ---------------- UI helpers ----------------

def table_to_dict(tbl: QTableWidget) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for r in range(tbl.rowCount()):
        kitem = tbl.item(r, 0)
        vitem = tbl.item(r, 1)
        k = (kitem.text() if kitem else "").strip()
        if not k:
            continue
        out[k] = vitem.text() if vitem else ""
    return out

def dict_to_table(tbl: QTableWidget, data: Dict[str, Any]):
    tbl.setRowCount(0)
    for k, v in data.items():
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setItem(r, 0, QTableWidgetItem(str(k)))
        tbl.setItem(r, 1, QTableWidgetItem(v if isinstance(v, str) else str(v)))
    tbl.resizeColumnsToContents()

def human_size(n: int) -> str:
    if n is None:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    return f"{f:.2f} {units[i]}"

def canon_path(path: str) -> str:
    """Normalize slashes and UNC for the current OS; prefer backslashes on Windows."""
    p = os.path.normpath(path)
    if os.name == "nt":
        # Ensure backslashes for UNC/network paths too
        p = p.replace("/", "\\")
    return p

# ---------------- Navigation Tab ----------------

class NavigationTab(QWidget):
    """Navigation with root dir chooser, lazy tree, and three info subtabs on the right."""
    DUMMY_CHILD_TEXT = "..."

    def __init__(self, app_state: AppState, on_load_session):
        super().__init__()
        self.app_state = app_state
        self.on_load_session = on_load_session
        self._build_ui()
        self.refresh_tree(collapsed=True, lazy=True)

    # ---------- Build UI (splitter for resizable panels) ----------

    def _build_ui(self):
        root = QHBoxLayout(self)

        splitter = QSplitter(Qt.Horizontal)
        root.addWidget(splitter)

        # LEFT PANEL
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)

        # Root dir controls
        row_root = QHBoxLayout()
        row_root.addWidget(QLabel("Root dir:"))
        self.ed_root = QLineEdit(self.app_state.settings.raw_root)
        row_root.addWidget(self.ed_root, 1)
        b_browse_root = QPushButton("Browse…")
        b_browse_root.clicked.connect(self._choose_root)
        row_root.addWidget(b_browse_root)
        b_reload = QPushButton("Reload")
        b_reload.clicked.connect(lambda: self.refresh_tree(collapsed=True, lazy=True))
        row_root.addWidget(b_reload)
        left_layout.addLayout(row_root)

        # Tree
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemSelectionChanged.connect(self._on_select)
        self.tree.itemExpanded.connect(self._on_item_expanded)
        left_layout.addWidget(self.tree, 1)

        # Buttons under tree
        btns = QHBoxLayout()
        b_open = QPushButton("Open folder")
        b_open.clicked.connect(self._open_selected_folder)
        btns.addWidget(b_open)
        b_copy = QPushButton("Copy path")
        b_copy.clicked.connect(self._copy_selected_path)
        btns.addWidget(b_copy)
        b_load = QPushButton("Load in Recording/Preprocessing")
        b_load.clicked.connect(self._load_selected_session)
        btns.addWidget(b_load)
        left_layout.addLayout(btns)

        splitter.addWidget(left_panel)

        # RIGHT PANEL (tabs)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.right_tabs = QTabWidget()
        right_layout.addWidget(self.right_tabs)

        # Project tab
        self.tab_proj = QWidget()
        self._build_project_info(self.tab_proj)
        self.right_tabs.addTab(self.tab_proj, "Project Info")

        # Animal tab
        self.tab_animal = QWidget()
        self._build_animal_info(self.tab_animal)
        self.right_tabs.addTab(self.tab_animal, "Animal Info")

        # Session tab
        self.tab_session = QWidget()
        self._build_session_info(self.tab_session)
        self.right_tabs.addTab(self.tab_session, "Session Metadata")

        splitter.addWidget(right_panel)
        splitter.setSizes([450, 800])

    # ---------- Sub-panels ----------

    def _build_project_info(self, w: QWidget):
        from PySide6.QtWidgets import QFormLayout
        lay = QVBoxLayout(w)
        form_top = QFormLayout()
        self.lbl_proj = QLabel("-")
        form_top.addRow("Project:", self.lbl_proj)
        lay.addLayout(form_top)

        self.tbl_proj = QTableWidget(0, 2)
        self.tbl_proj.setHorizontalHeaderLabels(["Key", "Value"])
        self.tbl_proj.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl_proj, 1)

        bar = QHBoxLayout()
        b_add = QPushButton("Add row")
        b_add.clicked.connect(lambda: self._add_row(self.tbl_proj))
        bar.addWidget(b_add)
        b_rm = QPushButton("Remove selected")
        b_rm.clicked.connect(lambda: self._remove_selected(self.tbl_proj))
        bar.addWidget(b_rm)
        b_save = QPushButton("Save project info")
        b_save.clicked.connect(self._save_project_info)
        bar.addWidget(b_save)
        b_csv = QPushButton("Load animal infos from CSV…")
        b_csv.clicked.connect(self._load_animal_csv)
        bar.addWidget(b_csv)
        lay.addLayout(bar)

    def _build_animal_info(self, w: QWidget):
        lay = QVBoxLayout(w)
        self.lbl_animal = QLabel("Animal: -")
        lay.addWidget(self.lbl_animal)

        self.tbl_animal = QTableWidget(0, 2)
        self.tbl_animal.setHorizontalHeaderLabels(["Key", "Value"])
        self.tbl_animal.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl_animal, 1)

        row = QHBoxLayout()
        b_add = QPushButton("Add row")
        b_add.clicked.connect(lambda: self._add_row(self.tbl_animal))
        row.addWidget(b_add)
        b_rm = QPushButton("Remove selected")
        b_rm.clicked.connect(lambda: self._remove_selected(self.tbl_animal))
        row.addWidget(b_rm)
        b_add_surg = QPushButton("Add surgery")
        b_add_surg.clicked.connect(lambda: self._add_struct_item("surgeries"))
        row.addWidget(b_add_surg)
        b_add_treat = QPushButton("Add treatment")
        b_add_treat.clicked.connect(lambda: self._add_struct_item("treatments"))
        row.addWidget(b_add_treat)
        b_save = QPushButton("Save animal info")
        b_save.clicked.connect(self._save_animal_info)
        row.addWidget(b_save)
        lay.addLayout(row)

        row2 = QHBoxLayout()
        b_csv = QPushButton("Load this animal from CSV…")
        b_csv.clicked.connect(self._load_animal_csv)
        row2.addWidget(b_csv)
        lay.addLayout(row2)

    def _build_session_info(self, w: QWidget):
        lay = QVBoxLayout(w)
        self.lbl_session_path = QLabel("")
        lay.addWidget(self.lbl_session_path)
        self.tbl_session = QTableWidget(0, 2)
        self.tbl_session.setHorizontalHeaderLabels(["Key", "Value"])
        self.tbl_session.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(self.tbl_session, 1)
        row = QHBoxLayout()
        b_add = QPushButton("Add row")
        b_add.clicked.connect(lambda: self._add_row(self.tbl_session))
        row.addWidget(b_add)
        b_rm = QPushButton("Remove selected")
        b_rm.clicked.connect(lambda: self._remove_selected(self.tbl_session))
        row.addWidget(b_rm)
        lay.addLayout(row)

    # ---------- Root dir change ----------

    def _choose_root(self):
        d = QFileDialog.getExistingDirectory(self, "Choose root directory", self.ed_root.text() or "")
        if not d:
            return
        self.ed_root.setText(canon_path(d))
        self.app_state.settings.raw_root = canon_path(d)
        self.refresh_tree(collapsed=True, lazy=True)

    # ---------- Tree (lazy) ----------

    def refresh_tree(self, collapsed=True, lazy=True):
        self.tree.clear()
        raw_root = self.app_state.settings.raw_root
        for proj in list_projects(raw_root):
            proj_dir = canon_path(os.path.join(raw_root, proj))
            pitem = QTreeWidgetItem([proj])
            pitem.setData(0, Qt.UserRole, ("project", proj_dir))
            self.tree.addTopLevelItem(pitem)
            if lazy:
                dummy = QTreeWidgetItem([self.DUMMY_CHILD_TEXT])
                pitem.addChild(dummy)
            else:
                self._populate_project_children(pitem, proj_dir)
        if collapsed:
            self.tree.collapseAll()
        last = self.app_state.settings.last_opened_project
        if last:
            for i in range(self.tree.topLevelItemCount()):
                item = self.tree.topLevelItem(i)
                if item.text(0) == last:
                    self.tree.setCurrentItem(item)
                    self._on_select()
                    break

    def _on_item_expanded(self, item: QTreeWidgetItem):
        data = item.data(0, Qt.UserRole)
        if not data:
            return
        kind, path = data
        if kind != "project":
            return
        if item.childCount() == 1 and item.child(0).text(0) == self.DUMMY_CHILD_TEXT:
            item.takeChild(0)
            self._populate_project_children(item, path)

    def _populate_project_children(self, pitem: QTreeWidgetItem, proj_dir: str):
        try:
            animals = sorted([d for d in os.listdir(proj_dir) if os.path.isdir(os.path.join(proj_dir, d))])
        except Exception:
            animals = []
        for animal in animals:
            adir = canon_path(os.path.join(proj_dir, animal))
            aitem = QTreeWidgetItem([animal])
            aitem.setData(0, Qt.UserRole, ("animal", adir))
            pitem.addChild(aitem)
            try:
                sessions = sorted([d for d in os.listdir(adir) if os.path.isdir(os.path.join(adir, d))])
            except Exception:
                sessions = []
            for sess in sessions:
                sdir = canon_path(os.path.join(adir, sess))
                sitem = QTreeWidgetItem([sess])
                sitem.setData(0, Qt.UserRole, ("session", sdir))
                aitem.addChild(sitem)

    # ---------- Selection ----------

    def _get_selected(self) -> Optional[Tuple[str, str, str]]:
        items = self.tree.selectedItems()
        if not items:
            return None
        item = items[0]
        data = item.data(0, Qt.UserRole)
        if not data:
            return None
        kind, path = data
        return kind, path, item.text(0)

    def _on_select(self):
        sel = self._get_selected()
        if not sel:
            return
        kind, path, text = sel
        if kind == "project":
            self.app_state.settings.last_opened_project = text
            self.lbl_proj.setText(text)
            info = load_project_info(path)
            combined = {**self._project_stats(path), **info}
            dict_to_table(self.tbl_proj, combined)
            self.right_tabs.setCurrentIndex(0)
        elif kind == "animal":
            self.lbl_animal.setText(f"Animal: {text}")
            info = load_animal_info(path)
            info.setdefault("age", ""); info.setdefault("sex", ""); info.setdefault("genotype", "")
            info.setdefault("surgeries", []); info.setdefault("treatments", [])
            flat = {
                **self._animal_stats(path),
                "age": info["age"],
                "sex": info["sex"],
                "genotype": info["genotype"],
                "surgeries": str(info["surgeries"]),
                "treatments": str(info["treatments"]),
            }
            dict_to_table(self.tbl_animal, flat)
            self.right_tabs.setCurrentIndex(1)
        elif kind == "session":
            meta = load_session_metadata(path) or {}
            self.lbl_session_path.setText(path)
            dict_to_table(self.tbl_session, meta)
            self.right_tabs.setCurrentIndex(2)

    # ---------- Stats (summaries) ----------

    def _project_stats(self, proj_dir: str) -> Dict[str, Any]:
        animals = []
        sessions_per_animal = {}
        sessions_total = 0
        experiments = set()
        experimenters = set()
        dt_list = []
        total_files = 0
        total_size = 0

        try:
            animals = [d for d in os.listdir(proj_dir) if os.path.isdir(os.path.join(proj_dir, d))]
        except Exception:
            animals = []

        for a in animals:
            adir = os.path.join(proj_dir, a)
            sessions = [d for d in os.listdir(adir) if os.path.isdir(os.path.join(adir, d))]
            sessions_per_animal[a] = len(sessions)
            sessions_total += len(sessions)
            for s in sessions:
                sdir = os.path.join(adir, s)
                meta = load_session_metadata(sdir) or {}
                if "Experiment" in meta and meta["Experiment"]:
                    experiments.add(str(meta["Experiment"]))
                if "Experimenter" in meta and meta["Experimenter"]:
                    experimenters.add(str(meta["Experimenter"]))
                if "DateTime" in meta and meta["DateTime"]:
                    dt_list.append(str(meta["DateTime"]))
                fl = meta.get("file_list") or []
                total_files += len(fl)
                for item in fl:
                    if isinstance(item, dict):
                        sz = item.get("size")
                        if isinstance(sz, int):
                            total_size += sz

        first_dt = min(dt_list) if dt_list else ""
        last_dt = max(dt_list) if dt_list else ""

        return {
            "_stat_animals_count": len(animals),
            "_stat_sessions_total": sessions_total,
            "_stat_sessions_per_animal": sessions_per_animal,
            "_stat_experiments": ", ".join(sorted(experiments)) if experiments else "",
            "_stat_experimenters": ", ".join(sorted(experimenters)) if experimenters else "",
            "_stat_first_session": first_dt,
            "_stat_last_session": last_dt,
            "_stat_total_files": total_files,
            "_stat_total_size_bytes": total_size,
            "_stat_total_size_human": human_size(total_size),
        }

    def _animal_stats(self, animal_dir: str) -> Dict[str, Any]:
        sessions = [d for d in os.listdir(animal_dir) if os.path.isdir(os.path.join(animal_dir, d))]
        sessions_total = len(sessions)
        rec_types = set()
        dt_list = []
        total_files = 0
        total_size = 0
        for s in sessions:
            sdir = os.path.join(animal_dir, s)
            meta = load_session_metadata(sdir) or {}
            rt = (meta.get("Recording") or "").strip()
            if rt:
                rec_types.add(rt)
            if "DateTime" in meta and meta["DateTime"]:
                dt_list.append(str(meta["DateTime"]))
            fl = meta.get("file_list") or []
            total_files += len(fl)
            for item in fl:
                if isinstance(item, dict):
                    sz = item.get("size")
                    if isinstance(sz, int):
                        total_size += sz
        first_dt = min(dt_list) if dt_list else ""
        last_dt = max(dt_list) if dt_list else ""
        return {
            "_stat_sessions_total": sessions_total,
            "_stat_recording_types": ", ".join(sorted(rec_types)) if rec_types else "",
            "_stat_first_session": first_dt,
            "_stat_last_session": last_dt,
            "_stat_files_count": total_files,
            "_stat_size_bytes": total_size,
            "_stat_size_human": human_size(total_size),
        }

    # ---------- Buttons under tree ----------

    def _open_selected_folder(self):
        """
        Open the selected path robustly:
          - normalize slashes/UNC
          - if path doesn't exist, try its parent
          - Windows: prefer os.startfile, fallback to explorer
          - macOS: open
          - Linux: xdg-open
        """
        sel = self._get_selected()
        if not sel:
            return
        raw_path = sel[1]
        path = canon_path(raw_path)

        # If it's a file or missing, try to open an existing directory
        target = path
        if not os.path.exists(target):
            parent = canon_path(os.path.dirname(target))
            if os.path.exists(parent):
                target = parent
            else:
                # Try replacing slashes more aggressively on Windows UNC
                if os.name == "nt":
                    alt = path.replace("/", "\\")
                    if os.path.exists(alt):
                        target = alt
                    else:
                        QMessageBox.critical(self, "Path not found", f"Cannot find:\n{path}")
                        return
                else:
                    QMessageBox.critical(self, "Path not found", f"Cannot find:\n{path}")
                    return

        # Open with OS-specific method
        try:
            if os.name == "nt":
                # Prefer startfile; if it fails, fallback to explorer
                try:
                    os.startfile(target)  # type: ignore[attr-defined]
                except Exception:
                    import subprocess
                    subprocess.run(["explorer", target])
            elif sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", target])
            else:
                import subprocess
                subprocess.run(["xdg-open", target])
        except Exception as e:
            QMessageBox.critical(self, "Open error", f"Failed to open:\n{target}\n\n{e}")

    def _copy_selected_path(self):
        sel = self._get_selected()
        if not sel:
            return
        from PySide6.QtGui import QGuiApplication
        path = canon_path(sel[1])
        QGuiApplication.clipboard().setText(path)
        QMessageBox.information(self, "Path copied", path)

    def _load_selected_session(self):
        sel = self._get_selected()
        if not sel:
            return
        kind, path, text = sel
        if kind != "session":
            QMessageBox.warning(self, "Select session", "Please select a session node.")
            return
        animal_dir = os.path.dirname(path)
        project_dir = os.path.dirname(animal_dir)
        session = os.path.basename(path)
        animal = os.path.basename(animal_dir)
        project = os.path.basename(project_dir)
        self.app_state.set_current(project=project, animal=animal, session=session, session_path=path)
        self.on_load_session(path)

    # ---------- Table helpers ----------

    def _add_row(self, tbl: QTableWidget):
        r = tbl.rowCount()
        tbl.insertRow(r)
        tbl.setItem(r, 0, QTableWidgetItem(""))
        tbl.setItem(r, 1, QTableWidgetItem(""))

    def _remove_selected(self, tbl: QTableWidget):
        rows = sorted({i.row() for i in tbl.selectedIndexes()}, reverse=True)
        for r in rows:
            tbl.removeRow(r)

    def _save_project_info(self):
        sel = self._get_selected()
        if not sel:
            return
        kind, path, text = sel
        if kind != "project":
            return
        data = table_to_dict(self.tbl_proj)
        for k in list(data.keys()):
            if k.startswith("_stat_"):
                data.pop(k, None)
        save_project_info(path, data)
        QMessageBox.information(self, "Saved", "Project info saved.")

    def _save_animal_info(self):
        sel = self._get_selected()
        if not sel:
            return
        kind, path, text = sel
        if kind != "animal":
            return
        existing = load_animal_info(path)
        edited = table_to_dict(self.tbl_animal)
        import ast
        for k in ("surgeries", "treatments"):
            if k in edited:
                try:
                    edited[k] = ast.literal_eval(edited[k])
                except Exception:
                    edited[k] = existing.get(k, [])
        for k in list(edited.keys()):
            if k.startswith("_stat_"):
                edited.pop(k, None)
        existing.update(edited)
        save_animal_info(path, existing)
        QMessageBox.information(self, "Saved", "Animal info saved.")

    # ---------- CSV importer (robust ID detection) ----------

    def _load_animal_csv(self):
        sel = self._get_selected()
        if not sel:
            return
        kind, path, text = sel
        if kind not in ("project", "animal"):
            QMessageBox.warning(self, "Select project/animal", "Select a project or an animal to import into.")
            return
        csv_path, _ = QFileDialog.getOpenFileName(self, "Choose CSV/Excel", "", "Tables (*.csv *.xlsx *.xls *.xlsm);;All files (*)")
        if not csv_path:
            return

        try:
            df = read_tabular_any(csv_path)
        except Exception as e:
            QMessageBox.critical(self, "Load error", f"Failed to read file:\n{e}")
            return

        df = ensure_id_header(df)
        id_col = find_id_column_smart(df)

        if not id_col:
            # last resort: try first row as header again
            try:
                first_row = [str(x) for x in list(df.iloc[0])]
                tmp_cols = [c.replace("\ufeff","").strip() for c in first_row]
                tmp_df = df.iloc[1:].copy()
                tmp_df.columns = tmp_cols
                id_col = find_id_column_smart(tmp_df)
                if id_col:
                    df = tmp_df.reset_index(drop=True)
            except Exception:
                pass

        if not id_col:
            QMessageBox.critical(self, "CSV format", "No 'ID' / '*id' column found (tolerates BOM, spaces, variants like Animal_ID/MouseID/SubjectID).")
            return

        def last5(x):
            s = str(x)
            return s[-5:] if len(s) >= 5 else s

        df["_ID5"] = df[id_col].map(last5)

        if kind == "project":
            animals = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
            count = 0
            for a in animals:
                a5 = last5(a)
                matches = df[df["_ID5"] == a5]
                if not matches.empty:
                    info = matches.iloc[0].to_dict()
                    adir = os.path.join(path, a)
                    existing = load_animal_info(adir)
                    for k, v in info.items():
                        if k == "_ID5":
                            continue
                        try:
                            if isinstance(v, float) and v != v:
                                v = ""
                        except Exception:
                            pass
                        existing[k] = v
                    save_animal_info(adir, existing)
                    count += 1
            QMessageBox.information(self, "Import complete", f"Updated {count} animals in project.")
        else:
            a = text
            a5 = last5(a)
            matches = df[df["_ID5"] == a5]
            if matches.empty:
                QMessageBox.warning(self, "No match", f"No rows with ID ending '{a5}'.")
                return
            info = matches.iloc[0].to_dict()
            existing = load_animal_info(path)
            for k, v in info.items():
                if k == "_ID5":
                    continue
                try:
                    if isinstance(v, float) and v != v:
                        v = ""
                except Exception:
                    pass
                existing[k] = v
            save_animal_info(path, existing)
            QMessageBox.information(self, "Import complete", f"Updated animal {a}.")
