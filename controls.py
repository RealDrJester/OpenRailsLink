# controls.py - Fixed version with reliable joystick input
import pygame
from PyQt5.QtCore import QObject, pyqtSignal, Qt, QTimer
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QLabel, QCheckBox, QGroupBox,
                             QFormLayout, QPushButton, QDialogButtonBox, QListWidgetItem, QStackedWidget,
                             QWidget, QScrollArea, QProgressBar, QGridLayout, QMenu, QTableWidget,
                             QTableWidgetItem, QSlider, QRadioButton)
from PyQt5.QtGui import QColor
import threading
import re
from functools import partial
from definitions import CONTROL_DEFINITIONS
import os
import sys

# --- HELPER FUNCTION TO FIND FILES WHEN COMPILED (COPIED TO AVOID CIRCULAR IMPORT) ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class JoystickManager(QObject):
    raw_joystick_event = pyqtSignal(int, str, int, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        pygame.init()
        pygame.joystick.init()
        self.joysticks = {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}
        
        # Initialize all joysticks
        for joy in self.joysticks.values():
            joy.init()
        
        # Track last axis values for change detection
        self.last_axis_values = {}
        self.last_button_values = {}
        
        # Polling timer instead of event thread
        self.poll_timer = QTimer()
        self.poll_timer.timeout.connect(self._poll_joysticks)
        self.active_joysticks = set()
    
    def get_devices(self):
        return {i: j.get_name() for i, j in self.joysticks.items()}
    
    def reinitialize(self):
        # Stop polling
        self.poll_timer.stop()
        self.active_joysticks.clear()
        
        # Reinit pygame
        pygame.joystick.quit()
        pygame.joystick.init()
        self.joysticks = {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}
        
        # Initialize all joysticks
        for joy in self.joysticks.values():
            joy.init()
        
        # Clear tracking
        self.last_axis_values.clear()
        self.last_button_values.clear()
        
        return self.get_devices()
    
    def start_listening(self, joystick_id):
        """Start polling for this joystick"""
        if joystick_id in self.joysticks:
            self.active_joysticks.add(joystick_id)
            
            # Start timer if not running (100Hz polling = 10ms)
            if not self.poll_timer.isActive():
                self.poll_timer.start(10)
    
    def stop_listening(self, joystick_id):
        """Stop polling for this joystick"""
        self.active_joysticks.discard(joystick_id)
        
        # Stop timer if no active joysticks
        if not self.active_joysticks:
            self.poll_timer.stop()
    
    def _poll_joysticks(self):
        """Poll all active joysticks for state changes"""
        # Process any pending events first
        pygame.event.pump()
        
        for joy_id in list(self.active_joysticks):
            if joy_id not in self.joysticks:
                continue
            
            joy = self.joysticks[joy_id]
            
            # Poll all axes
            num_axes = joy.get_numaxes()
            for axis_idx in range(num_axes):
                value = joy.get_axis(axis_idx)
                
                # Check if value changed significantly (0.5% threshold)
                last_key = f"{joy_id}_{axis_idx}"
                last_value = self.last_axis_values.get(last_key, 0.0)
                
                if abs(value - last_value) > 0.005:
                    self.last_axis_values[last_key] = value
                    self.raw_joystick_event.emit(joy_id, "axis", axis_idx, value)
            
            # Poll all buttons
            num_buttons = joy.get_numbuttons()
            for btn_idx in range(num_buttons):
                value = joy.get_button(btn_idx)
                
                # Check if button state changed
                last_key = f"{joy_id}_{btn_idx}"
                last_value = self.last_button_values.get(last_key, 0)
                
                if value != last_value:
                    self.last_button_values[last_key] = value
                    self.raw_joystick_event.emit(joy_id, "button", btn_idx, float(value))
    
    def shutdown(self):
        self.poll_timer.stop()
        self.active_joysticks.clear()
        pygame.quit()

class OverrideConfigDialog(QDialog):
    def __init__(self, current_override, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Button Behavior Configuration")
        self.resize(300, 150)
        self.selected_override = current_override
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Select how this button should behave:")
        layout.addWidget(lbl)
        
        # Radio buttons
        self.default_radio = QRadioButton("Default (Physical Switch/Hold)")
        self.default_radio.setChecked(current_override == "default" or not current_override)
        
        default_hint = QLabel("    (DEFAULT)")
        default_hint.setStyleSheet("color: #888; font-style: italic;")
        
        self.toggle_radio = QRadioButton("Toggle on Press Only")
        self.toggle_radio.setChecked(current_override == "toggle_on_press")
        
        layout.addWidget(self.default_radio)
        layout.addWidget(default_hint)
        layout.addWidget(self.toggle_radio)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
    def accept(self):
        if self.toggle_radio.isChecked():
            self.selected_override = "toggle_on_press"
        else:
            self.selected_override = "default"
        super().accept()
        
    def get_override(self):
        return self.selected_override

class BindingsEditor(QDialog):
    def __init__(self, current_bindings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bindings Editor - Key Mapping")
        self.resize(1200, 700)
        self.bindings = current_bindings.copy()
        self.listening_cell = None  # (control_id, device_column)
        self.device_columns = []  # Will store device identifiers
        
        main_layout = QVBoxLayout(self)
        
        # Top instruction label
        info_label = QLabel(
            "<b>Instructions:</b> Click any cell to bind. Press ESC to cancel listening. Right-click for options.<br>"
            "<b>Keyboard Column:</b> When you bind a keyboard key, pressing the bound controller button will <u>emulate that keyboard key press</u> in the game."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("background-color: #2a2a2a; padding: 8px; border-radius: 4px;")
        main_layout.addWidget(info_label)

        import_info = QLabel(
            "<b>💡 Tip:</b> To import OpenRails keybinds: In-game, go to <i>Options → Keyboard → Export</i>, "
            "then click 'Import OpenRails Keyboard...' below."
        )
        import_info.setWordWrap(True)
        import_info.setStyleSheet("background-color: #2a4a2a; padding: 5px; border-radius: 3px; color: #88ff88;")
        main_layout.addWidget(import_info)
        
        # Create the table
        self.table = QTableWidget()
        self.table.setColumnCount(1)  # Will add columns dynamically
        self.table.setHorizontalHeaderLabels(["MAPPING"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.on_right_click)
        
        main_layout.addWidget(self.table)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self.rebuild_device_columns)
        import_kb_btn = QPushButton("Import OpenRails Keyboard...")
        import_kb_btn.clicked.connect(self.import_openrails_keyboard)
        button_layout.addWidget(import_kb_btn)
        button_layout.addWidget(refresh_btn)
        button_layout.addStretch()
        apply_btn = QPushButton("Apply & Close")
        apply_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(apply_btn)
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)
        
        # Build initial table
        self.rebuild_device_columns()
        self.populate_table()
        self.load_default_keyboard_bindings()
    
    def rebuild_device_columns(self):
        """Detect all available devices and rebuild table columns"""
        from PyQt5.QtWidgets import QApplication
        joystick_manager = self.parent().joystick_manager
        saitek_manager = self.parent().saitek_manager
        
        devices = joystick_manager.get_devices()
        self.device_columns = ["KEYBOARD"]
        self.device_names = {"KEYBOARD": "KEYBOARD"}
        
        for joy_id in sorted(devices.keys()):
            device_key = f"JOY_{joy_id}"
            self.device_columns.append(device_key)
            controller_name = devices[joy_id]
            display_name = controller_name[:20] + "..." if len(controller_name) > 20 else controller_name
            self.device_names[device_key] = display_name
        
        if saitek_manager.is_connected():
            self.device_columns.append("SAITEK")
            self.device_names["SAITEK"] = "Saitek Panel"
        
        # +3: one for name column, one for workaround column, one for incremental mode
        self.table.setColumnCount(3 + len(self.device_columns))
        headers = ["MAPPING", "Workaround", "Incremental"] + [self.device_names[dev] for dev in self.device_columns]
        self.table.setHorizontalHeaderLabels(headers)
        
        # Improve header readability
        header = self.table.horizontalHeader()
        header.setStyleSheet("QHeaderView::section { background-color: #1a1a1a; color: #ffffff; font-weight: bold; padding: 4px; }")
        
        self.table.setColumnWidth(0, 300)
        self.table.setColumnWidth(1, 100)  # Workaround column
        self.table.setColumnWidth(2, 100)  # Incremental column
        for i in range(3, len(headers)):
            self.table.setColumnWidth(i, 180)
        
        self.populate_table()
    
    def populate_table(self):
        """Fill table with all controls and their current bindings"""
        from definitions import CONTROL_DEFINITIONS
        
        self.table.setRowCount(0)
        row = 0
        
        for control_id, definition in CONTROL_DEFINITIONS.items():
            self.table.insertRow(row)
            
            # Column 0: Control name
            name_item = QTableWidgetItem(definition['desc'])
            name_item.setData(Qt.UserRole, control_id)
            name_item.setFlags(name_item.flags() & ~Qt.ItemIsEditable)
            
            name_item.setBackground(QColor("#3c3c3c"))
            
            self.table.setItem(row, 0, name_item)

            # Check if this is a virtual control or COMBINED_THROTTLE
            is_virtual = (definition.get("behavior") == "virtual" or control_id == "COMBINED_THROTTLE")
            
            # Check if this is a TrackIR virtual control (color it differently)
            is_trackir_virtual = control_id in ["TOGGLE_TRACKIR", "SCAN_CAB_CAMERA", "SCAN_EXTERNAL_CAMERA", 
                                                 "SCAN_INTERIOR_CAMERA", "RESCAN_CAB_CAMERA", 
                                                 "RESCAN_EXTERNAL_CAMERA", "RESCAN_INTERIOR_CAMERA"]

            if is_virtual:
                # Set background color based on type
                if is_trackir_virtual:
                    name_item.setBackground(QColor("#6a4a6a"))  # Purple/magenta for TrackIR controls
                    name_item.setForeground(QColor("#ffffff"))
                else:
                    name_item.setBackground(QColor("#4a4a6a"))  # Blue for other virtual controls
                    name_item.setForeground(QColor("#ffffff"))
                
                # Column 1: Show "-" for virtual controls
                workaround_label = QLabel("-")
                workaround_label.setAlignment(Qt.AlignCenter)
                workaround_label.setStyleSheet("color: #888;")
                workaround_widget = QWidget()
                workaround_layout = QHBoxLayout(workaround_widget)
                workaround_layout.addWidget(workaround_label)
                workaround_layout.setAlignment(Qt.AlignCenter)
                workaround_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 1, workaround_widget)
                
                # Column 2: Show "-" for virtual controls
                incremental_label = QLabel("-")
                incremental_label.setAlignment(Qt.AlignCenter)
                incremental_label.setStyleSheet("color: #888;")
                incremental_widget = QWidget()
                incremental_layout = QHBoxLayout(incremental_widget)
                incremental_layout.addWidget(incremental_label)
                incremental_layout.setAlignment(Qt.AlignCenter)
                incremental_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 2, incremental_widget)
            else:
                # Column 1: Workaround checkbox for non-virtual controls
                control_bindings = self.bindings.get(control_id, {})
                workaround_cb = QCheckBox()
                workaround_cb.setChecked(control_bindings.get("use_workaround", False))
                workaround_cb.setToolTip(
                    "When checked: Pressing a bound controller button also triggers the 'Keyboard' binding for this control (if configured).\n"
                    "Useful for controls that OpenRails doesn't support via its external API yet (Wipers, etc)."
                )
                workaround_cb.stateChanged.connect(
                    partial(self.on_workaround_changed, control_id)
                )

                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(workaround_cb)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 1, checkbox_widget)

                # Column 2: Incremental Mode checkbox (for Increase/Decrease buttons)
                incremental_mode_cb = QCheckBox()
                incremental_mode_cb.setChecked(control_bindings.get("incremental_mode", False))
                incremental_mode_cb.setToolTip(
                    "When checked: Increase/Decrease buttons send small incremental changes to the game.\n"
                    "When unchecked: Increase/Decrease buttons simulate keyboard key presses."
                )
                incremental_mode_cb.stateChanged.connect(
                    partial(self.on_incremental_mode_changed, control_id)
                )

                incremental_checkbox_widget = QWidget()
                incremental_checkbox_layout = QHBoxLayout(incremental_checkbox_widget)
                incremental_checkbox_layout.addWidget(incremental_mode_cb)
                incremental_checkbox_layout.setAlignment(Qt.AlignCenter)
                incremental_checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 2, incremental_checkbox_widget)
            
            # Columns 3+: Device bindings (shifted by 2)
            for col_idx, device in enumerate(self.device_columns, start=3):
                binding_text = self.get_binding_text_for_device(control_id, device)
                cell_item = QTableWidgetItem(binding_text)
                cell_item.setData(Qt.UserRole, (control_id, device))
                cell_item.setTextAlignment(Qt.AlignCenter)
                
                if binding_text and binding_text != "---":
                    cell_item.setBackground(QColor("#2d5016"))
                else:
                    cell_item.setBackground(QColor("#2a2a2a"))
                
                self.table.setItem(row, col_idx, cell_item)
            
            row += 1
        
        self.table.resizeRowsToContents()

    def on_workaround_changed(self, control_id, state):
        """Toggle workaround mode for a control"""
        control_bindings = self.bindings.setdefault(control_id, {})
        control_bindings["use_workaround"] = (state == Qt.Checked)
        self.parent().log_message(
            f"Workaround {'enabled' if state == Qt.Checked else 'disabled'} for {control_id}",
            "BIND"
        )
    
    def on_incremental_mode_changed(self, control_id, state):
        """Toggle incremental mode for increase/decrease buttons"""
        control_bindings = self.bindings.setdefault(control_id, {})
        control_bindings["incremental_mode"] = (state == Qt.Checked)
        self.parent().log_message(
            f"Incremental mode {'enabled' if state == Qt.Checked else 'disabled'} for {control_id}",
            "BIND"
        )
    
    def get_binding_text_for_device(self, control_id, device):
        """Get the binding text for a specific control and device"""
        control_bindings = self.bindings.get(control_id, {})
        
        # Check all binding types (button, off_button, axis, increase, decrease, values)
        all_bindings = []
        
        for binding_type in ["button", "off_button", "axis", "increase", "decrease"]:
            binding_data = control_bindings.get(binding_type)
            if binding_data:
                bindings_list = binding_data if isinstance(binding_data, list) else [binding_data]
                for binding in bindings_list:
                    if self.binding_matches_device(binding, device):
                        text = self.format_single_binding(binding, binding_type)
                        # Append marker if override enabled
                        if binding.get('override') == 'toggle_on_press':
                            text += " (Toggle)"
                        all_bindings.append(text)
        
        # Check stepped values
        values_dict = control_bindings.get("values", {})
        for step, binding_data in values_dict.items():
            bindings_list = binding_data if isinstance(binding_data, list) else [binding_data]
            for binding in bindings_list:
                if self.binding_matches_device(binding, device):
                    all_bindings.append(f"Step {step}")
        
        return "\n".join(all_bindings) if all_bindings else "---"
    
    def binding_matches_device(self, binding, device):
        """Check if a binding belongs to the specified device"""
        device_type = binding.get("device_type")
        
        if device == "KEYBOARD":
            return device_type == "keyboard"
        elif device.startswith("JOY_"):
            joy_id = int(device.split("_")[1])
            return device_type == "joystick" and binding.get("joy_id") == joy_id
        elif device == "SAITEK":
            return device_type == "saitek"
        
        return False
    
    def format_single_binding(self, binding, binding_type):
        """Format a single binding for display"""
        device_type = binding.get("device_type")
        
        if device_type == "keyboard":
            return f"Key: {binding.get('key', '?')}"
        elif device_type == "joystick":
            type_str = binding.get('type', '?')
            index = binding.get('index', '?')
            if type_str == "axis":
                inv = " (INV)" if binding.get("inverted", False) else ""
                return f"Axis {index}{inv}"
            return f"Btn {index}"
        elif device_type == "saitek":
            return f"{binding.get('switch', '?')}"
        
        return "???"
    
    def on_cell_clicked(self, row, col):
        """Handle cell click to start listening for input"""
        if col == 0 or col == 1 or col == 2:  # Don't bind on name, workaround, or incremental columns
            return
        
        item = self.table.item(row, col)
        if not item:  # Safety check
            return
        
        control_id, device = item.data(Qt.UserRole)
        
        # Stop previous listening
        if self.listening_cell:
            prev_row, prev_col = self.listening_cell
            prev_item = self.table.item(prev_row, prev_col)
            if prev_item:  # Check if item still exists
                prev_item.setBackground(QColor("#2a2a2a"))
                prev_item.setText(self.get_binding_text_for_device(
                    prev_item.data(Qt.UserRole)[0],
                    prev_item.data(Qt.UserRole)[1]
                ))
        
        # Start listening
        self.listening_cell = (row, col)
        
        # Re-fetch item in case it was recreated
        item = self.table.item(row, col)
        if item:  # Safety check
            item.setBackground(QColor("#5a3a1a"))  # Orange tint for listening
            item.setText("LISTENING...")
        
        self.parent().log_message(f"Listening for input on {device} for {control_id}...", "BIND")
    
    def on_right_click(self, pos):
        """Handle right-click to show context menu"""
        item = self.table.itemAt(pos)
        if not item or self.table.column(item) <= 2:
            return
        
        control_id, device = item.data(Qt.UserRole)
        row = self.table.row(item)
        col = self.table.column(item)
        
        from definitions import CONTROL_DEFINITIONS
        definition = CONTROL_DEFINITIONS[control_id]
        
        # Create context menu
        menu = QMenu(self)
        
        # Always show delete option
        delete_action = menu.addAction("Delete Binding(s)")
        delete_action.triggered.connect(lambda: self.delete_binding_for_device(control_id, device))
        
        menu.addSeparator()
        
        # Add "Bind Button" option
        bind_button_action = menu.addAction("Bind Button...")
        bind_button_action.triggered.connect(lambda: self.bind_button_mode(row, col, control_id, device))
        
        # Add "Bind Axis" option (only for sliders or can convert button to axis-controlled)
        bind_axis_action = menu.addAction("Bind Axis...")
        bind_axis_action.triggered.connect(lambda: self.bind_axis_mode(row, col, control_id, device))
        
        menu.addSeparator()
        
        # Check if there is a button binding to configure
        if self.has_button_binding(control_id, device):
            config_action = menu.addAction("Configure Button Behavior...")
            config_action.triggered.connect(lambda: self.configure_button_behavior(control_id, device))
            menu.addSeparator()
        
        # If there's an existing axis binding, allow editing
        current_axis = self.get_axis_binding_for_device(control_id, device)
        if current_axis:
            edit_axis_action = menu.addAction("Edit Axis Configuration...")
            edit_axis_action.triggered.connect(lambda: self.edit_axis_config(control_id, device, current_axis))
        
        menu.exec_(self.table.viewport().mapToGlobal(pos))

    def has_button_binding(self, control_id, device):
        """Check if there is at least one button binding for this control on this device"""
        control_bindings = self.bindings.get(control_id, {})
        for binding_type in ["button", "off_button", "increase", "decrease"]:
            bindings = control_bindings.get(binding_type)
            if bindings:
                if not isinstance(bindings, list): bindings = [bindings]
                for b in bindings:
                    if self.binding_matches_device(b, device): return True
        return False

    def configure_button_behavior(self, control_id, device):
        """Open dialog to configure override behavior"""
        # We need to find the binding to edit. For simplicity, we edit the first matching button binding.
        # Ideally, we should support multiple, but typically there's only one button per device per control.
        control_bindings = self.bindings.get(control_id, {})
        target_binding = None
        
        for binding_type in ["button", "increase", "decrease"]:
            bindings = control_bindings.get(binding_type)
            if bindings:
                if not isinstance(bindings, list): bindings = [bindings]
                for b in bindings:
                    if self.binding_matches_device(b, device):
                        target_binding = b
                        break
            if target_binding: break
            
        if not target_binding:
            return

        current_override = target_binding.get('override', 'default')
        dialog = OverrideConfigDialog(current_override, self)
        
        if dialog.exec_():
            new_override = dialog.get_override()
            
            # Update ALL matching button bindings for consistency
            count = 0
            for binding_type in ["button", "off_button", "increase", "decrease"]:
                 bindings = control_bindings.get(binding_type)
                 if bindings:
                    is_list = isinstance(bindings, list)
                    if not is_list: bindings = [bindings]
                    
                    for b in bindings:
                        if self.binding_matches_device(b, device):
                            if new_override == 'default':
                                if 'override' in b: del b['override']
                            else:
                                b['override'] = new_override
                            count += 1
                    
                    if not is_list: control_bindings[binding_type] = bindings[0]

            self.parent().log_message(f"Updated behavior for {control_id} ({count} bindings updated)", "BIND")
            self.populate_table()

    def delete_binding_for_device(self, control_id, device):
        """Clear all bindings for this control/device combo"""
        control_bindings = self.bindings.get(control_id, {})
        
        for binding_type in list(control_bindings.keys()):
            # Skip non-binding keys (settings flags)
            if binding_type in ["use_workaround", "incremental_mode"]:
                continue
                
            if binding_type == "values":
                values_dict = control_bindings["values"]
                for step in list(values_dict.keys()):
                    bindings_list = values_dict[step] if isinstance(values_dict[step], list) else [values_dict[step]]
                    values_dict[step] = [b for b in bindings_list if not self.binding_matches_device(b, device)]
                    if not values_dict[step]:
                        del values_dict[step]
                if not control_bindings["values"]:
                    del control_bindings["values"]
            else:
                binding_data = control_bindings[binding_type]
                # Only process if it's actually a binding (dict or list of dicts)
                if isinstance(binding_data, dict):
                    if self.binding_matches_device(binding_data, device):
                        del control_bindings[binding_type]
                elif isinstance(binding_data, list):
                    filtered = [b for b in binding_data if isinstance(b, dict) and not self.binding_matches_device(b, device)]
                    
                    if filtered:
                        if binding_type == 'axis': # Axis should not be a list
                            control_bindings[binding_type] = filtered[0]
                        else:
                            control_bindings[binding_type] = filtered
                    else:
                        del control_bindings[binding_type]
        
        if not control_bindings or all(k in ["use_workaround", "incremental_mode"] for k in control_bindings.keys()):
            if control_id in self.bindings:
                del self.bindings[control_id]
        
        self.populate_table()
        self.parent().log_message(f"Cleared {device} binding for {control_id}", "BIND")

    def bind_button_mode(self, row, col, control_id, device):
        """Enter button binding mode for this cell"""
        self.on_cell_clicked(row, col)
        # The existing capture logic will handle button presses

    def bind_axis_mode(self, row, col, control_id, device):
        """Open axis configuration dialog"""
        if device == "KEYBOARD":
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Invalid Binding", "Cannot bind keyboard to axis controls.")
            return
        
        dialog = AxisConfigDialog(parent=self)
        
        # Connect joystick events to the dialog
        def axis_listener(joy_id, type, index, value):
            if type == "axis" and abs(value) > 0.1:  # Significant movement
                if device == f"JOY_{joy_id}" or device == "SAITEK":
                    dialog.update_axis_input(joy_id, index, value)
                # Always update visualization if binding already detected
                if not dialog.is_listening:
                    dialog.show_axis_value(value)
        
        self.parent().joystick_manager.raw_joystick_event.connect(axis_listener)
        
        if dialog.exec_():
            binding_data = dialog.get_binding_data()
            if binding_data and "joy_id" in binding_data:
                # Add to bindings
                from definitions import CONTROL_DEFINITIONS
                definition = CONTROL_DEFINITIONS[control_id]
                
                if definition['type'] == 'slider' and 'id' not in definition:
                    # Analog slider - bind to axis
                    control_bindings = self.bindings.setdefault(control_id, {})
                    control_bindings["axis"] = binding_data
                else:
                    # For other controls, we can use axis as increase/decrease based on value
                    # This is advanced - store as special axis binding
                    control_bindings = self.bindings.setdefault(control_id, {})
                    control_bindings["axis"] = binding_data
                    control_bindings["axis"]["_button_mode"] = True  # Special flag
                
                self.populate_table()
                self.parent().log_message(f"Bound axis to {control_id}", "BIND")
        
        try:
            self.parent().joystick_manager.raw_joystick_event.disconnect(axis_listener)
        except TypeError:
            pass

    def get_axis_binding_for_device(self, control_id, device):
        """Get axis binding for a specific device"""
        control_bindings = self.bindings.get(control_id, {})
        axis_binding = control_bindings.get("axis")
        
        if axis_binding and self.binding_matches_device(axis_binding, device):
            return axis_binding
        
        return None

    def edit_axis_config(self, control_id, device, current_binding):
        """Edit existing axis configuration"""
        dialog = AxisConfigDialog(existing_binding=current_binding, parent=self)
        
        # Connect live updates
        def axis_listener(joy_id, type, index, value):
            if (type == "axis" and 
                joy_id == current_binding.get("joy_id") and 
                index == current_binding.get("index")):
                dialog.show_axis_value(value)
        
        self.parent().joystick_manager.raw_joystick_event.connect(axis_listener)
        
        if dialog.exec_():
            binding_data = dialog.get_binding_data()
            # Update the binding
            control_bindings = self.bindings.setdefault(control_id, {})
            control_bindings["axis"] = binding_data
            self.populate_table()
            self.parent().log_message(f"Updated axis config for {control_id}", "BIND")
        
        try:
            self.parent().joystick_manager.raw_joystick_event.disconnect(axis_listener)
        except TypeError:
            pass
    
    def capture_input(self, joy_id, input_type, index, value, device_type="joystick"):
        """Universal input capture from joystick/saitek/keyboard"""
        if not self.listening_cell:
            return
        
        row, col = self.listening_cell
        item = self.table.item(row, col)
        control_id, device = item.data(Qt.UserRole)
        
        # Verify input matches the device column
        if device_type == "keyboard" and device != "KEYBOARD":
            return
        if device_type == "joystick" and device != f"JOY_{joy_id}":
            return
        if device_type == "saitek" and device != "SAITEK":
            return
        
        # Determine binding type based on control definition
        from definitions import CONTROL_DEFINITIONS
        definition = CONTROL_DEFINITIONS[control_id]
        
        binding_data = {
            "device_type": device_type,
        }
        
        if device_type == "joystick":
            binding_data.update({"joy_id": joy_id, "type": input_type, "index": index})
        elif device_type == "saitek":
            binding_data.update({"switch": index, "state": "ON" if value == 1.0 else "OFF"})
        elif device_type == "keyboard":
            binding_data["key"] = index  # index will be the key name
        
        # Decide which binding slot to use
        if definition['type'] == 'slider':
            if 'id' in definition:  # Stepped slider
                # Prompt user for which step
                from PyQt5.QtWidgets import QInputDialog
                steps = definition.get('steps', {})
                step_choices = [f"{k}: {v}" for k, v in steps.items()]
                if not step_choices: self.stop_listening(); return
                choice, ok = QInputDialog.getItem(self, "Select Step", 
                                                   "Which step should this bind to?",
                                                   step_choices, 0, False)
                if ok and choice:
                    step_value = choice.split(":")[0]
                    control_bindings = self.bindings.setdefault(control_id, {})
                    values_dict = control_bindings.setdefault("values", {})
                    values_list = values_dict.setdefault(step_value, [])
                    if isinstance(values_list, dict):
                        values_list = [values_list]
                    if binding_data not in values_list:
                        values_list.append(binding_data)
                    values_dict[step_value] = values_list
                else:
                    self.stop_listening()
                    return
            else:  # Analog slider
                if input_type == "axis":
                    # This path should now be handled by bind_axis_mode
                    self.stop_listening()
                    return
                elif input_type == "button":
                    # Ask if increase or decrease
                    from PyQt5.QtWidgets import QInputDialog
                    choice, ok = QInputDialog.getItem(self, "Button Direction",
                                                       "Increase or Decrease?",
                                                       ["Increase", "Decrease"], 0, False)
                    if ok:
                        binding_type = choice.lower()
                        control_bindings = self.bindings.setdefault(control_id, {})
                        existing = control_bindings.get(binding_type, [])
                        if not isinstance(existing, list): existing = [existing]
                        if binding_data not in existing:
                            existing.append(binding_data)
                        control_bindings[binding_type] = existing
                    else:
                        self.stop_listening()
                        return
                else:
                    self.stop_listening()
                    return
        
        elif definition['type'] == 'button':
            behavior = definition.get("behavior")
            binding_type = "button" # Default
            if (behavior == 'hold' or behavior == 'toggle') and (device_type == "saitek" or (device_type == 'joystick' and input_type == 'button')):
                from PyQt5.QtWidgets import QInputDialog
                choice, ok = QInputDialog.getItem(self, "Button Event",
                                                   "Bind to Press or Release?",
                                                   ["Press (ON)", "Release (OFF)"], 0, False)
                if ok:
                    binding_type = "button" if "Press" in choice else "off_button"
                else:
                    self.stop_listening()
                    return

            control_bindings = self.bindings.setdefault(control_id, {})
            existing = control_bindings.get(binding_type, [])
            if not isinstance(existing, list): existing = [existing]
            if binding_data not in existing:
                existing.append(binding_data)
            control_bindings[binding_type] = existing
        
        self.stop_listening()
        self.populate_table()
        self.parent().log_message(f"Bound {device} to {control_id}", "BIND")
    
    def stop_listening(self):
        """Stop listening mode"""
        if self.listening_cell:
            self.listening_cell = None
            # Force a full repopulate to avoid stale references
            self.populate_table()
    
    def keyPressEvent(self, event):
        """Handle ESC to cancel listening, or capture key for keyboard binding"""
        if event.key() == Qt.Key_Escape:
            self.stop_listening()
            return
        
        if self.listening_cell:
            row, col = self.listening_cell
            item = self.table.item(row, col)
            control_id, device = item.data(Qt.UserRole)
            
            if device == "KEYBOARD":
                # Build key string with modifiers
                key_parts = []
                
                if event.modifiers() & Qt.ControlModifier:
                    key_parts.append('ctrl')
                if event.modifiers() & Qt.ShiftModifier:
                    key_parts.append('shift')
                if event.modifiers() & Qt.AltModifier:
                    key_parts.append('alt')
                if event.modifiers() & Qt.MetaModifier:
                    key_parts.append('win')
                
                # Map special keys
                key_map = {
                    Qt.Key_Control: None,  # Already handled by modifiers
                    Qt.Key_Shift: None,
                    Qt.Key_Alt: None,
                    Qt.Key_Meta: None,
                    Qt.Key_Return: 'enter',
                    Qt.Key_Enter: 'enter',
                    Qt.Key_Escape: 'esc',
                    Qt.Key_Space: 'space',
                    Qt.Key_Tab: 'tab',
                    Qt.Key_Backspace: 'backspace',
                    Qt.Key_Delete: 'delete',
                    Qt.Key_Insert: 'insert',
                    Qt.Key_Home: 'home',
                    Qt.Key_End: 'end',
                    Qt.Key_PageUp: 'pageup',
                    Qt.Key_PageDown: 'pagedown',
                    Qt.Key_Up: 'up',
                    Qt.Key_Down: 'down',
                    Qt.Key_Left: 'left',
                    Qt.Key_Right: 'right',
                    Qt.Key_F1: 'f1', Qt.Key_F2: 'f2', Qt.Key_F3: 'f3', Qt.Key_F4: 'f4',
                    Qt.Key_F5: 'f5', Qt.Key_F6: 'f6', Qt.Key_F7: 'f7', Qt.Key_F8: 'f8',
                    Qt.Key_F9: 'f9', Qt.Key_F10: 'f10', Qt.Key_F11: 'f11', Qt.Key_F12: 'f12',
                }
                
                # For F-keys with modifiers, handle specially
                if event.key() in [Qt.Key_F1, Qt.Key_F2, Qt.Key_F3, Qt.Key_F4, Qt.Key_F5, 
                                   Qt.Key_F6, Qt.Key_F7, Qt.Key_F8, Qt.Key_F9, Qt.Key_F10, 
                                   Qt.Key_F11, Qt.Key_F12]:
                    # For F-keys, always add the function key first to key_parts before processing
                    pass  # Will be handled below
                
                key_char = key_map.get(event.key())
                
                if key_char is None:
                    # Regular character key
                    key_text = event.text().lower()
                    if key_text and key_text.isprintable():
                        key_char = key_text
                    else:
                        # Ignore modifier-only presses
                        super().keyPressEvent(event)
                        return
                
                if key_char:
                    key_parts.append(key_char)
                    # Ensure consistent format: modifiers first, then key
                    # pyautogui expects: 'ctrl', 'alt', 'shift', then the key
                    key_name = '_'.join(key_parts)
                    self.capture_input(None, "keyboard", key_name, 1.0, "keyboard")
                    return
        
        super().keyPressEvent(event)
    
    def get_bindings(self):
        return self.bindings

    def import_openrails_keyboard(self):
        """Import keyboard bindings from OpenRails export file"""
        from PyQt5.QtWidgets import QFileDialog, QMessageBox
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select OpenRails Keyboard Export",
            "",
            "Keyboard Files (*.keyboard.txt *.txt);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            # OpenRails export format: "CommandName=KeyName"
            imported_count = 0
            
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    
                    parts = line.split('=', 1)
                    if len(parts) != 2:
                        continue
                    
                    command_name = parts[0].strip().upper()
                    key_name = parts[1].strip()
                    
                    # Try to match to our control definitions
                    from definitions import CONTROL_DEFINITIONS
                    
                    # Find matching control
                    matched_control = None
                    for control_id, definition in CONTROL_DEFINITIONS.items():
                        # Match by similar names
                        if command_name in control_id.upper() or control_id.upper() in command_name:
                            matched_control = control_id
                            break
                    
                    if matched_control:
                        # Add keyboard binding
                        binding_data = {"device_type": "keyboard", "key": key_name}
                        control_bindings = self.bindings.setdefault(matched_control, {})
                        
                        if "button" not in control_bindings:
                            control_bindings["button"] = []
                        elif not isinstance(control_bindings["button"], list):
                            control_bindings["button"] = [control_bindings["button"]]
                        
                        if binding_data not in control_bindings["button"]:
                            control_bindings["button"].append(binding_data)
                            imported_count += 1
            
            self.populate_table()
            QMessageBox.information(self, "Import Complete", 
                                    f"Successfully imported {imported_count} keyboard bindings.\n\n"
                                    "Note: Go to Options → Keyboard → Export in OpenRails to create this file.")
            self.parent().log_message(f"Imported {imported_count} keyboard bindings from OpenRails", "BIND")
            
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Error reading file:\n{str(e)}")

    def load_default_keyboard_bindings(self):
        """Load default OpenRails keyboard bindings from Open Rails Keyboard.txt"""
        default_kb_file = resource_path("Open Rails Keyboard.txt")
        
        if not os.path.exists(default_kb_file):
            return  # Silently skip if file doesn't exist
        
        try:
            command_mapping = {
                "GAME_SAVE": ("SAVE", "button"), "GAME_QUIT": ("QUIT", "button"), "GAME_PAUSE": ("PAUSE", "button"),
                "GAME_FACING_SWITCH_AHEAD": ("SWITCH_AHEAD", "button"), "GAME_FACING_SWITCH_BEHIND": ("SWITCH_BEHIND", "button"),
                "GAME_CHANGE_CAB": ("CHANGE_CAB", "button"), "GAME_SWITCH_MANUAL_MODE": ("MANUAL_SWITCH", "button"),
                "GAME_CLEAR_SIGNAL_FORWARD": ("CLEAR_SIGNAL", "button"), "GAME_AUTOPILOT_MODE": ("AUTOPILOT", "button"),
                "DISPLAY_TRACK_MONITOR_WINDOW": ("TRACK_MONITOR", "button"), "DISPLAY_HUD": ("HUD", "button"),
                "DISPLAY_TRAIN_DRIVING_WINDOW": ("TRAIN_DRIVING", "button"), "DISPLAY_SWITCH_WINDOW": ("SWITCH_PANEL", "button"),
                "DISPLAY_TRAIN_OPERATIONS_WINDOW": ("TRAIN_OPERATIONS", "button"), "DISPLAY_TRAIN_DPU_WINDOW": ("TRAIN_DPU", "button"),
                "DISPLAY_NEXT_STATION_WINDOW": ("NEXT_STATION", "button"), "DISPLAY_TRAIN_LIST_WINDOW": ("TRAIN_LIST", "button"),
                "DISPLAY_EOTLIST_WINDOW": ("EOT_LIST", "button"),
                "CAMERA_CAB": ("CAB_CAMERA", "button"), "CAMERA_OUTSIDE_FRONT": ("EXTERNAL_CAMERA", "button"),
                "CAMERA_OUTSIDE_REAR": ("EXTERNAL_CAMERA", "button"), "CAMERA_TRACKSIDE": ("TRACKSIDE_CAMERA", "button"),
                "CAMERA_PASSENGER": ("PASSENGER_CAMERA", "button"), "CAMERA_BRAKEMAN": ("CAR_CAMERA", "button"),
                "CAMERA_FREE": ("FREE_CAMERA", "button"), "CAMERA_HEAD_OUT_FORWARD": ("HEADOUT_CAMERA", "button"),
                "CONTROL_THROTTLE_INCREASE": ("THROTTLE", "increase"), "CONTROL_THROTTLE_DECREASE": ("THROTTLE", "decrease"),
                "CONTROL_TRAIN_BRAKE_INCREASE": ("TRAIN_BRAKE", "increase"), "CONTROL_TRAIN_BRAKE_DECREASE": ("TRAIN_BRAKE", "decrease"),
                "CONTROL_ENGINE_BRAKE_INCREASE": ("ENGINE_BRAKE", "increase"), "CONTROL_ENGINE_BRAKE_DECREASE": ("ENGINE_BRAKE", "decrease"),
                "CONTROL_DYNAMIC_BRAKE_INCREASE": ("DYNAMIC_BRAKE", "increase"), "CONTROL_DYNAMIC_BRAKE_DECREASE": ("DYNAMIC_BRAKE", "decrease"),
                "CONTROL_INDEPENDENT_BRAKE_INCREASE": ("INDEPENDENT_BRAKE", "increase"), "CONTROL_INDEPENDENT_BRAKE_DECREASE": ("INDEPENDENT_BRAKE", "decrease"),
                "CONTROL_HEADLIGHT_INCREASE": ("FRONT_HLIGHT", "increase"), "CONTROL_HEADLIGHT_DECREASE": ("FRONT_HLIGHT", "decrease"),
                "CONTROL_BAIL_OFF": ("BAIL_OFF", "button"), "CONTROL_HANDBRAKE_FULL": ("HANDBRAKE", "button"),
                "CONTROL_HANDBRAKE_NONE": ("HANDBRAKE", "off_button"), "CONTROL_RETAINERS_ON": ("RETAINERS", "button"),
                "CONTROL_RETAINERS_OFF": ("RETAINERS", "off_button"), "CONTROL_BRAKE_HOSE_CONNECT": ("BRAKE_HOSE", "button"),
                "CONTROL_BRAKE_HOSE_DISCONNECT": ("BRAKE_HOSE", "off_button"), "CONTROL_ALERTER": ("ALERTER", "button"),
                "CONTROL_EMERGENCY_PUSH_BUTTON": ("EMERGENCY", "button"), "CONTROL_SANDER": ("SANDER", "button"),
                "CONTROL_SANDER_TOGGLE": ("SANDER", "button"), "CONTROL_WIPER": ("WIPER", "button"),
                "CONTROL_HORN": ("HORN", "button"), "CONTROL_BELL": ("BELL", "button"),
                "CONTROL_BELL_TOGGLE": ("BELL", "button"), "CONTROL_DOOR_LEFT": ("DOOR_LEFT", "button"),
                "CONTROL_DOOR_RIGHT": ("DOOR_RIGHT", "button"), "CONTROL_LIGHT": ("LIGHT", "button"),
                "CONTROL_PANTOGRAPH_1": ("PANTOGRAPH", "button"), "CONTROL_PANTOGRAPH_2": ("PANTOGRAPH2", "button"),
                "CONTROL_BATTERY_SWITCH_CLOSE": ("BATTERY", "button"), "CONTROL_MASTER_KEY": ("MASTER_KEY", "button"),
                "CONTROL_CIRCUIT_BREAKER_CLOSING_ORDER": ("CIRCUIT_BREAKER", "button"), "CONTROL_DIESEL_PLAYER": ("ENGINE_START", "button"),
                "CONTROL_CYLINDER_COCKS": ("CYLINDER_COCKS", "button"), "CONTROL_INJECTOR_1": ("STEAM_INJECTOR1", "button"),
                "CONTROL_INJECTOR_2": ("STEAM_INJECTOR2", "button"), "CONTROL_BLOWER_INCREASE": ("STEAM_BLOWER", "button"),
            }
            
            with open(default_kb_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('Command') or line.startswith('===='):
                        continue
                    
                    parts = re.split(r'\s{2,}', line)
                    if len(parts) < 2:
                        continue
                    
                    command_name = parts[0].strip().upper().replace(' ', '_')
                    key_combo = parts[1].strip()
                    
                    if command_name in command_mapping:
                        control_id, binding_type = command_mapping[command_name]
                        
                        key_name = key_combo.lower().replace(' + ', '_')
                        
                        binding_data = {"device_type": "keyboard", "key": key_name}
                        
                        control_bindings = self.bindings.setdefault(control_id, {})
                        
                        if binding_type not in control_bindings:
                            control_bindings[binding_type] = []
                        elif not isinstance(control_bindings[binding_type], list):
                            control_bindings[binding_type] = [control_bindings[binding_type]]
                        
                        if binding_data not in control_bindings[binding_type]:
                            control_bindings[binding_type].append(binding_data)
            
            self.populate_table()
            
        except Exception as e:
            # Silently fail - don't disrupt program startup
            pass

class AxisConfigDialog(QDialog):
    axis_value_changed = pyqtSignal(float)  # Emits current axis value
    
    def __init__(self, existing_binding=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configure Axis Binding")
        self.resize(500, 400)
        self.binding_data = existing_binding.copy() if existing_binding else {}
        self.is_listening = True
        
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("<b>Move the axis you want to bind.</b> The meter below will show live input.")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Live visualization
        vis_group = QGroupBox("Live Axis Input")
        vis_layout = QVBoxLayout(vis_group)
        
        self.axis_meter = QProgressBar()
        self.axis_meter.setRange(-1000, 1000)
        self.axis_meter.setValue(0)
        self.axis_meter.setTextVisible(False)
        vis_layout.addWidget(self.axis_meter)
        
        self.raw_value_label = QLabel("Raw Value: 0.0000")
        self.raw_value_label.setAlignment(Qt.AlignCenter)
        self.raw_value_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        vis_layout.addWidget(self.raw_value_label)
        
        self.device_info_label = QLabel("Waiting for axis input...")
        self.device_info_label.setAlignment(Qt.AlignCenter)
        vis_layout.addWidget(self.device_info_label)
        
        layout.addWidget(vis_group)
        
        # Configuration options
        config_group = QGroupBox("Axis Settings")
        config_form = QFormLayout(config_group)
        
        self.invert_cb = QCheckBox("Invert Axis")
        self.invert_cb.setChecked(self.binding_data.get("inverted", False))
        config_form.addRow(self.invert_cb)
        
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(10, 200)  # 10% to 200%
        self.sensitivity_slider.setValue(int(self.binding_data.get("sensitivity", 1.0) * 100))
        self.sensitivity_label = QLabel(f"{self.sensitivity_slider.value()}%")
        self.sensitivity_slider.valueChanged.connect(lambda v: self.sensitivity_label.setText(f"{v}%"))
        
        sens_layout = QHBoxLayout()
        sens_layout.addWidget(self.sensitivity_slider)
        sens_layout.addWidget(self.sensitivity_label)
        config_form.addRow("Sensitivity:", sens_layout)
        
        self.deadzone_slider = QSlider(Qt.Horizontal)
        self.deadzone_slider.setRange(0, 30)  # 0% to 30%
        self.deadzone_slider.setValue(int(self.binding_data.get("deadzone", 0.02) * 100))
        self.deadzone_label = QLabel(f"{self.deadzone_slider.value()}%")
        self.deadzone_slider.valueChanged.connect(lambda v: self.deadzone_label.setText(f"{v}%"))
        
        dead_layout = QHBoxLayout()
        dead_layout.addWidget(self.deadzone_slider)
        dead_layout.addWidget(self.deadzone_label)
        config_form.addRow("Deadzone:", dead_layout)
        
        layout.addWidget(config_group)
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # If editing existing binding, populate info
        if existing_binding and "joy_id" in existing_binding:
            self.device_info_label.setText(f"Joy {existing_binding['joy_id']}, Axis {existing_binding['index']}")
            self.is_listening = False
    
    def update_axis_input(self, joy_id, axis_index, value):
        """Called by parent when axis input is detected"""
        if not self.is_listening:
            return
        
        # Store the binding info
        self.binding_data = {
            "device_type": "joystick",
            "joy_id": joy_id,
            "type": "axis",
            "index": axis_index
        }
        
        self.device_info_label.setText(f"Detected: Joy {joy_id}, Axis {axis_index}")
        self.is_listening = False  # Stop listening after first detection
        
        # Continue showing live values
        self.show_axis_value(value)
    
    def show_axis_value(self, value):
        """Update the visualization with current axis value"""
        self.axis_meter.setValue(int(value * 1000))
        self.raw_value_label.setText(f"Raw Value: {value:+.4f}")
    
    def get_binding_data(self):
        """Return the configured binding data"""
        self.binding_data["inverted"] = self.invert_cb.isChecked()
        self.binding_data["sensitivity"] = self.sensitivity_slider.value() / 100.0
        self.binding_data["deadzone"] = self.deadzone_slider.value() / 100.0
        return self.binding_data