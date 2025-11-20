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

