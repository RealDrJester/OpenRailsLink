# controls.py
import pygame
from PyQt5.QtCore import QObject, pyqtSignal, Qt
from PyQt5.QtWidgets import (QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QLabel, QCheckBox, QGroupBox,
                             QFormLayout, QPushButton, QDialogButtonBox, QListWidgetItem, QStackedWidget,
                             QWidget, QScrollArea, QProgressBar, QGridLayout)
import threading
from functools import partial
from definitions import CONTROL_DEFINITIONS

class JoystickManager(QObject):
    raw_joystick_event = pyqtSignal(int, str, int, object)
    def __init__(self, parent=None):
        super().__init__(parent); pygame.init(); pygame.joystick.init()
        self.joysticks = {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}
        self.listener_threads = {}; self.stop_events = {}
    def get_devices(self): return {i: j.get_name() for i, j in self.joysticks.items()}
    def reinitialize(self):
        for joy_id in list(self.listener_threads.keys()): self.stop_listening(joy_id)
        pygame.joystick.quit(); pygame.joystick.init()
        self.joysticks = {i: pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())}
        return self.get_devices()
    def start_listening(self, joystick_id):
        if joystick_id in self.joysticks and joystick_id not in self.listener_threads:
            self.stop_events[joystick_id] = threading.Event()
            thread = threading.Thread(target=self._listen_for_events, args=(joystick_id, self.stop_events[joystick_id]), daemon=True)
            self.listener_threads[joystick_id] = thread; thread.start()
    def stop_listening(self, joystick_id):
        if joystick_id in self.listener_threads:
            self.stop_events[joystick_id].set(); thread = self.listener_threads.pop(joystick_id); thread.join(timeout=1); del self.stop_events[joystick_id]
    def _listen_for_events(self, joystick_id, stop_event):
        while not stop_event.is_set():
            for event in pygame.event.get():
                if 'joy' in event.dict and event.joy == joystick_id: self._process_event(event.type, event.joy, event.dict)
            pygame.time.wait(10)
    def _process_event(self, event_type, joy_id, event_dict):
        if event_type == pygame.JOYAXISMOTION: self.raw_joystick_event.emit(joy_id, "axis", event_dict['axis'], event_dict['value'])
        elif event_type == pygame.JOYBUTTONDOWN: self.raw_joystick_event.emit(joy_id, "button", event_dict['button'], 1.0)
        elif event_type == pygame.JOYBUTTONUP: self.raw_joystick_event.emit(joy_id, "button", event_dict['button'], 0.0)
    def shutdown(self):
        for joystick_id in list(self.listener_threads.keys()): self.stop_listening(joystick_id)
        pygame.quit()

class BindingsEditor(QDialog):
    def __init__(self, current_bindings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bindings Editor"); self.resize(800, 600)
        self.bindings = current_bindings.copy(); self.current_control_id = None; self.listening_button = None; self.binding_target = None
        main_layout = QHBoxLayout(self)
        left_panel = QVBoxLayout(); left_panel.addWidget(QLabel("<h3>Available Controls</h3>"))
        self.controls_list = QListWidget()
        for control_id, definition in CONTROL_DEFINITIONS.items():
            item = QListWidgetItem(f"{definition['desc']}"); item.setData(Qt.UserRole, control_id); self.controls_list.addItem(item)
        self.controls_list.itemClicked.connect(self.select_control)
        left_panel.addWidget(self.controls_list); main_layout.addLayout(left_panel, 1)
        right_panel = QVBoxLayout(); self.control_name_label = QLabel("<h3>Select a control to begin</h3>")
        right_panel.addWidget(self.control_name_label)
        self.editor_stack = QStackedWidget(); right_panel.addWidget(self.editor_stack)
        self.setup_editor_panels()
        button_layout = QHBoxLayout(); apply_button = QPushButton("Apply & Close"); apply_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel"); cancel_button.clicked.connect(self.reject)
        button_layout.addStretch(); button_layout.addWidget(apply_button); button_layout.addWidget(cancel_button)
        right_panel.addLayout(button_layout); main_layout.addLayout(right_panel, 2)

    def setup_editor_panels(self):
        self.placeholder_widget = QWidget(); self.editor_stack.addWidget(self.placeholder_widget)
        self.button_editor_widget = self.create_simple_button_editor(); self.editor_stack.addWidget(self.button_editor_widget)
        self.slider_editor_widget = self.create_slider_editor(); self.editor_stack.addWidget(self.slider_editor_widget)
        
    def create_simple_button_editor(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0)

        # 'ON' Binding Group
        group_on = QGroupBox("ON / Press Event"); form_on = QFormLayout(group_on)
        self.button_bind_label = QLabel("None")
        btn_layout_on = QHBoxLayout()
        btn_on = QPushButton("Bind"); btn_on.setCheckable(True)
        btn_on_del = QPushButton("Delete")
        btn_layout_on.addWidget(btn_on); btn_layout_on.addWidget(btn_on_del); btn_layout_on.addStretch()
        form_on.addRow("Binding:", self.button_bind_label)
        form_on.addRow(btn_layout_on)
        layout.addWidget(group_on)

        # 'OFF' Binding Group
        group_off = QGroupBox("OFF / Release Event"); form_off = QFormLayout(group_off)
        self.off_button_bind_label = QLabel("None")
        btn_layout_off = QHBoxLayout()
        btn_off = QPushButton("Bind"); btn_off.setCheckable(True)
        btn_off_del = QPushButton("Delete")
        btn_layout_off.addWidget(btn_off); btn_layout_off.addWidget(btn_off_del); btn_layout_off.addStretch()
        form_off.addRow("Binding:", self.off_button_bind_label)
        form_off.addRow(btn_layout_off)
        layout.addWidget(group_off)

        # Connections
        btn_on.toggled.connect(partial(self.toggle_listen_mode, btn_on, "button"))
        btn_on_del.clicked.connect(partial(self.delete_binding, "button"))
        btn_off.toggled.connect(partial(self.toggle_listen_mode, btn_off, "off_button"))
        btn_off_del.clicked.connect(partial(self.delete_binding, "off_button"))
        
        layout.addStretch()
        return widget

    def create_slider_editor(self):
        widget = QWidget(); layout = QVBoxLayout(widget); layout.setContentsMargins(0,0,0,0)
        
        # Analog & Button Group
        self.analog_group = QGroupBox("Analog and Button Controls"); analog_layout = QFormLayout(self.analog_group)
        
        # --- Axis Controls ---
        self.axis_bind_label = QLabel("None")
        axis_controls_widget = QWidget()
        axis_controls_layout = QHBoxLayout(axis_controls_widget)
        axis_controls_layout.setContentsMargins(0,0,0,0)
        self.btn_axis = QPushButton("Bind"); self.btn_axis.setCheckable(True)
        btn_axis_del = QPushButton("Delete")
        axis_controls_layout.addWidget(self.btn_axis)
        axis_controls_layout.addWidget(btn_axis_del)
        axis_controls_layout.addStretch()
        self.axis_invert_cb = QCheckBox("Invert")
        self.axis_invert_cb.stateChanged.connect(self.update_axis_inversion)
        axis_controls_layout.addWidget(self.axis_invert_cb)
        analog_layout.addRow("Axis Binding:", self.axis_bind_label)
        analog_layout.addRow(axis_controls_widget)

        # --- Increase Controls ---
        self.increase_bind_label = QLabel("None")
        inc_btn_layout = QHBoxLayout()
        btn_inc = QPushButton("Bind"); btn_inc.setCheckable(True)
        btn_inc_del = QPushButton("Delete")
        inc_btn_layout.addWidget(btn_inc); inc_btn_layout.addWidget(btn_inc_del); inc_btn_layout.addStretch()
        analog_layout.addRow("Increase Button:", self.increase_bind_label)
        analog_layout.addRow(inc_btn_layout)

        # --- Decrease Controls ---
        self.decrease_bind_label = QLabel("None")
        dec_btn_layout = QHBoxLayout()
        btn_dec = QPushButton("Bind"); btn_dec.setCheckable(True)
        btn_dec_del = QPushButton("Delete")
        dec_btn_layout.addWidget(btn_dec); dec_btn_layout.addWidget(btn_dec_del); dec_btn_layout.addStretch()
        analog_layout.addRow("Decrease Button:", self.decrease_bind_label)
        analog_layout.addRow(dec_btn_layout)
        
        layout.addWidget(self.analog_group)

        # Connections
        self.btn_axis.toggled.connect(partial(self.toggle_listen_mode, self.btn_axis, "axis"))
        btn_axis_del.clicked.connect(partial(self.delete_binding, "axis"))
        btn_inc.toggled.connect(partial(self.toggle_listen_mode, btn_inc, "increase"))
        btn_inc_del.clicked.connect(partial(self.delete_binding, "increase"))
        btn_dec.toggled.connect(partial(self.toggle_listen_mode, btn_dec, "decrease"))
        btn_dec_del.clicked.connect(partial(self.delete_binding, "decrease"))
        
        # Live Input Meter
        meter_group = QGroupBox("Live Input Meter"); meter_layout = QGridLayout(meter_group)
        self.input_meter_bar = QProgressBar(); self.input_meter_bar.setRange(-1000, 1000); self.input_meter_bar.setValue(0); self.input_meter_bar.setTextVisible(False)
        self.input_meter_label = QLabel("0.0000"); self.input_meter_label.setAlignment(Qt.AlignCenter)
        meter_layout.addWidget(self.input_meter_bar, 0, 0); meter_layout.addWidget(self.input_meter_label, 0, 1)
        layout.addWidget(meter_group)
        
        # Stepped Bindings - No ScrollArea
        self.stepped_group = QGroupBox("Discrete Step Binding")
        self.stepped_layout = QFormLayout()
        self.stepped_group.setLayout(self.stepped_layout)
        layout.addWidget(self.stepped_group)

        layout.addStretch()
        return widget

    def select_control(self, item):
        self.current_control_id = item.data(Qt.UserRole); definition = CONTROL_DEFINITIONS[self.current_control_id]
        self.control_name_label.setText(f"<h3>Editing: {definition['desc']}</h3>")
        control_type = definition.get("type")
        if control_type == "button": self.populate_simple_button_editor(); self.editor_stack.setCurrentWidget(self.button_editor_widget)
        elif control_type == "slider": self.populate_slider_editor(); self.editor_stack.setCurrentWidget(self.slider_editor_widget)
        self.input_meter_bar.setValue(0); self.input_meter_label.setText("0.0000")

    def populate_simple_button_editor(self):
        on_binding = self.bindings.get(self.current_control_id, {}).get("button")
        off_binding = self.bindings.get(self.current_control_id, {}).get("off_button")
        self.button_bind_label.setText(self.format_binding_text(on_binding))
        self.off_button_bind_label.setText(self.format_binding_text(off_binding))

    def populate_slider_editor(self):
        bindings = self.bindings.get(self.current_control_id, {})
        definition = CONTROL_DEFINITIONS[self.current_control_id]
        
        form_layout = self.analog_group.layout()
        has_axis = 'id' not in definition

        form_layout.labelForField(self.axis_bind_label).setVisible(has_axis)
        self.axis_bind_label.setVisible(has_axis)
        self.axis_bind_label.parent().findChild(QWidget).setVisible(has_axis) # Hide the whole controls widget

        if has_axis:
            self.axis_bind_label.setText(self.format_binding_text(bindings.get("axis")))
            self.axis_invert_cb.setChecked(bindings.get("axis", {}).get("inverted", False))
        
        self.increase_bind_label.setText(self.format_binding_text(bindings.get("increase")))
        self.decrease_bind_label.setText(self.format_binding_text(bindings.get("decrease")))
        
        self.stepped_group.setVisible('steps' in definition)
        if 'steps' in definition:
            while self.stepped_layout.count():
                self.stepped_layout.removeRow(0)

            value_bindings = bindings.get("values", {})
            for value, desc in definition['steps'].items():
                step_binding = value_bindings.get(value)
                label = QLabel(f"Set to {desc} ({value}):")
                bind_label = QLabel(self.format_binding_text(step_binding))
                
                btn_widget = QWidget()
                btn_layout = QHBoxLayout(btn_widget)
                btn_layout.setContentsMargins(0,0,0,0)
                btn = QPushButton("Bind"); btn.setCheckable(True)
                btn_del = QPushButton("Delete")
                btn_layout.addWidget(btn); btn_layout.addWidget(btn_del); btn_layout.addStretch()
                
                btn.toggled.connect(partial(self.toggle_listen_mode, btn, f"value_{value}"))
                btn_del.clicked.connect(partial(self.delete_binding, f"value_{value}"))
                
                self.stepped_layout.addRow(label, bind_label)
                self.stepped_layout.addRow(btn_widget)
                
    def format_binding_text(self, binding_data):
        if not binding_data: return "None"
        if binding_data.get("device_type") == "saitek": return f"Saitek Panel - {binding_data['switch']} ({binding_data['state']})"
        return f"Joy {binding_data['joy_id']}, {binding_data['type'].capitalize()} {binding_data['index']}"
                
    def update_input_meter(self, joy_id, type, index, value):
        if self.editor_stack.currentWidget() == self.slider_editor_widget and type == 'axis':
            self.input_meter_bar.setValue(int(value * 1000)); self.input_meter_label.setText(f"{value:.4f}")

    def toggle_listen_mode(self, button, target, is_listening):
        if self.listening_button and self.listening_button != button: self.listening_button.setChecked(False)
        self.listening_button = button if is_listening else None; self.binding_target = target if is_listening else None
        button.setText("Listening..." if is_listening else "Bind")

    def capture_joystick_input(self, joy_id, type, index, value):
        if not self.listening_button: return
        target_type = self.binding_target
        if target_type == "axis" and type == "axis":
            self.bindings.setdefault(self.current_control_id, {})["axis"] = {"device_type": "joystick", "joy_id": joy_id, "type": type, "index": index, "inverted": self.axis_invert_cb.isChecked()}
        elif type == "button":
            binding_data = {"device_type": "joystick", "joy_id": joy_id, "type": type, "index": index}
            if target_type == "button" and value == 1.0: self.bindings.setdefault(self.current_control_id, {})["button"] = binding_data
            elif target_type == "off_button" and value == 1.0: self.bindings.setdefault(self.current_control_id, {})["off_button"] = binding_data
            elif target_type == "increase" and value == 1.0: self.bindings.setdefault(self.current_control_id, {})["increase"] = binding_data
            elif target_type == "decrease" and value == 1.0: self.bindings.setdefault(self.current_control_id, {})["decrease"] = binding_data
            elif "value_" in target_type and value == 1.0:
                step = target_type.split("_")[1]; self.bindings.setdefault(self.current_control_id, {}).setdefault("values", {})[step] = binding_data
            else: return
        else: return
        self.listening_button.setChecked(False); self.select_control(self.controls_list.currentItem())
        
    def capture_saitek_input(self, switch, state):
        if not self.listening_button: return
        binding_data = {"device_type": "saitek", "switch": switch, "state": state}
        target_type = self.binding_target
        if target_type == "button" and state == "ON": self.bindings.setdefault(self.current_control_id, {})["button"] = binding_data
        elif target_type == "off_button" and state == "OFF": self.bindings.setdefault(self.current_control_id, {})["off_button"] = binding_data
        elif target_type == "increase" and state == "ON": self.bindings.setdefault(self.current_control_id, {})["increase"] = binding_data
        elif target_type == "decrease" and state == "ON": self.bindings.setdefault(self.current_control_id, {})["decrease"] = binding_data
        elif "value_" in target_type and state == "ON":
            step = target_type.split("_")[1]; self.bindings.setdefault(self.current_control_id, {}).setdefault("values", {})[step] = binding_data
        else: return
        self.listening_button.setChecked(False); self.select_control(self.controls_list.currentItem())

    def delete_binding(self, target):
        if self.current_control_id is None: return
        
        control_bindings = self.bindings.get(self.current_control_id)
        if not control_bindings: return

        if target.startswith("value_"):
            step = target.split("_")[1]
            if "values" in control_bindings and step in control_bindings["values"]:
                del control_bindings["values"][step]
                if not control_bindings["values"]:
                    del control_bindings["values"]
        elif target in control_bindings:
            del control_bindings[target]
            
        if not self.bindings.get(self.current_control_id):
            del self.bindings[self.current_control_id]
        
        self.select_control(self.controls_list.currentItem())
        
    def update_axis_inversion(self):
        if self.current_control_id:
            axis_binding = self.bindings.setdefault(self.current_control_id, {}).get("axis")
            if axis_binding: axis_binding["inverted"] = self.axis_invert_cb.isChecked()
            
    def get_bindings(self): return self.bindings