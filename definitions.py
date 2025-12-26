# definitions.py
# Bell and Horn behavior changed to send numeric values (0.0/1.0) via HTTP POST.
# LIGHT (Cab Light) behavior reverted to 'hold' to match user's expected
# ON/OFF state behavior, similar to the Sander.
CONTROL_DEFINITIONS = {
    # -- VIRTUAL CONTROLS --
    "TOGGLE_COMBINED_THROTTLE": {"type": "button", "desc": "Toggle Combined Throttle Mode", "behavior": "virtual"},
    "TOGGLE_INVERT_COMBINED": {"type": "button", "desc": "Toggle Invert Combined Axis", "behavior": "virtual"},
    "COMBINED_THROTTLE": {"type": "slider", "range": [-100, 100], "desc": "Combined Throttle / Brake"},
    
    # -- TRACKIR VIRTUAL CONTROLS --
    "TOGGLE_TRACKIR": {"type": "button", "desc": "Toggle TrackIR Writer (All Cameras)", "behavior": "virtual"},
    "START_CAB_WRITER": {"type": "button", "desc": "Start Cab Camera Writer", "behavior": "virtual"},
    "STOP_CAB_WRITER": {"type": "button", "desc": "Stop Cab Camera Writer", "behavior": "virtual"},
    "START_EXTERNAL_WRITER": {"type": "button", "desc": "Start External Camera Writer", "behavior": "virtual"},
    "STOP_EXTERNAL_WRITER": {"type": "button", "desc": "Stop External Camera Writer", "behavior": "virtual"},
    "START_INTERIOR_WRITER": {"type": "button", "desc": "Start Interior Camera Writer", "behavior": "virtual"},
    "STOP_INTERIOR_WRITER": {"type": "button", "desc": "Stop Interior Camera Writer", "behavior": "virtual"},
    "SCAN_CAB_CAMERA": {"type": "button", "desc": "Scan Cab Camera", "behavior": "virtual"},
    "SCAN_EXTERNAL_CAMERA": {"type": "button", "desc": "Scan External Camera", "behavior": "virtual"},
    "SCAN_INTERIOR_CAMERA": {"type": "button", "desc": "Scan Interior Camera", "behavior": "virtual"},
    "RESCAN_CAB_CAMERA": {"type": "button", "desc": "Rescan Cab Camera", "behavior": "virtual"},
    "RESCAN_EXTERNAL_CAMERA": {"type": "button", "desc": "Rescan External Camera", "behavior": "virtual"},
    "RESCAN_INTERIOR_CAMERA": {"type": "button", "desc": "Rescan Interior Camera", "behavior": "virtual"},

    # -- SLIDERS (CONTINUOUS) --
    "THROTTLE":         {"type": "slider", "range": [0, 100], "desc": "Throttle"},
    "TRAIN_BRAKE":      {"type": "slider", "range": [0, 100], "desc": "Train Brake"},
    "INDEPENDENT_BRAKE":{"type": "slider", "range": [0, 100], "desc": "Independent Brake"},
    "DYNAMIC_BRAKE":    {"type": "slider", "range": [0, 100], "desc": "Dynamic Brake"},
    "ENGINE_BRAKE":     {"type": "slider", "range": [0, 100], "desc": "Engine Brake"},
    "CP_HANDLE":        {"type": "slider", "range": [0, 100], "desc": "CP Handle"},

    # -- SLIDERS (STEPPED) --
    "DIRECTION":        {"type": "slider", "id": [115, 114], "range": [-1, 1], "desc": "Reverser", "steps": {"-1": "Reverse", "0": "Neutral", "1": "Forward"}},
    "GEAR":             {"type": "slider", "id": [120, 119], "range": [0, 4],  "desc": "Gear", "steps": {"0":"N", "1":"1", "2":"2", "3":"3", "4":"4"}},
    "FRONT_HLIGHT":     {"type": "slider", "id": [177, 176], "range": [0, 3],  "desc": "Headlights", "steps": {"0":"Off", "1":"Dim", "2":"Medium", "3":"Bright"}},

    # -- CAB BUTTONS --
    "HORN":             {"type": "button", "id": 145, "desc": "Horn", "behavior": "hold", "send_as": "value"},
    "BELL":             {"type": "button", "id": 147, "desc": "Bell", "behavior": "hold", "send_as": "value"},
    "SANDER":           {"type": "button", "id": 146, "desc": "Sander", "behavior": "hold"},
    "EMERGENCY":        {"type": "button", "id": 144, "desc": "Emergency Brake"},
    "WIPER":            {"type": "button", "id": 148, "desc": "Wiper", "behavior": "toggle"},
    "ALERTER":          {"type": "button", "id": 143, "desc": "Alerter / Reset"},
    "DOOR_LEFT":        {"type": "button", "style": "door", "id": 152, "desc": "Left Door"},
    "DOOR_RIGHT":       {"type": "button", "style": "door", "id": 153, "desc": "Right Door"},
    "LIGHT":            {"type": "button", "id": 155, "desc": "Cab Light", "behavior": "toggle"},
    "LIGHTS":           {"type": "button", "id": 156, "desc": "Instrument Lights", "behavior": "toggle"},
    
    # -- ENGINE CONTROLS (ELECTRIC) --
    "BATTERY":          {"type": "button", "style": "engine_electric", "id": 162, "desc": "Battery Switch", "behavior": "toggle"},
    "MASTER_KEY":       {"type": "button", "style": "engine_electric", "id": 164, "desc": "Master Key", "behavior": "toggle"},
    "PANTOGRAPH":       {"type": "button", "style": "engine_electric", "id": 156, "desc": "Pantograph 1", "behavior": "toggle"},
    "PANTOGRAPH2":      {"type": "button", "style": "engine_electric", "id": 167, "desc": "Pantograph 2", "behavior": "toggle"},
    "CIRCUIT_BREAKER":  {"type": "button", "style": "engine_electric", "id": 168, "desc": "Circuit Breaker"},

    # -- ENGINE CONTROLS (DIESEL) --
    "ENGINE_START":     {"type": "button", "style": "engine_diesel", "id": 170, "desc": "Engine Start/Stop", "behavior": "toggle"},
    "ENGINE_STOP":      {"type": "button", "style": "engine_diesel", "id": 171, "desc": "Helper Engine Start/Stop", "behavior": "toggle"},
    "TRACTION_CUTOFF":  {"type": "button", "style": "engine_diesel", "id": 172, "desc": "Traction Cut-Off"},

    # -- ENGINE CONTROLS (STEAM) --
    "CYLINDER_COCKS":   {"type": "button", "style": "engine_steam", "id": 190, "desc": "Cylinder Cocks"},
    "STEAM_BLOWER":     {"type": "button", "style": "engine_steam", "id": 191, "desc": "Blower"},
    "STEAM_INJECTOR1":  {"type": "button", "style": "engine_steam", "id": 192, "desc": "Live Steam Injector"},
    "STEAM_INJECTOR2":  {"type": "button", "style": "engine_steam", "id": 193, "desc": "Exhaust Steam Injector"},

    # -- BRAKE SYSTEMS --
    "HANDBRAKE":        {"type": "button", "style": "brakes", "id": [184, 185], "desc": "Handbrake"},
    "BRAKE_HOSE":       {"type": "button", "style": "brakes", "id": [186, 187], "desc": "Brake Hose"},
    "RETAINERS":        {"type": "button", "style": "brakes", "id": [188, 189], "desc": "Retainers"},
    "BAIL_OFF":         {"type": "button", "id": 183, "desc": "Bail-Off Independent Brake", "style": "brakes"},

    # -- GAME & VIEW CONTROLS --
    "CHANGE_CAB":       {"type": "button", "style": "game", "id": 2, "desc": "Change Cab"},
    "MANUAL_SWITCH":    {"type": "button", "style": "game", "id": 6, "desc": "Manual Switch"},
    "AUTOPILOT":        {"type": "button", "style": "game", "id": 25, "desc": "Autopilot"},
    "HUD":              {"type": "button", "style": "game", "id": 30, "desc": "HUD"},
    "MAP":              {"type": "button", "style": "game", "id": 17, "desc": "Map"},
    "TRACK_MONITOR":    {"type": "button", "style": "game", "id": 29, "desc": "Track Monitor"},
    "TRAIN_DRIVING":    {"type": "button", "style": "game", "id": 31, "desc": "Train Driving"},
    "SWITCH_PANEL":     {"type": "button", "style": "game", "id": 35, "desc": "Switch Panel"},
    "TRAIN_OPERATIONS": {"type": "button", "style": "game", "id": 37, "desc": "Train Operations"},
    "TRAIN_DPU":        {"type": "button", "style": "game", "id": 38, "desc": "Train DPU"},
    "NEXT_STATION":     {"type": "button", "style": "game", "id": 39, "desc": "Next Station"},
    "TRAIN_LIST":       {"type": "button", "style": "game", "id": 42, "desc": "Train List"},
    "EOT_LIST":         {"type": "button", "style": "game", "id": 43, "desc": "EOT List"},
    "SWITCH_AHEAD":     {"type": "button", "style": "game", "id": 7, "desc": "Facing Switch Ahead"},
    "SWITCH_BEHIND":    {"type": "button", "style": "game", "id": 8, "desc": "Facing Switch Behind"},
    "CLEAR_SIGNAL":     {"type": "button", "style": "game", "id": 21, "desc": "Clear Signal Forward"},

    # -- CAMERAS --
    "CAB_CAMERA":       {"type": "button", "style": "camera", "id": 3, "desc": "Cab Camera"},
    "EXTERNAL_CAMERA":  {"type": "button", "style": "camera", "id": 4, "desc": "External Camera"},
    "PASSENGER_CAMERA": {"type": "button", "style": "camera", "id": 5, "desc": "Passenger Camera"},
    "HEADOUT_CAMERA":   {"type": "button", "style": "camera", "id": 10, "desc": "Head Out Camera"},
    "TRACKSIDE_CAMERA": {"type": "button", "style": "camera", "id": 11, "desc": "Trackside Camera"},
    "YARD_CAMERA":      {"type": "button", "style": "camera", "id": 12, "desc": "Yard Camera"},
    "CAR_CAMERA":       {"type": "button", "style": "camera", "id": 13, "desc": "Car Camera"},
    "FREE_CAMERA":      {"type": "button", "style": "camera", "id": 14, "desc": "Free Camera"},

    # -- SIMULATION --
    "PAUSE":            {"type": "button", "style": "game", "id": 1, "desc": "Pause Simulation", "behavior": "toggle"},
    "SAVE":             {"type": "button", "style": "game", "id": 22, "desc": "Save Game"},
    "QUIT":             {"type": "button", "style": "game", "id": 23, "desc": "Quit Game"},

    # -- DEBUG --
    "DEBUG_OVERLAY":    {"type": "button", "style": "debug", "id": 24, "desc": "Toggle Debug Overlay"},
    "DEBUG_WIREFRAME":  {"type": "button", "style": "debug", "id": 25, "desc": "Toggle Debug Wireframe"},
    "DEBUG_NORMALS":    {"type": "button", "style": "debug", "id": 26, "desc": "Toggle Debug Normals"},
    "DEBUG_TANGENTS":   {"type": "button", "style": "debug", "id": 27, "desc": "Toggle Debug Tangents"},
    "DEBUG_AABB":       {"type": "button", "style": "debug", "id": 28, "desc": "Toggle Debug AABB"},
}