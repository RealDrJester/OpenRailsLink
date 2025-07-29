# gui.py
import sys, json, argparse, os, subprocess, importlib
from lxml import etree
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
                             QListWidget, QPushButton, QLabel, QLineEdit, QSlider, QGroupBox,
                             QGridLayout, QFrame, QListWidgetItem, QSizePolicy, QInputDialog,
                             QTextEdit, QDockWidget, QFileDialog, QDialog, QCheckBox, QFormLayout, QFileIconProvider,
                             QToolButton, QDialogButtonBox, QScrollArea)
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtCore import Qt, QDateTime, QFileInfo, QSize, pyqtSignal
from functools import partial

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

class MainAppWindow(QMainWindow):
    def __init__(self, profile_path=None):
        super().__init__()
        # MODIFIED: Widened the window
        self.setWindowTitle("OpenRailsLink"); self.setGeometry(100, 100, 1600, 800); self.setStyleSheet(STYLE_SHEET)
        self.bindings = {}; self.gui_controls = {}; self.gui_labels = {}; self.config = {}
        self.current_profile_path = None; self.active_cab_controls = []
        self.slider_last_values = {}
        self.joystick_manager = JoystickManager(self); self.saitek_manager = SaitekPanelManager(self); self.web_interface = OpenRailsWebInterface(self)
        self.launcher_editor = LauncherEditor(self)

        # --- CORRECTED INITIALIZATION ORDER ---
        # 1. Build the UI first, which creates the debug_log widget.
        self.init_ui()
        # 2. Now load the config. If it fails, log_message will work.
        self.load_app_config()
        # 3. Connect signals now that all widgets and managers exist.
        self.connect_signals()
        
        # --- Continue with startup logic ---
        self.log_message(f"Found {len(self.joystick_manager.get_devices())} joystick(s) during startup scan.", "APP")
        if self.saitek_manager.is_connected(): self.log_message("Found Saitek Switch Panel.", "APP")
        self.web_interface.start()
        if profile_path:
            self.log_message(f"Loading profile from command-line: {profile_path}", "APP"); self.load_profile(profile_path)
        else:
            default_profile = self.config.get("settings", {}).get("default_profile_path", "")
            if default_profile and os.path.exists(default_profile): self.log_message(f"Loading default profile: {default_profile}", "APP"); self.load_profile(default_profile)

    def init_ui(self):
        self.setup_menus_and_debug()
        main_widget = QWidget(); self.setCentralWidget(main_widget); main_layout = QHBoxLayout(main_widget)
        left_panel = QFrame(); left_layout = QVBoxLayout(left_panel); main_layout.addWidget(left_panel, 1)
        port_group = QGroupBox("Connection"); port_layout = QGridLayout(port_group)
        port_layout.addWidget(QLabel("Port:"), 0, 0); self.port_input = QLineEdit("2150"); self.port_input.setFixedWidth(50)
        port_layout.addWidget(self.port_input, 0, 1)
        set_port_btn = QPushButton("Set"); set_port_btn.clicked.connect(lambda: self.web_interface.set_port(self.port_input.text())); port_layout.addWidget(set_port_btn, 0, 2)
        reconnect_btn = QPushButton("Reconnect"); reconnect_btn.clicked.connect(self.web_interface.force_reconnect); port_layout.addWidget(reconnect_btn, 0, 3)
        self.status_label = QLabel("DISCONNECTED"); self.status_label.setObjectName("status_label_fail")
        port_layout.addWidget(self.status_label, 1, 0, 1, 2)
        self.active_profile_label = QLabel("Profile: None"); self.active_profile_label.setStyleSheet("color: #aaa;")
        port_layout.addWidget(self.active_profile_label, 1, 2, 1, 2)
        left_layout.addWidget(port_group)
        devices_group = QGroupBox("Connected Devices"); devices_layout = QVBoxLayout(devices_group)
        self.device_list = QListWidget()
        self.populate_device_list()
        devices_layout.addWidget(self.device_list)
        joy_btn_layout = QHBoxLayout(); edit_bindings_btn = QPushButton("Edit Control Bindings"); edit_bindings_btn.clicked.connect(self.open_bindings_editor)
        refresh_joy_btn = QPushButton("Refresh Devices"); refresh_joy_btn.clicked.connect(self.refresh_devices)
        joy_btn_layout.addWidget(edit_bindings_btn); joy_btn_layout.addWidget(refresh_joy_btn)
        devices_layout.addLayout(joy_btn_layout)
        left_layout.addWidget(devices_group)
        left_layout.addStretch()
        launcher_group = QGroupBox("Game Launcher"); launcher_main_layout = QVBoxLayout(launcher_group)
        self.launch_button_layout = QGridLayout()
        launcher_main_layout.addLayout(self.launch_button_layout)
        edit_launchers_btn = QPushButton("Edit Launchers..."); edit_launchers_btn.clicked.connect(self.open_launcher_editor)
        launcher_main_layout.addWidget(edit_launchers_btn)
        left_layout.addWidget(launcher_group)
        self.rebuild_launcher_buttons()
        
        right_panel_scroll = QScrollArea(); right_panel_scroll.setWidgetResizable(True); right_panel_scroll.setFrameShape(QFrame.NoFrame)
        main_layout.addWidget(right_panel_scroll, 2)
        
        scroll_content = QWidget(); right_layout = QHBoxLayout(scroll_content)
        right_panel_scroll.setWidget(scroll_content)

        sliders_container = QWidget(); sliders_main_layout = QVBoxLayout(sliders_container)
        sliders_layout = QGridLayout()
        sliders = {k: v for k, v in CONTROL_DEFINITIONS.items() if v['type'] == 'slider'}
        row = 0
        for id, definition in sliders.items():
            label = QLabel(f"<b>{definition['desc']}</b> ({definition['range'][0]}-{definition['range'][1]})"); self.gui_labels[id] = label
            slider = QSlider(Qt.Horizontal); slider.setRange(definition['range'][0], definition['range'][1]); slider.setMinimumWidth(200)
            slider.valueChanged.connect(partial(self.handle_slider_move, id, slider)); slider.sliderReleased.connect(partial(self.handle_slider_release, id, slider))
            if id == "COMBINED_THROTTLE":
                self.combined_throttle_cb = QCheckBox("Use Combined Handle")
                row_layout = QHBoxLayout(); row_layout.addWidget(label); row_layout.addWidget(self.combined_throttle_cb); row_layout.addStretch()
                sliders_layout.addLayout(row_layout, row, 0, 1, 2); row +=1
            else:
                 sliders_layout.addWidget(label, row, 0)
            sliders_layout.addWidget(slider, row, 1); self.gui_controls[id] = slider; row += 1
        sliders_main_layout.addLayout(sliders_layout)
        
        # Add decorative icon below sliders
        icon_label = QLabel()
        icon_path = resource_path("icon.png") # MODIFIED: Use helper function
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # Resize the icon to be 96x96 pixels, keeping its aspect ratio.
            icon_label.setPixmap(pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        sliders_main_layout.addWidget(icon_label)
        
        sliders_main_layout.addStretch()
        
        button_tabs = QTabWidget()
        button_tabs.setUsesScrollButtons(False)
        # MODIFIED: Added 'camera' and 'debug' categories to display new controls
        categories = {
            "cab": ("Cab Controls", QVBoxLayout()), "brakes": ("Brake Systems", QVBoxLayout()), 
            "engine_electric": ("Engine (Electric)", QVBoxLayout()), "engine_diesel": ("Engine (Diesel)", QVBoxLayout()),
            "engine_steam": ("Engine (Steam)", QVBoxLayout()), "game": ("Game", QGridLayout()),
            "camera": ("Cameras", QGridLayout()), "debug": ("Debug", QGridLayout())
        }
        for cat, (title, layout) in categories.items():
            tab = QWidget(); tab.setLayout(layout); button_tabs.addTab(tab, title)

        game_row, game_col = 0, 0
        camera_row, camera_col = 0, 0
        debug_row, debug_col = 0, 0
        for id, definition in CONTROL_DEFINITIONS.items():
            if definition['type'] == 'button':
                btn = QPushButton(definition['desc'])
                btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                self.gui_controls[id] = btn
                
                behavior = definition.get("behavior")
                if behavior == "hold" or behavior == "toggle":
                    btn.setCheckable(True)
                    btn.toggled.connect(partial(self.handle_gui_toggle, id))
                else: # Standard momentary click button
                    btn.pressed.connect(partial(self.handle_button_press, id))

                style = definition.get("style", "cab")
                # MODIFIED: Logic to place buttons in the new tabs
                if style == "game":
                    categories[style][1].addWidget(btn, game_row, game_col)
                    game_col += 1
                    if game_col > 1: game_col = 0; game_row += 1
                elif style == "camera":
                    categories[style][1].addWidget(btn, camera_row, camera_col)
                    camera_col += 1
                    if camera_col > 1: camera_col = 0; camera_row += 1
                elif style == "debug":
                    categories[style][1].addWidget(btn, debug_row, debug_col)
                    debug_col += 1
                    if debug_col > 1: debug_col = 0; debug_row += 1
                elif style in categories:
                    categories[style][1].addWidget(btn)
                else:
                    categories["cab"][1].addWidget(btn)
                if style != "cab": btn.setObjectName(f"{style}_button")

        for cat, (title, layout) in categories.items():
            if isinstance(layout, QGridLayout): layout.setRowStretch(layout.rowCount(), 1)
            else: layout.addStretch()
            
        right_layout.addWidget(sliders_container, 1)
        right_layout.addWidget(button_tabs, 1)
        for widget in self.gui_controls.values(): widget.setEnabled(False)

    def setup_menus_and_debug(self):
        self.debug_log = QTextEdit(); self.debug_log.setReadOnly(True)
        self.debug_dock = QDockWidget("Debug Console", self); self.debug_dock.setWidget(self.debug_log)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.debug_dock); menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        file_menu.addAction("New Profile", self.new_profile); file_menu.addAction("Load Profile...", self.load_profile)
        file_menu.addAction("Save Profile", self.save_profile); file_menu.addAction("Save Profile As...", lambda: self.save_profile(save_as=True))
        self.set_default_profile_action = file_menu.addAction("Set Current as Default Profile", self.set_default_profile); self.set_default_profile_action.setEnabled(False)
        view_menu = menu_bar.addMenu("View"); view_menu.addAction(self.debug_dock.toggleViewAction())
        help_menu = menu_bar.addMenu("Help"); help_menu.addAction("About...", self.show_about_dialog); help_menu.addAction("Help / Readme", self.show_readme_dialog)
        self.log_message("Application starting...", "APP")

    def connect_signals(self):
        self.device_list.itemChanged.connect(self.toggle_device_listener)
        self.web_interface.connection_status_changed.connect(self.on_connection_status_changed)
        self.web_interface.cab_controls_updated.connect(self.on_cab_controls_updated)
        self.web_interface.command_sent.connect(lambda p, c, v: self.log_message(f"{c} = {v}", f"SENT-{p}"))
        self.web_interface.update_received.connect(lambda data: self.log_message(data, "RECV"))
        self.joystick_manager.raw_joystick_event.connect(self.process_raw_joystick_input)
        self.saitek_manager.saitek_event.connect(self.process_saitek_input)
        self.launcher_editor.profiles_changed.connect(self.rebuild_launcher_buttons)

    def log_message(self, text, source):
        timestamp = QDateTime.currentDateTime().toString("HH:mm:ss.zzz"); self.debug_log.append(f"[{timestamp}] [{source}] {text}")

    def on_connection_status_changed(self, is_connected, server_data):
        if is_connected:
            self.status_label.setText("CONNECTED"); self.status_label.setObjectName("status_label_ok"); self.log_message("Connection established.", "APP")
            
            # MODIFIED: Always enable all buttons on connect
            for our_id, definition in CONTROL_DEFINITIONS.items():
                widget = self.gui_controls.get(our_id)
                if not widget: continue
                if definition.get('type') == 'button':
                    widget.setEnabled(True)
            self.gui_controls['COMBINED_THROTTLE'].setEnabled(True)
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
                widget.setEnabled(True)
                control_data = next((c for c in server_data if c['TypeName'] == control_id), None)
                if control_data:
                    min_val_f, max_val_f = control_data['MinValue'], control_data['MaxValue']
                    if max_val_f == 1.0 and min_val_f == 0.0:
                        widget.setRange(0, 100); label.setText(f"<b>{definition['desc']}</b> (0-100)")
                    else:
                        min_val, max_val = int(min_val_f), int(max_val_f)
                        widget.setRange(min_val, max_val); label.setText(f"<b>{definition['desc']}</b> ({min_val}-{max_val})")
            else:
                widget.setEnabled(False)

    def process_raw_joystick_input(self, joy_id, type, index, value):
        if self.combined_throttle_cb.isChecked():
            binding = self.bindings.get("COMBINED_THROTTLE", {}).get("axis")
            if binding and binding.get('joy_id') == joy_id and binding.get('index') == index and type == 'axis':
                active_slider_names = {c['TypeName'] for c in self.active_cab_controls}
                brake_type = "TRAIN_BRAKE" 
                if 'DYNAMIC_BRAKE' in active_slider_names and 'TRAIN_BRAKE' not in active_slider_names: brake_type = 'DYNAMIC_BRAKE'
                
                if binding.get("inverted", False): value = -value
                self.handle_combined_brake_logic(brake_type, value)
                return 

        for control_id, control_bindings in self.bindings.items():
            if 'values' in control_bindings and type == 'button' and value == 1.0:
                for step_value, binding_data in control_bindings['values'].items():
                    if binding_data.get('device_type') == 'joystick' and binding_data.get('joy_id') == joy_id and binding_data.get('index') == index:
                        self.execute_step_binding(control_id, step_value); return
            
            for binding_type, binding_data in control_bindings.items():
                if binding_type == 'values': continue
                if binding_data.get('device_type') == 'joystick' and binding_data.get('joy_id') == joy_id and binding_data.get('index') == index:
                    if (binding_type == 'axis' and type == 'axis') or (binding_type == 'button' and type == 'button'):
                        self.execute_binding(control_id, binding_type, value)
                        
    def process_saitek_input(self, switch, state):
        for control_id, control_bindings in self.bindings.items():
            if 'values' in control_bindings and state == "ON":
                for step_value, binding_data in control_bindings['values'].items():
                    if binding_data.get('device_type') == 'saitek' and binding_data.get('switch') == switch:
                        self.execute_step_binding(control_id, step_value); return

            for binding_type, binding_data in control_bindings.items():
                if binding_type == 'values': continue
                if binding_data.get('device_type') == 'saitek' and binding_data.get('switch') == switch and binding_data.get('state') == state:
                    self.execute_binding(control_id, binding_type, 1.0 if state == "ON" else 0.0)

    def execute_binding(self, control_id, binding_type, value):
        widget = self.gui_controls.get(control_id)
        if not widget or not widget.isEnabled(): return
        definition = CONTROL_DEFINITIONS[control_id]
        
        if definition['type'] == 'slider':
            binding_data = self.bindings.get(control_id, {}).get(binding_type)
            if not binding_data: return
            if binding_type == 'axis':
                if binding_data.get("inverted", False): value = -value
                if 'id' in definition:
                    min_val, max_val = widget.minimum(), widget.maximum(); target_value = int(min_val + ((value + 1) / 2) * (max_val - min_val)); current_value = widget.value()
                    if target_value > current_value: [self.web_interface.send_ws_click(definition['id'][1]) for _ in range(target_value - current_value)]
                    elif target_value < current_value: [self.web_interface.send_ws_click(definition['id'][0]) for _ in range(current_value - target_value)]
                    widget.blockSignals(True); widget.setValue(target_value); widget.blockSignals(False)
                else: 
                    range_fraction = (value + 1) / 2.0; self.web_interface.send_control_value(control_id, range_fraction)
                    display_value = int(widget.minimum() + range_fraction * (widget.maximum() - widget.minimum()))
                    widget.blockSignals(True); widget.setValue(display_value); widget.blockSignals(False)
            elif binding_type in ["increase", "decrease"] and value == 1.0:
                 new_val = widget.value() + (1 if binding_type == 'increase' else -1)
                 new_val = max(widget.minimum(), min(widget.maximum(), new_val))
                 self.send_slider_value_from_gui(control_id, new_val); widget.setValue(new_val)
        
        elif definition['type'] == 'button':
            command_id = definition.get('id')
            if command_id is None: return

            if definition.get("send_as") == "value":
                self.web_interface.send_control_value(control_id, value)
                widget.blockSignals(True); widget.setChecked(value == 1.0); widget.blockSignals(False)
                return
            
            behavior = definition.get("behavior")
            if behavior == "toggle":
                # This logic correctly handles momentary buttons (like joysticks) and maintained switches (like Saitek).
                # Momentary buttons should only be bound to the 'button' type and will fire on press (value=1.0).
                # Maintained switches should be bound to 'button' (for ON) and 'off_button' (for OFF) and will fire on both.
                if (binding_type == 'button' and value == 1.0) or (binding_type == 'off_button'):
                    self.web_interface.send_ws_click(command_id)
                
                # The GUI state should always reflect the physical input's state for checkable buttons.
                widget.blockSignals(True)
                widget.setChecked(value == 1.0)
                widget.blockSignals(False)

            elif behavior == "hold":
                event = "buttonDown" if value == 1.0 else "buttonUp"
                self.web_interface.send_button_event(command_id, event)
                widget.blockSignals(True); widget.setChecked(value == 1.0); widget.blockSignals(False)
            elif value == 1.0: # Standard momentary button
                self.web_interface.send_ws_click(command_id)
    
    def execute_step_binding(self, control_id, target_step_str):
        widget = self.gui_controls.get(control_id)
        if not widget or not widget.isEnabled(): return
        definition = CONTROL_DEFINITIONS[control_id]
        if 'id' not in definition or definition.get('type') != 'slider': return
        try:
            target_value = int(target_step_str)
        except (ValueError, TypeError):
            self.log_message(f"Invalid step value '{target_step_str}' for {control_id}", "ERROR"); return
        current_value = self.slider_last_values.get(control_id, widget.value())
        if target_value > current_value:
            [self.web_interface.send_ws_click(definition['id'][1]) for _ in range(target_value - current_value)]
        elif target_value < current_value:
            [self.web_interface.send_ws_click(definition['id'][0]) for _ in range(current_value - target_value)]
        widget.blockSignals(True); widget.setValue(target_value); widget.blockSignals(False)
        self.slider_last_values[control_id] = target_value
        self.log_message(f"Set {control_id} to step {target_value}", "BINDING")

    def handle_combined_brake_logic(self, brake_type, value):
        throttle_widget = self.gui_controls.get("THROTTLE"); brake_widget = self.gui_controls.get(brake_type); combined_widget = self.gui_controls.get("COMBINED_THROTTLE")
        if not all([throttle_widget, brake_widget, combined_widget]): return
        if value >= 0:
            self.web_interface.send_control_value("THROTTLE", value); self.web_interface.send_control_value(brake_type, 0.0)
            throttle_display = int(value * 100); brake_display = 0; combined_display = int(value * 100)
        else:
            brake_fraction = -value
            self.web_interface.send_control_value("THROTTLE", 0.0); self.web_interface.send_control_value(brake_type, brake_fraction)
            throttle_display = 0; brake_display = int(brake_fraction * 100); combined_display = -int(brake_fraction * 100)
        throttle_widget.blockSignals(True); throttle_widget.setValue(throttle_display); throttle_widget.blockSignals(False)
        brake_widget.blockSignals(True); brake_widget.setValue(brake_display); brake_widget.blockSignals(False)
        combined_widget.blockSignals(True); combined_widget.setValue(combined_display); combined_widget.blockSignals(False)

    def toggle_device_listener(self, item):
        device_id = item.data(Qt.UserRole)
        is_checked = item.checkState() == Qt.Checked
        if device_id == "SAITEK_PANEL":
            if is_checked:
                if self.saitek_manager.start_listening(): self.log_message("Saitek Panel listener started.", "APP")
                else: self.log_message("ERROR: Failed to start Saitek Panel listener.", "ERROR"); item.setCheckState(Qt.Unchecked)
            else:
                self.saitek_manager.stop_listening(); self.log_message("Saitek Panel listener stopped.", "APP")
        else:
            if is_checked: self.joystick_manager.start_listening(device_id)
            else: self.joystick_manager.stop_listening(device_id)
        
    def open_bindings_editor(self):
        editor = BindingsEditor(self.bindings, self); 
        self.joystick_manager.raw_joystick_event.connect(editor.update_input_meter)
        self.joystick_manager.raw_joystick_event.connect(editor.capture_joystick_input)
        self.saitek_manager.saitek_event.connect(editor.capture_saitek_input)
        if editor.exec_():
            self.bindings = editor.get_bindings()
            self.log_message("Bindings updated.", "APP")
        try:
            self.joystick_manager.raw_joystick_event.disconnect(editor.capture_joystick_input)
            self.joystick_manager.raw_joystick_event.disconnect(editor.update_input_meter)
            self.saitek_manager.saitek_event.disconnect(editor.capture_saitek_input)
        except TypeError: pass

    def handle_slider_move(self, control_id, slider, value):
        if control_id in self.bindings and "axis" in self.bindings.get(control_id, {}):
            return
        self.send_slider_value_from_gui(control_id, value)
        
    def handle_slider_release(self, control_id, slider):
        if control_id in self.bindings and "axis" in self.bindings.get(control_id, {}):
            self.log_message(f"Final mouse input for '{control_id}' ignored.", "APP"); return
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
        definition = CONTROL_DEFINITIONS[control_id]
        command_id = definition.get('id')
        if command_id is not None: 
            self.web_interface.send_ws_click(command_id)

    def handle_gui_toggle(self, control_id, is_checked):
        definition = CONTROL_DEFINITIONS[control_id]
        command_id = definition.get('id')
        if command_id is None: return

        if definition.get("send_as") == "value":
            self.web_interface.send_control_value(control_id, 1.0 if is_checked else 0.0)
            return

        behavior = definition.get("behavior")
        if behavior == "toggle":
            self.web_interface.send_ws_click(command_id)
        elif behavior == "hold":
            event = "buttonDown" if is_checked else "buttonUp"
            self.web_interface.send_button_event(command_id, event)

    def new_profile(self):
        self.bindings.clear(); self.current_profile_path = None
        self.slider_last_values.clear()
        for i in range(self.device_list.count()): self.device_list.item(i).setCheckState(Qt.Unchecked)
        self.set_default_profile_action.setEnabled(False); self.log_message("New profile created.", "APP")
        self.combined_throttle_cb.setChecked(False)
        self.active_profile_label.setText("Profile: None")

    def save_profile(self, save_as=False):
        if save_as or not self.current_profile_path:
            path, _ = QFileDialog.getSaveFileName(self, "Save Profile As", "", "XML Profiles (*.xml)");
            if not path: self.log_message("Save cancelled.", "APP"); return
            self.current_profile_path = path
        if not self.current_profile_path: return
        root = etree.Element("OpenRailsControlProfile"); 
        settings_el = etree.SubElement(root, "Settings")
        etree.SubElement(settings_el, "UseCombinedThrottle").text = str(self.combined_throttle_cb.isChecked())
        bindings_el = etree.SubElement(root, "Bindings")
        for control, b_data in self.bindings.items():
            bind_el = etree.SubElement(bindings_el, "Binding", control=control)
            for b_type, b_sub_data in b_data.items():
                if b_type == "values":
                    vals_el = etree.SubElement(bind_el, "Values")
                    for step, step_data in b_sub_data.items(): etree.SubElement(vals_el, "Value", step=str(step), **{k:str(v) for k,v in step_data.items()})
                else:
                    sub_el = etree.SubElement(bind_el, b_type.capitalize());
                    for key, val in b_sub_data.items(): sub_el.set(key, str(val))
        active_joy_el = etree.SubElement(root, "ActiveJoysticks")
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            if item.checkState() == Qt.Checked: etree.SubElement(active_joy_el, "Joystick", id=str(item.data(Qt.UserRole)))
        etree.ElementTree(root).write(self.current_profile_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
        self.log_message(f"Profile saved to {self.current_profile_path}", "APP"); self.set_default_profile_action.setEnabled(True)
        self.active_profile_label.setText(f"Profile: {os.path.basename(self.current_profile_path)}")
        
    def load_profile(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Load Profile", "", "XML Profiles (*.xml)")
            if not path: self.log_message("Load cancelled.", "APP"); return
        try:
            tree = etree.parse(path); self.bindings.clear(); self.slider_last_values.clear()
            use_combined_el = tree.find("./Settings/UseCombinedThrottle")
            use_combined = use_combined_el is not None and use_combined_el.text.lower() == 'true'
            self.combined_throttle_cb.setChecked(use_combined)
            for bind_el in tree.xpath("/OpenRailsControlProfile/Bindings/Binding"):
                control = bind_el.get("control"); self.bindings[control] = {}
                for sub_el in bind_el:
                    if sub_el.tag == "Values":
                        self.bindings[control]["values"] = {}
                        for val_el in sub_el:
                            step = val_el.get("step"); data = {k: v for k, v in val_el.attrib.items() if k != 'step'}
                            if 'joy_id' in data: data['joy_id'] = int(data['joy_id'])
                            if 'index' in data: data['index'] = int(data['index'])
                            self.bindings[control]["values"][step] = data
                    else:
                        data = {k: v for k, v in sub_el.attrib.items()}
                        if 'joy_id' in data: data['joy_id'] = int(data['joy_id'])
                        if 'index' in data: data['index'] = int(data['index'])
                        if 'inverted' in data: data['inverted'] = (data['inverted'].lower() == 'true')
                        self.bindings[control][sub_el.tag.lower()] = data
            
            for i in range(self.device_list.count()): self.device_list.item(i).setCheckState(Qt.Unchecked)
            active_ids = {el.get("id") for el in tree.xpath("/OpenRailsControlProfile/ActiveJoysticks/Joystick")}
            for i in range(self.device_list.count()):
                item = self.device_list.item(i)
                if str(item.data(Qt.UserRole)) in active_ids: item.setCheckState(Qt.Checked)
            self.current_profile_path = path; self.log_message(f"Profile loaded from {path}", "APP"); self.set_default_profile_action.setEnabled(True)
            self.active_profile_label.setText(f"Profile: {os.path.basename(self.current_profile_path)}")
        except Exception as e: self.log_message(f"Error loading profile: {e}", "ERROR")

    def load_app_config(self):
        try:
            with open(resource_path("config.json"), 'r') as f: self.config = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.log_message("config.json not found or invalid. Creating default config.", "WARN")
            self.config = {"settings": {"default_profile_path": "","launcher_profiles": []},"about": {"title": "About", "text": "Default config."}}; self.save_app_config()
            
    def save_app_config(self):
        try:
            if getattr(sys, 'frozen', False):
                path = os.path.join(os.path.dirname(sys.executable), "config.json")
            else:
                path = "config.json"
            with open(path, 'w') as f: json.dump(self.config, f, indent=2)
        except Exception as e: self.log_message(f"Error saving config.json: {e}", "ERROR")
        
    def set_default_profile(self):
        if not self.current_profile_path: self.log_message("Cannot set default profile.", "WARN"); return
        self.config["settings"]["default_profile_path"] = self.current_profile_path
        self.save_app_config(); self.log_message(f"Set {os.path.basename(self.current_profile_path)} as default.", "APP")
        
    def show_about_dialog(self):
        about_info = self.config.get("about", {}); dialog = QDialog(self); dialog.setWindowTitle(about_info.get("title", "About"))
        layout = QVBoxLayout(dialog)

        icon_label = QLabel()
        icon_path = resource_path("icon.png") # MODIFIED
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            icon_label.setPixmap(pixmap.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        for key in ["version", "date", "author", "text"]:
            if key in about_info:
                label = QLabel(about_info[key])
                label.setAlignment(Qt.AlignCenter)
                layout.addWidget(label)
        
        for i in [1, 2]:
            if f"link{i}_url" in about_info and f"link{i}_text" in about_info:
                link_label = QLabel(f'<a href="{about_info[f"link{i}_url"]}">{about_info[f"link{i}_text"]}</a>')
                link_label.setOpenExternalLinks(True)
                link_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(link_label)
        
        dialog.exec_()
        
    def show_readme_dialog(self):
        dialog = QDialog(self); dialog.setWindowTitle("Help / Readme"); dialog.resize(600, 500)
        layout = QVBoxLayout(dialog); text_edit = QTextEdit(); text_edit.setReadOnly(True)
        try:
            with open(resource_path("readme.txt"), 'r', encoding='utf-8') as f: text_edit.setPlainText(f.read()) # MODIFIED
        except FileNotFoundError:
            text_edit.setPlainText("readme.txt not found.")
        layout.addWidget(text_edit); dialog.exec_()

    def refresh_devices(self):
        self.log_message("Refreshing device list...", "APP")
        new_joysticks = self.joystick_manager.reinitialize()
        self.populate_device_list(new_joysticks)
        self.log_message(f"Found {len(new_joysticks)} joysticks.", "APP")
        if self.saitek_manager.is_connected(): self.log_message("Found Saitek Switch Panel.", "APP")
        
    def populate_device_list(self, devices=None):
        if devices is None: devices = self.joystick_manager.get_devices()
        checked_states = {}
        for i in range(self.device_list.count()):
            item = self.device_list.item(i)
            checked_states[item.data(Qt.UserRole)] = item.checkState()
        
        self.device_list.clear()
        for joy_id, name in devices.items():
            item = QListWidgetItem(f"Joy {joy_id}: {name}"); item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(checked_states.get(joy_id, Qt.Unchecked)); item.setData(Qt.UserRole, joy_id); self.device_list.addItem(item)
            
        if self.saitek_manager.is_connected():
            item = QListWidgetItem("Saitek Switch Panel"); item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(checked_states.get("SAITEK_PANEL", Qt.Unchecked)); item.setData(Qt.UserRole, "SAITEK_PANEL")
            self.device_list.addItem(item)
    
    def rebuild_launcher_buttons(self):
        while self.launch_button_layout.count():
            child = self.launch_button_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        profiles = self.config.get("settings", {}).get("launcher_profiles", [])
        row, col = 0, 0
        for profile in profiles:
            btn = QToolButton(); btn.setText(profile['name']); btn.setIconSize(QSize(32,32))
            info = QFileInfo(profile['exe']); provider = QFileIconProvider(); icon = provider.icon(info); btn.setIcon(icon)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            btn.clicked.connect(lambda ch, d=profile: self.on_launch_button_clicked(d))
            self.launch_button_layout.addWidget(btn, row, col)
            col += 1
            if col > 1: col = 0; row += 1

    def open_launcher_editor(self):
        self.launcher_editor.load_launcher_tabs()
        if self.launcher_editor.exec_():
            self.config['settings']['launcher_profiles'] = self.launcher_editor.get_all_profiles()
            self.save_app_config()
            self.rebuild_launcher_buttons()
            self.log_message("Launcher profiles updated and saved.", "APP")
        
    def on_launch_button_clicked(self, data):
        path = data['exe']
        if path and os.path.exists(path):
            try:
                command = [path] + data['args'].split()
                subprocess.Popen(command, cwd=os.path.dirname(path)); self.log_message(f"Launching: {' '.join(command)}", "APP")
            except Exception as e: self.log_message(f"Failed to launch: {e}", "ERROR")
        else: self.log_message(f"Invalid path for launcher '{data['name']}': {path}", "ERROR")
    
    def closeEvent(self, event):
        if self.launcher_editor.isVisible():
            self.config['settings']['launcher_profiles'] = self.launcher_editor.get_all_profiles()
        self.save_app_config(); self.log_message("Application shutting down.", "APP"); 
        self.joystick_manager.shutdown(); self.saitek_manager.shutdown()
        self.web_interface.stop()
        event.accept()

def check_dependencies():
    print("--- Checking Dependencies ---")
    dependencies = [('PyQt5', 'pyqt5'), ('pygame', 'pygame'), ('requests', 'requests'), ('websockets', 'websockets'), ('lxml', 'lxml'), ('hid', 'hidapi')]
    all_ok = True
    for mod_name, pkg_name in dependencies:
        try: importlib.import_module(mod_name); print(f"[ OK ] {mod_name} is installed.")
        except ImportError: print(f"[ MISSING ] {mod_name} is not installed. Please run: pip install {pkg_name}"); all_ok = False
    if all_ok: print("All dependencies are satisfied.")
    print("-----------------------------\n")

if __name__ == "__main__":
    check_dependencies()
    parser = argparse.ArgumentParser(description="Open Rails Advanced Controller.")
    parser.add_argument("--profile", help="Path to an XML profile to load on startup.")
    args = parser.parse_args()
    app = QApplication(sys.argv); window = MainAppWindow(profile_path=args.profile); window.show(); sys.exit(app.exec_())