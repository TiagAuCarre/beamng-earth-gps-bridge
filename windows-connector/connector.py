"""Offline Windows relay: localhost TCP (BeamNG Lua) -> Bluetooth Classic RFCOMM."""
from __future__ import annotations
import queue
import re
import socket
import threading
import time
import tkinter as tk
from collections import deque
from tkinter import messagebox, simpledialog, ttk

from protocol import validate_line

TCP_HOST, TCP_PORT = "127.0.0.1", 47720


class Connector:
    def __init__(self, ui):
        self.ui = ui
        self.stop = threading.Event()
        # Keep only the newest location. A slow/disconnected phone must not receive a burst of stale points.
        self.outgoing = queue.Queue(maxsize=1)
        self.outgoing_lock = threading.Lock()
        self.sock = None
        self.target_address = None
        self.connection_enabled = threading.Event()
        self.bt_thread = None
        self.bt_lock = threading.Lock()
        self.client = None
        self.received = 0
        self.errors = 0
        self.last_message = ""
        self.arrivals = deque(maxlen=20)
        self.test_mode = False
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((TCP_HOST, TCP_PORT))
        self.server.listen(1)
        self.server.settimeout(1)
        threading.Thread(target=self.accept_loop, daemon=True).start()

    def accept_loop(self):
        while not self.stop.is_set():
            try:
                conn, _ = self.server.accept()
                conn.settimeout(1)
                if self.client:
                    self.client.close()
                self.client = conn
                self.ui.event("Lua bridge connected on localhost")
                threading.Thread(target=self.tcp_read, args=(conn,), daemon=True).start()
            except socket.timeout:
                pass
            except OSError as exc:
                if not self.stop.is_set(): self.fail(str(exc))

    def tcp_read(self, conn):
        buf = bytearray()
        try:
            while not self.stop.is_set():
                try: chunk = conn.recv(1024)
                except socket.timeout: continue
                if not chunk: break
                buf.extend(chunk)
                if len(buf) > 4096 and b"\n" not in buf:
                    buf.clear(); self.fail("Lua message buffer exceeded 4096 bytes"); continue
                while b"\n" in buf:
                    line, _, rest = buf.partition(b"\n"); buf = bytearray(rest)
                    try:
                        obj = validate_line(bytes(line), now_ms=int(time.time() * 1000))
                        if obj["source"] == "test": self.fail("test coordinates are disabled unless sent by the dedicated test control")
                        with self.outgoing_lock:
                            try: self.outgoing.get_nowait()
                            except queue.Empty: pass
                            try: self.outgoing.put_nowait(bytes(line) + b"\n")
                            except queue.Full: pass
                        self.received += 1; self.last_message = f"seq {obj['seq']} {obj['latitude']:.6f}, {obj['longitude']:.6f}"
                        self.arrivals.append((time.monotonic(), obj["timestamp_utc_ms"]))
                        rate = (len(self.arrivals) - 1) / max(.001, self.arrivals[-1][0] - self.arrivals[0][0]) if len(self.arrivals) > 1 else 0
                        latency = int(time.time() * 1000) - obj["timestamp_utc_ms"]
                        self.ui.stats(self.received, self.errors, self.last_message, rate, latency)
                    except ValueError as exc: self.fail(f"rejected position: {exc}")
        finally:
            try: conn.close()
            except OSError: pass
            if self.client is conn: self.client = None
            self.ui.event("Lua bridge disconnected")

    def connect_phone(self, address):
        compact = re.sub(r"[:-]", "", address.strip())
        if not re.fullmatch(r"[0-9A-Fa-f]{12}", compact):
            raise ValueError("Adresse Bluetooth invalide. Format attendu : AA:BB:CC:DD:EE:FF")
        self.target_address = ":".join(compact[i:i+2] for i in range(0, 12, 2)).upper()
        self.connection_enabled.set()
        with self.bt_lock:
            if self.bt_thread is None or not self.bt_thread.is_alive():
                self.bt_thread = threading.Thread(target=self.bluetooth_client_loop, daemon=True)
                self.bt_thread.start()
        self.ui.event(f"Connexion automatique au téléphone {self.target_address}; démarrez la réception SPP dans l’application Android")

    def bluetooth_client_loop(self):
        from bluetooth_win import connect
        while not self.stop.is_set() and self.connection_enabled.is_set():
            address = self.target_address
            candidate = None
            try:
                candidate = connect(address)
                if not self.connection_enabled.is_set() or address != self.target_address:
                    candidate.close(); continue
                # Discard old locations queued while the phone was not connected.
                while True:
                    try: self.outgoing.get_nowait()
                    except queue.Empty: break
                self.sock = candidate
                self.ui.event("Téléphone Android connecté en RFCOMM")
                while not self.stop.is_set() and self.connection_enabled.is_set() and self.sock is candidate:
                    try: packet = self.outgoing.get(timeout=.5)
                    except queue.Empty: continue
                    try:
                        validate_line(packet, now_ms=int(time.time() * 1000), max_age_ms=2000)
                    except ValueError:
                        continue
                    candidate.sendall(packet)
            except Exception as exc:
                if not self.stop.is_set() and self.connection_enabled.is_set():
                    self.ui.event(f"Connexion RFCOMM au téléphone impossible : {exc}; nouvel essai dans 2 s")
            finally:
                if self.sock is candidate: self.sock = None
                if candidate:
                    try: candidate.close()
                    except OSError: pass
            if self.connection_enabled.is_set() and not self.stop.wait(2):
                continue

    def disconnect_phone(self):
        self.connection_enabled.clear()
        if self.sock:
            try: self.sock.shutdown(socket.SHUT_RDWR)
            except OSError: pass
            try: self.sock.close()
            except OSError: pass
            self.sock = None
        self.ui.event("Session RFCOMM fermée")

    def fail(self, text):
        self.errors += 1; self.ui.event(text)
        self.ui.stats(self.received, self.errors, self.last_message, 0, None)

    def close(self):
        self.stop.set()
        try: self.server.close()
        except OSError: pass
        self.connection_enabled.clear()
        if self.client:
            try: self.client.close()
            except OSError: pass
        if self.sock:
            try: self.sock.close()
            except OSError: pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("BeamNG.earth GPS Bridge")
        self.geometry("700x560")
        self.configure(bg="#171a21")
        style = ttk.Style(self); style.theme_use("clam")
        style.configure("TFrame", background="#171a21"); style.configure("TLabel", background="#171a21", foreground="#e8edf4")
        style.configure("TButton", padding=8)
        ttk.Label(self, text="BeamNG.earth GPS Bridge", font=("Segoe UI", 17, "bold")).pack(pady=(14, 4))
        ttk.Label(self, text=f"Local relay: {TCP_HOST}:{TCP_PORT}  •  RFCOMM / SPP").pack()
        device_row = ttk.Frame(self); device_row.pack(fill="x", padx=16, pady=(12, 2))
        ttk.Label(device_row, text="Téléphone Android appairé (adresse Bluetooth) :").pack(side="left")
        self.address_var = tk.StringVar()
        ttk.Entry(device_row, textvariable=self.address_var, width=20).pack(side="left", padx=8)
        ttk.Button(device_row, text="Actualiser la liste", command=self.refresh_devices).pack(side="left")
        self.device_picker = ttk.Combobox(self, state="readonly", width=58)
        self.device_picker.pack(anchor="w", padx=16)
        self.device_picker.bind("<<ComboboxSelected>>", self.select_device)
        row = ttk.Frame(self); row.pack(fill="x", padx=16, pady=12)
        ttk.Button(row, text="Connecter / réessayer", command=self.start_phone_connection).pack(side="left")
        ttk.Button(row, text="Envoyer position fictive…", command=self.send_test).pack(side="left")
        ttk.Button(row, text="Déconnecter", command=lambda: self.connector.disconnect_phone()).pack(side="left", padx=8)
        ttk.Label(self, text="Démarre d’abord la réception Bluetooth dans l’application Android. Windows tentera la connexion puis réessaiera automatiquement.", wraplength=650).pack(anchor="w", padx=18)
        self.stats_label = ttk.Label(self, text="Messages reçus : 0  |  Erreurs : 0\nFréquence : —  |  Latence approximative : —\nDernier : —", justify="left"); self.stats_label.pack(anchor="w", padx=18, pady=6)
        ttk.Label(self, text="Événements").pack(anchor="w", padx=18)
        self.log = tk.Text(self, height=15, bg="#0e1117", fg="#cbd5e1", insertbackground="white", state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        self.addresses = []
        self.connector = Connector(self)
        self.refresh_devices()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.event("Connecteur prêt; le PC se connectera au téléphone appairé. Aucun Wi-Fi n’est touché.")

    def refresh_devices(self):
        try:
            from bluetooth_win import paired_devices
            self.paired_devices = paired_devices()
            self.device_picker["values"] = [f"{name} ({address})" for address, name in self.paired_devices]
            self.event(f"{len(self.paired_devices)} appareil(s) Bluetooth trouvés dans les appareils Windows")
        except Exception as exc:
            self.event(f"Lecture des appareils appairés impossible : {exc}")

    def select_device(self, _event=None):
        match = re.search(r"\(([0-9A-Fa-f:]{17})\)$", self.device_picker.get())
        if match: self.address_var.set(match.group(1))

    def start_phone_connection(self):
        try: self.connector.connect_phone(self.address_var.get())
        except ValueError as exc: messagebox.showerror("Adresse Bluetooth", str(exc), parent=self)

    def send_test(self):
        """Only sends user-entered coordinates and marks them unmistakably as test data."""
        try:
            lat = float(simpledialog.askstring("Position de test", "Latitude fictive (-90 à 90) :", parent=self))
            lon = float(simpledialog.askstring("Position de test", "Longitude fictive (-180 à 180) :", parent=self))
            if not (-90 <= lat <= 90 and -180 <= lon <= 180): raise ValueError("coordonnées hors limites")
            import json
            packet = {"version": 1, "type": "position", "source": "test", "stream_id": "windows-manual-test",
                      "seq": int(time.time() * 1000), "timestamp_utc_ms": int(time.time() * 1000),
                      "latitude": lat, "longitude": lon, "altitude_m": None, "speed_mps": 0.0,
                      "heading_deg": None, "test": True}
            payload = json.dumps(packet, separators=(",", ":")).encode() + b"\n"
            validate_line(payload, now_ms=int(time.time() * 1000))
            if not self.connector.sock: raise RuntimeError("Bluetooth RFCOMM non connecté")
            self.connector.sock.sendall(payload)
            self.event("Position FICTIVE envoyée sur RFCOMM; elle n'est pas issue du jeu")
        except (TypeError, ValueError, RuntimeError, OSError) as exc:
            if exc: messagebox.showerror("Test non envoyé", str(exc), parent=self)

    def event(self, text):
        self.after(0, self._event, text)

    def _event(self, text):
        self.log.configure(state="normal"); self.log.insert("end", time.strftime("%H:%M:%S ") + text + "\n"); self.log.see("end"); self.log.configure(state="disabled")

    def stats(self, count, errors, last, rate=0, latency=None):
        latency_text = f"{latency} ms (Lua → PC local)" if latency is not None else "—"
        self.after(0, self.stats_label.configure, {"text": f"Messages reçus : {count}  |  Erreurs : {errors}\nFréquence : {rate:.1f} Hz  |  Latence approximative : {latency_text}\nDernier : {last or '—'}"})

    def on_close(self):
        self.connector.close(); self.destroy()


if __name__ == "__main__":
    App().mainloop()
