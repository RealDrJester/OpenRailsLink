# definitions.py
# Bell and Horn behavior changed to send numeric values (0.0/1.0) via HTTP POST.
# LIGHT (Cab Light) behavior reverted to 'hold' to match user's expected
# ON/OFF state behavior, similar to the Sander.
CONTROL_DEFINITIONS = {
    # -- VIRTUAL CONTROLS --
    "COMBINED_THROTTLE": {"type": "slider", "range": [-100, 100], "desc": "Combined Throttle / Brake"},

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
    "BATTERY":          {"type": "button", "style": "engine_electric", "id": 162, "desc": "Battery Switch"},
    "MASTER_KEY":       {"type": "button", "style": "engine_electric", "id": 164, "desc": "Master Key"},
    "PANTOGRAPH":       {"type": "button", "style": "engine_electric", "id": 166, "desc": "Pantograph 1"},
    "PANTOGRAPH2":      {"type": "button", "style": "engine_electric", "id": 167, "desc": "Pantograph 2"},
    "CIRCUIT_BREAKER":  {"type": "button", "style": "engine_electric", "id": 168, "desc": "Circuit Breaker"},

    # -- ENGINE CONTROLS (DIESEL) --
    "DIESEL_PLAYER":    {"type": "button", "style": "engine_diesel", "id": 170, "desc": "Diesel (Player)"},
    "DIESEL_HELPER":    {"type": "button", "style": "engine_diesel", "id": 171, "desc": "Diesel (Helper)"},
    "TRACTION_CUTOFF":  {"type": "button", "style": "engine_diesel", "id": 172, "desc": "Traction Cut-Off"},

    # -- STEAM CONTROLS --
    "CYLINDER_COCKS":   {"type": "button", "style": "engine_steam", "id": 190, "desc": "Cylinder Cocks"},

    # -- BRAKE SYSTEMS --
    "HANDBRAKE":        {"type": "button", "style": "brakes", "id": [184, 185], "desc": "Handbrake"},
    "BRAKE_HOSE":       {"type": "button", "style": "brakes", "id": [186, 187], "desc": "Brake Hose"},
    "RETAINERS":        {"type": "button", "style": "brakes", "id": [188, 189], "desc": "Retainers"},

    # -- GAME & VIEW CONTROLS --
    "CHANGE_CAB":       {"type": "button", "style": "game", "id": 2, "desc": "Change Cab"},
    "MANUAL_SWITCH":    {"type": "button", "style": "game", "id": 6, "desc": "Manual Switch"},
    "AUTOPILOT":        {"type": "button", "style": "game", "id": 15, "desc": "Autopilot"},
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
}