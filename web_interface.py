# web_interface.py
import asyncio, json, threading, requests, websockets
from PyQt5.QtCore import QObject, pyqtSignal

class OpenRailsWebInterface(QObject):
    connection_status_changed = pyqtSignal(bool, list); cab_controls_updated = pyqtSignal(list); update_received = pyqtSignal(str); command_sent = pyqtSignal(str, str, str)
    def __init__(self, parent=None):
        super().__init__(parent); self.port = "2150"; self._websocket = None; self._is_running = False
        self.thread = threading.Thread(target=self._run_async_loop, daemon=True)
    def set_port(self, port): self.port = port; self.force_reconnect()
    def start(self):
        if not self._is_running: self._is_running = True; self.thread.start()
    def stop(self):
        if self._is_running:
            self._is_running = False
            if self._websocket: asyncio.run_coroutine_threadsafe(self._websocket.close(), self.async_loop)
            self.thread.join(timeout=2)
    def _run_async_loop(self):
        self.async_loop = asyncio.new_event_loop(); asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_until_complete(self._connection_handler())
    async def _poll_cab_controls(self):
        while self._websocket and self._is_running:
            try:
                response = await asyncio.to_thread(requests.get, f"http://localhost:{self.port}/API/CABCONTROLS", timeout=2)
                response.raise_for_status(); self.cab_controls_updated.emit(response.json())
            except requests.exceptions.RequestException: pass
            await asyncio.sleep(2)
    async def _connection_handler(self):
        while self._is_running:
            uri = f"ws://localhost:{self.port}/switchpanel"
            try:
                async with websockets.connect(uri, subprotocols=["json"]) as websocket:
                    self._websocket = websocket; asyncio.create_task(self._poll_cab_controls()); await self._send_ws_message("init", "")
                    async for message in websocket:
                        data = json.loads(message)
                        if data.get('type') == 'init':
                            init_data = data.get('data', [])
                            active_ids = {cell['Definition']['UserCommand'][0] for row in init_data for cell in row if 'Definition' in cell and 'UserCommand' in cell['Definition']}
                            self.connection_status_changed.emit(True, list(active_ids))
                        self.update_received.emit(json.dumps(data))
            except Exception as e:
                if self._websocket is not None: self._websocket = None; self.cab_controls_updated.emit([]) 
                self.connection_status_changed.emit(False, [str(e)])
            if self._is_running: await asyncio.sleep(2)

    async def _send_ws_message(self, msg_type, data):
        if self._websocket: message = json.dumps({"type": msg_type, "data": data}); await self._websocket.send(message)
    
    def force_reconnect(self):
        if self._websocket: asyncio.run_coroutine_threadsafe(self._websocket.close(), self.async_loop)
        
    def send_button_event(self, command_id, event_type):
        self.command_sent.emit("WS", str(command_id), event_type)
        if self._websocket: asyncio.run_coroutine_threadsafe(self._send_ws_message(event_type, command_id), self.async_loop)
        
    async def _send_click_coro(self, command_id):
        await self._send_ws_message("buttonDown", command_id)
        await asyncio.sleep(0.05)
        await self._send_ws_message("buttonUp", command_id)

    def send_ws_click(self, command_id):
        self.command_sent.emit("WS", str(command_id), "CLICK")
        if self._websocket:
            asyncio.run_coroutine_threadsafe(self._send_click_coro(command_id), self.async_loop)
            
    def send_control_value(self, control_name, value):
        self.command_sent.emit("HTTP", control_name, f"{value:.4f}")
        payload = [{"TypeName": control_name, "Value": value}];
        try: requests.post(f"http://localhost:{self.port}/API/CABCONTROLS", json=payload, timeout=0.5)
        except requests.exceptions.RequestException: pass