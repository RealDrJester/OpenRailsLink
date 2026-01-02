# trackir_integration.py
# Simplified multi-camera version based on working deprecated code

import ctypes
import time
import pymem
import pymem.process
import pymem.memory
import winreg
from ctypes import wintypes
from enum import Enum
import tkinter as tk
import psutil
import sys
import os
import argparse
import json
import tempfile

PROCESS_NAME = "RunActivity.exe"

def is_parent_alive(parent_pid):
    """Check if parent process is still running"""
    try:
        return psutil.pid_exists(parent_pid)
    except:
        return False

class NPRESULT(Enum):
    NP_OK = 0
    NP_ERR_DEVICE_NOT_PRESENT = 1
    NP_ERR_DLL_NOT_FOUND = 4
    NP_ERR_NO_DATA = 5

class TRACKIRDATA(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("Status", ctypes.c_ushort), ("FrameSignature", ctypes.c_ushort),
        ("IOData", ctypes.c_ulong), ("Roll", ctypes.c_float),
        ("Pitch", ctypes.c_float), ("Yaw", ctypes.c_float),
        ("X", ctypes.c_float), ("Y", ctypes.c_float), ("Z", ctypes.c_float),
    ]

class TrackIRClient:
    def __init__(self, hwnd):
        self.dll = None
        self.hwnd = hwnd
        self.is_running = False
        self.status = "Inactive"
        self._initialize_dll()

    def _initialize_dll(self):
        try:
            reg = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
            key = winreg.OpenKey(reg, r'Software\NaturalPoint\NATURALPOINT\NPClient Location')
            dll_path, _ = winreg.QueryValueEx(key, "Path")
            winreg.CloseKey(key)
            winreg.CloseKey(reg)
            full_dll_path = f"{dll_path}\\NPClient64.dll"
            self.dll = ctypes.WinDLL(full_dll_path)
            self._NP_RegisterWindowHandle = self.dll.NP_RegisterWindowHandle
            self._NP_RegisterWindowHandle.restype = NPRESULT
            self._NP_RegisterWindowHandle.argtypes = [wintypes.HWND]
            self._NP_UnregisterWindowHandle = self.dll.NP_UnregisterWindowHandle
            self._NP_UnregisterWindowHandle.restype = NPRESULT
            self._NP_StartDataTransmission = self.dll.NP_StartDataTransmission
            self._NP_StartDataTransmission.restype = NPRESULT
            self._NP_StopDataTransmission = self.dll.NP_StopDataTransmission
            self._NP_StopDataTransmission.restype = NPRESULT
            self._NP_GetData = self.dll.NP_GetData
            self._NP_GetData.restype = NPRESULT
            self._NP_GetData.argtypes = [ctypes.POINTER(TRACKIRDATA)]
            self._NP_RegisterProgramProfileID = self.dll.NP_RegisterProgramProfileID
            self._NP_RegisterProgramProfileID.restype = NPRESULT
            self._NP_RegisterProgramProfileID.argtypes = [ctypes.c_ushort]
            self._NP_RequestData = self.dll.NP_RequestData
            self._NP_RequestData.restype = NPRESULT
            self._NP_RequestData.argtypes = [ctypes.c_ushort]
            self.status = "DLL Loaded"
            print("[TrackIR] DLL loaded")
        except Exception as e:
            self.status = f"Error: {e}"
            print(f"[TrackIR] Failed to load DLL: {e}")

    def start(self):
        if not self.dll or self.is_running:
            return False
        try:
            if self._NP_RegisterWindowHandle(self.hwnd) != NPRESULT.NP_OK:
                raise Exception("Failed to register window handle")
            if self._NP_RequestData(119) != NPRESULT.NP_OK:
                raise Exception("Failed to request data fields")
            if self._NP_RegisterProgramProfileID(13302) != NPRESULT.NP_OK:
                raise Exception("Failed to register profile ID")
            if self._NP_StartDataTransmission() != NPRESULT.NP_OK:
                raise Exception("Failed to start transmission")
            self.is_running = True
            self.status = "Running"
            print("[TrackIR] Started")
            return True
        except Exception as e:
            self.status = f"Error: {e}"
            print(f"[TrackIR] Start failed: {e}")
            return False

    def stop(self):
        if not self.dll or not self.is_running:
            return
        try:
            self._NP_StopDataTransmission()
            self._NP_UnregisterWindowHandle()
            self.is_running = False
            self.status = "Stopped"
            print("[TrackIR] Stopped")
        except Exception as e:
            print(f"[TrackIR] Error stopping: {e}")

    def get_data(self):
        if not self.is_running:
            return None
        data = TRACKIRDATA()
        if self._NP_GetData(ctypes.byref(data)) == NPRESULT.NP_OK:
            return data
        return None

class SimpleTrackIRWriter:
    def __init__(self, config, initial_address=None):
        self.pm = None
        self.config = config
        self.address = int(initial_address, 16) if initial_address and initial_address != "0" else None
        self.running = True
        self.my_pid = os.getpid()
        self.parent_pid = os.getppid()
        
        # Create Tkinter window once
        self.root = tk.Tk()
        self.root.withdraw()
        hwnd = int(self.root.wm_frame(), 16)
        
        self.trackir = TrackIRClient(hwnd)
        self.last_print_time = 0
        
        # Baselines for 6-DOF
        self.baseline_fb = None
        self.baseline_ud = None
        self.baseline_lr = None
        
    def attach_to_game(self):
        while self.running:
            try:
                self.pm = pymem.Pymem(PROCESS_NAME)
                print(f"[Game] Attached (PID: {self.pm.process_id})")
                return True
            except pymem.exception.ProcessNotFound:
                print(f"[Game] Waiting for {PROCESS_NAME}...")
                time.sleep(5)
        return False
    
    def run(self):
        print("="*60)
        print(f"[Writer] Starting (PID: {self.my_pid})")
        print("="*60)
        
        if not self.attach_to_game():
            return
        
        if not self.trackir.start():
            print("[TrackIR] Failed to start")
            return
        
        print("[Writer] Entering main loop...")
        
        while self.running:
            try:
                # Check if game still running
                if not psutil.pid_exists(self.pm.process_id):
                    print("[Game] Process ended")
                    break
                
                # Check for shutdown flag (only check, don't do file I/O every frame)
                if self.my_pid and os.path.exists(os.path.join(tempfile.gettempdir(), f"trackir_writer_shutdown_{self.my_pid}.flag")):
                    print("[Writer] Shutdown requested")
                    try:
                        os.remove(os.path.join(tempfile.gettempdir(), f"trackir_writer_shutdown_{self.my_pid}.flag"))
                    except:
                        pass
                    break
                
                # Check for address updates (simple check)
                update_file = os.path.join(tempfile.gettempdir(), f"trackir_address_update_{self.my_pid}.dat")
                if os.path.exists(update_file):
                    try:
                        with open(update_file, 'r') as f:
                            line = f.read().strip()
                        os.remove(update_file)
                        if ':' in line:
                            _, addr_hex = line.split(':', 1)
                            self.address = int(addr_hex.strip(), 16)
                            self.baseline_fb = None
                            self.baseline_ud = None
                            self.baseline_lr = None
                            print(f"[Writer] Address updated: {hex(self.address)}")
                    except:
                        pass
                
                # If no address, skip
                if not self.address:
                    time.sleep(0.1)
                    continue
                
                # Get TrackIR data
                trackir_data = self.trackir.get_data()
                
                if trackir_data:
                    # Parse config
                    x_limit = self.config.get("x_limit", 2.7)
                    y_limit = self.config.get("y_limit", 1.5)
                    x_offset = int(self.config.get("x_offset", "C"), 16)
                    y_offset = int(self.config.get("y_offset", "0"), 16)
                    
                    # Scale rotation
                    yaw_scaled = (-trackir_data.Yaw / 16383.0) * x_limit
                    pitch_scaled = (trackir_data.Pitch / 16383.0) * y_limit
                    final_yaw = max(-x_limit, min(x_limit, yaw_scaled))
                    final_pitch = max(-y_limit, min(y_limit, pitch_scaled))
                    
                    # Write rotation - SIMPLE, NO VALIDATION
                    try:
                        self.pm.write_float(self.address + x_offset, final_yaw)
                        self.pm.write_float(self.address + y_offset, final_pitch)
                    except Exception as e:
                        print(f"\n[Writer] Write failed: {e}")
                        print("[Writer] Clearing address, will rescan")
                        self.address = None
                        self.baseline_fb = None
                        self.baseline_ud = None
                        self.baseline_lr = None
                        time.sleep(1)
                        continue
                    
                    # Handle 6-DOF if enabled
                    if self.config.get("enable_camera_movement", False):
                        fb_add = self.config.get("forward_backward_add", 0.6)
                        ud_add = self.config.get("up_down_add", 0.5)
                        lr_add = self.config.get("left_right_add", 0.6)
                        
                        fb_offset_str = self.config.get("forward_backward_offset", "6c")
                        ud_offset_str = self.config.get("up_down_offset", "68")
                        lr_offset_str = self.config.get("left_right_offset", "64")
                        
                        # Parse offsets
                        fb_offset = sum(int(p.strip(), 16) for p in fb_offset_str.split('+')) if '+' in fb_offset_str else int(fb_offset_str, 16)
                        ud_offset = int(ud_offset_str, 16)
                        lr_offset = int(lr_offset_str, 16)
                        
                        forward_backward = -(trackir_data.Z / 16383.0) * fb_add
                        up_down = (trackir_data.Y / 16383.0) * ud_add
                        left_right = -(trackir_data.X / 16383.0) * lr_add
                        
                        # Capture baseline
                        if self.baseline_fb is None:
                            try:
                                self.baseline_fb = self.pm.read_float(self.address + fb_offset)
                                self.baseline_ud = self.pm.read_float(self.address + ud_offset)
                                self.baseline_lr = self.pm.read_float(self.address + lr_offset)
                                print(f"[Writer] Baseline: FB={self.baseline_fb:.2f}, UD={self.baseline_ud:.2f}, LR={self.baseline_lr:.2f}")
                            except:
                                self.baseline_fb = 0.0
                                self.baseline_ud = 0.0
                                self.baseline_lr = 0.0
                        
                        # Write position
                        try:
                            self.pm.write_float(self.address + fb_offset, self.baseline_fb + forward_backward)
                            self.pm.write_float(self.address + ud_offset, self.baseline_ud + up_down)
                            self.pm.write_float(self.address + lr_offset, self.baseline_lr + left_right)
                        except Exception as e:
                            print(f"\n[Writer] Position write failed: {e}")
                            self.address = None
                            self.baseline_fb = None
                            self.baseline_ud = None
                            self.baseline_lr = None
                            time.sleep(1)
                            continue
                
                # Minimal output (overwrite same line)
                current_time = time.time()
                if current_time - self.last_print_time > 5.0:
                    print(f"[Heartbeat] Active, Address: {hex(self.address) if self.address else 'None'}         ")
                    self.last_print_time = current_time
                
                # Minimal sleep
                time.sleep(0.01)
                
                # Check parent status less frequently (every ~1 second)
                if not hasattr(self, '_parent_check_counter'):
                    self._parent_check_counter = 0
                self._parent_check_counter += 1
                
                if self._parent_check_counter >= 100:  # 100 * 0.01s = 1 second
                    self._parent_check_counter = 0
                    if not is_parent_alive(self.parent_pid):
                        print("[Writer] Parent process died - shutting down")
                        self.running = False
                        break
                
            except KeyboardInterrupt:
                self.running = False
                print("\n[Writer] User interrupt")
                break
            except Exception as e:
                # ANY error - just log and continue
                print(f"\n[Writer] Error: {e}")
                print("[Writer] Resetting...")
                self.address = None
                self.baseline_fb = None
                self.baseline_ud = None
                self.baseline_lr = None
                time.sleep(1)
                continue
        
        self.trackir.stop()
        print("[Writer] Shutdown complete")

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Error: Administrator privileges required")
        sys.exit(1)
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", type=str, required=True)
    parser.add_argument("--cab-address", type=str, default="0")
    parser.add_argument("--external-address", type=str, default="0")
    parser.add_argument("--interior-address", type=str, default="0")
    parser.add_argument("--active-camera", type=str, default="cab")
    args = parser.parse_args()
    
    # Load config
    with open(args.config_file, 'r') as f:
        all_configs = json.load(f)
    
    # Use config for active camera
    config = all_configs.get(args.active_camera, all_configs.get('cab', {}))
    
    # Get initial address
    initial_address = None
    if args.active_camera == 'cab' and args.cab_address != "0":
        initial_address = args.cab_address
    elif args.active_camera == 'external' and args.external_address != "0":
        initial_address = args.external_address
    elif args.active_camera == 'interior' and args.interior_address != "0":
        initial_address = args.interior_address
    
    writer = SimpleTrackIRWriter(config, initial_address)
    writer.run()