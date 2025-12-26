# trackir_scanner.py
# New scanner that implements the 2-step LUA script logic in Python.
# 1. Broadly scans for all possible camera candidates using a generic AOB.
# 2. Filters candidates based on a "radius" float value.
# 3. Selects the final address based on the camera type (highest for cab, second-to-last for passenger).

import pymem
import pymem.process
import pymem.memory
import time
import sys
import argparse
import os
import tempfile
import ctypes
from pymem.ptypes import RemotePointer

PROCESS_NAME = "RunActivity.exe"
RADIUS_OFFSET = 0x34 # Offset from AOB start to the "Radius" float value.

def convert_aob_string_to_pattern(aob_string):
    """
    Converts CE-style AOB to pattern + mask for fast byte comparison.
    Returns: (pattern_bytes, mask_bytes) where mask[i] = True means check that byte.
    """
    parts = aob_string.split()
    pattern = bytearray()
    mask = bytearray()
    
    for part in parts:
        if part == '??':
            pattern.append(0x00)  # Value doesn't matter
            mask.append(0x00)     # Don't check this byte
        else:
            try:
                pattern.append(int(part, 16))
                mask.append(0x01)  # Check this byte
            except ValueError:
                print(f"[AOB CONVERTER] WARNING: Invalid hex '{part}', treating as wildcard.", flush=True)
                pattern.append(0x00)
                mask.append(0x00)
    
    print(f"[AOB CONVERTER] Converted {len(parts)} parts into pattern", flush=True)
    return bytes(pattern), bytes(mask)

class CameraScanner:
    def __init__(self, camera_type, aob, radius_threshold):
        self.pm = None
        self.running = True
        self.camera_type = camera_type.upper()
        self.aob_pattern, self.aob_mask = convert_aob_string_to_pattern(aob)
        self.pattern_length = len(self.aob_pattern)
        print(f"[Scanner-{self.camera_type}] Pattern: {self.pattern_length} bytes", flush=True)
        self.radius_threshold = radius_threshold
        self.pid = 0
        self.my_pid = os.getpid()
    
    def find_pattern_in_buffer(self, buffer, base_address):
        """
        FAST pattern matcher with pre-filtering
        """
        matches = []
        buf_len = len(buffer)
        pat_len = self.pattern_length
        
        if buf_len < pat_len:
            return matches
        
        # OPTIMIZATION: Find signature bytes first (bytes 11-12: 0x40)
        # This is the "?? ?? 40" part of the pattern which is distinctive
        signature_offset = 11  # Position of 0x40 in pattern
        signature_byte = 0x40
        
        # Quick scan for signature first
        signature_positions = []
        for i in range(buf_len - pat_len + 1):
            if buffer[i + signature_offset] == signature_byte:
                signature_positions.append(i)
        
        # If no signature found, return early
        if not signature_positions:
            return matches

        # Now check full pattern only at signature positions
        for i in signature_positions:
            # Check if pattern matches at position i
            is_match = True
            for j in range(pat_len):
                # If not wildcard, check if bytes match
                if self.aob_mask[j] == 0x01 and buffer[i + j] != self.aob_pattern[j]:
                    is_match = False
                    break
            
            if is_match:
                matches.append(base_address + i)
        
        return matches

    def attach_to_game(self):
        """Attaches to the game process."""
        while self.running:
            try:
                self.pm = pymem.Pymem(PROCESS_NAME)
                self.pid = self.pm.process_id
                print(f"[Scanner-{self.camera_type}] Attached to {PROCESS_NAME} (PID: {self.pid})", flush=True)
                print(f"FOUND_PID: {self.camera_type}: {self.pid}", flush=True)
                return True
            except pymem.exception.ProcessNotFound:
                print(f"[Scanner-{self.camera_type}] {PROCESS_NAME} not found. Waiting...", flush=True)
                time.sleep(5)
        return False

    def smart_scan(self):
        """
        Fast memory scanner - skip huge regions to avoid slowdown.
        """
        print(f"[Scanner-{self.camera_type}] Starting Fast Memory Scan...", flush=True)
        start_time = time.time()
        candidates = []
        next_address = 0
        regions_scanned = 0
        regions_skipped = 0
        last_progress_time = start_time
        
        # Max region size to scan (150MB) - camera data is often in large regions
        MAX_REGION_SIZE = 150 * 1024 * 1024
        
        try:
            is_64bit = pymem.process.is_64_bit(self.pm.process_handle)
            max_address = 0x7FFFFFFFFFFF if is_64bit else 0xFFFFFFFF
            print(f"[Scanner-{self.camera_type}] Target process is {'64-bit' if is_64bit else '32-bit'}.", flush=True)
            
            while next_address < max_address:
                try:
                    mbi = pymem.memory.virtual_query(self.pm.process_handle, next_address)
                    next_address = mbi.BaseAddress + mbi.RegionSize
                    
                    # FAST SCAN: Only scan committed, PRIVATE, writable memory
                    # Skip shared/mapped memory (DLLs, system regions)
                    is_committed = mbi.State == 0x1000
                    is_private = mbi.Type == 0x20000  # MEM_PRIVATE only
                    is_writable = mbi.Protect in [0x04, 0x40]  # Only PAGE_READWRITE and PAGE_EXECUTE_READWRITE
                    is_reasonable_size = mbi.RegionSize <= MAX_REGION_SIZE
                    
                    if is_committed and is_private and is_writable and is_reasonable_size:
                        regions_scanned += 1
                        
                        # Progress update every 10 seconds
                        current_time = time.time()
                        if current_time - last_progress_time > 10.0:
                            elapsed = current_time - start_time
                            print(f"     [PROGRESS] Scanned {regions_scanned} regions ({regions_skipped} skipped) in {elapsed:.1f}s, found {len(candidates)} matches...", flush=True)
                            last_progress_time = current_time
                        
                        try:
                            buffer = self.pm.read_bytes(mbi.BaseAddress, mbi.RegionSize)
                            region_matches = self.find_pattern_in_buffer(buffer, mbi.BaseAddress)
                            
                            if region_matches:
                                for addr in region_matches:
                                    # IMMEDIATE RADIUS TEST (CRITICAL FIX)
                                    # Verify radius immediately so we can report FOUND_ADDRESS instantly
                                    try:
                                        radius = self.pm.read_float(addr + RADIUS_OFFSET)
                                        
                                        if abs(radius) < self.radius_threshold:
                                            # VALID CAMERA - ANNOUNCE IMMEDIATELY
                                            candidates.append(addr)
                                            print(f"     [OK] Match #{len(candidates)} at {hex(addr)} (Region: {hex(mbi.BaseAddress)}, Size: {mbi.RegionSize:,} bytes)", flush=True)
                                            print(f"     [VALID] Radius: {radius:.2f} - This is a valid camera!", flush=True)
                                            # ANNOUNCE IMMEDIATELY so GUI can start writer
                                            print(f"FOUND_ADDRESS: {self.camera_type}: {hex(addr)}", flush=True)
                                            # Continue scanning to find ALL cameras
                                        else:
                                            print(f"     [INVALID] Radius: {radius:.2f} at {hex(addr)} - Skipping (outside camera)", flush=True)
                                    except Exception as e:
                                        print(f"     [ERROR] Could not read radius at {hex(addr)}: {e}", flush=True)
                        
                        except Exception:
                            pass
                    elif is_committed and is_writable and not is_reasonable_size:
                        regions_skipped += 1
                        if regions_skipped % 10 == 0:
                            print(f"     [SKIP] Skipped huge region {hex(mbi.BaseAddress)} (Size: {mbi.RegionSize:,} bytes)", flush=True)
                
                except pymem.exception.WinAPIError as e:
                    if e.error_code == 87:
                        break
                    else:
                        if 'mbi' in locals() and mbi.BaseAddress:
                            next_address = mbi.BaseAddress + max(mbi.RegionSize, 4096)
                        else:
                            next_address += 4096
                
                except (TypeError, BufferError):
                    next_address += 4096
                    continue
        
        except Exception as e:
            print(f"[Scanner-{self.camera_type}] CRITICAL ERROR: {e}", flush=True)
            import traceback
            traceback.print_exc()
        
        end_time = time.time()
        print(f"[Scanner-{self.camera_type}] ========================================", flush=True)
        print(f"[Scanner-{self.camera_type}] Scan Complete:", flush=True)
        print(f"[Scanner-{self.camera_type}]   - Duration: {end_time - start_time:.2f} seconds", flush=True)
        print(f"[Scanner-{self.camera_type}]   - Writable Regions Scanned: {regions_scanned}", flush=True)
        print(f"[Scanner-{self.camera_type}]   - Huge Regions Skipped: {regions_skipped}", flush=True)
        print(f"[Scanner-{self.camera_type}]   - Total Candidates: {len(candidates)}", flush=True)
        print(f"[Scanner-{self.camera_type}] ========================================", flush=True)
        
        # ANNOUNCE ALL FOUND ADDRESSES (CRITICAL CHANGE)
        for addr in candidates:
            print(f"FOUND_ADDRESS: {self.camera_type}: {hex(addr)}", flush=True)
            
        return candidates

    def scan_for_address(self):
        """
        Performs the 2-step scan to find the correct camera address.
        Implements the exact logic from the CE Lua scripts.
        """
        print(f"[Scanner-{self.camera_type}] ====================================================", flush=True)
        print(f"[Scanner-{self.camera_type}]   STARTING 2-STEP CAMERA SCAN (CE LUA LOGIC)", flush=True)
        print(f"[Scanner-{self.camera_type}] ====================================================", flush=True)
        
        # STEP 1: Find all candidates using AOB pattern
        print(f"[Scanner-{self.camera_type}] STEP 1: Scanning for AOB pattern...", flush=True)
        candidates = self.smart_scan()
        
        if not candidates:
            print(f"[Scanner-{self.camera_type}] >> ERROR: No camera candidates found.", flush=True)
            print(f"[Scanner-{self.camera_type}] >> The AOB pattern may be outdated or game view is not active.", flush=True)
            return False
        
        # STEP 2: Matches were already filtered during scan (CRITICAL FIX)
        print(f"[Scanner-{self.camera_type}]", flush=True)
        print(f"[Scanner-{self.camera_type}] STEP 2: Scan complete, found {len(candidates)} valid cameras", flush=True)
        
        valid_cameras = candidates
        
        if not valid_cameras:
            print(f"[Scanner-{self.camera_type}] >> ERROR: No valid cameras found after filtering.", flush=True)
            print(f"[Scanner-{self.camera_type}] >> Are you in Outside View? Try switching to Cab/Interior view.", flush=True)
            return False
        
        # STEP 3: Select final address based on camera type
        print(f"[Scanner-{self.camera_type}]", flush=True)
        print(f"[Scanner-{self.camera_type}] STEP 3: Applying Selection Strategy...", flush=True)
        print(f"[Scanner-{self.camera_type}]    Valid Cameras Found: {len(valid_cameras)}", flush=True)
        
        target_address = 0
        
        if self.camera_type == 'CAB':
            # CAB CAMERA: Pick HIGHEST address (last valid result)
            # From CE script: "We DO NOT break the loop. We keep going."
            # "This ensures we pick the LAST valid result (Highest Memory Address)"
            target_address = max(valid_cameras)
            print(f"[Scanner-{self.camera_type}]    Strategy: 'HIGHEST ADDRESS' (Active Cab Camera)", flush=True)
            print(f"[Scanner-{self.camera_type}]    Logic: The highest address = the last/active cab", flush=True)
            print(f"[Scanner-{self.camera_type}]    Selected: {hex(target_address)}", flush=True)
        
        elif self.camera_type == 'INTERIOR':
            # INTERIOR/PASSENGER CAMERA: Pick SECOND-TO-LAST
            # From CE script: "Select the 'Second to Last' Camera"
            # Order: [1] Outside Front, [2] Outside Rear, [3] Passenger, [4] 3D Cab
            if len(valid_cameras) >= 2:
                sorted_cameras = sorted(valid_cameras)
                target_address = sorted_cameras[-2]  # Second-to-last
                print(f"[Scanner-{self.camera_type}]    Strategy: 'SECOND-TO-LAST' (Ignoring Cab at highest)", flush=True)
                print(f"[Scanner-{self.camera_type}]    Logic: [1] Outside Front, [2] Outside Rear, [3] Passenger <- TARGET, [4] Cab", flush=True)
                print(f"[Scanner-{self.camera_type}]    Selected: {hex(target_address)} (position {len(valid_cameras)-1} of {len(valid_cameras)})", flush=True)
            elif len(valid_cameras) == 1:
                target_address = valid_cameras[0]
                print(f"[Scanner-{self.camera_type}]    Strategy: 'ONLY ONE CAMERA' (Taking the only result)", flush=True)
                print(f"[Scanner-{self.camera_type}]    Selected: {hex(target_address)}", flush=True)
            else:
                print(f"[Scanner-{self.camera_type}] >> ERROR: Not enough valid cameras for Passenger View selection.", flush=True)
                return False
        
        elif self.camera_type == 'EXTERNAL':
            # EXTERNAL CAMERA: Using same logic as Interior for now
            # (Can be customized if needed - might need FIRST or different strategy)
            if len(valid_cameras) >= 2:
                sorted_cameras = sorted(valid_cameras)
                target_address = sorted_cameras[0]  # FIRST valid camera (Outside Front)
                print(f"[Scanner-{self.camera_type}]    Strategy: 'FIRST ADDRESS' (Outside Front View)", flush=True)
                print(f"[Scanner-{self.camera_type}]    Logic: First small-radius camera = External front", flush=True)
                print(f"[Scanner-{self.camera_type}]    Selected: {hex(target_address)}", flush=True)
            elif len(valid_cameras) == 1:
                target_address = valid_cameras[0]
                print(f"[Scanner-{self.camera_type}]    Strategy: 'ONLY ONE CAMERA' (Taking the only result)", flush=True)
                print(f"[Scanner-{self.camera_type}]    Selected: {hex(target_address)}", flush=True)
            else:
                print(f"[Scanner-{self.camera_type}] >> ERROR: Not enough valid cameras for External View.", flush=True)
                return False
        
        # SUCCESS - Announce the result
        if target_address:
            print(f"[Scanner-{self.camera_type}]", flush=True)
            print(f"[Scanner-{self.camera_type}] ====================================================", flush=True)
            print(f"[Scanner-{self.camera_type}]   SUCCESS: CAMERA FOUND", flush=True)
            print(f"[Scanner-{self.camera_type}] ====================================================", flush=True)
            print(f"[Scanner-{self.camera_type}] >> Camera Type: {self.camera_type}", flush=True)
            print(f"[Scanner-{self.camera_type}] >> Address: {hex(target_address)}", flush=True)
            print(f"[Scanner-{self.camera_type}]", flush=True)
            
            # Send to GUI (this is what the GUI listens for)
            # Re-announce the final best pick just in case
            print(f"FOUND_ADDRESS: {self.camera_type}: {hex(target_address)}", flush=True)
            return True
        else:
            print(f"[Scanner-{self.camera_type}] >> ERROR: Could not determine final address for {self.camera_type}.", flush=True)
            return False

    def run(self):
        """Main execution loop."""
        print("="*60, flush=True)
        print(f"[Scanner-{self.camera_type}] TrackIR LUA-Logic Scanner Starting...", flush=True)
        print(f"[Scanner-{self.camera_type}] PID: {self.my_pid}", flush=True)
        print("="*60, flush=True)
        
        if not self.attach_to_game():
            print(f"[Scanner-{self.camera_type}] Failed to attach. Exiting.", flush=True)
            return
        
        self.scan_for_address()
        
        print(f"[Scanner-{self.camera_type}] Entering monitoring loop...", flush=True)
        while self.running:
            try:
                rescan_flag = os.path.join(tempfile.gettempdir(), f"trackir_scanner_{self.camera_type.lower()}_rescan_{self.my_pid}.flag")
                if os.path.exists(rescan_flag):
                    print(f"[Scanner-{self.camera_type}] *** RESCAN TRIGGERED ***", flush=True)
                    try: os.remove(rescan_flag)
                    except: pass
                    self.scan_for_address()
                
                shutdown_flag = os.path.join(tempfile.gettempdir(), f"trackir_scanner_{self.camera_type.lower()}_shutdown_{self.my_pid}.flag")
                if os.path.exists(shutdown_flag):
                    print(f"[Scanner-{self.camera_type}] Shutdown signal received.", flush=True)
                    os.remove(shutdown_flag)
                    self.running = False
                    break
                
                try: pymem.process.is_64_bit(self.pm.process_handle)
                except pymem.exception.WinAPIError:
                    print(f"[Scanner-{self.camera_type}] Game process lost. Re-attaching...", flush=True)
                    if not self.attach_to_game():
                        self.running = False
                        break
                    else:
                        self.scan_for_address()
                time.sleep(1)
            except KeyboardInterrupt:
                self.running = False
                break
            except Exception as e:
                print(f"[Scanner-{self.camera_type}] UNHANDLED ERROR in monitoring loop: {e}", flush=True)
                time.sleep(1)
        
        print(f"[Scanner-{self.camera_type}] Shutdown complete.", flush=True)

if __name__ == "__main__":
    if not ctypes.windll.shell32.IsUserAnAdmin():
        print("Error: Administrator privileges required.")
        sys.exit(1)

    parser = argparse.ArgumentParser()
    parser.add_argument("--camera-type", type=str, required=True, choices=['cab', 'external', 'interior'])
    parser.add_argument("--radius", type=float, required=True)
    parser.add_argument("--aob", nargs='+', required=True)
    args = parser.parse_args()
    
    aob_string = ' '.join(args.aob)
    
    print(f"[Scanner-{args.camera_type.upper()}] Received AOB: {aob_string}", flush=True)
    print(f"[Scanner-{args.camera_type.upper()}] Received Radius: {args.radius}", flush=True)
    
    # DIAGNOSTIC: Show what pattern we're actually using
    pattern, mask = convert_aob_string_to_pattern(aob_string)
    print(f"[Scanner-{args.camera_type.upper()}] Pattern breakdown:", flush=True)
    print(f"  - Total bytes: {len(pattern)}", flush=True)
    print(f"  - Wildcards: {sum(1 for m in mask if m == 0x00)}", flush=True)
    print(f"  - Fixed bytes: {sum(1 for m in mask if m == 0x01)}", flush=True)

    scanner = CameraScanner(camera_type=args.camera_type, aob=aob_string, radius_threshold=args.radius)
    scanner.run()