import sys
import os
import mimetypes
import json
import ctypes
import fnmatch
import shutil
import zipfile
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTreeWidget, QComboBox,
                             QTreeWidgetItem, QFileDialog, QMessageBox, QCheckBox,
                             QDialog, QTextEdit, QTreeWidgetItemIterator, QLineEdit, QScrollArea,
                             QSizePolicy, QTabWidget)
from PyQt5.QtCore import Qt, QTimer, QUrl, QMimeData
# Added QDesktopServices to open the folder
from PyQt5.QtGui import QIcon, QDesktopServices

TEXT_EXTENSIONS = {
    '.txt', '.py', '.html', '.css', '.js', '.json', '.xml', '.md', '.csv', 
    '.java', '.c', '.cpp', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift',
    '.bat', '.sh', '.yaml', '.yml', '.ini', '.sql', '.log'
}

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not running as a bundle, use the current working directory
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

appdata_dir = os.environ.get('APPDATA', os.path.expanduser('~')) 
CACHE_FILE = os.path.join(appdata_dir, "mergerdict.json")
SETTINGS_FILE = os.path.join(appdata_dir, "mergersettings.json")

DEFAULT_DESKTOP = os.path.join(os.environ.get("USERPROFILE", os.path.expanduser("~")), "Desktop")

DEFAULT_SETTINGS = {
    "theme": "light",
    "font_size": "10",
    "save_path": DEFAULT_DESKTOP,
    "merger_filename": "merged_code_output.txt",
    "merger_inclusions": [],
    "merger_exclusions": [".*", "__pycache__", "node_modules", "*.pyc", "*.pyd", "*.exe", "*.dll"],
    "zipper_filename": "project_zip.zip",
    "zipper_inclusions": ["*/migrations/__init__.py"],
    "zipper_exclusions": [
        ".venv", "venv", "env", "__pycache__", "*.pyc", "staticfiles", 
        "*.zip", ".git", ".idea", ".vscode", "media", "Raw_Templates", 
        "db.sqlite3", ".gitignore", ".env", "*/migrations/*.py", 
        "config", "zip_project.py", "manage.py", "static", "requirements.txt"
    ]
}

DARK_THEME_CSS = """
QWidget {
    background-color: #2b2b2b;
    color: #e0e0e0;
}
QTreeWidget {
    background-color: #333333;
    alternate-background-color: #3d3d3d;
    color: #e0e0e0;
    border: 1px solid #555555;
}
QHeaderView::section {
    background-color: #444444;
    color: #ffffff;
    border: 1px solid #555555;
    padding: 4px;
}
QPushButton {
    background-color: #555555;
    border: 1px solid #333333;
    padding: 6px;
    border-radius: 4px;
}
QPushButton:hover {
    background-color: #666666;
}
QComboBox, QLineEdit, QTextEdit {
    background-color: #444444;
    border: 1px solid #555555;
    color: #ffffff;
}
QCheckBox {
    spacing: 5px;
}
QTabWidget::pane { border: 1px solid #555555; }
QTabBar::tab { background: #444444; padding: 8px; margin-right: 2px; }
QTabBar::tab:selected { background: #666666; font-weight: bold; }
"""

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Settings & Filters")
        self.resize(600, 650)
        self.settings = settings or DEFAULT_SETTINGS.copy()
        
        main_layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        # --- TAB 1: General ---
        self.tab_general = QWidget()
        gen_layout = QVBoxLayout()
        
        theme_layout = QHBoxLayout()
        theme_layout.addWidget(QLabel("Appearance:"))
        self.theme_cb = QComboBox()
        self.theme_cb.addItems(["light", "dark"])
        self.theme_cb.setCurrentText(self.settings.get("theme", "light"))
        self.theme_cb.setMinimumWidth(90)
        theme_layout.addWidget(self.theme_cb)
        theme_layout.addStretch()
        gen_layout.addLayout(theme_layout)
        
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Font Size:"))
        self.font_cb = QComboBox()
        self.font_cb.addItems(["10", "12", "14", "16", "18", "20", "22", "24", "28", "32"])
        self.font_cb.setMinimumWidth(50)
        self.font_cb.setCurrentText(str(self.settings.get("font_size", "10")))
        font_layout.addWidget(self.font_cb)
        font_layout.addStretch()
        gen_layout.addLayout(font_layout)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(QLabel("Default Save Path:"))
        self.save_path_edit = QLineEdit(self.settings.get("save_path", DEFAULT_DESKTOP))
        browse_path_btn = QPushButton("Browse")
        browse_path_btn.clicked.connect(self.browse_save_path)
        path_layout.addWidget(self.save_path_edit)
        path_layout.addWidget(browse_path_btn)
        gen_layout.addLayout(path_layout)
        
        gen_layout.addStretch()
        self.tab_general.setLayout(gen_layout)
        
        # --- TAB 2: Merger ---
        self.tab_merger = QWidget()
        merger_layout = QVBoxLayout()
        
        m_filename_layout = QHBoxLayout()
        m_filename_layout.addWidget(QLabel("Merge File Name:"))
        self.merger_filename_edit = QLineEdit(self.settings.get("merger_filename", "merged_code_output.txt"))
        m_filename_layout.addWidget(self.merger_filename_edit)
        merger_layout.addLayout(m_filename_layout)
        
        merger_layout.addWidget(QLabel("Inclusions (Priority override, e.g., apps.py):"))
        self.merger_inc_edit = QTextEdit()
        self.merger_inc_edit.setPlainText("\n".join(self.settings.get("merger_inclusions", [])))
        merger_layout.addWidget(self.merger_inc_edit)

        merger_layout.addWidget(QLabel("Exclusions (one pattern per line):"))
        self.merger_exc_edit = QTextEdit()
        self.merger_exc_edit.setPlainText("\n".join(self.settings.get("merger_exclusions", [])))
        merger_layout.addWidget(self.merger_exc_edit)
        
        self.tab_merger.setLayout(merger_layout)

        # --- TAB 3: Zipper ---
        self.tab_zipper = QWidget()
        zipper_layout = QVBoxLayout()
        
        z_filename_layout = QHBoxLayout()
        z_filename_layout.addWidget(QLabel("Zip File Name:"))
        self.zipper_filename_edit = QLineEdit(self.settings.get("zipper_filename", "project_zip.zip"))
        z_filename_layout.addWidget(self.zipper_filename_edit)
        zipper_layout.addLayout(z_filename_layout)
        
        zipper_layout.addWidget(QLabel("Inclusions (Priority override, e.g., */migrations/__init__.py):"))
        self.zipper_inc_edit = QTextEdit()
        self.zipper_inc_edit.setPlainText("\n".join(self.settings.get("zipper_inclusions", [])))
        zipper_layout.addWidget(self.zipper_inc_edit)

        zipper_layout.addWidget(QLabel("Exclusions (Files/Folders to omit, e.g., venv, .git):"))
        self.zipper_exc_edit = QTextEdit()
        self.zipper_exc_edit.setPlainText("\n".join(self.settings.get("zipper_exclusions", [])))
        zipper_layout.addWidget(self.zipper_exc_edit)
        
        self.tab_zipper.setLayout(zipper_layout)

        # Add tabs
        self.tabs.addTab(self.tab_general, "General")
        self.tabs.addTab(self.tab_merger, "Merger")
        self.tabs.addTab(self.tab_zipper, "Zipper")
        main_layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Save All Settings")
        save_btn.clicked.connect(self.save_and_close)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        main_layout.addLayout(btn_layout)
        
        self.setLayout(main_layout)
        
    def browse_save_path(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Save Directory", self.save_path_edit.text())
        if folder:
            self.save_path_edit.setText(folder)
            
    def save_and_close(self):
        self.settings["theme"] = self.theme_cb.currentText()
        self.settings["font_size"] = self.font_cb.currentText()
        self.settings["save_path"] = self.save_path_edit.text().strip()
        
        self.settings["merger_filename"] = self.merger_filename_edit.text().strip()
        self.settings["merger_inclusions"] = [line.strip() for line in self.merger_inc_edit.toPlainText().split('\n') if line.strip()]
        self.settings["merger_exclusions"] = [line.strip() for line in self.merger_exc_edit.toPlainText().split('\n') if line.strip()]

        self.settings["zipper_filename"] = self.zipper_filename_edit.text().strip()
        self.settings["zipper_inclusions"] = [line.strip() for line in self.zipper_inc_edit.toPlainText().split('\n') if line.strip()]
        self.settings["zipper_exclusions"] = [line.strip() for line in self.zipper_exc_edit.toPlainText().split('\n') if line.strip()]

        self.accept()


class FileMergerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 Code Merger & Zipper")
        self.resize(750, 650)
        icon_path = resource_path('icon.ico')
        self.setWindowIcon(QIcon(icon_path))
        self.root_dir = ""
        self.recent_paths = []
        self.settings = DEFAULT_SETTINGS.copy()
        
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_tree_structure)
        
        self.load_settings()
        self.init_ui()
        self.load_cache()

    def init_ui(self):
        main_layout = QVBoxLayout()
        path_layout = QHBoxLayout()        
        container_widget = QWidget()
        container_widget.setLayout(main_layout)
        
        self.path_cb = QComboBox()
        self.path_cb.setEditable(True)
        self.path_cb.setInsertPolicy(QComboBox.NoInsert)
        self.path_cb.setPlaceholderText("Select or enter a directory path...")
        self.path_cb.setMinimumWidth(40)
        self.path_cb.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.path_cb.activated.connect(self.on_dropdown_selected)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True) 
        scroll_area.setWidget(container_widget)
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll_area)
        self.setLayout(final_layout)
        
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.browse_folder)
        
        self.confirm_btn = QPushButton("Refresh")
        self.confirm_btn.clicked.connect(self.trigger_scan)

        path_layout.addWidget(QLabel("Path:"))
        path_layout.addWidget(self.path_cb, stretch=1)
        path_layout.addWidget(browse_btn)
        path_layout.addWidget(self.confirm_btn)
        
        options_layout = QHBoxLayout()
        self.chk_auto_refresh = QCheckBox("Auto-Refresh (10s)")
        self.chk_auto_refresh.setChecked(False)
        self.chk_auto_refresh.toggled.connect(self.toggle_timer)
        options_layout.addWidget(self.chk_auto_refresh)
        
        options_layout.addStretch()
        
        # --- NEW BUTTON ADDED HERE ---
        open_folder_btn = QPushButton("ð")
        open_folder_btn.setToolTip("Open Default Save Folder")
        open_folder_btn.clicked.connect(self.open_default_save_path)
        options_layout.addWidget(open_folder_btn)

        settings_btn = QPushButton("âï¸")
        settings_btn.clicked.connect(self.open_settings)
        options_layout.addWidget(settings_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("File System")
        self.tree.setMinimumWidth(113)
        self.tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        action_layout = QHBoxLayout()
        
        self.action_clip_btn = QPushButton("Copy")
        self.action_clip_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.action_clip_btn.clicked.connect(self.execute_merge)
        
        self.action_zip_btn = QPushButton("Zipper")
        self.action_zip_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.action_zip_btn.clicked.connect(self.execute_zip)

        action_layout.addWidget(self.action_clip_btn)
        action_layout.addWidget(self.action_zip_btn)

        self.status_label = QLabel("Ready")
        
        main_layout.addLayout(path_layout)
        main_layout.addLayout(options_layout)
        main_layout.addWidget(self.tree)
        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.status_label)

        self.apply_theme()

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    saved_settings = json.load(f)
                    self.settings.update(saved_settings)
            except Exception as e:
                print(f"Failed to load settings: {e}")
                
        # Ensure new nested/renamed keys exist even if older setting file is loaded
        for k, v in DEFAULT_SETTINGS.items():
            if k not in self.settings:
                self.settings[k] = v

    def save_settings(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Failed to save settings: {e}")

    def apply_theme(self):
        base_css = DARK_THEME_CSS if self.settings.get("theme") == "dark" else ""
        font_size = int(self.settings.get("font_size", 10))
        check_size = int(font_size * 1.4) 
        
        dynamic_css = f"""
        QWidget {{ font-size: {font_size}pt; }}
        QCheckBox::indicator, QTreeView::indicator {{
            width: {check_size}px; height: {check_size}px;
        }}
        """
        
        self.setStyleSheet(base_css + dynamic_css)
        
        if hasattr(self, 'action_clip_btn'):
            self.action_clip_btn.setStyleSheet(f"background-color: #2196F3; color: white; font-weight: bold; padding: 10px; border: none; font-size: {font_size}pt;")
            self.action_zip_btn.setStyleSheet(f"background-color: #FF9800; color: white; font-weight: bold; padding: 10px; border: none; font-size: {font_size}pt;")

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings.copy())
        if dlg.exec_():
            self.settings = dlg.settings
            self.save_settings()
            self.apply_theme() 
            if self.root_dir:
                self.refresh_tree_structure()
                
    # --- NEW FUNCTION TO OPEN THE SAVE PATH ---
    def open_default_save_path(self):
        save_dir = self.settings.get("save_path", DEFAULT_DESKTOP)
        if not os.path.exists(save_dir):
            save_dir = DEFAULT_DESKTOP
            
        # Opens the URL via the OS's default file browser
        QDesktopServices.openUrl(QUrl.fromLocalFile(save_dir))

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.recent_paths = json.load(f)
                self.path_cb.addItems(self.recent_paths)
                if self.recent_paths:
                    self.path_cb.setCurrentIndex(-1)
            except Exception as e:
                print(f"Failed to load cache: {e}")

    def add_path_to_cache(self, path):
        if not path or not os.path.isdir(path): return
        path = os.path.normpath(path)
        if path in self.recent_paths: self.recent_paths.remove(path)
        self.recent_paths.insert(0, path)
        self.recent_paths = self.recent_paths[:5]
        try:
            with open(CACHE_FILE, 'w') as f: json.dump(self.recent_paths, f)
        except Exception: pass

        self.path_cb.blockSignals(True)
        self.path_cb.clear()
        self.path_cb.addItems(self.recent_paths)
        self.path_cb.setCurrentText(path)
        self.path_cb.blockSignals(False)

    def on_dropdown_selected(self, index):
        self.process_new_path(self.path_cb.itemText(index))

    def trigger_scan(self):
        self.confirm_btn.setStyleSheet("background-color: #4CAF50; color: white;")
        QTimer.singleShot(1000, lambda: self.confirm_btn.setStyleSheet(""))
        self.process_new_path(self.path_cb.currentText())

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Directory")
        if folder: self.process_new_path(folder)

    def process_new_path(self, target_path):
        if os.path.isdir(target_path):
            self.add_path_to_cache(target_path)
            self.root_dir = target_path
            self.refresh_tree_structure()
        else:
            QMessageBox.warning(self, "Invalid Path", f"Directory does not exist:\n{target_path}")

    def toggle_timer(self, checked):
        if checked: self.refresh_timer.start(10000)
        else: self.refresh_timer.stop()

    def get_checked_paths(self):
        checked = set()
        iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
        while iterator.value():
            item = iterator.value()
            file_path = item.data(0, Qt.UserRole)
            if file_path and os.path.isfile(file_path): checked.add(file_path)
            iterator += 1
        return checked

    def get_expanded_paths(self):
        expanded = set()
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.isExpanded() and item.data(0, Qt.UserRole):
                expanded.add(item.data(0, Qt.UserRole))
            iterator += 1
        return expanded

    def restore_expanded_paths(self, expanded_paths):
        iterator = QTreeWidgetItemIterator(self.tree)
        while iterator.value():
            item = iterator.value()
            if item.data(0, Qt.UserRole) in expanded_paths:
                item.setExpanded(True)
            iterator += 1

    def refresh_tree_structure(self):
        if not self.root_dir or not os.path.exists(self.root_dir): return
        previously_checked = self.get_checked_paths()
        previously_expanded = self.get_expanded_paths()
        self.tree.blockSignals(True)
        self.tree.clear()
        self.status_label.setText("Scanning...")
        QApplication.processEvents()
        
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, self.root_dir)
        root_item.setData(0, Qt.UserRole, self.root_dir)
        root_item.setFlags(root_item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
        root_item.setCheckState(0, Qt.Unchecked)
        
        has_content = self.populate_tree(self.root_dir, root_item, previously_checked)
        if has_content:
            root_item.setExpanded(True)
            self.restore_expanded_paths(previously_expanded)
        else:
            root_item.setText(0, f"{self.root_dir} (No valid/unexcluded files found)")
            
        self.tree.blockSignals(False)
        self.status_label.setText(f"Scan complete. {len(previously_checked)} files restored.")

    def is_included(self, name, full_path):
        rel_path = os.path.relpath(full_path, self.root_dir).replace('\\', '/')
        for pattern in self.settings.get("merger_inclusions", []):
            if not pattern: continue
            if (fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(f"*/{name}", pattern)):
                return True
        return False
        
    def is_ignored(self, name, full_path):
        if self.is_included(name, full_path): return False
        rel_path = os.path.relpath(full_path, self.root_dir).replace('\\', '/')
        for pattern in self.settings.get("merger_exclusions", []):
            if not pattern: continue
            if (fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(f"*/{name}", pattern)):
                return True
            if os.path.isdir(full_path) and fnmatch.fnmatch(name + '/', pattern):
                return True
        return False
        
    def is_valid_file(self, filename, filepath):
        try:
            if os.path.getsize(filepath) == 0: return False
        except OSError: return False
        ext = os.path.splitext(filename)[1].lower()
        if ext in TEXT_EXTENSIONS: return True
        guess_type, _ = mimetypes.guess_type(filepath)
        if guess_type and guess_type.startswith('text'): return True
        return False
        
    def populate_tree(self, current_path, parent_item, previously_checked_set):
        has_valid_children = False
        try: entries = sorted(os.listdir(current_path))
        except PermissionError: return False
        for entry in entries:
            full_path = os.path.join(current_path, entry)
            if self.is_ignored(entry, full_path): continue
            if os.path.isdir(full_path):
                dir_item = QTreeWidgetItem()
                dir_item.setText(0, entry)
                dir_item.setData(0, Qt.UserRole, full_path)
                dir_item.setFlags(dir_item.flags() | Qt.ItemIsTristate | Qt.ItemIsUserCheckable)
                dir_item.setCheckState(0, Qt.Unchecked)
                child_has_content = self.populate_tree(full_path, dir_item, previously_checked_set)
                if child_has_content:
                    parent_item.addChild(dir_item)
                    has_valid_children = True
            elif os.path.isfile(full_path):
                if self.is_valid_file(entry, full_path):
                    file_item = QTreeWidgetItem(parent_item)
                    file_item.setText(0, entry)
                    file_item.setData(0, Qt.UserRole, full_path)
                    file_item.setFlags(file_item.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    if full_path in previously_checked_set:
                        file_item.setCheckState(0, Qt.Checked)
                    else: file_item.setCheckState(0, Qt.Unchecked)
                    has_valid_children = True
        return has_valid_children

    def execute_merge(self):
        files_to_merge = []
        iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
        while iterator.value():
            item = iterator.value()
            path = item.data(0, Qt.UserRole)
            if path and os.path.isfile(path): files_to_merge.append(path)
            iterator += 1
            
        if not files_to_merge:
            QMessageBox.warning(self, "No Selection", "Please select at least one file to process.")
            return
            
        save_dir = self.settings.get("save_path", DEFAULT_DESKTOP)
        if not os.path.exists(save_dir): save_dir = DEFAULT_DESKTOP 
        
        save_filename = self.settings.get("merger_filename", "merged_code_output.txt")
        if not save_filename.strip(): save_filename = "merged_code_output.txt"
        
        # Single File logic
        if len(files_to_merge) == 1:
            single_file = files_to_merge[0]
            output_file = os.path.join(save_dir, os.path.basename(single_file))
            try:
                shutil.copy2(single_file, output_file)
                clipboard = QApplication.clipboard()
                mime_data = QMimeData()
                mime_data.setUrls([QUrl.fromLocalFile(output_file)])
                clipboard.setMimeData(mime_data)
                
                self.action_clip_btn.setText("Copy â")
                QTimer.singleShot(2000, lambda: self.action_clip_btn.setText("Copy"))
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to copy single file:\n{str(e)}")
            return
            
        # Multi-file Logic
        merged_text_chunks = []
        merged_text_chunks.append("MERGED OUTPUT\n")
        merged_text_chunks.append(f"Total Files: {len(files_to_merge)}\n")
        merged_text_chunks.append("="*50 + "\n\n")
        for fpath in files_to_merge:
            merged_text_chunks.append(f"\n{'='*20}\nFILE: {fpath}\n{'='*20}\n\n")
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as infile:
                    merged_text_chunks.append(infile.read())
            except Exception as e:
                merged_text_chunks.append(f"\n[ERROR READING FILE: {e}]\n")
            merged_text_chunks.append("\n")
            
        final_output_string = "".join(merged_text_chunks)
        output_file = os.path.join(save_dir, save_filename)
        try:
            with open(output_file, 'w', encoding='utf-8') as outfile:
                outfile.write(final_output_string)
                
            clipboard = QApplication.clipboard()
            mime_data = QMimeData()
            mime_data.setUrls([QUrl.fromLocalFile(output_file)])
            clipboard.setMimeData(mime_data)
            
            self.action_clip_btn.setText("Copy â")
            QTimer.singleShot(2000, lambda: self.action_clip_btn.setText("Copy"))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save or copy file:\n{str(e)}")

    def should_skip_zip(self, relative_path):
        path_str = str(relative_path).replace("\\", "/")
        z_inc = self.settings.get("zipper_inclusions", [])
        z_exc = self.settings.get("zipper_exclusions", [])

        # 1. ALWAYS INCLUDE Priority
        for pattern in z_inc:
            if pattern and fnmatch.fnmatch(path_str, pattern): return False

        for pattern in z_exc:
            if not pattern: continue
            if fnmatch.fnmatch(path_str, pattern): return True
        parts = Path(relative_path).parts
        for part in parts:
            if part in z_exc:
                return True
        return False

    def execute_zip(self):
            if not self.root_dir or not os.path.exists(self.root_dir):
                QMessageBox.warning(self, "No Directory", "Please select a valid directory to zip first.")
                return
            files_to_zip = []
            iterator = QTreeWidgetItemIterator(self.tree, QTreeWidgetItemIterator.Checked)
            while iterator.value():
                item = iterator.value()
                path = item.data(0, Qt.UserRole)
                if path and os.path.isfile(path): 
                    files_to_zip.append(path)
                iterator += 1
            base_dir = Path(self.root_dir)
            if not files_to_zip:
                for root, dirs, files in os.walk(self.root_dir):
                    for file in files:
                        file_path = Path(root) / file
                        try:
                            relative_path = file_path.relative_to(base_dir)
                            # Check if it should be skipped based on Zipper Settings
                            if not self.should_skip_zip(relative_path):
                                files_to_zip.append(str(file_path))
                        except ValueError:
                            pass
                if not files_to_zip:
                    QMessageBox.warning(self, "No valid files", "No files selected and no valid files found based on zipper exclusions.")
                    return
            save_dir = self.settings.get("save_path", DEFAULT_DESKTOP)
            if not os.path.exists(save_dir):
                save_dir = DEFAULT_DESKTOP
            zip_filename = self.settings.get("zipper_filename", "project_zip.zip")
            output_zip_path = Path(save_dir) / zip_filename
            self.status_label.setText("Creating ZIP Archive...")
            QApplication.processEvents()

            try:
                with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                    for file_path_str in files_to_zip:
                        file_path = Path(file_path_str)
                        if file_path.resolve() == output_zip_path.resolve():
                            continue
                        
                        try:
                            relative_path = file_path.relative_to(base_dir)
                            zipf.write(file_path, relative_path)
                        except ValueError:
                            zipf.write(file_path, file_path.name)

                self.status_label.setText(f"ZIP created successfully: {output_zip_path.name}")
                self.action_zip_btn.setText("Zipped â")
                QTimer.singleShot(2000, lambda: self.action_zip_btn.setText("Zipper"))
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to create ZIP:\n{str(e)}")
                self.status_label.setText("Error creating ZIP.")


if __name__ == '__main__':
    myappid = 'mycustom.filemerger.app.3.0' 
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid) 
    app = QApplication(sys.argv)
    try:
        app.setAttribute(Qt.AA_EnableHighDpiScaling)
        app.setAttribute(Qt.AA_UseHighDpiPixmaps)
    except: pass
    window = FileMergerApp()
    window.show()
    sys.exit(app.exec_())