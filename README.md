# MetaMan

# MetaMan 🧠📁  
*A desktop metadata manager for electrophysiology, fiber photometry & behavior projects*

> MetaMan is a PySide6 desktop app for organizing **project / animal / session** metadata, tracking all generated files, documenting preprocessing steps, and synchronizing data to a server – all in a way that is reusable for analysis.

---

<!--
TODO: Hero screenshot
Replace with a real image, e.g.:

![MetaMan main window](docs/img/metaman-main-window.png)
-->

---

## Table of Contents

- [Why MetaMan?](#why-metaman)
- [Key Features](#key-features)
- [Data Model & Folder Structure](#data-model--folder-structure)
- [Installation](#installation)
- [Running the App](#running-the-app)
- [User Interface Overview](#user-interface-overview)
  - [Navigation Tab](#navigation-tab)
  - [Recording Tab](#recording-tab)
  - [Preprocessing Tab](#preprocessing-tab)
  - [Search / Query Dialog](#search--query-dialog)
- [Metadata Files & Formats](#metadata-files--formats)
  - [Session Metadata](#session-metadata)
  - [Animal Metadata](#animal-metadata)
  - [Project Metadata](#project-metadata)
  - [File List & Server Paths](#file-list--server-paths)
  - [Preprocessing Steps](#preprocessing-steps)
- [Copy to Server Workflow](#copy-to-server-workflow)
- [Importing Animal Info from CSV](#importing-animal-info-from-csv)
- [Adapting Legacy Data](#adapting-legacy-data)
- [Configuration](#configuration)
- [Development Notes](#development-notes)
- [Roadmap / Ideas](#roadmap--ideas)
- [License](#license)

---

## Why MetaMan?

In real neuroscience projects you typically have:

- Many **projects**
- Each with several **animals**
- Each animal with multiple **sessions** (and trials)
- Multiple **recording modalities** (NPX, fiber, behavior)
- A growing zoo of **analysis & preprocessing outputs**

Most of the pain is not in analysis itself but in:

- Remembering *what was recorded where*
- Keeping **metadata consistent** across sessions
- Tracking **which files belong to which session**
- Recording **preprocessing steps** (what was done, with which parameters, where results are stored)
- Synchronizing local raw data to a **central lab server**

MetaMan is designed to sit on top of your existing folder structure and give you:

> One place to **navigate, edit, query, and sync** all your metadata.

---

## Key Features

- **Project / Animal / Session navigation**
  - Root directory selection (local or server)
  - Tree: `Project → Animal → Session`
  - Summary stats for projects and animals (number of sessions, recording types, file counts, sizes…)

- **Recording metadata editor**
  - Default fields for typical experiments:
    - DateTime (auto on new recording)
    - Project, Animal, Experiment
    - Session, Trial number
    - Condition, Region, Recording type (NPX / fiber / behavior)
    - Experimenter, Room, Box
    - Comments (editable anytime)
  - Trial-level info (trial list, trial type)

- **Automatic file tracking**
  - `file_list` metadata for each session
  - Stores **absolute paths** for all files in the session directory
  - Can be updated with an **“Update file list”** button

- **Preprocessing tab**
  - Creates a `processedData` tree mirroring `rawData`
  - Predefined step menus per modality:
    - NPX: `spike_sorting`, `curation`, `histology`, `time_sync`, `add_new_step`
    - Fiber: `artefact_removal`, `delta_F/F`, `time_sync`, `add_new_step`
    - Behavior: `manual_scoring`, `DLC`, `lisbet`, `add_new_step`
  - For each step:
    - JSON parameters
    - Comments
    - Status (`in_progress` / `completed`)
    - Results folder path
    - Import parameters from **CSV or JSON**

- **Rich metadata formats**
  - Each session metadata saved as:
    - `metadata.json`
    - `metadata.csv`
    - `metadata.h5`
  - Auto-maintained **animal-level** and **project-level** summary metadata

- **Copy project to server**
  - Button to sync a local project folder to a server root
  - Only new files are copied
  - Logs progress and time taken
  - Annotates session metadata with **`server_path`** for each file

- **Flexible query dialog**
  - Build a **search index** over all sessions
  - Filter by:
    - Project / Animal (regex)
    - Session (single value or list)
    - Multiple metadata filters (Key + equals/contains/regex)
    - File name / glob / regex
  - Results shown in a table and exportable to CSV

- **Animal info from CSV**
  - Load animal metadata (age, sex, genotype, treatments, surgeries, etc.) from an external CSV/Excel
  - Match on **ID column** (tolerant to formats) and map to animal folders

---
Typical dependencies (for reference):

PySide6

pandas

numpy

h5py

openpyxl (for Excel imports)

plus standard library (json, os, etc.)

## Data Model & Folder Structure

MetaMan assumes a simple, explicit structure:

```text
raw_root/
  ProjectA/
    Animal12345/
      1/
        metadata.json
        ...
      2/
        metadata.json
        ...
    Animal67890/
      ...
  ProjectB/
    ...
```
## Running the App

From the repo root:
```
python run_app.py
```

This will:

Create a single AppState

Instantiate the main window (MetaMan)

Open the UI with the 3 main tabs and the Tools menu

## User Interface Overview
<!-- TODO: Insert actual screenshots later, e.g. ![Navigation tab](docs/img/navigation-tab.png) ![Recording tab](docs/img/recording-tab.png) ![Preprocessing tab](docs/img/preprocessing-tab.png) ![Query dialog](docs/img/query-dialog.png) -->
**Navigation Tab

The Navigation tab is your entry point into the data hierarchy.

Root dir:

A text field + “Browse…” button to choose your raw_root.

A “Reload” button to rebuild the tree.

**Tree view:

Left-hand side: Project → Animal → Session

Supports lazy loading of folders to keep things fast.

Selecting a node updates the right-hand panel.

**Project info subtab:

Shows:

Number of animals

Number of sessions

Session counts per animal

List of experiments and experimenters

Total files and total size

Creation / last session timestamps (if available)

Editable metadata rows (key/value)

Button to load animal info from CSV for the whole project

**Animal info subtab:

Shows:

Sessions count

Recording types

First/last session date

File counts and sizes

Editable fields: age, sex, genotype

Structured fields: surgeries, treatments

**Buttons:

Add/remove metadata rows

Add surgery, Add treatment

Load this animal’s info from CSV

**Session metadata subtab:

Displays all keys in the session’s metadata.json as a table

Rows can be added/removed and saved back to disk

**Buttons under the tree:

Open folder: open the selected project/animal/session folder in the OS file explorer (handles UNC paths)

Copy path: copy normalized path to clipboard

Load in Recording/Preprocessing: loads the selected session into the other tabs

**Recording Tab

The Recording tab is focused on per-session acquisition metadata:

Shows the full session metadata on the left (key/value table)

On the right, a trial info panel for trial-level data (trial number, type, etc.)

All panels are resizable

Buttons to:

Start a new recording (creates project/animal/session folders, sets DateTime)

Save / update comments

Update the file_list for the session (scan files and store their paths)

This is the tab you use before and during acquisition to make sure all basic metadata is filled.

**Preprocessing Tab

The Preprocessing tab is your analysis diary for each session.

Processed root field:

Points to your processedData root

“Create folder” / “New preprocessing” button:

Creates processed_root/Project/Animal/Session

Copies the session metadata there

Steps list (left):

Shows steps like spike_sorting, curation, histology, etc.

Add steps from a predefined list depending on recording type (NPX / fiber / behavior)

add_new_step lets you define arbitrary named steps

Mark steps as completed or remove them

Parameters & Comments (center):

JSON text box for step parameters

Button “Add/Update parameters” to save into metadata

Button “Import params (CSV/JSON)”:

JSON: loads as dict or list into params

CSV: supports key/value pairs, or table-like structures

Comments text area for free-form notes

Results folder (per step):

Text field + “Choose…” button to select where the output of that step is stored

Saved in metadata as results_dir

Session Info (right):

Read-only table with all session metadata for quick reference

Search / Query Dialog

Accessible via Tools → “Search / Query…” (and optionally via a button).

Index building:

“Build/Refresh Index” scans the raw_root and builds an in-memory list of all sessions and file paths.

Filters:

Project (regex)

Animal (regex)

Session: single or comma-separated list (2 or 1,2,3)

Metadata filters (multiple rows):

Each row: Key + Op (equals / contains / regex) + Value

All rows are AND-combined

Example:

Recording equals fiber

protocol_session equals 1Door_FR1-1

File pattern:

exact: exact file name (e.g. spike_times.npy)

glob: wildcard pattern (*.npy, *spike*)

regex: full regex applied to path

**Results table:

Columns: project, animal, session, session_dir, Experiment, Recording, protocol_session, matched_files_count, file_path

Export to CSV

Copy all file paths (or session dirs) to clipboard

Metadata Files & Formats
Session Metadata

For each session, MetaMan maintains (at least) three files in the session folder:

metadata.json

metadata.csv

metadata.h5

Typical keys include:

DateTime

Project

Animal

Experiment

Session

Trial

Condition

Recording (e.g. NPX, fiber, behavior)

Region

Experimenter

Room

Box

Comments

file_list (see below)

Preprocessing related keys (preprocessing, etc.)

Animal Metadata

Each animal folder has an animal-level metadata file (JSON/HDF5), aggregating information such as:

Age, sex, genotype

Surgeries (list of dicts: date, virus, coordinates, comments)

Treatments (list of dicts: date, dosage, compound, etc.)

Derived stats:

Number of sessions

Recording types used

First/last session date

Total files and size

These are updated when you:

Use “Load animal infos from CSV”

Hit “Update all” in the main app (if you have such a button wired)

Add/edit surgeries/treatments manually

Project Metadata

For each project, MetaMan stores a project-level metadata object with:

Creation / first session / last session timestamps (if available)

Number of animals

Session counts per animal

List of experiments and experimenters

Any custom fields you define (e.g. Goal, Notes, Funding, etc.)

File List & Server Paths

The file_list key in session metadata is a list of entries like:

"file_list": [
  {
    "path": "B:\\NPX\\rawData\\ProjectA\\Animal12345\\1\\spike_times.npy",
    "size": 1234567,
    "server_path": "\\\\nas-server\\share\\ProjectA\\Animal12345\\1\\spike_times.npy"
  },
  ...
]


path is local absolute path

server_path is filled/updated by the Copy to server workflow (if the file exists on server)

size is the file size in bytes (optional but useful for stats)

Preprocessing Steps

For each session, a preprocessing field stores a list of steps, e.g.:

"preprocessing": [
  {
    "name": "spike_sorting",
    "params": {
      "sorter": "Kilosort3",
      "threshold": 6.0
    },
    "comments": "Good quality, removed noisy channels.",
    "status": "completed",
    "results_dir": "B:\\NPX\\processedData\\ProjectA\\Animal12345\\1\\spikes"
  },
  ...
]


This gives you a machine-readable processing history per session.

Copy to Server Workflow

In the main window, click “Copy project to server…”.

Choose a server root (e.g. a network share).

MetaMan will:

Copy only missing files from raw_root/Project → server_root/Project

Log progress, file counts, and total time in the Recording tab log

For the currently loaded session, compute server_path for each file_list entry and store it in metadata.

This lets you later query only sessions whose files are already present on the server, or quickly reconstruct server paths from metadata.

Importing Animal Info from CSV

MetaMan supports loading animal metadata from a CSV/Excel table, either:

Per project (update all animals that match), or

Per animal (update only the selected one)

The importer is robust to:

BOM issues (UTF-8-SIG, UTF-16, cp1252, etc.)

“ID” column variants:

ID, Animal_ID, AnimalID, MouseID, Subject, SubjectID, etc.

Extra header rows (it can promote the first non-empty row as header)

Matching logic:

For each animal folder, the last 5 characters of its name are extracted.

The importer looks for rows where the last 5 characters of the ID column match.

All columns for that row are added as key/value pairs to the animal metadata.

Adapting Legacy Data

For datasets that predate MetaMan, you can:

Use your existing plan Excel files (with columns like Animal_ID, Ethovision_File, Trial, Session, recording, etc.).

Run a helper script (e.g. ingest_plan_to_app / organize_data) that:

Creates the Project/Animal/Session structure in a chosen output root

Copies behavior and fiber files into session folders (matching by trial numbers, recording type)

Populates metadata files with:

The original plan columns

Automatically detected Behavior_File_Type, Behavior_File_Path, Fiber_File_Path

From there, MetaMan can read and extend the metadata for navigation and preprocessing.

You can treat this as a one-time migration step to make legacy projects MetaMan-compatible.

Configuration

Most configuration lives in neuro_meta_app_qt/config.py and in the AppState:

APP_TITLE

WINDOW_GEOMETRY

Default paths:

raw_root (e.g. B:\NPX\rawData or a server share)

processed_root (e.g. B:\NPX\processedData)

Per-project server roots (stored in settings)

You can:

Change defaults to match your lab’s filesystem

Extend the list of default metadata keys

Customize modality-specific preprocessing step menus

Development Notes

Project structure (simplified):

neuro_meta_app_qt/
  main.py                 # Main window / launch
  config.py               # App constants
  state.py                # AppState (current project/animal/session, settings)
  io_ops.py               # Load/save metadata (json/csv/h5), summaries
  tabs/
    navigation_tab.py     # Navigation & info panels
    recording_tab.py      # Recording metadata & trial info
    preprocessing_tab.py  # Preprocessing steps, params, comments
  services/
    server_sync.py        # Copy project to server
    search_service.py     # Text search in metadata
    query_engine.py       # DataIndex & MetaQuery
  dialogs/
    query_dialog.py       # GUI query interface
  utils.py                # Helpers (threading, etc.)
  ...
run_app.py                # Entry script


## Dev hints:

Use a dedicated virtual environment.

On changes to modules, delete __pycache__ if Python is picking up stale bytecode.

You can run specific components (like plan ingestion scripts) as standalone utilities for debugging.

Roadmap / Ideas

Some possible future features:

Tagging sessions with quality flags (good/bad/needs review).

Built-in viewer hooks (open spike-sorting GUIs or behavior videos directly from the app).

Richer multi-project dashboards (e.g. training history across projects).

Automated backup checks (flag sessions whose server files are incomplete).

If you implement any of these and want to share, PRs are welcome!

## License


This project is currently shared for internal / lab use.
If you plan to open-source it, add a standard LICENSE file and update this section accordingly.
