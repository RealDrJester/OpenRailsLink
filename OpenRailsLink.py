# OpenRailsLink.py
# gui.py
import sys, json, argparse, os, subprocess, importlib, threading, time, tempfile, re
import psutil
import traceback
from functools import partial
from collections import defaultdict
import numpy # FIX: Prevents a runtime error in compiled EXE by initializing numpy early.
from lxml import etree
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QListWidget, QPushButton, QLabel, QLineEdit, QSlider, QGroupBox,
                             QGridLayout, QFrame, QListWidgetItem, QSizePolicy, QInputDialog,
                             QTextEdit, QDockWidget, QFileDialog, QDialog, QCheckBox, QFormLayout, QFileIconProvider,
                             QToolButton, QDialogButtonBox, QScrollArea, QRadioButton, QMessageBox)
from PyQt5.QtGui import QIcon, QPixmap, QColor
from PyQt5.QtCore import Qt, QDateTime, QFileInfo, QSize, pyqtSignal, QMetaObject, pyqtSlot
from pynput.keyboard import Controller as KeyboardController, Key

from definitions import CONTROL_DEFINITIONS
from controls import JoystickManager, BindingsEditor
from web_interface import OpenRailsWebInterface
from hid_manager import SaitekPanelManager

# --- HELPER FUNCTION TO FIND FILES WHEN COMPILED ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def is_admin():
    """Check if the program is running with administrator privileges"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

STYLE_SHEET = """
QMainWindow, QWidget { background-color: #282828; color: #E0E0E0; font-family: 'Segoe UI', sans-serif; }
QFrame, QGroupBox { background-color: #3c3c3c; border-radius: 5px; }
QGroupBox { font-weight: bold; padding: 12px 0px 0px 0px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: top center; padding: 0 10px; }
QLabel { background-color: transparent; }
QLabel#status_label_ok { color: #00FF00; font-weight: bold; }
QLabel#status_label_fail { color: red; font-weight: bold; }
QPushButton, QToolButton { background-color: #555555; border: 1px solid #666666; border-radius: 4px; padding: 8px; min-height: 20px; }
QToolButton { padding: 4px; font-size: 9px; }
QPushButton:disabled, QToolButton:disabled { background-color: #404040; color: #888888; }
QPushButton:pressed, QPushButton:checked, QToolButton:pressed { background-color: #DDAA33; color: #000000; border: 1px solid #FFFFFF; }
QLineEdit, QListWidget, QTextEdit { background-color: #222222; border: 1px solid #666666; border-radius: 4px; padding: 4px; }
QSlider::groove:horizontal { border: 1px solid #555; background: #222; height: 8px; border-radius: 4px; }
QSlider::handle:horizontal { background: #DDAA33; border: 1px solid #DDCC77; width: 18px; margin: -2px 0; border-radius: 9px; }
QTabWidget::pane { border-top: 2px solid #555555; }
QTabBar { qproperty-drawBase: 0; }
QTabBar::tab { background: #555555; border: 1px solid #666666; border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px; padding: 6px; }
QTabBar::tab:selected { background: #3c3c3c; }
QPushButton#game_button { background-color: #5D9CEC; }
QPushButton#brakes_button { background-color: #B22222; }
QPushButton#engine_electric_button { background-color: #4682B4; }
QPushButton#engine_diesel_button { background-color: #006400; }
QPushButton#engine_steam_button { background-color: #8B4513; }
QPushButton#door_button { background-color: #2E8B57; }
"""

class LauncherEditor(QDialog):
    profiles_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Game Launchers")
        self.resize(500, 300)
        self.main_window = parent
        
        main_layout = QVBoxLayout(self)
        self.launcher_tabs = QTabWidget()
        self.launcher_tabs.setMovable(True)
        self.launcher_tabs.setUsesScrollButtons(True)
        main_layout.addWidget(self.launcher_tabs)
        
        launcher_btn_layout = QHBoxLayout()
        add_tab_btn = QPushButton("+"); add_tab_btn.clicked.connect(lambda: self.add_launcher_tab())
        remove_tab_btn = QPushButton("-"); remove_tab_btn.clicked.connect(self.remove_launcher_tab)
        rename_tab_btn = QPushButton("Rename"); rename_tab_btn.clicked.connect(self.rename_launcher_tab)
        
        launcher_btn_layout.addWidget(add_tab_btn)
        launcher_btn_layout.addWidget(remove_tab_btn)
        launcher_btn_layout.addWidget(rename_tab_btn)
        launcher_btn_layout.addStretch()
        main_layout.addLayout(launcher_btn_layout)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def add_launcher_tab(self, name="New Profile", exe_path="C:/", args=""):
        tab = QWidget(); layout = QFormLayout(tab)
        exe_edit = QLineEdit(exe_path); args_edit = QLineEdit(args)
        launch_btn = QPushButton("Execute"); launch_btn.clicked.connect(lambda: self.main_window.on_launch_button_clicked(self.get_launcher_tab_data(self.launcher_tabs.indexOf(tab))))
        launcher_browse_btn = QPushButton("Browse..."); launcher_browse_btn.clicked.connect(lambda: self.on_launcher_exe_browse(self.launcher_tabs.indexOf(tab)))
        
        exe_edit.textChanged.connect(self.on_launcher_data_changed)
        
        layout.addRow("Executable:", exe_edit); layout.addRow(launcher_browse_btn); layout.addRow("Arguments:", args_edit); layout.addRow(launch_btn)
        index = self.launcher_tabs.addTab(tab, name)
        self.update_tab_from_data(index, {'name': name, 'exe': exe_path, 'args': args})
        self.launcher_tabs.setCurrentIndex(index)
        return index

    def remove_launcher_tab(self):
        current_index = self.launcher_tabs.currentIndex()
        if self.launcher_tabs.count() > 1: self.launcher_tabs.removeTab(current_index)
        else: self.main_window.log_message("Cannot remove the last launcher tab.", "INFO")
        
    def rename_launcher_tab(self):
        current_index = self.launcher_tabs.currentIndex()
        if current_index != -1:
            name, ok = QInputDialog.getText(self, "Rename Tab", "Enter new name:", text=self.launcher_tabs.tabText(current_index))
            if ok and name: self.launcher_tabs.setTabText(current_index, name)
            
    def get_all_profiles(self):
        profiles = []
        for i in range(self.launcher_tabs.count()):
            profiles.append(self.get_launcher_tab_data(i))
        return profiles
        
    def load_launcher_tabs(self):
        self.launcher_tabs.clear()
        profiles = self.main_window.config.get("settings", {}).get("launcher_profiles", [])
        if not profiles: self.add_launcher_tab(); return
        for profile in profiles: self.add_launcher_tab(profile['name'], profile['exe'], profile['args'])
        
    def on_launcher_exe_browse(self, index):
        widgets = self.get_launcher_tab_widgets(index)
        if not widgets: return
        path, _ = QFileDialog.getOpenFileName(self, "Select Executable", "", "Executables (*.exe)")
        if path:
            widgets['exe'].setText(path)
    
    def get_launcher_tab_data(self, index):
        tab = self.launcher_tabs.widget(index)
        if not tab: return None
        exe_edit, args_edit = tab.findChildren(QLineEdit)
        return {'name': self.launcher_tabs.tabText(index), 'exe': exe_edit.text(), 'args': args_edit.text()}
        
    def get_launcher_tab_widgets(self, index):
        if index < 0: return None
        tab = self.launcher_tabs.widget(index);
        children = tab.findChildren(QPushButton)
        if len(children) < 2: return None
        exe_edit, args_edit = tab.findChildren(QLineEdit)
        launch_btn, browse_btn = children
        return {'exe': exe_edit, 'args': args_edit, 'launch': launch_btn}
        
    def update_tab_from_data(self, index, data):
        widgets = self.get_launcher_tab_widgets(index)
        if not widgets: return
        is_valid = bool(data['exe'] and os.path.exists(data['exe']))
        widgets['launch'].setEnabled(is_valid)
        if is_valid:
            info = QFileInfo(data['exe']); provider = QFileIconProvider()
            icon = provider.icon(info); self.launcher_tabs.setTabIcon(index, icon)
        else:
            self.launcher_tabs.setTabIcon(index, QIcon())

    def on_launcher_data_changed(self):
        current_index = self.launcher_tabs.currentIndex()
        if current_index != -1:
            self.update_tab_from_data(current_index, self.get_launcher_tab_data(current_index))
            
    def accept(self):
        self.profiles_changed.emit()
        super().accept()

class TrackIRSettingsDialog(QDialog):
    def __init__(self, current_settings_cab, current_settings_external, current_settings_interior, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TrackIR Settings - Multi-Camera Configuration")
        self.resize(950, 750)
        
        main_layout = QVBoxLayout(self)
        
        # Create tabs for 3 cameras
        self.camera_tabs = QTabWidget()
        main_layout.addWidget(self.camera_tabs)
        
        # Create 3 identical settings tabs
        self.cab_widgets = self.create_camera_tab("Cab Camera", current_settings_cab)
        self.external_widgets = self.create_camera_tab("External Camera", current_settings_external)
        self.interior_widgets = self.create_camera_tab("Interior Camera", current_settings_interior)
        
        self.camera_tabs.addTab(self.cab_widgets['widget'], "Cab Camera")
        self.camera_tabs.addTab(self.external_widgets['widget'], "External Camera")
        self.camera_tabs.addTab(self.interior_widgets['widget'], "Interior Camera")

        # Add checkbox for enabling external/interior scanning
        self.enable_extra_cameras_cb = QCheckBox(
            "Enable External and Interior camera scanning (EXPERIMENTAL)"
        )
        self.enable_extra_cameras_cb.setChecked(False)  # Disabled by default
        self.enable_extra_cameras_cb.setStyleSheet("color: #ffaa00; font-weight: bold;")
        self.enable_extra_cameras_cb.setToolTip(
            "⚠️ WARNING: External and Interior camera scanning is EXPERIMENTAL and may be unreliable.\n"
            "These cameras may not be found consistently and could cause issues.\n"
            "NO SUPPORT will be provided for issues related to this feature.\n"
            "Only enable if you specifically need multi-camera support and accept the risks."
        )

        current_enable_extra = self.parent().config.get("trackir_settings", {}).get("enable_extra_cameras", False)
        self.enable_extra_cameras_cb.setChecked(current_enable_extra)

        # Add to layout (before button box)
        warning_label = QLabel(
            "<b>⚠️ External/Interior Scanning:</b> Unreliable and buggy. "
            "Use only if you understand the limitations. <b>NO SUPPORT will be provided for this feature.</b>"
        )
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet("color: #ff6b6b; padding: 8px; background-color: #3a1a1a; border-radius: 4px;")

        main_layout.addWidget(warning_label)
        main_layout.addWidget(self.enable_extra_cameras_cb)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
    
    def create_camera_tab(self, camera_name, current_settings):
        """Create a settings tab for one camera"""
        tab_widget = QWidget()
        layout = QVBoxLayout(tab_widget)
        
        # Instructions
        instructions = QTextEdit()
        instructions.setReadOnly(True)
        instructions.setMaximumHeight(120)
        instructions.setPlainText(f"""HOW TO FIND AOB PATTERN FOR {camera_name.upper()}:

1. Open Cheat Engine, select RUNACTIVITY.EXE process
2. Click ".NET" on menu bar → Orts.Viewer3D → RotatingCamera → RotateByMouse
3. Right-click → "JIT", Memory window opens - search for pattern
4. Use "??" for bytes that change (wildcards)

Each camera has unique signature bytes at the start of the pattern.""")
        layout.addWidget(QLabel(f"<b>{camera_name} Instructions:</b>"))
        layout.addWidget(instructions)
        
        # AOB and Radius Settings
        scanner_group = QGroupBox("Scanner Settings")
        scanner_form = QFormLayout(scanner_group)

        aob_input = QLineEdit(current_settings.get("aob", "?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 40 ?? ?? ?? ?? 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 01 00 00 00"))
        scanner_form.addRow("AOB Pattern:", aob_input)

        radius_input = QLineEdit(str(current_settings.get("radius", 10.0)))
        scanner_form.addRow("Radius:", radius_input)

        layout.addWidget(scanner_group)
        
        layout.addWidget(QLabel("<hr>"))
        
        # Two-column layout
        config_grid = QGridLayout()
        
        # LEFT COLUMN: Movement Limits
        left_group = QGroupBox("Movement Limits (Raw Values)")
        left_form = QFormLayout(left_group)
        
        x_limit_input = QLineEdit(str(current_settings.get("x_limit", 2.7)))
        left_form.addRow("X-Axis Limit (Yaw):", x_limit_input)
        
        y_limit_input = QLineEdit(str(current_settings.get("y_limit", 1.5)))
        left_form.addRow("Y-Axis Limit (Pitch):", y_limit_input)
        
        fb_add_input = QLineEdit(str(current_settings.get("forward_backward_add", 0.6)))
        left_form.addRow("Forward/Backward Add:", fb_add_input)
        
        ud_add_input = QLineEdit(str(current_settings.get("up_down_add", 0.5)))
        left_form.addRow("Up/Down Add:", ud_add_input)
        
        lr_add_input = QLineEdit(str(current_settings.get("left_right_add", 0.6)))
        left_form.addRow("Left/Right Add:", lr_add_input)
        
        enable_camera_movement_cb = QCheckBox("Enable Camera Movement (X/Y/Z Translation)")
        enable_camera_movement_cb.setChecked(current_settings.get("enable_camera_movement", True))
        left_form.addRow(enable_camera_movement_cb)
        
        # Force write checkbox with warning
        force_write_cb = QCheckBox("Force write even when camera inactive")
        force_write_cb.setChecked(current_settings.get("force_write_when_inactive", False))
        force_write_cb.setToolTip("⚠️ WARNING: Writing to inactive cameras may cause instability or crashes!")
        force_write_cb.setStyleSheet("QCheckBox { color: #ff6b6b; font-weight: bold; }")
        left_form.addRow(force_write_cb)
        
        config_grid.addWidget(left_group, 0, 0)
        
        # RIGHT COLUMN: Memory Offsets
        right_group = QGroupBox("Memory Offsets (Hex)")
        right_form = QFormLayout(right_group)
        
        offset_info = QLabel("<b>⚠ WARNING:</b> Use Cheat Engine notation (e.g., 68+4, not 72)")
        offset_info.setWordWrap(True)
        offset_info.setStyleSheet("color: #ff6b6b; padding: 5px;")
        right_form.addRow(offset_info)
        
        x_offset_input = QLineEdit(current_settings.get("x_offset", "C"))
        right_form.addRow("X (Yaw) Offset:", x_offset_input)
        
        y_offset_input = QLineEdit(current_settings.get("y_offset", "0"))
        right_form.addRow("Y (Pitch) Offset:", y_offset_input)
        
        fb_offset_input = QLineEdit(current_settings.get("forward_backward_offset", "6c"))
        right_form.addRow("Forward/Backward Offset:", fb_offset_input)
        
        ud_offset_input = QLineEdit(current_settings.get("up_down_offset", "68"))
        right_form.addRow("Up/Down Offset:", ud_offset_input)
        
        lr_offset_input = QLineEdit(current_settings.get("left_right_offset", "64"))
        right_form.addRow("Left/Right Offset:", lr_offset_input)
        
        config_grid.addWidget(right_group, 0, 1)
        
        layout.addLayout(config_grid)
        
        # Return all widgets for later retrieval
        return {
            'widget': tab_widget,
            'aob': aob_input,
            'radius': radius_input,
            'x_limit': x_limit_input,
            'y_limit': y_limit_input,
            'fb_add': fb_add_input,
            'ud_add': ud_add_input,
            'lr_add': lr_add_input,
            'enable_movement': enable_camera_movement_cb,
            'force_write': force_write_cb,
            'x_offset': x_offset_input,
            'y_offset': y_offset_input,
            'fb_offset': fb_offset_input,
            'ud_offset': ud_offset_input,
            'lr_offset': lr_offset_input
        }
    
    def get_settings(self, widgets):
        """Extract settings from a camera tab's widgets"""
        try:
            radius = float(widgets['radius'].text())
            x_limit = float(widgets['x_limit'].text())
            y_limit = float(widgets['y_limit'].text())
            fb_add = float(widgets['fb_add'].text())
            ud_add = float(widgets['ud_add'].text())
            lr_add = float(widgets['lr_add'].text())
        except ValueError:
            radius = 10.0
            x_limit, y_limit = 2.7, 1.5
            fb_add, ud_add, lr_add = 0.6, 0.5, 0.6
        
        return {
            "aob": widgets['aob'].text().strip(),
            "radius": radius,
            "x_limit": x_limit,
            "y_limit": y_limit,
            "forward_backward_add": fb_add,
            "up_down_add": ud_add,
            "left_right_add": lr_add,
            "enable_camera_movement": widgets['enable_movement'].isChecked(),
            "force_write_when_inactive": widgets['force_write'].isChecked(),
            "x_offset": widgets['x_offset'].text().strip(),
            "y_offset": widgets['y_offset'].text().strip(),
            "forward_backward_offset": widgets['fb_offset'].text().strip(),
            "up_down_offset": widgets['ud_offset'].text().strip(),
            "left_right_offset": widgets['lr_offset'].text().strip()
        }
    
    def get_all_settings(self):
        """Get settings for all 3 cameras"""
        return {
            'cab': self.get_settings(self.cab_widgets),
            'external': self.get_settings(self.external_widgets),
            'interior': self.get_settings(self.interior_widgets),
            'enable_extra_cameras': self.enable_extra_cameras_cb.isChecked()
        }

class MainAppWindow(QMainWindow):
    trackir_log_signal = pyqtSignal(str)
    trackir_aob_signal = pyqtSignal(str)
    trackir_rescan_signal = pyqtSignal()
    trackir_rotation_signal = pyqtSignal(float, float, float) # Yaw, Pitch, Roll
    trackir_position_signal = pyqtSignal(float, float, float) # X, Y, Z
    trackir_addresses_updated = pyqtSignal(list)  # List of found addresses
    trackir_address_invalid = pyqtSignal(str) # Hex string of invalid address
    
    def __init__(self, profile_path=None):
        super().__init__()
        self.setWindowTitle("OpenRailsLink"); self.setGeometry(100, 100, 1920, 900); self.setStyleSheet(STYLE_SHEET)
        self.bindings = {}; self.gui_controls = {}; self.gui_labels = {}; self.config = {}
        self.current_profile_path = None; self.active_cab_controls = []
        self.slider_last_values = {}
        self.joystick_manager = JoystickManager(self); self.saitek_manager = SaitekPanelManager(self); self.web_interface = OpenRailsWebInterface(self)
        self.launcher_editor = LauncherEditor(self)
        self.keyboard_controller = KeyboardController()
        self.held_keys = {}  # Track which keys are currently held down
        self.button_hold_states = {}  # Track physical button states for hold behavior
        
        # TrackIR process management - Multi-camera
        self.trackir_writer_process = None
        self.trackir_scanner_processes = {
            'cab': None,
            'external': None,
            'interior': None
        }
        self.trackir_addresses = {
            'cab': [],
            'external': [],
            'interior': []
        }
        self.trackir_active_camera = 'cab'  # Currently selected camera for writing
        self.trackir_game_pid = 0
        self.trackir_debug_log = None

        self.trackir_default_patterns = {
            "cab": "6D 40 ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 40 ?? ?? ?? ?? 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 01 00 00 00",
            "external": "03 CC ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 40 ?? ?? ?? ?? 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 01 00 00 00",
            "interior": "B6 52 ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? ?? 40 ?? ?? ?? ?? 00 00 00 00 00 00 00 00 00 00 00 00 00 00 80 3F 00 00 00 00 01 00 00 00"
        }
        
        # --- CORRECTED INITIALIZATION ORDER ---
        self.init_ui()
        self.load_app_config()
        self.connect_signals()
        self.update_extra_camera_visibility()
        
        # Clean up any orphaned TrackIR processes from previous crashed sessions
        self._cleanup_orphaned_trackir_processes()
        
        # --- Continue with startup logic ---
        self.log_message(f"Found {len(self.joystick_manager.get_devices())} joystick(s) during startup scan.", "APP")
        
        # Start timer to check TrackIR game status every 5 seconds
        from PyQt5.QtCore import QTimer
        self.trackir_game_check_timer = QTimer()
        self.trackir_game_check_timer.timeout.connect(self.check_trackir_game_status)
        self.trackir_game_check_timer.start(5000)  # Check every 5 seconds

        if self.saitek_manager.is_connected(): self.log_message("Found Saitek Switch Panel.", "APP")
        self.web_interface.start()
        if profile_path:
            self.log_message(f"Loading profile from command-line: {profile_path}", "APP"); self.load_profile(profile_path)
        else:
            default_profile = self.config.get("settings", {}).get("default_profile_path", "")
            if default_profile and os.path.exists(default_profile): self.log_message(f"Loading default profile: {default_profile}", "APP"); self.load_profile(default_profile)

    def _cleanup_orphaned_trackir_processes(self):
        """Kill any trackir_scanner or trackir_integration processes running without a parent"""
        try:
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    proc_name = proc.info['name'].lower()
                    if 'trackir_scanner' in proc_name or 'trackir_integration' in proc_name:
                        # Found a TrackIR process - kill it
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            if killed_count > 0:
                self.log_message(f"Cleaned up {killed_count} orphaned TrackIR process(es) from previous session", "APP")
        except Exception as e:
            self.log_message(f"Error cleaning orphaned processes: {e}", "ERROR")

    def init_ui(self):
        self.setup_menus_and_debug()
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QHBoxLayout(main_widget)
        
        # Left Panel (Connection & Devices) - Wider
        left_panel = QFrame()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMinimumWidth(350)
        left_panel.setMaximumWidth(400)
        main_layout.addWidget(left_panel, 0)
        
        port_group = QGroupBox("Connection")
        port_layout = QGridLayout(port_group)
        port_layout.setSpacing(5)
        port_layout.setContentsMargins(5, 5, 5, 5)
        port_layout.addWidget(QLabel("Port:"), 0, 0); self.port_input = QLineEdit("2150"); self.port_input.setFixedWidth(50)
        port_layout.addWidget(self.port_input, 0, 1)
        set_port_btn = QPushButton("Set"); set_port_btn.clicked.connect(lambda: self.web_interface.set_port(self.port_input.text())); port_layout.addWidget(set_port_btn, 0, 2)
        reconnect_btn = QPushButton("Reconnect"); reconnect_btn.clicked.connect(self.web_interface.force_reconnect); port_layout.addWidget(reconnect_btn, 0, 3)
        self.status_label = QLabel("DISCONNECTED"); self.status_label.setObjectName("status_label_fail")
        port_layout.addWidget(self.status_label, 1, 0, 1, 2)
        self.active_profile_label = QLabel("Profile: None"); self.active_profile_label.setStyleSheet("color: #aaa;")
        port_layout.addWidget(self.active_profile_label, 1, 2, 1, 2)
        left_layout.addWidget(port_group)

        devices_group = QGroupBox("Connected Devices")
        devices_layout = QVBoxLayout(devices_group)
        devices_layout.setSpacing(5)
        devices_layout.setContentsMargins(5, 5, 5, 5)
        self.device_list = QListWidget()
        self.populate_device_list()
        devices_layout.addWidget(self.device_list)
        joy_btn_layout = QHBoxLayout(); edit_bindings_btn = QPushButton("Edit Control Bindings"); edit_bindings_btn.clicked.connect(self.open_bindings_editor)
        refresh_joy_btn = QPushButton("Refresh Devices"); refresh_joy_btn.clicked.connect(self.refresh_devices)
        joy_btn_layout.addWidget(edit_bindings_btn); joy_btn_layout.addWidget(refresh_joy_btn)
        devices_layout.addLayout(joy_btn_layout)
        left_layout.addWidget(devices_group)

        launcher_group = QGroupBox("Game Launcher")
        launcher_main_layout = QVBoxLayout(launcher_group)
        launcher_main_layout.setSpacing(5)
        launcher_main_layout.setContentsMargins(5, 5, 5, 5)
        self.launch_button_layout = QGridLayout()
        launcher_main_layout.addLayout(self.launch_button_layout)
        edit_launchers_btn = QPushButton("Edit Launchers..."); edit_launchers_btn.clicked.connect(self.open_launcher_editor)
        launcher_main_layout.addWidget(edit_launchers_btn)
        
        # Logo under Edit Launchers
        icon_label = QLabel()
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_label.setPixmap(pixmap.scaled(80, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            icon_label.setMaximumHeight(80)
        icon_label.setAlignment(Qt.AlignCenter)
        launcher_main_layout.addWidget(icon_label)
        
        left_layout.addWidget(launcher_group)
        self.rebuild_launcher_buttons()
        left_layout.addStretch()

        # Middle panel - TrackIR (new column)
        trackir_panel = QFrame()
        trackir_layout = QVBoxLayout(trackir_panel)
        trackir_layout.setSpacing(5)
        trackir_layout.setContentsMargins(5, 5, 5, 5)
        trackir_panel.setMinimumWidth(320)
        trackir_panel.setMaximumWidth(360)
        main_layout.addWidget(trackir_panel, 0)

        # Right Panel (Controls)
        right_panel_scroll = QScrollArea()
        right_panel_scroll.setWidgetResizable(True)
        right_panel_scroll.setFrameShape(QFrame.NoFrame)
        right_panel_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_panel_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        main_layout.addWidget(right_panel_scroll, 2)
        
        scroll_content = QWidget()
        right_main_layout = QVBoxLayout(scroll_content)
        right_main_layout.setSpacing(5)
        right_main_layout.setContentsMargins(5, 5, 5, 5)
        right_panel_scroll.setWidget(scroll_content)
        
        top_section_layout = QHBoxLayout()
        top_section_layout.setSpacing(5)
        top_section_layout.setContentsMargins(0, 0, 0, 0)
        
        sliders_container = QWidget()
        sliders_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sliders_main_layout = QVBoxLayout(sliders_container)
        sliders_main_layout.setContentsMargins(5, 5, 5, 5)
        sliders_main_layout.setSpacing(5)
        sliders_layout = QGridLayout()
        sliders_layout.setSpacing(5)
        sliders_layout.setContentsMargins(5, 5, 5, 5)
        
        sliders = {k: v for k, v in CONTROL_DEFINITIONS.items() if v['type'] == 'slider'}
        row = 0
        for id, definition in sliders.items():
            label = QLabel(f"<b>{definition['desc']}</b> ({definition['range'][0]}-{definition['range'][1]})"); self.gui_labels[id] = label
            slider = QSlider(Qt.Horizontal); slider.setRange(definition['range'][0], definition['range'][1]); slider.setMinimumWidth(200)
            slider.valueChanged.connect(partial(self.handle_slider_move, id, slider)); slider.sliderReleased.connect(partial(self.handle_slider_release, id, slider))
            if id == "COMBINED_THROTTLE":
                self.combined_throttle_cb = QCheckBox("Use Combined Handle")
                self.invert_combined_cb = QCheckBox("Invert")
                row_layout = QHBoxLayout(); row_layout.addWidget(label); row_layout.addWidget(self.combined_throttle_cb); row_layout.addWidget(self.invert_combined_cb); row_layout.addStretch()
                sliders_layout.addLayout(row_layout, row, 0, 1, 2); row += 1
            else:
                 sliders_layout.addWidget(label, row, 0)
            sliders_layout.addWidget(slider, row, 1); self.gui_controls[id] = slider; row += 1
        sliders_main_layout.addLayout(sliders_layout)
        sliders_main_layout.addStretch()
        
        # TrackIR Integration
        trackir_group = QGroupBox("TrackIR Integration - Multi-Camera")
        trackir_main_layout = QVBoxLayout(trackir_group)
        trackir_main_layout.setSpacing(2)
        trackir_main_layout.setContentsMargins(4, 4, 4, 4)
        
        status_header = QLabel("<b>1. Camera Status</b>")
        trackir_main_layout.addWidget(status_header)
        
        cab_row_layout = QHBoxLayout()
        cab_row_layout.setSpacing(4)
        self.trackir_cab_radio = QRadioButton()
        self.trackir_cab_radio.setChecked(True)
        self.trackir_cab_radio.toggled.connect(self.on_camera_radio_changed)
        self.trackir_cab_label = QLabel("Cab: Not Found")
        self.trackir_cab_label.setStyleSheet("font-family: 'Courier New'; font-size: 9px; min-width: 150px;")
        self.trackir_cab_data = QLabel("Yaw: -- | Pitch: -- | X: -- | Y: -- | Z: --")
        self.trackir_cab_data.setStyleSheet("font-family: 'Courier New'; font-size: 8px; color: #888;")
        cab_row_layout.addWidget(self.trackir_cab_radio)
        cab_row_layout.addWidget(self.trackir_cab_label)
        cab_row_layout.addWidget(self.trackir_cab_data)
        cab_row_layout.addStretch()
        trackir_main_layout.addLayout(cab_row_layout)
        
        self.external_camera_container = QWidget()
        external_row_layout = QHBoxLayout(self.external_camera_container)
        external_row_layout.setSpacing(4)
        external_row_layout.setContentsMargins(0, 0, 0, 0)
        self.trackir_external_radio = QRadioButton()
        self.trackir_external_radio.toggled.connect(self.on_camera_radio_changed)
        self.trackir_external_label = QLabel("External: Not Found")
        self.trackir_external_label.setStyleSheet("font-family: 'Courier New'; font-size: 9px; min-width: 150px;")
        self.trackir_external_data = QLabel("Yaw: -- | Pitch: -- | X: -- | Y: -- | Z: --")
        self.trackir_external_data.setStyleSheet("font-family: 'Courier New'; font-size: 8px; color: #888;")
        external_row_layout.addWidget(self.trackir_external_radio)
        external_row_layout.addWidget(self.trackir_external_label)
        external_row_layout.addWidget(self.trackir_external_data)
        external_row_layout.addStretch()
        trackir_main_layout.addWidget(self.external_camera_container)
        self.external_camera_container.setVisible(False)
        
        self.interior_camera_container = QWidget()
        interior_row_layout = QHBoxLayout(self.interior_camera_container)
        interior_row_layout.setSpacing(4)
        interior_row_layout.setContentsMargins(0, 0, 0, 0)
        self.trackir_interior_radio = QRadioButton()
        self.trackir_interior_radio.toggled.connect(self.on_camera_radio_changed)
        self.trackir_interior_label = QLabel("Interior: Not Found")
        self.trackir_interior_label.setStyleSheet("font-family: 'Courier New'; font-size: 9px; min-width: 150px;")
        self.trackir_interior_data = QLabel("Yaw: -- | Pitch: -- | X: -- | Y: -- | Z: --")
        self.trackir_interior_data.setStyleSheet("font-family: 'Courier New'; font-size: 8px; color: #888;")
        interior_row_layout.addWidget(self.trackir_interior_radio)
        interior_row_layout.addWidget(self.trackir_interior_label)
        interior_row_layout.addWidget(self.trackir_interior_data)
        interior_row_layout.addStretch()
        trackir_main_layout.addWidget(self.interior_camera_container)
        self.interior_camera_container.setVisible(False)
        
        address_selection_group = QGroupBox("Address Selection (Multiple Found)")
        address_selection_layout = QVBoxLayout(address_selection_group)
        address_selection_layout.setSpacing(2)
        address_selection_layout.setContentsMargins(4, 4, 4, 4)
        self.cab_address_label = QLabel("Cab Addresses: None")
        self.cab_address_label.setStyleSheet("font-size: 9px; color: #aaa;")
        address_selection_layout.addWidget(self.cab_address_label)
        self.cab_address_list = QListWidget()
        self.cab_address_list.setMaximumHeight(60)
        self.cab_address_list.setStyleSheet("font-family: 'Courier New'; font-size: 9px;")
        self.cab_address_list.itemClicked.connect(lambda item: self.switch_camera_address('cab', item.text()))
        address_selection_layout.addWidget(self.cab_address_list)
        
        self.external_address_container = QWidget()
        ext_addr_layout = QVBoxLayout(self.external_address_container); ext_addr_layout.setContentsMargins(0, 0, 0, 0); ext_addr_layout.setSpacing(2)
        self.external_address_label = QLabel("External Addresses: None"); self.external_address_label.setStyleSheet("font-size: 9px; color: #aaa;")
        ext_addr_layout.addWidget(self.external_address_label)
        self.external_address_list = QListWidget(); self.external_address_list.setMaximumHeight(60); self.external_address_list.setStyleSheet("font-family: 'Courier New'; font-size: 9px;")
        self.external_address_list.itemClicked.connect(lambda item: self.switch_camera_address('external', item.text()))
        ext_addr_layout.addWidget(self.external_address_list); address_selection_layout.addWidget(self.external_address_container); self.external_address_container.setVisible(False)
        
        self.interior_address_container = QWidget()
        int_addr_layout = QVBoxLayout(self.interior_address_container); int_addr_layout.setContentsMargins(0, 0, 0, 0); int_addr_layout.setSpacing(2)
        self.interior_address_label = QLabel("Interior Addresses: None"); self.interior_address_label.setStyleSheet("font-size: 9px; color: #aaa;")
        int_addr_layout.addWidget(self.interior_address_label)
        self.interior_address_list = QListWidget(); self.interior_address_list.setMaximumHeight(60); self.interior_address_list.setStyleSheet("font-family: 'Courier New'; font-size: 9px;")
        self.interior_address_list.itemClicked.connect(lambda item: self.switch_camera_address('interior', item.text()))
        int_addr_layout.addWidget(self.interior_address_list); address_selection_layout.addWidget(self.interior_address_container); self.interior_address_container.setVisible(False)
        
        self.try_next_address_btn = QPushButton("Try Next Address (Cab)"); self.try_next_address_btn.setStyleSheet("font-size: 9px; padding: 3px;"); self.try_next_address_btn.clicked.connect(lambda: self.try_next_address('cab')); self.try_next_address_btn.setEnabled(False)
        address_selection_layout.addWidget(self.try_next_address_btn); trackir_main_layout.addWidget(address_selection_group)
        
        scan_header = QLabel("<b>Camera Scanning</b>"); trackir_main_layout.addWidget(scan_header)
        scan_grid = QGridLayout(); scan_grid.setSpacing(3); scan_grid.setContentsMargins(0, 0, 0, 0)
        self.trackir_scan_cab_btn = QPushButton("Scan Cab"); self.trackir_scan_cab_btn.clicked.connect(lambda: self.start_camera_scan('cab'))
        self.trackir_restart_cab_scan_btn = QPushButton("⟻ Restart Cab Scan"); self.trackir_restart_cab_scan_btn.setStyleSheet("font-size: 9px; padding: 3px;"); self.trackir_restart_cab_scan_btn.clicked.connect(lambda: self.restart_camera_scan('cab')); self.trackir_restart_cab_scan_btn.setEnabled(False)
        scan_grid.addWidget(self.trackir_restart_cab_scan_btn, 0, 1); self.trackir_scan_external_btn = QPushButton("Scan External"); self.trackir_scan_external_btn.clicked.connect(lambda: self.start_camera_scan('external'))
        self.trackir_scan_interior_btn = QPushButton("Scan Interior"); self.trackir_scan_interior_btn.clicked.connect(lambda: self.start_camera_scan('interior')); scan_grid.addWidget(self.trackir_scan_cab_btn, 0, 0)
        
        self.external_scan_container = QWidget(); ext_scan_layout = QHBoxLayout(self.external_scan_container); ext_scan_layout.setContentsMargins(0,0,0,0); ext_scan_layout.addWidget(self.trackir_scan_external_btn); scan_grid.addWidget(self.external_scan_container, 1, 0, 1, 2); self.external_scan_container.setVisible(False)
        self.interior_scan_container = QWidget(); int_scan_layout = QHBoxLayout(self.interior_scan_container); int_scan_layout.setContentsMargins(0,0,0,0); int_scan_layout.addWidget(self.trackir_scan_interior_btn); scan_grid.addWidget(self.interior_scan_container, 2, 0, 1, 2); self.interior_scan_container.setVisible(False)
        trackir_main_layout.addLayout(scan_grid)
        
        writer_header = QLabel("<b>2. Camera Writers</b>"); trackir_main_layout.addWidget(writer_header)
        writer_grid = QGridLayout(); writer_grid.setSpacing(3); writer_grid.setContentsMargins(0, 0, 0, 0)
        self.trackir_start_cab_writer_btn = QPushButton("Start Cab Writer"); self.trackir_start_cab_writer_btn.clicked.connect(lambda: self.start_individual_camera_writer('cab'))
        self.trackir_stop_cab_writer_btn = QPushButton("Stop Cab"); self.trackir_stop_cab_writer_btn.clicked.connect(lambda: self.stop_individual_camera_writer('cab')); self.trackir_stop_cab_writer_btn.setEnabled(False)
        self.trackir_start_external_writer_btn = QPushButton("Start External Writer"); self.trackir_start_external_writer_btn.clicked.connect(lambda: self.start_individual_camera_writer('external'))
        self.trackir_stop_external_writer_btn = QPushButton("Stop External"); self.trackir_stop_external_writer_btn.clicked.connect(lambda: self.stop_individual_camera_writer('external')); self.trackir_stop_external_writer_btn.setEnabled(False)
        self.trackir_start_interior_writer_btn = QPushButton("Start Interior Writer"); self.trackir_start_interior_writer_btn.clicked.connect(lambda: self.start_individual_camera_writer('interior'))
        self.trackir_stop_interior_writer_btn = QPushButton("Stop Interior"); self.trackir_stop_interior_writer_btn.clicked.connect(lambda: self.stop_individual_camera_writer('interior')); self.trackir_stop_interior_writer_btn.setEnabled(False)
        writer_grid.addWidget(self.trackir_start_cab_writer_btn, 0, 0); writer_grid.addWidget(self.trackir_stop_cab_writer_btn, 0, 1)
        
        self.external_writer_container = QWidget(); ext_writer_layout = QHBoxLayout(self.external_writer_container); ext_writer_layout.setContentsMargins(0,0,0,0); ext_writer_layout.addWidget(self.trackir_start_external_writer_btn); ext_writer_layout.addWidget(self.trackir_stop_external_writer_btn); writer_grid.addWidget(self.external_writer_container, 1, 0, 1, 2); self.external_writer_container.setVisible(False)
        self.interior_writer_container = QWidget(); int_writer_layout = QHBoxLayout(self.interior_writer_container); int_writer_layout.setContentsMargins(0,0,0,0); int_writer_layout.addWidget(self.trackir_start_interior_writer_btn); int_writer_layout.addWidget(self.trackir_stop_interior_writer_btn); writer_grid.addWidget(self.interior_writer_container, 2, 0, 1, 2); self.interior_writer_container.setVisible(False)
        trackir_main_layout.addLayout(writer_grid)
        
        global_btn_layout = QHBoxLayout(); global_btn_layout.setSpacing(3)
        self.trackir_start_all_btn = QPushButton("Start All Writers"); self.trackir_start_all_btn.clicked.connect(self.start_trackir_writer); self.trackir_stop_all_btn = QPushButton("Stop All Writers"); self.trackir_stop_all_btn.clicked.connect(self.stop_trackir_writer); self.trackir_stop_all_btn.setEnabled(False)
        trackir_settings_btn = QPushButton("Settings..."); trackir_settings_btn.clicked.connect(self.open_trackir_settings); global_btn_layout.addWidget(self.trackir_start_all_btn); global_btn_layout.addWidget(self.trackir_stop_all_btn); global_btn_layout.addWidget(trackir_settings_btn); trackir_main_layout.addLayout(global_btn_layout)
        
        # Add warning message about camera initialization
        trackir_warning = QLabel(
            "<b><u>⚠️THE PROGRAM NEEDS TO BE RUN AS ADMINISTRATOR⚠️</u></b><br><br>"
            "<b>Important:</b> Before starting TrackIR integration, "
            "<b>move the camera in-game first</b> "
            "to generate the memory location. If the scanner can't find the location in a reasonable time, "
            "restart the game and try again."
        )
        trackir_warning.setWordWrap(True)
        trackir_warning.setStyleSheet(
            "background-color: #3a2a1a; color: #ffcc00; padding: 8px; "
            "border: 1px solid #665522; border-radius: 4px; margin-top: 5px;"
        )
        trackir_main_layout.addWidget(trackir_warning)
        
        trackir_layout.addWidget(trackir_group); trackir_layout.addStretch()

        button_tabs = QTabWidget()
        button_tabs.setUsesScrollButtons(False)
        button_tabs.setDocumentMode(True)
        categories = {"cab": ("Cab Controls", QGridLayout()), "brakes": ("Brake Systems", QVBoxLayout()), "engine_electric": ("Engine (Electric)", QVBoxLayout()), "engine_diesel": ("Engine (Diesel)", QVBoxLayout()), "engine_steam": ("Engine (Steam)", QVBoxLayout()), "game": ("Game", QGridLayout()), "camera": ("Cameras", QGridLayout()), "debug": ("Debug", QGridLayout())}
        tab_order = ["cab", "brakes", "engine_electric", "engine_diesel", "engine_steam", "game", "camera", "debug"]
        for cat in tab_order:
            if cat in categories:
                title, layout = categories[cat]
                layout.setSpacing(5)
                layout.setContentsMargins(5, 5, 5, 5)
                tab = QWidget(); tab.setLayout(layout); button_tabs.addTab(tab, title)

        game_row, game_col = 0, 0; camera_row, camera_col = 0, 0; debug_row, debug_col = 0, 0; cab_row, cab_col = 0, 0
        for id, definition in CONTROL_DEFINITIONS.items():
            if definition['type'] == 'button':
                btn = QPushButton(definition['desc']); btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred); self.gui_controls[id] = btn
                behavior = definition.get("behavior")
                if behavior == "hold" or behavior == "toggle": btn.setCheckable(True); btn.toggled.connect(partial(self.handle_gui_toggle, id))
                elif behavior == "virtual": pass
                else: btn.pressed.connect(partial(self.handle_button_press, id))
                style = definition.get("style", "cab")
                if style == "cab": categories[style][1].addWidget(btn, cab_row, cab_col); cab_col += 1;
                elif style == "game": categories[style][1].addWidget(btn, game_row, game_col); game_col += 1;
                elif style == "camera": categories[style][1].addWidget(btn, camera_row, camera_col); camera_col += 1;
                elif style == "debug": categories[style][1].addWidget(btn, debug_row, debug_col); debug_col += 1;
                elif style in categories and style != "cab": categories[style][1].addWidget(btn)
                if cab_col > 1: cab_col = 0; cab_row += 1
                if game_col > 1: game_col = 0; game_row += 1
                if camera_col > 1: camera_col = 0; camera_row += 1
                if debug_col > 1: debug_col = 0; debug_row += 1
                if style != "cab": btn.setObjectName(f"{style}_button")

        for cat, (title, layout) in categories.items():
            if isinstance(layout, QGridLayout): layout.setRowStretch(layout.rowCount(), 1)
            else: layout.addStretch()
        
        top_section_layout = QHBoxLayout()
        top_section_layout.setSpacing(5)
        top_section_layout.setContentsMargins(0, 0, 0, 0)
        
        top_section_layout.addWidget(sliders_container, 1)
        top_section_layout.addWidget(button_tabs, 1)
        right_main_layout.addLayout(top_section_layout)
        right_main_layout.addStretch()

        for widget in self.gui_controls.values(): widget.setEnabled(False)

    def setup_menus_and_debug(self):
        main_debug_widget = QWidget()
        h_layout = QHBoxLayout(main_debug_widget); h_layout.setContentsMargins(0, 0, 0, 0); h_layout.setSpacing(5)
        self.debug_log = QTextEdit(); self.debug_log.setReadOnly(True); h_layout.addWidget(self.debug_log)
        self.trackir_debug_log = QTextEdit(); self.trackir_debug_log.setReadOnly(True); self.trackir_debug_log.setStyleSheet("font-family: 'Courier New';"); h_layout.addWidget(self.trackir_debug_log)
        self.debug_dock = QDockWidget("Debug Consoles (App Log | TrackIR Log)", self); self.debug_dock.setWidget(main_debug_widget); self.addDockWidget(Qt.BottomDockWidgetArea, self.debug_dock)
        menu_bar = self.menuBar(); file_menu = menu_bar.addMenu("File")
        file_menu.addAction("New Profile", self.new_profile); file_menu.addAction("Load Profile...", self.load_profile)
        file_menu.addAction("Save Profile", self.save_profile); file_menu.addAction("Save Profile As...", lambda: self.save_profile(save_as=True))
        self.set_default_profile_action = file_menu.addAction("Set Current as Default Profile", self.set_default_profile); self.set_default_profile_action.setEnabled(False)
        view_menu = menu_bar.addMenu("View"); view_menu.addAction(self.debug_dock.toggleViewAction())
        help_menu = menu_bar.addMenu("Help"); help_menu.addAction("About...", self.show_about_dialog); help_menu.addAction("Help / Readme", self.show_readme_dialog)
        self.log_message("Application starting...", "APP")

    def connect_signals(self):
        self.log_message("Connecting all signals...", "APP")
        self.device_list.itemChanged.connect(self.toggle_device_listener)
        self.trackir_log_signal.connect(self.trackir_debug_log.append)
        self.log_message("Connecting TrackIR rotation signal...", "APP")
        self.trackir_rotation_signal.connect(self.update_trackir_rotation_display)
        self.log_message("Connecting TrackIR position signal...", "APP")
        self.trackir_position_signal.connect(self.update_trackir_position_display)
        self.log_message("Connecting TrackIR address signals...", "APP")
        self.trackir_addresses_updated.connect(self.update_camera_labels)
        self.trackir_address_invalid.connect(self.on_trackir_address_invalid)
        self.web_interface.connection_status_changed.connect(self.on_connection_status_changed)
        self.web_interface.cab_controls_updated.connect(self.on_cab_controls_updated)
        self.web_interface.command_sent.connect(lambda p, c, v: self.log_message(f"{c} = {v}", f"SENT-{p}"))
        self.web_interface.update_received.connect(lambda data: self.log_message(data, "RECV"))
        self.joystick_manager.raw_joystick_event.connect(self.process_raw_joystick_input)
        self.saitek_manager.saitek_event.connect(self.process_saitek_input)
        self.launcher_editor.profiles_changed.connect(self.rebuild_launcher_buttons)
        self.log_message("All signals connected successfully", "APP")

    def update_trackir_rotation_display(self, yaw, pitch, roll):
        self.log_message(f"[TRACKIR DATA] Rotation received: Yaw={yaw:.2f}, Pitch={pitch:.2f}, Roll={roll:.2f}", "TRACKIR")
        data_text = f"Yaw: {yaw:>6.1f} | Pitch: {pitch:>6.1f}"
        self.trackir_cab_data.setText(data_text); self.trackir_external_data.setText(data_text); self.trackir_interior_data.setText(data_text)

    def update_trackir_position_display(self, x, y, z):
        self.log_message(f"[TRACKIR DATA] Position received: X={x:.2f}, Y={y:.2f}, Z={z:.2f}", "TRACKIR")
        data_text = f"X: {x:>6.1f} | Y: {y:>6.1f} | Z: {z:>6.1f}"
        for label in [self.trackir_cab_data, self.trackir_external_data, self.trackir_interior_data]:
            current = label.text()
            if '|' in current:
                rotation_part = current.split('|')[:2]
                label.setText(' | '.join(rotation_part) + ' | ' + data_text)

    def update_camera_labels(self):
        label_map = {'cab': self.trackir_cab_label, 'external': self.trackir_external_label, 'interior': self.trackir_interior_label}
        for camera_type, label in label_map.items():
            addresses = self.trackir_addresses[camera_type]
            if not addresses:
                label.setText(f"{camera_type.capitalize()}: Not Found"); label.setStyleSheet("font-family: 'Courier New'; font-size: 11px; color: #888;")
            elif len(addresses) == 1:
                addr = addresses[0]; is_active = (camera_type == self.trackir_active_camera); status = "[ACTIVE]" if is_active else "[INACTIVE]"
                label.setText(f"{camera_type.capitalize()}: {addr} {status}"); label.setStyleSheet("font-family: 'Courier New'; font-size: 11px; color: #00ff00;" if is_active else "font-family: 'Courier New'; font-size: 11px; color: #ffaa00;")
            else:
                addr = addresses[0]; is_active = (camera_type == self.trackir_active_camera); status = "[ACTIVE]" if is_active else "[INACTIVE]"
                label.setText(f"{camera_type.capitalize()}: {addr} (+{len(addresses)-1} more) {status}"); label.setStyleSheet("font-family: 'Courier New'; font-size: 11px; color: #00ff00;" if is_active else "font-family: 'Courier New'; font-size: 11px; color: #ffaa00;")
        self.update_writer_button_states(); self.update_address_list_display()

    def update_address_list_display(self):
        address_lists = {'cab': (self.cab_address_list, self.cab_address_label), 'external': (self.external_address_list, self.external_address_label), 'interior': (self.interior_address_list, self.interior_address_label)}
        for camera_type, (list_widget, label_widget) in address_lists.items():
            addresses = self.trackir_addresses.get(camera_type, []); list_widget.clear()
            if not addresses: label_widget.setText(f"{camera_type.capitalize()} Addresses: None")
            else:
                label_widget.setText(f"{camera_type.capitalize()} Addresses: {len(addresses)} found")
                for i, addr in enumerate(addresses):
                    if i == 0: item_text = f"{addr} [ACTIVE]"; item = QListWidgetItem(item_text); item.setBackground(QColor("#2d5016"))
                    else: item_text = addr; item = QListWidgetItem(item_text); item.setBackground(QColor("#3a3a3a"))
                    list_widget.addItem(item)
        self.try_next_address_btn.setEnabled(len(self.trackir_addresses.get('cab', [])) > 1)

    def switch_camera_address(self, camera_type, address_text):
        address_hex = address_text.split()[0]; self.log_message(f"User selected {camera_type} address: {address_hex}", "TRACKIR")
        if self.trackir_writer_process:
            try:
                pid = self.trackir_writer_process.pid; update_file = os.path.join(tempfile.gettempdir(), f"trackir_manual_switch_{pid}.dat")
                with open(update_file, 'w') as f: f.write(f"{camera_type}:{address_hex}\n")
                self.log_message(f"Sent manual address switch to writer", "TRACKIR")
            except Exception as e: self.log_message(f"Failed to send address switch: {e}", "ERROR")
        else:
            self.log_message("No writer running - address will be used on next start", "TRACKIR")
            if camera_type in self.trackir_addresses: self.trackir_addresses[camera_type] = [address_hex]
        self.update_address_list_display()

    def try_next_address(self, camera_type):
        addresses = self.trackir_addresses.get(camera_type, [])
        if len(addresses) < 2: self.log_message(f"Only one address available for {camera_type}", "TRACKIR"); return
        current = addresses[0]; addresses.append(addresses.pop(0)); next_addr = addresses[0]
        self.log_message(f"Switching {camera_type} from {current} to {next_addr}", "TRACKIR"); self.switch_camera_address(camera_type, next_addr)

    def on_camera_radio_changed(self):
        if self.trackir_cab_radio.isChecked(): self.trackir_active_camera = 'cab'
        elif self.trackir_external_radio.isChecked(): self.trackir_active_camera = 'external'
        elif self.trackir_interior_radio.isChecked(): self.trackir_active_camera = 'interior'
        self.update_camera_labels(); self.log_message(f"Active camera changed to: {self.trackir_active_camera}", "TRACKIR")
        if self.trackir_writer_process: self.send_active_camera_to_writer()

    def send_address_to_writer(self, camera_type, address_hex):
        if not self.trackir_writer_process: return
        try:
            pid = self.trackir_writer_process.pid; update_file = os.path.join(tempfile.gettempdir(), f"trackir_address_update_{pid}.dat")
            with open(update_file, 'w') as f: f.write(f"{camera_type}:{address_hex}\n")
            self.log_message(f"Sent {camera_type} address {address_hex} to writer", "TRACKIR")
        except Exception as e: self.log_message(f"Failed to send address to writer: {e}", "ERROR")

    def on_trackir_address_invalid(self, address_hex):
        self.log_message(f"Received write error for address {address_hex}. Marking as invalid.", "TRACKIR")
        if address_hex in self.trackir_addresses:
            try:
                idx = self.trackir_addresses.index(address_hex)
                if idx < len(self.trackir_region_labels):
                    self.trackir_region_labels[idx].setStyleSheet("QPushButton { text-align: left; padding: 4px; border: 1px solid #882222; border-radius: 3px; background-color: #4a1a1a; color: #aaa; text-decoration: line-through; }")
                    self.trackir_region_labels[idx].setEnabled(False)
                if idx == self.trackir_active_index: self.trackir_active_index = -1
            except Exception as e: self.log_message(f"Error updating GUI for invalid address: {e}", "ERROR")

    def log_message(self, text, source):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz")
        self.debug_log.append(f"[{timestamp}] [{source}] {text}")

    def on_connection_status_changed(self, is_connected, server_data):
        if is_connected:
            self.status_label.setText("CONNECTED"); self.status_label.setObjectName("status_label_ok"); self.log_message("Connection established.", "APP")
            server_active_button_ids = set(server_data); self.gui_controls['COMBINED_THROTTLE'].setEnabled(True)
            for our_id, definition in CONTROL_DEFINITIONS.items():
                widget = self.gui_controls.get(our_id)
                if not widget or our_id == 'COMBINED_THROTTLE' or definition.get('behavior') == 'virtual': continue
                if our_id in ['HORN', 'BELL']: widget.setEnabled(True); continue
                if 'id' in definition:
                    command_id = definition.get('id')
                    is_active = any(sub_id in server_active_button_ids for sub_id in command_id) if isinstance(command_id, list) else command_id in server_active_button_ids
                    widget.setEnabled(is_active)
        else:
            self.status_label.setText("DISCONNECTED"); self.status_label.setObjectName("status_label_fail")
            error_msg = server_data[0] if isinstance(server_data, list) and server_data else "Connection lost."
            self.log_message(f"Connection failed or lost: {error_msg}", "APP")
            for widget in self.gui_controls.values(): widget.setEnabled(False)
        self.status_label.style().unpolish(self.status_label); self.status_label.style().polish(self.status_label)
    
    def on_cab_controls_updated(self, server_data):
        self.active_cab_controls = server_data
        if not server_data: return
        active_slider_names = {control['TypeName'] for control in server_data}
        for control_id, definition in CONTROL_DEFINITIONS.items():
            if definition.get('type') != 'slider' or 'id' in definition: continue
            widget = self.gui_controls.get(control_id); label = self.gui_labels.get(control_id)
            if not widget or not label: continue
            if control_id in active_slider_names:
                widget.setEnabled(True); control_data = next((c for c in server_data if c['TypeName'] == control_id), None)
                if control_data:
                    min_val_f, max_val_f = control_data['MinValue'], control_data['MaxValue']
                    if max_val_f == 1.0 and min_val_f == 0.0: widget.setRange(0, 100); label.setText(f"<b>{definition['desc']}</b> (0-100)")
                    else:
                        min_val, max_val = int(min_val_f), int(max_val_f); widget.setRange(min_val, max_val); label.setText(f"<b>{definition['desc']}</b> ({min_val}-{max_val})")
            else: widget.setEnabled(False)

    def process_raw_joystick_input(self, joy_id, type, index, value):
        if type == 'axis':
            percentage = ((value + 1) / 2.0) * 100; at_max = "⚠ AT MAX" if abs(value) >= 0.95 else ""
            bound_to = "UNBOUND"
            for control_id, bindings in self.bindings.items():
                axis_binding = bindings.get('axis')
                if axis_binding:
                    if isinstance(axis_binding, list): axis_binding = axis_binding[0]
                    if (axis_binding.get('joy_id') == joy_id and axis_binding.get('index') == index): bound_to = control_id; break
            self.log_message(f"[AXIS RAW] Joy{joy_id} Axis{index} → {bound_to}: Raw={value:.6f} ({percentage:.2f}%) {at_max}", "DEBUG")
        if type == 'axis':
            last_value_key = f"joy{joy_id}_axis{index}"; last_value = getattr(self, '_last_axis_values', {}).get(last_value_key, 0.0)
            if abs(value - last_value) < 0.01: return
            if not hasattr(self, '_last_axis_values'): self._last_axis_values = {}
            self._last_axis_values[last_value_key] = value
        if type == 'button':
            if not hasattr(self, '_button_states'): self._button_states = {}
            button_key = f"joy{joy_id}_btn{index}"; old_state = self._button_states.get(button_key, 0.0); self._button_states[button_key] = value
            if old_state == 1.0 and value == 0.0:
                for control_id, control_bindings in self.bindings.items():
                    # Check if ANY button binding for this control has override='toggle_on_press'
                    skip_release = False
                    button_bindings = control_bindings.get('button', [])
                    if not isinstance(button_bindings, list): button_bindings = [button_bindings]
                    
                    for b in button_bindings:
                        if (isinstance(b, dict) and 
                            b.get('device_type') == 'joystick' and 
                            b.get('joy_id') == joy_id and 
                            b.get('index') == index and 
                            b.get('override') == 'toggle_on_press'):
                            skip_release = True
                            self.log_message(f"Ignoring button release for {control_id} due to toggle_on_press override", "BINDING")
                            break
                    
                    if skip_release:
                        continue
                    
                    # WORKAROUND HOLD: Process release events for workaround controls
                    use_workaround = control_bindings.get("use_workaround", False)
                    if use_workaround:
                        button_bindings = control_bindings.get('button', [])
                        if not isinstance(button_bindings, list): button_bindings = [button_bindings]
                        
                        for b in button_bindings:
                            if (isinstance(b, dict) and 
                                b.get('device_type') == 'joystick' and 
                                b.get('joy_id') == joy_id and 
                                b.get('index') == index):
                                # Send release event to workaround
                                self.execute_binding(control_id, 'button', 0.0)
                                break
                    
                    # Process off_button bindings normally
                    off_button_bindings = control_bindings.get('off_button', [])
                    if not isinstance(off_button_bindings, list): off_button_bindings = [off_button_bindings]
                        
                    for binding in off_button_bindings:
                        if (isinstance(binding, dict) and binding.get('device_type') == 'joystick' and binding.get('joy_id') == joy_id and binding.get('index') == index):
                            self.execute_binding(control_id, 'off_button', 0.0); self.log_message(f"Switch OFF detected: {control_id}", "BINDING")
                    values_dict = control_bindings.get('values', {})
                    for step_value, binding_list in values_dict.items():
                        bindings = binding_list if isinstance(binding_list, list) else [binding_list]
                        for binding in bindings:
                            if (isinstance(binding, dict) and binding.get('device_type') == 'joystick' and binding.get('joy_id') == joy_id and binding.get('index') == index):
                                self.release_step_binding(control_id, step_value); break
        if type == 'button' and value == 1.0:
            virtual_controls = ["TOGGLE_COMBINED_THROTTLE", "TOGGLE_INVERT_COMBINED", "TOGGLE_TRACKIR", "SCAN_CAB_CAMERA", "SCAN_EXTERNAL_CAMERA", "SCAN_INTERIOR_CAMERA", "RESCAN_CAB_CAMERA", "RESCAN_EXTERNAL_CAMERA", "RESCAN_INTERIOR_CAMERA", "START_CAB_WRITER", "STOP_CAB_WRITER", "START_EXTERNAL_WRITER", "STOP_EXTERNAL_WRITER", "START_INTERIOR_WRITER", "STOP_INTERIOR_WRITER", "COMBINED_THROTTLE"]
            for control_id in virtual_controls:
                control_bindings = self.bindings.get(control_id, {}); button_bindings = control_bindings.get('button', [])
                if not isinstance(button_bindings, list): button_bindings = [button_bindings]
                for binding in button_bindings:
                    if (isinstance(binding, dict) and binding.get('device_type') == 'joystick' and binding.get('joy_id') == joy_id and binding.get('index') == index):
                        self.log_message(f"Virtual control button detected: {control_id} from Joy{joy_id} Btn{index}", "BINDING"); self.execute_binding(control_id, 'button', 1.0); return
        if self.combined_throttle_cb.isChecked():
            binding = self.bindings.get("COMBINED_THROTTLE", {}).get("axis")
            if binding and binding.get('joy_id') == joy_id and binding.get('index') == index and type == 'axis':
                active_slider_names = {c['TypeName'] for c in self.active_cab_controls}; brake_type = "TRAIN_BRAKE" 
                if 'DYNAMIC_BRAKE' in active_slider_names and 'TRAIN_BRAKE' not in active_slider_names: brake_type = 'DYNAMIC_BRAKE'
                if binding.get("inverted", False): value = -value
                if self.invert_combined_cb.isChecked(): value = -value
                self.handle_combined_brake_logic(brake_type, value); return 
        for control_id, control_bindings in self.bindings.items():
            if 'values' in control_bindings and type == 'button' and value == 1.0:
                for step_value, binding_list in control_bindings['values'].items():
                    bindings = binding_list if isinstance(binding_list, list) else [binding_list]
                    for binding_data in bindings:
                        if binding_data.get('device_type') == 'joystick' and binding_data.get('joy_id') == joy_id and binding_data.get('index') == index:
                            self.log_message(f"Button {index} pressed → {control_id} step {step_value}", "DEBUG")
                            self.execute_step_binding(control_id, step_value)
                            return
            for binding_type, binding_data in control_bindings.items():
                if binding_type in ['values', 'use_workaround', 'incremental_mode', 'binding_behavior_override']: continue
                bindings = binding_data if isinstance(binding_data, list) else [binding_data]
                for binding in bindings:
                    if not isinstance(binding, dict): continue
                    if binding.get('device_type') == 'joystick' and binding.get('joy_id') == joy_id and binding.get('index') == index:
                        override = binding.get('override')
                        if (binding_type == 'axis' and type == 'axis') or (binding_type != 'axis' and type == 'button'): 
                            self.execute_binding(control_id, binding_type, value, override)
                        
    def process_saitek_input(self, switch, state):
        if not hasattr(self, '_saitek_switch_states'): 
            self._saitek_switch_states = {}
        
        old_state = self._saitek_switch_states.get(switch)
        self._saitek_switch_states[switch] = state
        
        # Log the raw input
        self.log_message(f"🎛️ Saitek: {switch} → {state}", "SAITEK")
        
        for control_id, control_bindings in self.bindings.items():
            # Handle stepped values (3-way switches, etc.)
            if 'values' in control_bindings and state == "ON":
                for step_value, binding_list in control_bindings['values'].items():
                    bindings = binding_list if isinstance(binding_list, list) else [binding_list]
                    for binding_data in bindings:
                        if (binding_data.get('device_type') == 'saitek' and 
                            binding_data.get('switch') == switch):
                            self.log_message(f"  ✓ Matched stepped binding: {control_id} step={step_value}", "SAITEK")
                            self.execute_step_binding(control_id, step_value)
                            return
            
            # Handle regular bindings - SIMPLE like old version
            for binding_type, binding_data in control_bindings.items():
                if binding_type in ['values', 'use_workaround', 'incremental_mode']: 
                    continue
                
                bindings = binding_data if isinstance(binding_data, list) else [binding_data]
                
                for binding in bindings:
                    if not isinstance(binding, dict): 
                        continue
                    
                    # Check if this binding matches the Saitek input
                    if binding.get('device_type') == 'saitek' and binding.get('switch') == switch:
                        expected_state = binding.get('state')
                        
                        # Log what we're checking
                        self.log_message(
                            f"  🔍 Checking {control_id}.{binding_type}: "
                            f"expected_state={expected_state}, actual_state={state}, "
                            f"match={expected_state == state}", 
                            "SAITEK"
                        )
                        
                        # Only execute if state matches
                        if expected_state == state:
                            # For Saitek switches, always pass the correct value based on state
                            # ON = 1.0, OFF = 0.0 (even for off_button bindings)
                            value_to_send = 1.0 if state == "ON" else 0.0
                            self.log_message(f"  ✓ Executing: {control_id}.{binding_type} with value={value_to_send}", "SAITEK")
                            self.execute_binding(control_id, binding_type, value_to_send)
                        else:
                            self.log_message(f"  ✗ Skipped (state mismatch)", "SAITEK")

    def execute_binding(self, control_id, binding_type, value, override=None):
        control_bindings = self.bindings.get(control_id, {}); use_workaround = control_bindings.get("use_workaround", False)
        
        # Add logging for workaround detection
        if use_workaround and value >= 0.0:  # Changed: process both press (1.0) and release (0.0)
            self.log_message(f"⚙ Workaround triggered for {control_id}, value={value}, binding_type={binding_type}", "WORKAROUND")
            try:
                import win32gui
                hwnd = win32gui.GetForegroundWindow()
                window_text = win32gui.GetWindowText(hwnd)
                
                # Only log window check on initial press to reduce spam
                if value == 1.0:
                    self.log_message(f"🖥 Foreground window: '{window_text}'", "WORKAROUND")
                
                if "RunActivity" in window_text or "Open Rails" in window_text:
                    if value == 1.0:
                        self.log_message(f"✔ Game window is focused - proceeding with workaround", "WORKAROUND")
                    
                    # Collect all keyboard bindings for this control
                    keyboard_bindings = []
                    for key in ['button', 'off_button', 'increase', 'decrease']:
                        bindings = control_bindings.get(key, [])
                        if not isinstance(bindings, list):
                            bindings = [bindings]
                        for b in bindings:
                            if isinstance(b, dict) and b.get('device_type') == 'keyboard':
                                keyboard_bindings.append(b)
                    
                    if keyboard_bindings:
                        if value == 1.0:
                            self.log_message(f"⌨ Found {len(keyboard_bindings)} keyboard binding(s)", "WORKAROUND")
                        
                        for kb_binding in keyboard_bindings:
                            key_str = kb_binding.get('key', '')
                            if not key_str:
                                continue
                            
                            # Create unique key for tracking this binding
                            tracking_key = f"{control_id}_{key_str}"
                            
                            try:
                                # PRESS EVENT (value == 1.0)
                                if value == 1.0:
                                    self.log_message(f"⇨ Pressing and HOLDING key: '{key_str}'", "WORKAROUND")
                                    
                                    # Handle modifier combinations (e.g., "ctrl_shift_a")
                                    if '_' in key_str:
                                        parts = key_str.split('_')
                                        self.log_message(f"  Parsing key combo: {parts}", "WORKAROUND")
                                        
                                        modifiers = []
                                        main_key = parts[-1]
                                        
                                        for part in parts[:-1]:
                                            if part == 'ctrl':
                                                modifiers.append(Key.ctrl)
                                            elif part == 'shift':
                                                modifiers.append(Key.shift)
                                            elif part == 'alt':
                                                modifiers.append(Key.alt)
                                            elif part == 'win':
                                                modifiers.append(Key.cmd)
                                        
                                        # Press and HOLD modifiers
                                        for mod in modifiers:
                                            self.keyboard_controller.press(mod)
                                        
                                        # Press and HOLD main key
                                        self.keyboard_controller.press(main_key)
                                        
                                        # Store what we pressed so we can release it later
                                        self.held_keys[tracking_key] = {
                                            'modifiers': modifiers,
                                            'main_key': main_key,
                                            'is_combo': True
                                        }
                                        
                                        self.log_message(f"  ✔ Hotkey combo HELD", "WORKAROUND")
                                    
                                    else:
                                        # Single key - press and HOLD
                                        self.log_message(f"  Pressing and holding: '{key_str}'", "WORKAROUND")
                                        
                                        # Try to map to Key enum first
                                        try:
                                            if hasattr(Key, key_str):
                                                key_obj = getattr(Key, key_str)
                                                self.keyboard_controller.press(key_obj)
                                                self.held_keys[tracking_key] = {
                                                    'key': key_obj,
                                                    'is_combo': False
                                                }
                                            else:
                                                # Regular character key (including "/")
                                                self.keyboard_controller.press(key_str)
                                                self.held_keys[tracking_key] = {
                                                    'key': key_str,
                                                    'is_combo': False
                                                }
                                            
                                            self.log_message(f"  ✔ Key '{key_str}' HELD DOWN", "WORKAROUND")
                                        
                                        except Exception as key_error:
                                            self.log_message(f"  ✗ Key mapping error: {key_error}", "ERROR")
                                            # Fallback
                                            self.keyboard_controller.press(key_str)
                                            self.held_keys[tracking_key] = {
                                                'key': key_str,
                                                'is_combo': False
                                            }
                                    
                                    # SUCCESS - mark this control as having held keys
                                    return
                                
                                # RELEASE EVENT (value == 0.0)
                                elif value == 0.0:
                                    self.log_message(f"⇧ Releasing key: '{key_str}'", "WORKAROUND")
                                    
                                    if tracking_key in self.held_keys:
                                        held_data = self.held_keys[tracking_key]
                                        
                                        if held_data['is_combo']:
                                            # Release combo (reverse order)
                                            self.keyboard_controller.release(held_data['main_key'])
                                            for mod in reversed(held_data['modifiers']):
                                                self.keyboard_controller.release(mod)
                                            self.log_message(f"  ✔ Hotkey combo RELEASED", "WORKAROUND")
                                        else:
                                            # Release single key
                                            self.keyboard_controller.release(held_data['key'])
                                            self.log_message(f"  ✔ Key '{key_str}' RELEASED", "WORKAROUND")
                                        
                                        # Remove from tracking
                                        del self.held_keys[tracking_key]
                                    else:
                                        self.log_message(f"  ⚠ Key '{key_str}' was not held (already released?)", "WORKAROUND")
                                    
                                    return
                                
                            except Exception as e:
                                self.log_message(f"  ✗ Keyboard emulation error: {e}", "ERROR")
                                import traceback
                                self.log_message(f"  Stack trace: {traceback.format_exc()}", "ERROR")
                                
                                # Clean up on error
                                if tracking_key in self.held_keys:
                                    del self.held_keys[tracking_key]
                                continue
                        
                        # If we get here, no bindings succeeded
                        if value == 1.0:
                            self.log_message(f"✗ All keyboard bindings failed", "ERROR")
                        return
                    else:
                        if value == 1.0:
                            self.log_message(f"⚠ No keyboard bindings configured for {control_id}", "WORKAROUND")
                        return
                else:
                    if value == 1.0:
                        self.log_message(f"✗ Game window not focused ('{window_text}') - workaround skipped", "WORKAROUND")
                    return
                    
            except Exception as e:
                self.log_message(f"⚠ Workaround system error: {e}", "ERROR")
                import traceback
                self.log_message(f"Stack trace: {traceback.format_exc()}", "ERROR")
                return
        virtual_controls = ["TOGGLE_COMBINED_THROTTLE", "TOGGLE_INVERT_COMBINED", "TOGGLE_TRACKIR", "SCAN_CAB_CAMERA", "SCAN_EXTERNAL_CAMERA", "SCAN_INTERIOR_CAMERA", "RESCAN_CAB_CAMERA", "RESCAN_EXTERNAL_CAMERA", "RESCAN_INTERIOR_CAMERA", "START_CAB_WRITER", "STOP_CAB_WRITER", "START_EXTERNAL_WRITER", "STOP_EXTERNAL_WRITER", "START_INTERIOR_WRITER", "STOP_INTERIOR_WRITER", "COMBINED_THROTTLE"]
        if control_id in virtual_controls:
            if control_id == "TOGGLE_COMBINED_THROTTLE":
                if binding_type == "button" and value == 1.0: self.combined_throttle_cb.setChecked(True); return
                if binding_type == "off_button" and value == 0.0: self.combined_throttle_cb.setChecked(False); return
                if binding_type == "button" and value == 0.0 and 'off_button' not in control_bindings: self.combined_throttle_cb.setChecked(not self.combined_throttle_cb.isChecked()); return
                if binding_type in ["button", "off_button"]: return
            if control_id == "TOGGLE_INVERT_COMBINED":
                if binding_type == "button" and value == 1.0: self.invert_combined_cb.setChecked(True); return
                if binding_type == "off_button" and value == 0.0: self.invert_combined_cb.setChecked(False); return
                if binding_type == "button" and value == 0.0 and 'off_button' not in control_bindings: self.invert_combined_cb.setChecked(not self.invert_combined_cb.isChecked()); return
                if binding_type in ["button", "off_button"]: return
            if control_id == "TOGGLE_TRACKIR":
                # For toggle buttons: only respond to press (value=1.0), ignore release unless separate off_button exists
                if binding_type == "button" and value == 1.0:
                    # Toggle: if running, stop it; if stopped, start it
                    if self.trackir_writer_process:
                        self.stop_trackir_writer()
                    else:
                        self.start_trackir_writer()
                    return
                if binding_type == "off_button" and value == 0.0: 
                    self.stop_trackir_writer()
                    return
                # Ignore button release (value=0.0) if no separate off_button
                if binding_type == "button" and value == 0.0:
                    return
            if value == 1.0:
                if control_id == "SCAN_CAB_CAMERA": self.start_camera_scan('cab'); return
                if control_id == "SCAN_EXTERNAL_CAMERA": self.start_camera_scan('external'); return
                if control_id == "SCAN_INTERIOR_CAMERA": self.start_camera_scan('interior'); return
                if control_id == "RESCAN_CAB_CAMERA": self.restart_camera_scan('cab'); return
                if control_id == "RESCAN_EXTERNAL_CAMERA": self.restart_camera_scan('external'); return
                if control_id == "RESCAN_INTERIOR_CAMERA": self.restart_camera_scan('interior'); return
                if control_id == "START_CAB_WRITER": self.start_individual_camera_writer('cab'); return
                if control_id == "STOP_CAB_WRITER": self.stop_individual_camera_writer('cab'); return
                if control_id == "START_EXTERNAL_WRITER": self.start_individual_camera_writer('external'); return
                if control_id == "STOP_EXTERNAL_WRITER": self.stop_individual_camera_writer('external'); return
                if control_id == "START_INTERIOR_WRITER": self.start_individual_camera_writer('interior'); return
                if control_id == "STOP_INTERIOR_WRITER": self.stop_individual_camera_writer('interior'); return
        widget = self.gui_controls.get(control_id)
        if not widget or not widget.isEnabled(): return
        definition = CONTROL_DEFINITIONS[control_id]
        if definition['type'] == 'slider':
            binding_data = self.bindings.get(control_id, {}).get(binding_type)
            if not binding_data: return
            if binding_type == 'axis':
                if isinstance(binding_data, list): binding_data = binding_data[0]
                if binding_data.get("inverted", False): value = -value
                if 'id' in definition:
                    min_val, max_val = widget.minimum(), widget.maximum(); target_value = int(min_val + ((value + 1) / 2) * (max_val - min_val)); current_value = widget.value()
                    if target_value > current_value: [self.web_interface.send_ws_click(definition['id'][1]) for _ in range(target_value - current_value)]
                    elif target_value < current_value: [self.web_interface.send_ws_click(definition['id'][0]) for _ in range(current_value - target_value)]
                    widget.blockSignals(True); widget.setValue(target_value); widget.blockSignals(False)
                else: 
                    AXIS_DEADZONE = 0.02; AXIS_MAX_THRESHOLD = 0.95
                    if abs(value) < AXIS_DEADZONE: value = 0.0
                    elif abs(value) > AXIS_MAX_THRESHOLD: value = 1.0 if value > 0 else -1.0
                    range_fraction = (value + 1) / 2.0; self.web_interface.send_control_value(control_id, range_fraction)
                    display_value = int(widget.minimum() + range_fraction * (widget.maximum() - widget.minimum()))
                    widget.blockSignals(True); widget.setValue(display_value); widget.blockSignals(False)
            elif binding_type in ["increase", "decrease"] and value == 1.0:
                if self.bindings.get(control_id, {}).get("incremental_mode", False):
                    new_val = max(widget.minimum(), min(widget.maximum(), widget.value() + (1 if binding_type == 'increase' else -1)))
                    self.send_slider_value_from_gui(control_id, new_val); widget.setValue(new_val)
        elif definition['type'] == 'button':
            command_id = definition.get('id')
            if command_id is None: return
            
            # OVERRIDE: Toggle on Press
            if override == 'toggle_on_press':
                if value == 1.0: # Press event only
                     self.web_interface.send_ws_click(command_id)
                     # Visually toggle the GUI button
                     widget.blockSignals(True)
                     widget.setChecked(not widget.isChecked())
                     widget.blockSignals(False)
                return # Skip standard processing
            
            if definition.get("send_as") == "value": self.web_interface.send_control_value(control_id, value); widget.blockSignals(True); widget.setChecked(value == 1.0); widget.blockSignals(False); return
            behavior = definition.get("behavior")
            if behavior == "toggle":
                # TOGGLE BEHAVIOR (from old working code):
                # - Momentary button (joystick): bound to 'button' only, fires on press (value=1.0)
                # - Maintained switch (Saitek): bound to 'button' (ON) AND 'off_button' (OFF)
                # 
                # Send click when:
                # 1. 'button' binding fires with value=1.0 (press OR switch ON)
                # 2. 'off_button' binding fires (ANY value - usually 0.0 for Saitek OFF)
                if (binding_type == 'button' and value == 1.0) or (binding_type == 'off_button'):
                    self.web_interface.send_ws_click(command_id)
                    self.log_message(f"✓ Toggle click sent for {control_id} (type={binding_type}, value={value})", "BIND")
                
                # Update GUI state to reflect physical input's state
                widget.blockSignals(True)
                widget.setChecked(value == 1.0)
                widget.blockSignals(False)
            elif behavior == "hold": 
                event = "buttonDown" if value == 1.0 else "buttonUp"
                self.web_interface.send_button_event(command_id, event)
                self.log_message(f"✓ Hold event sent for {control_id}: {event} (value={value})", "BIND")
                widget.blockSignals(True); widget.setChecked(value == 1.0); widget.blockSignals(False)
            elif value == 1.0: self.web_interface.send_ws_click(command_id)
    
    def execute_step_binding(self, control_id, target_step_str):
        """Execute a stepped slider binding (for 3-way switches, etc.)"""
        widget = self.gui_controls.get(control_id)
        if not widget or not widget.isEnabled(): return
        definition = CONTROL_DEFINITIONS[control_id]
        if 'id' not in definition or definition.get('type') != 'slider': return
        try: target_value = int(target_step_str)
        except (ValueError, TypeError): self.log_message(f"Invalid step value '{target_step_str}' for {control_id}", "ERROR"); return
        # Track which buttons are pressed for this control (for 3-way switch neutral detection)
        if not hasattr(self, '_active_step_buttons'): self._active_step_buttons = {}
        
        # IMPORTANT: For 3-way switches, only ONE position can be active at a time
        # Clear ALL other steps for this control before setting the new one
        control_steps = self._active_step_buttons.setdefault(control_id, {})
        control_steps.clear()  # Clear all previous steps
        control_steps[target_step_str] = True  # Set only this step as active
        
        self.log_message(f"{control_id}: Button pressed for step {target_step_str}, cleared other steps", "DEBUG")
        current_value = self.slider_last_values.get(control_id, widget.value())
        if target_value > current_value: [self.web_interface.send_ws_click(definition['id'][1]) for _ in range(target_value - current_value)]
        elif target_value < current_value: [self.web_interface.send_ws_click(definition['id'][0]) for _ in range(current_value - target_value)]
        widget.blockSignals(True); widget.setValue(target_value); widget.blockSignals(False); self.slider_last_values[control_id] = target_value; self.log_message(f"Set {control_id} to step {target_value}", "BINDING")

    def release_step_binding(self, control_id, step_str):
        """Handle button release for stepped sliders - check if we should return to neutral"""
        if not hasattr(self, '_active_step_buttons'): return
        control_steps = self._active_step_buttons.get(control_id, {})
        # Mark this step button as released
        if step_str in control_steps:
            del control_steps[step_str]
            self.log_message(f"{control_id}: Released step {step_str}, remaining active: {list(control_steps.keys())}", "DEBUG")
        
        # If ALL buttons for this control are released, go to neutral (step 0)
        if not control_steps:
            self.log_message(f"{control_id}: All buttons released, returning to NEUTRAL (step 0)", "BINDING")
            definition = CONTROL_DEFINITIONS[control_id]; steps = definition.get('steps', {})
            neutral_step = None
            for step_val, step_name in steps.items():
                if step_val == "0" or "Neutral" in step_name or "N" == step_name: neutral_step = step_val; break
            if neutral_step is not None: self.execute_step_binding(control_id, neutral_step)

    def handle_combined_brake_logic(self, brake_type, value):
        throttle_widget = self.gui_controls.get("THROTTLE"); brake_widget = self.gui_controls.get(brake_type); combined_widget = self.gui_controls.get("COMBINED_THROTTLE")
        if not all([throttle_widget, brake_widget, combined_widget]): return
        if value >= 0: self.web_interface.send_control_value("THROTTLE", value); self.web_interface.send_control_value(brake_type, 0.0); throttle_display = int(value * 100); brake_display = 0; combined_display = int(value * 100)
        else: brake_fraction = -value; self.web_interface.send_control_value("THROTTLE", 0.0); self.web_interface.send_control_value(brake_type, brake_fraction); throttle_display = 0; brake_display = int(brake_fraction * 100); combined_display = -int(brake_fraction * 100)
        throttle_widget.blockSignals(True); throttle_widget.setValue(throttle_display); throttle_widget.blockSignals(False); brake_widget.blockSignals(True); brake_widget.setValue(brake_display); brake_widget.blockSignals(False); combined_widget.blockSignals(True); combined_widget.setValue(combined_display); combined_widget.blockSignals(False)

    def toggle_device_listener(self, item):
        device_id = item.data(Qt.UserRole); is_checked = item.checkState() == Qt.Checked
        if device_id == "SAITEK_PANEL":
            if is_checked:
                if self.saitek_manager.start_listening(): self.log_message("Saitek Panel listener started.", "APP")
                else: self.log_message("ERROR: Failed to start Saitek Panel listener.", "ERROR"); item.setCheckState(Qt.Unchecked)
            else: self.saitek_manager.stop_listening()
        else: self.joystick_manager.start_listening(device_id) if is_checked else self.joystick_manager.stop_listening(device_id)
        
    def open_bindings_editor(self):
        editor = BindingsEditor(self.bindings, self)
        def joy_capture(joy_id, type, index, value):
            if type == "button" and value == 1.0: editor.capture_input(joy_id, type, index, value, "joystick")
            elif type == "axis" and abs(value) > 0.8: editor.capture_input(joy_id, type, index, value, "joystick")
        self.joystick_manager.raw_joystick_event.connect(joy_capture)
        def saitek_capture(switch, state): editor.capture_input(None, "saitek", switch, 1.0 if state == "ON" else 0.0, "saitek")
        self.saitek_manager.saitek_event.connect(saitek_capture)
        if editor.exec_():
            self.bindings = editor.get_bindings()
            if self.current_profile_path: self.save_profile()
        try:
            self.joystick_manager.raw_joystick_event.disconnect(joy_capture)
            self.saitek_manager.saitek_event.disconnect(saitek_capture)
        except TypeError: pass

    def handle_slider_move(self, control_id, slider, value):
        if control_id in self.bindings and "axis" in self.bindings.get(control_id, {}): return
        self.send_slider_value_from_gui(control_id, value)
        
    def handle_slider_release(self, control_id, slider):
        if control_id in self.bindings and "axis" in self.bindings.get(control_id, {}): return
        self.send_slider_value_from_gui(control_id, slider.value())
        
    def send_slider_value_from_gui(self, control_id, value):
        slider = self.gui_controls[control_id]; definition = CONTROL_DEFINITIONS[control_id]
        if 'id' in definition:
            last_val = self.slider_last_values.get(control_id, slider.value())
            if value > last_val: [self.web_interface.send_ws_click(definition['id'][1]) for _ in range(value - last_val)]
            elif value < last_val: [self.web_interface.send_ws_click(definition['id'][0]) for _ in range(last_val - value)]
            self.slider_last_values[control_id] = value
        else:
            min_val, max_val = slider.minimum(), slider.maximum(); range_size = max_val - min_val
            fraction = (value - min_val) / range_size if range_size > 0 else 0
            self.web_interface.send_control_value(control_id, fraction)
            
    def handle_button_press(self, control_id):
        command_id = CONTROL_DEFINITIONS[control_id].get('id')
        if command_id is not None: self.web_interface.send_ws_click(command_id)

    def handle_gui_toggle(self, control_id, is_checked):
        definition = CONTROL_DEFINITIONS[control_id]; command_id = definition.get('id')
        if command_id is None: return
        if definition.get("send_as") == "value": self.web_interface.send_control_value(control_id, 1.0 if is_checked else 0.0); return
        behavior = definition.get("behavior")
        if behavior == "toggle": self.web_interface.send_ws_click(command_id)
        elif behavior == "hold": event = "buttonDown" if is_checked else "buttonUp"; self.web_interface.send_button_event(command_id, event)

    def new_profile(self):
        self.bindings.clear(); self.current_profile_path = None; self.slider_last_values.clear(); self.combined_throttle_cb.setChecked(False); self.invert_combined_cb.setChecked(False); self.active_profile_label.setText("Profile: None")
        for i in range(self.device_list.count()): self.device_list.item(i).setCheckState(Qt.Unchecked)
        self.set_default_profile_action.setEnabled(False)

    def save_profile(self, save_as=False):
        if save_as or not self.current_profile_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Profile As", "", "XML Profiles (*.xml)")
            if not path: return
            self.current_profile_path = path
        root = etree.Element("OpenRailsControlProfile"); settings_el = etree.SubElement(root, "Settings")
        etree.SubElement(settings_el, "UseCombinedThrottle").text = str(self.combined_throttle_cb.isChecked()); etree.SubElement(settings_el, "InvertCombinedAxis").text = str(self.invert_combined_cb.isChecked()); bindings_el = etree.SubElement(root, "Bindings")
        for control, b_data in self.bindings.items():
            bind_el = etree.SubElement(bindings_el, "Binding", control=control)
            if "use_workaround" in b_data: etree.SubElement(bind_el, "UseWorkaround").text = str(b_data["use_workaround"])
            if "incremental_mode" in b_data: etree.SubElement(bind_el, "IncrementalMode").text = str(b_data["incremental_mode"])
            for b_type, b_sub_data in b_data.items():
                if b_type in ["use_workaround", "incremental_mode"]: continue
                if b_type == "values":
                    vals_el = etree.SubElement(bind_el, "Values")
                    for step, step_bindings in b_sub_data.items():
                        bindings_list = step_bindings if isinstance(step_bindings, list) else [step_bindings]
                        for binding in bindings_list: etree.SubElement(vals_el, "Value", step=str(step), **{k:str(v) for k,v in binding.items()})
                else:
                    bindings_list = b_sub_data if isinstance(b_sub_data, list) else [b_sub_data]
                    for binding in bindings_list:
                        if isinstance(binding, dict):
                            sub_el = etree.SubElement(bind_el, b_type.capitalize())
                            for key, val in binding.items(): sub_el.set(key, str(val))
        active_joy_el = etree.SubElement(root, "ActiveJoysticks")
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.checkState() == Qt.Checked: etree.SubElement(active_joy_el, "Joystick", id=str(item.data(Qt.UserRole)))
        etree.ElementTree(root).write(self.current_profile_path, pretty_print=True, xml_declaration=True, encoding='UTF-8'); self.set_default_profile_action.setEnabled(True); self.active_profile_label.setText(f"Profile: {os.path.basename(self.current_profile_path)}")
        
    def load_profile(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "XML Profiles (*.xml)")
            if not path: return
        try:
            tree = etree.parse(path); self.bindings.clear(); self.slider_last_values.clear()
            use_combined_el = tree.find("./Settings/UseCombinedThrottle"); self.combined_throttle_cb.setChecked(use_combined_el is not None and use_combined_el.text.lower() == 'true')
            invert_combined_el = tree.find("./Settings/InvertCombinedAxis"); self.invert_combined_cb.setChecked(invert_combined_el is not None and invert_combined_el.text.lower() == 'true')
            for bind_el in tree.xpath("/OpenRailsControlProfile/Bindings/Binding"):
                control = bind_el.get("control"); self.bindings[control] = {}
                use_work_el = bind_el.find("UseWorkaround"); self.bindings[control]["use_workaround"] = use_work_el is not None and use_work_el.text.lower() == 'true'
                inc_el = bind_el.find("IncrementalMode"); self.bindings[control]["incremental_mode"] = inc_el is not None and inc_el.text.lower() == 'true'
                for sub_el in bind_el:
                    binding_type = sub_el.tag.lower()
                    if binding_type in ["useworkaround", "incrementalmode"]: continue
                    if binding_type == "values":
                        if "values" not in self.bindings[control]: self.bindings[control]["values"] = defaultdict(list)
                        for val_el in sub_el:
                            data = {k: int(v) if k in ['joy_id', 'index'] else v for k, v in val_el.attrib.items() if k != 'step'}
                            self.bindings[control]["values"][val_el.get("step")].append(data)
                    else:
                        data = {k: (v.lower() == 'true') if k == 'inverted' else (int(v) if k in ['joy_id', 'index'] else v) for k, v in sub_el.attrib.items()}
                        if binding_type == 'axis': self.bindings[control][binding_type] = data
                        else:
                            if binding_type not in self.bindings[control]: self.bindings[control][binding_type] = []
                            self.bindings[control][binding_type].append(data)
            for i in range(self.device_list.count()): self.device_list.item(i).setCheckState(Qt.Unchecked)
            active_ids = {el.get("id") for el in tree.xpath("/OpenRailsControlProfile/ActiveJoysticks/Joystick")}
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if str(item.data(Qt.UserRole)) in active_ids: item.setCheckState(Qt.Checked)
            self.current_profile_path = path; self.set_default_profile_action.setEnabled(True); self.active_profile_label.setText(f"Profile: {os.path.basename(path)}")
        except Exception as e: self.log_message(f"Error loading profile: {e}", "ERROR")

    def load_app_config(self):
        try:
            with open(resource_path("config.json"), 'r') as f: self.config = json.load(f)
        except: self.config = {"settings": {"default_profile_path": "","launcher_profiles": []}}; self.save_app_config()
            
    def save_app_config(self):
        path = os.path.join(os.path.dirname(sys.executable), "config.json") if getattr(sys, 'frozen', False) else "config.json"
        with open(path, 'w') as f: json.dump(self.config, f, indent=2)
        
    def set_default_profile(self):
        if self.current_profile_path: self.config["settings"]["default_profile_path"] = self.current_profile_path; self.save_app_config()
        
    def show_about_dialog(self):
        info = self.config.get("about", {}); dialog = QDialog(self); dialog.setWindowTitle(info.get("title", "About")); layout = QVBoxLayout(dialog)
        icon_path = resource_path("icon.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path); icon_label = QLabel(); icon_label.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)); icon_label.setAlignment(Qt.AlignCenter); layout.addWidget(icon_label)
        for key in ["version", "date", "author", "text"]:
            if key in info: label = QLabel(info[key]); label.setAlignment(Qt.AlignCenter); layout.addWidget(label)
        dialog.exec_()
        
    def show_readme_dialog(self):
        dialog = QDialog(self); dialog.setWindowTitle("Help / Readme"); dialog.resize(600, 500); layout = QVBoxLayout(dialog); text_edit = QTextEdit(); text_edit.setReadOnly(True)
        try:
            with open(resource_path("readme.txt"), 'r', encoding='utf-8') as f: text_edit.setPlainText(f.read())
        except: text_edit.setPlainText("readme.txt not found.")
        layout.addWidget(text_edit); dialog.exec_()

    def refresh_devices(self):
        new_joysticks = self.joystick_manager.reinitialize(); self.populate_device_list(new_joysticks)
        
    def populate_device_list(self, devices=None):
        if devices is None: devices = self.joystick_manager.get_devices()
        states = {self.device_list.item(i).data(Qt.UserRole): self.device_list.item(i).checkState() for i in range(self.device_list.count())}; self.device_list.clear()
        for joy_id, name in devices.items():
            item = QListWidgetItem(f"Joy {joy_id}: {name}"); item.setFlags(item.flags() | Qt.ItemIsUserCheckable); item.setCheckState(states.get(joy_id, Qt.Unchecked)); item.setData(Qt.UserRole, joy_id); self.device_list.addItem(item)
        if self.saitek_manager.is_connected():
            item = QListWidgetItem("Saitek Switch Panel"); item.setFlags(item.flags() | Qt.ItemIsUserCheckable); item.setCheckState(states.get("SAITEK_PANEL", Qt.Unchecked)); item.setData(Qt.UserRole, "SAITEK_PANEL"); self.device_list.addItem(item)
    
    def rebuild_launcher_buttons(self):
        while self.launch_button_layout.count():
            child = self.launch_button_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        profiles = self.config.get("settings", {}).get("launcher_profiles", []); row, col = 0, 0
        for profile in profiles:
            btn = QToolButton(); btn.setText(profile['name']); btn.setIcon(QFileIconProvider().icon(QFileInfo(profile['exe']))); btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon); btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.clicked.connect(lambda ch, d=profile: self.on_launch_button_clicked(d)); self.launch_button_layout.addWidget(btn, row, col); col += 1
            if col > 1: col = 0; row += 1

    def open_launcher_editor(self):
        self.launcher_editor.load_launcher_tabs()
        if self.launcher_editor.exec_(): self.config['settings']['launcher_profiles'] = self.launcher_editor.get_all_profiles(); self.save_app_config(); self.rebuild_launcher_buttons()
        
    def on_launch_button_clicked(self, data):
        path = data['exe']
        if path and os.path.exists(path):
            try: subprocess.Popen([path] + data['args'].split(), cwd=os.path.dirname(path))
            except: pass

    def _get_base_cmd(self, script_name):
        """Get command to run a helper script/exe"""
        if getattr(sys, 'frozen', False):
            # Running as compiled .exe
            # The helper exes should be in the same directory as the main exe
            exe_dir = os.path.dirname(sys.executable)
            helper_exe = script_name.replace('.py', '.exe')
            full_path = os.path.join(exe_dir, helper_exe)
            
            # Check if the helper exe exists
            if not os.path.exists(full_path):
                self.log_message(f"⚠️ Helper executable not found: {full_path}", "ERROR")
                self.log_message(f"   Make sure {helper_exe} is in the same folder as OpenRailsLink.exe", "ERROR")
            
            return [full_path]
        else:
            # Running in development mode with Python
            return [sys.executable, resource_path(script_name)]

    def start_trackir_writer(self):
        # Check for admin rights first - SAFE Qt version
        if not is_admin():
            from PyQt5.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self,
                "_show_admin_warning_writer",
                Qt.QueuedConnection
            )
            self.log_message("❌ TrackIR writer blocked - not running as administrator", "TRACKIR")
            return
        
        # Stop any existing writer first
        if self.trackir_writer_process:
            self.log_message("Stopping existing writer before starting new one...", "TRACKIR")
            self.stop_trackir_writer()
            time.sleep(0.5)
            
        if not self.trackir_addresses.get('cab'): 
            return
            
        camera_configs = {'cab': self.config.get("trackir_cab", {}), 'external': self.config.get("trackir_external", {}), 'interior': self.config.get("trackir_interior", {})}
        config_file = os.path.join(tempfile.gettempdir(), f"trackir_config_{os.getpid()}.json")
        
        try:
            with open(config_file, 'w') as f: 
                json.dump(camera_configs, f)
            
            cmd = self._get_base_cmd("trackir_integration.py")
            cmd.extend(["--config-file", config_file])
            [cmd.extend([f"--{k}-address", v[0]]) for k, v in self.trackir_addresses.items() if v]
            cmd.extend(["--active-camera", self.trackir_active_camera])
            
            self.log_message(f"Starting TrackIR writer with command: {' '.join(cmd)}", "TRACKIR")
            self.trackir_writer_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=False, 
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            threading.Thread(target=self._read_writer_output, daemon=True).start()
            self.update_writer_button_states()
            self.log_message(f"✓ TrackIR writer started successfully", "TRACKIR")
        except FileNotFoundError as e:
            self.log_message(f"❌ Writer executable not found!", "ERROR")
            self.log_message(f"   Command attempted: {' '.join(cmd)}", "ERROR")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Writer Not Found",
                f"<b>Cannot find trackir_integration.exe!</b><br><br>"
                f"Make sure these files are in the same folder:<br>"
                f"• OpenRailsLink.exe<br>"
                f"• trackir_scanner.exe<br>"
                f"• trackir_integration.exe",
                QMessageBox.Ok
            )
        except Exception as e:
            self.log_message(f"❌ Failed to start TrackIR writer: {e}", "ERROR")
            import traceback
            self.log_message(f"Stack trace: {traceback.format_exc()}", "ERROR")

    def stop_trackir_writer(self):
        if not self.trackir_writer_process: return
        
        self.log_message("Stopping TrackIR writer...", "TRACKIR")
        
        try:
            pid = self.trackir_writer_process.pid
            
            # Try shutdown flag first
            shutdown_flag = os.path.join(tempfile.gettempdir(), f"trackir_writer_shutdown_{pid}.flag")
            with open(shutdown_flag, 'w') as f: 
                f.write('1')
            
            # Wait briefly for graceful shutdown
            try:
                self.trackir_writer_process.wait(timeout=1)
                self.log_message("Writer stopped gracefully", "TRACKIR")
            except:
                # Force terminate
                self.log_message("Writer not responding, forcing termination...", "TRACKIR")
                self.trackir_writer_process.terminate()
                try:
                    self.trackir_writer_process.wait(timeout=0.5)
                except:
                    # Force kill
                    self.trackir_writer_process.kill()
                    self.trackir_writer_process.wait(timeout=2)
            
            # Clean up flag file
            try:
                if os.path.exists(shutdown_flag):
                    os.remove(shutdown_flag)
            except:
                pass
                
        except Exception as e:
            self.log_message(f"Error stopping writer: {e}", "ERROR")
        
        self.trackir_writer_process = None
        self.update_writer_button_states()

    def check_trackir_game_status(self):
        if self.trackir_game_pid == 0: return
        try:
            import psutil
            if not psutil.pid_exists(self.trackir_game_pid):
                self.stop_trackir_writer(); [self.stop_camera_scan(c) for c in ['cab', 'external', 'interior'] if self.trackir_scanner_processes[c]]; self.trackir_game_pid = 0; [self.trackir_addresses[c].clear() for c in ['cab', 'external', 'interior']]; self.update_camera_labels(); self.update_address_list_display()
        except: pass

    def start_camera_scan(self, camera_type):
        # Check for admin rights first - SAFE Qt version
        if not is_admin():
            # Use QMetaObject to ensure we're on the GUI thread
            from PyQt5.QtCore import QMetaObject, Qt
            QMetaObject.invokeMethod(
                self,
                "_show_admin_warning_scanner",
                Qt.QueuedConnection
            )
            self.log_message("❌ Camera scan blocked - not running as administrator", "TRACKIR")
            return
        
        # Prevent double-clicks - if scanner is already running, force stop it first
        if self.trackir_scanner_processes[camera_type]:
            self.log_message(f"⚠️ Scanner already running! Force stopping before restart...", "TRACKIR")
            try:
                # Force kill immediately
                self.trackir_scanner_processes[camera_type].kill()
                self.trackir_scanner_processes[camera_type].wait(timeout=1)
            except:
                pass
            self.trackir_scanner_processes[camera_type] = None
            time.sleep(0.5)
        
        if camera_type in ['external', 'interior'] and not self.config.get("trackir_settings", {}).get("enable_extra_cameras", False): return
        conf = self.config.get(f"trackir_{camera_type}", {}); cmd = self._get_base_cmd("trackir_scanner.py"); cmd.extend(["--camera-type", camera_type, "--aob", conf.get("aob", ""), "--radius", str(conf.get("radius", 10.0))])
        
        try:
            self.log_message(f"Starting {camera_type} scanner with command: {' '.join(cmd)}", "TRACKIR")
            self.trackir_scanner_processes[camera_type] = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                universal_newlines=False, 
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            threading.Thread(target=self._read_scanner_output, args=(camera_type,), daemon=True).start()
            if camera_type == 'cab':
                self.trackir_restart_cab_scan_btn.setEnabled(True)
            self.update_writer_button_states()
            self.log_message(f"✓ {camera_type} scanner started successfully", "TRACKIR")
        except FileNotFoundError as e:
            self.log_message(f"❌ Scanner executable not found!", "ERROR")
            self.log_message(f"   Command attempted: {' '.join(cmd)}", "ERROR")
            self.log_message(f"   Make sure trackir_scanner.exe is in the same folder as OpenRailsLink.exe", "ERROR")
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(
                self,
                "Scanner Not Found",
                f"<b>Cannot find trackir_scanner.exe!</b><br><br>"
                f"Make sure these files are in the same folder:<br>"
                f"• OpenRailsLink.exe<br>"
                f"• trackir_scanner.exe<br>"
                f"• trackir_integration.exe<br><br>"
                f"Command attempted:<br>"
                f"<code>{' '.join(cmd)}</code>",
                QMessageBox.Ok
            )
        except Exception as e:
            self.log_message(f"❌ Failed to start {camera_type} scanner: {e}", "ERROR")
            import traceback
            self.log_message(f"Stack trace: {traceback.format_exc()}", "ERROR")

    @pyqtSlot()
    def _show_admin_warning_scanner(self):
        """Show admin warning dialog - safe to call from any thread"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(
            self,
            "Administrator Rights Required",
            "<b>TrackIR Scanner requires Administrator privileges!</b><br><br>"
            "Please restart OpenRailsLink as Administrator:<br>"
            "1. Right-click on OpenRailsLink.exe<br>"
            "2. Select 'Run as administrator'<br><br>"
            "The scanner needs admin rights to read game memory.",
            QMessageBox.Ok
        )

    @pyqtSlot()
    def _show_admin_warning_writer(self):
        """Show admin warning dialog for writer - safe to call from any thread"""
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.critical(
            self,
            "Administrator Rights Required",
            "<b>TrackIR Writer requires Administrator privileges!</b><br><br>"
            "Please restart OpenRailsLink as Administrator:<br>"
            "1. Right-click on OpenRailsLink.exe<br>"
            "2. Select 'Run as administrator'<br><br>"
            "The writer needs admin rights to write to game memory.",
            QMessageBox.Ok
        )

    def restart_camera_scan(self, camera_type):
        """Restart camera scanner"""
        # Prevent double-clicks
        if camera_type == 'cab':
            self.trackir_restart_cab_scan_btn.setEnabled(False)
        
        try:
            self.log_message(f"🔄 Restarting {camera_type} scanner...", "TRACKIR")
            
            # Force kill existing scanner
            self.stop_camera_scan(camera_type)
            
            # Wait for full termination
            time.sleep(1.5)
            
            # Start fresh scanner
            self.start_camera_scan(camera_type)
            
        except Exception as e:
            self.log_message(f"❌ Error restarting {camera_type} scanner: {e}", "ERROR")
            # Re-enable button on error
            if camera_type == 'cab':
                self.trackir_restart_cab_scan_btn.setEnabled(True)

    def stop_camera_scan(self, camera_type):
        if not self.trackir_scanner_processes[camera_type]: return
        
        self.log_message(f"Stopping {camera_type} scanner...", "TRACKIR")
        
        try:
            pid = self.trackir_scanner_processes[camera_type].pid
            
            # Try shutdown flag first
            flag = os.path.join(tempfile.gettempdir(), f"trackir_scanner_{camera_type}_shutdown_{pid}.flag")
            with open(flag, 'w') as f: 
                f.write('1')
            
            # Wait briefly for graceful shutdown
            try:
                self.trackir_scanner_processes[camera_type].wait(timeout=1)
                self.log_message(f"{camera_type} scanner stopped gracefully", "TRACKIR")
            except:
                # Force terminate
                self.log_message(f"{camera_type} scanner not responding, forcing termination...", "TRACKIR")
                self.trackir_scanner_processes[camera_type].terminate()
                try:
                    self.trackir_scanner_processes[camera_type].wait(timeout=0.5)
                except:
                    # Force kill
                    self.trackir_scanner_processes[camera_type].kill()
                    self.trackir_scanner_processes[camera_type].wait(timeout=2)
            
            # Clean up flag file
            try:
                if os.path.exists(flag):
                    os.remove(flag)
            except:
                pass
                
        except Exception as e:
            self.log_message(f"Error stopping {camera_type} scanner: {e}", "ERROR")
        
        self.trackir_scanner_processes[camera_type] = None
        if camera_type == 'cab':
            self.trackir_restart_cab_scan_btn.setEnabled(False)
        self.update_writer_button_states()

    def start_individual_camera_writer(self, camera_type):
        if not self.trackir_addresses[camera_type]: return
        self.trackir_active_camera = camera_type
        if not self.trackir_writer_process: self.start_trackir_writer()
        else: self.send_active_camera_to_writer()
        self.update_writer_button_states()
    
    def stop_individual_camera_writer(self, camera_type):
        self.stop_trackir_writer()

    def update_writer_button_states(self):
        writer_running = self.trackir_writer_process is not None
        for c, (start_btn, stop_btn) in {'cab': (self.trackir_start_cab_writer_btn, self.trackir_stop_cab_writer_btn), 'external': (self.trackir_start_external_writer_btn, self.trackir_stop_external_writer_btn), 'interior': (self.trackir_start_interior_writer_btn, self.trackir_stop_interior_writer_btn)}.items():
            start_btn.setEnabled((len(self.trackir_addresses[c]) > 0 or (c == 'cab' and self.trackir_scanner_processes[c])) and not writer_running); stop_btn.setEnabled(writer_running and self.trackir_active_camera == c)
        self.trackir_start_all_btn.setEnabled((any(len(a) > 0 for a in self.trackir_addresses.values()) or self.trackir_scanner_processes['cab']) and not writer_running); self.trackir_stop_all_btn.setEnabled(writer_running)

    def update_extra_camera_visibility(self):
        enabled = self.config.get("trackir_settings", {}).get("enable_extra_cameras", False)
        self.external_camera_container.setVisible(enabled); self.external_scan_container.setVisible(enabled); self.external_writer_container.setVisible(enabled); self.interior_camera_container.setVisible(enabled); self.interior_scan_container.setVisible(enabled); self.interior_writer_container.setVisible(enabled); self.interior_address_container.setVisible(enabled)

    def _read_writer_output(self):
        proc = self.trackir_writer_process
        while proc and proc.poll() is None:
            line = proc.stdout.readline()
            if not line: time.sleep(0.01); continue
            decoded = line.decode('utf-8', errors='ignore').strip()
            if not decoded: continue
            self.trackir_log_signal.emit(f"[{QDateTime.currentDateTime().toString('HH:mm:ss.zzz')}] {decoded}")
            try:
                if "RAW_DATA_ROT" in decoded:
                    m = re.search(r'Yaw: ([-\d.]+), Pitch: ([-\d.]+), Roll: ([-\d.]+)', decoded)
                    if m: self.trackir_rotation_signal.emit(float(m.group(1)), float(m.group(2)), float(m.group(3)))
                if "RAW_DATA_POS" in decoded:
                    m = re.search(r'X: ([-\d.]+), Y: ([-\d.]+), Z: ([-\d.]+)', decoded)
                    if m: self.trackir_position_signal.emit(float(m.group(1)), float(m.group(2)), float(m.group(3)))
                if "WRITE_ERROR:" in decoded: self.trackir_address_invalid.emit(decoded.split(":", 1)[1].strip())
            except: pass

    def _read_scanner_output(self, camera_type):
        proc = self.trackir_scanner_processes[camera_type]
        while proc and proc.poll() is None:
            line = proc.stdout.readline()
            if not line: break
            decoded = line.decode('utf-8', errors='ignore').strip()
            if not decoded: continue
            self.trackir_log_signal.emit(f"[{QDateTime.currentDateTime().toString('HH:mm:ss.zzz')}] {decoded}")
            try:
                if "FOUND_PID:" in decoded:
                    new_pid = int(decoded.split(":")[2].strip())
                    if self.trackir_game_pid != 0 and self.trackir_game_pid != new_pid: [self.trackir_addresses[c].clear() for c in ['cab', 'external', 'interior']]; self.update_camera_labels()
                    self.trackir_game_pid = new_pid
                elif "FOUND_ADDRESS:" in decoded:
                    parts = decoded.split(":")
                    if len(parts) >= 3:
                        cam, addr = parts[1].strip().lower(), parts[2].strip()
                        if cam in self.trackir_addresses and addr not in self.trackir_addresses[cam]:
                            self.trackir_addresses[cam].append(addr); self.trackir_addresses_updated.emit(list(self.trackir_addresses.keys()))
                            if self.trackir_writer_process: self.send_address_to_writer(cam, addr)
                            if cam == 'cab' and not self.trackir_writer_process: self.start_trackir_writer()
            except: pass

    def open_trackir_settings(self):
        dialog = TrackIRSettingsDialog(self.config.get("trackir_cab", {}), self.config.get("trackir_external", {}), self.config.get("trackir_interior", {}), self)
        if dialog.exec_():
            settings = dialog.get_all_settings(); self.config["trackir_cab"], self.config["trackir_external"], self.config["trackir_interior"] = settings['cab'], settings['external'], settings['interior']
            if "trackir_settings" not in self.config: self.config["trackir_settings"] = {}
            self.config["trackir_settings"]["enable_extra_cameras"] = settings['enable_extra_cameras']; self.save_app_config(); self.update_extra_camera_visibility()

    def send_active_camera_to_writer(self):
        if not self.trackir_writer_process: return
        try:
            with open(os.path.join(tempfile.gettempdir(), f"trackir_active_camera_{self.trackir_writer_process.pid}.dat"), 'w') as f: f.write(self.trackir_active_camera)
        except: pass

    def closeEvent(self, event):
        self.log_message("Application closing - cleaning up...", "APP")
        
        # Release any held keys on shutdown
        for tracking_key, held_data in list(self.held_keys.items()):
            try:
                if held_data['is_combo']:
                    self.keyboard_controller.release(held_data['main_key'])
                    for mod in reversed(held_data['modifiers']):
                        self.keyboard_controller.release(mod)
                else:
                    self.keyboard_controller.release(held_data['key'])
            except:
                pass
        self.held_keys.clear()
        
        # CRITICAL: Kill all TrackIR child processes with improved cleanup
        self.log_message("Terminating TrackIR processes...", "APP")
        
        # Collect all child process PIDs before termination
        child_pids = []
        
        # Stop TrackIR writer process
        if self.trackir_writer_process:
            try:
                pid = self.trackir_writer_process.pid
                child_pids.append(pid)
                
                # Try graceful termination first
                self.trackir_writer_process.terminate()
                try:
                    self.trackir_writer_process.wait(timeout=0.5)
                except:
                    # Force kill if terminate didn't work
                    self.trackir_writer_process.kill()
                    self.trackir_writer_process.wait(timeout=2)
            except Exception as e:
                pass
            self.trackir_writer_process = None
        
        # Stop all scanner processes
        for camera_type in ['cab', 'external', 'interior']:
            if self.trackir_scanner_processes[camera_type]:
                try:
                    pid = self.trackir_scanner_processes[camera_type].pid
                    child_pids.append(pid)
                    
                    # Try graceful termination first
                    self.trackir_scanner_processes[camera_type].terminate()
                    try:
                        self.trackir_scanner_processes[camera_type].wait(timeout=0.5)
                    except:
                        # Force kill if terminate didn't work
                        self.trackir_scanner_processes[camera_type].kill()
                        self.trackir_scanner_processes[camera_type].wait(timeout=2)
                except Exception as e:
                    pass
                self.trackir_scanner_processes[camera_type] = None
        
        # Clean up temp files that might cause respawn
        try:
            temp_dir = tempfile.gettempdir()
            my_pid = os.getpid()
            
            # Remove config files
            config_file = os.path.join(temp_dir, f"trackir_config_{my_pid}.json")
            if os.path.exists(config_file):
                os.remove(config_file)
            
            # Remove any shutdown flags
            for camera in ['cab', 'external', 'interior']:
                for child_pid in child_pids:
                    flag_file = os.path.join(temp_dir, f"trackir_scanner_{camera}_shutdown_{child_pid}.flag")
                    if os.path.exists(flag_file):
                        os.remove(flag_file)
            
            for child_pid in child_pids:
                shutdown_flag = os.path.join(temp_dir, f"trackir_writer_shutdown_{child_pid}.flag")
                if os.path.exists(shutdown_flag):
                    os.remove(shutdown_flag)
        except:
            pass
        
        # Final sweep: Use psutil to ensure all child processes are dead
        try:
            current_process = psutil.Process(os.getpid())
            children = current_process.children(recursive=True)
            
            for child in children:
                try:
                    # Only kill trackir processes, not game processes
                    if 'trackir' in child.name().lower():
                        child.terminate()
                except:
                    pass
            
            # Wait for termination
            time.sleep(0.5)
            
            # Force kill any that didn't terminate
            for child in children:
                try:
                    if child.is_running() and 'trackir' in child.name().lower():
                        child.kill()
                except:
                    pass
        except:
            pass
        
        # Save config
        if self.launcher_editor.isVisible():
            self.config['settings']['launcher_profiles'] = self.launcher_editor.get_all_profiles()
        self.save_app_config()
        
        # Shutdown managers
        self.joystick_manager.shutdown()
        self.saitek_manager.shutdown()
        self.web_interface.stop()
        
        self.log_message("✓ Cleanup complete. Goodbye!", "APP")
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); window = MainAppWindow(); window.show(); sys.exit(app.exec_())