# hid_manager.py
import hid
import threading
from PyQt5.QtCore import QObject, pyqtSignal

class SaitekPanelManager(QObject):
    saitek_event = pyqtSignal(str, str) # Emits switch_name, state ("ON" or "OFF")
    
    VENDOR_ID = 0x06A3
    PRODUCT_ID = 0x0D67
    # MAPPING CORRECTED based on user's direct observation of cyclical shift.
    PANEL_MAPPING = { 
        "BAT":        {'byte': 0, 'bit': 0}, "ALT":      {'byte': 0, 'bit': 1}, 
        "AVIONICS":   {'byte': 0, 'bit': 2}, "FUEL PUMP":{'byte': 0, 'bit': 3}, 
        "DE-ICE":     {'byte': 0, 'bit': 4}, "PITOT HEAT":{'byte': 0, 'bit': 5}, 
        "COWL":       {'byte': 0, 'bit': 6}, "PANEL":    {'byte': 0, 'bit': 7}, 
        "BEACON":     {'byte': 1, 'bit': 0}, "NAV":      {'byte': 1, 'bit': 1}, 
        "STROBE":     {'byte': 1, 'bit': 2}, "TAXI":     {'byte': 1, 'bit': 3}, 
        "LANDING":    {'byte': 1, 'bit': 4}, 
        "DIAL_OFF":   {'byte': 2, 'bit': 1}, # Was START's position
        "DIAL_R":     {'byte': 1, 'bit': 5}, # Was OFF's position
        "DIAL_L":     {'byte': 1, 'bit': 6}, # Was R's position
        "DIAL_BOTH":  {'byte': 1, 'bit': 7}, # Was L's position
        "DIAL_START": {'byte': 2, 'bit': 0}, # Was BOTH's position
        "GEAR_UP":    {'byte': 2, 'bit': 2}, "GEAR_DOWN":{'byte': 2, 'bit': 3}
    }
    SWITCH_NAMES = ["BAT", "ALT", "AVIONICS", "FUEL PUMP", "DE-ICE", "PITOT HEAT", "COWL", "PANEL", "BEACON", "NAV", "STROBE", "TAXI", "LANDING"]
    ROTARY_POSITIONS = ["DIAL_OFF", "DIAL_R", "DIAL_L", "DIAL_BOTH", "DIAL_START"]
    
    def __init__(self, parent=None):
        super().__init__(parent); self.device = None; self.running = False; self.thread = None
        self.stop_event = threading.Event(); self.last_states = {}

    def is_connected(self):
        try:
            if hid.enumerate(self.VENDOR_ID, self.PRODUCT_ID): return True
        except hid.HIDException: pass
        return False

    def start_listening(self):
        if self.running: return True
        try:
            self.device = hid.device(); self.device.open(self.VENDOR_ID, self.PRODUCT_ID)
            self.running = True; self.stop_event.clear()
            self.thread = threading.Thread(target=self.read_loop, daemon=True); self.thread.start()
            return True
        except (IOError, hid.HIDException, ValueError): self.device = None; return False

    def stop_listening(self):
        if not self.running: return
        self.running = False; self.stop_event.set()
        if self.thread: self.thread.join(timeout=1)
        if self.device: self.device.close()

    def is_bit_set(self, data, alias):
        m = self.PANEL_MAPPING.get(alias)
        if m and m['byte'] < len(data): return (data[m['byte']] & (1 << m['bit'])) != 0
        return False

    def read_loop(self):
        while not self.stop_event.is_set():
            try:
                data = self.device.read(8, timeout_ms=100)
                if data: self.handle_input(data)
            except (hid.HIDException, ValueError):
                self.stop_event.set(); self.running = False
        if self.device: self.device.close(); self.device = None
            
    def handle_input(self, data):
        for name in self.SWITCH_NAMES:
            is_on = self.is_bit_set(data, name)
            if self.last_states.get(name) != is_on: self.saitek_event.emit(name, "ON" if is_on else "OFF"); self.last_states[name] = is_on
        is_up = self.is_bit_set(data, "GEAR_UP"); is_down = self.is_bit_set(data, "GEAR_DOWN")
        if is_up != self.last_states.get("GEAR_UP"): self.saitek_event.emit("GEAR_UP", "ON" if is_up else "OFF"); self.last_states["GEAR_UP"] = is_up
        if is_down != self.last_states.get("GEAR_DOWN"): self.saitek_event.emit("GEAR_DOWN", "ON" if is_down else "OFF"); self.last_states["GEAR_DOWN"] = is_down
        current_rotary = next((pos for pos in self.ROTARY_POSITIONS if self.is_bit_set(data, pos)), None)
        last_rotary = self.last_states.get("ROTARY")
        if current_rotary != last_rotary:
            if last_rotary: self.saitek_event.emit(last_rotary, "OFF")
            if current_rotary: self.saitek_event.emit(current_rotary, "ON")
            self.last_states["ROTARY"] = current_rotary
            
    def shutdown(self):
        self.stop_listening()