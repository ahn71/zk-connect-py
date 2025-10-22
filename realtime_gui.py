import time
import json
import threading
from datetime import datetime
from tkinter import Tk, Label, ttk, StringVar, END, Button, Frame
from zk import ZK, const
from zk.exception import ZKNetworkError

# === Configuration ===
DEVICES = [
    {"name": "ZKTeco F18", "ip": "192.168.30.199", "port": 4370},
    # You can add more devices here if needed
]
PROCESSED_FILE = "processed_logs.json"


# === Utility Functions ===
def connect_device(ip, port):
    """Connects to ZKTeco device and returns connection object"""
    zk = ZK(ip, port=port, timeout=10)
    return zk.connect()

def get_log_key(log):
    """Creates a unique key for a punch (user + timestamp)"""
    return f"{log.user_id}_{log.timestamp}"

def load_processed_logs():
    try:
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_processed_logs(logs):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(logs), f)


# === GUI App ===
class ZKRealtimeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZKTeco Real-Time Attendance Monitor")
        self.root.geometry("900x500")
        self.root.resizable(False, False)

        self.running = False
        self.conn = None
        self.last_logs = load_processed_logs()
        self.status_var = StringVar(value="🔌 Not connected")

        # === Top Section: Device List ===
        device_frame = Frame(root)
        device_frame.pack(pady=8, padx=10, fill="x")

        Label(device_frame, text="Available Devices:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.tree_devices = ttk.Treeview(device_frame, columns=("IP", "Port", "Status"), show="headings", height=3)
        self.tree_devices.heading("IP", text="IP Address")
        self.tree_devices.heading("Port", text="Port")
        self.tree_devices.heading("Status", text="Status")
        self.tree_devices.column("IP", width=200)
        self.tree_devices.column("Port", width=100)
        self.tree_devices.column("Status", width=150)
        self.tree_devices.pack(fill="x", pady=5)

        for d in DEVICES:
            self.tree_devices.insert("", END, values=(d["ip"], d["port"], "Disconnected"))

        btn_frame = Frame(device_frame)
        btn_frame.pack(fill="x")
        Button(btn_frame, text="🔗 Connect", command=self.connect_selected_device, width=15, bg="#4CAF50", fg="white").pack(side="left", padx=5)
        Button(btn_frame, text="❌ Disconnect", command=self.disconnect_device, width=15, bg="#f44336", fg="white").pack(side="left", padx=5)

        Label(root, textvariable=self.status_var, font=("Segoe UI", 10, "bold"), fg="blue").pack(pady=5)

        # === Attendance Log Table ===
        self.tree = ttk.Treeview(root, columns=("User ID", "Name", "Timestamp", "Status"), show='headings')
        self.tree.heading("User ID", text="User ID")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Timestamp", text="Timestamp")
        self.tree.heading("Status", text="Status")
        self.tree.column("User ID", width=100)
        self.tree.column("Name", width=200)
        self.tree.column("Timestamp", width=200)
        self.tree.column("Status", width=100)
        self.tree.pack(expand=True, fill="both", padx=10, pady=10)

    # === Device Connection Handlers ===
    def connect_selected_device(self):
        if self.running:
            self.status_var.set("⚠️ Already connected to a device.")
            return

        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Please select a device to connect.")
            return

        item = self.tree_devices.item(selected[0])
        ip, port = item['values'][0], item['values'][1]

        threading.Thread(target=self.run_listener, args=(ip, int(port)), daemon=True).start()

    def disconnect_device(self):
        if not self.running:
            self.status_var.set("ℹ️ No active connection.")
            return
        self.running = False
        if self.conn:
            try:
                self.conn.disconnect()
            except:
                pass
            self.conn = None
        self.status_var.set("❌ Disconnected manually.")
        self.update_device_status("Disconnected")

    def update_device_status(self, status):
        for iid in self.tree_devices.get_children():
            ip = self.tree_devices.item(iid, "values")[0]
            if ip == getattr(self, "device_ip", None):
                values = list(self.tree_devices.item(iid, "values"))
                values[2] = status
                self.tree_devices.item(iid, values=values)

    # === Real-Time Punch Listener ===
    def run_listener(self, ip, port):
        self.device_ip = ip
        self.running = True

        while self.running:
            try:
                self.status_var.set(f"⚙️ Connecting to device {ip} ...")
                self.update_device_status("Connecting...")
                self.conn = connect_device(ip, port)
                self.status_var.set(f"✅ Connected to {ip}")
                self.update_device_status("Connected")

                users = {u.user_id: u.name for u in self.conn.get_users()}

                while self.running:
                    logs = self.conn.get_attendance()
                    if logs:
                        new_entries = [log for log in logs if get_log_key(log) not in self.last_logs]

                        for log in new_entries:
                            key = get_log_key(log)
                            self.last_logs.add(key)
                            user_name = users.get(log.user_id, "Unknown")

                            self.tree.insert("", END, values=(
                                log.user_id,
                                user_name,
                                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                "IN" if log.status == 0 else "OUT"
                            ))

                            self.status_var.set(f"📢 New Punch: {user_name} ({log.user_id}) at {log.timestamp}")
                            save_processed_logs(self.last_logs)

                    time.sleep(3)

            except ZKNetworkError as e:
                if not self.running:
                    break
                self.status_var.set(f"⚠️ Connection lost: {e}. Retrying...")
                self.update_device_status("Reconnecting...")
                time.sleep(5)

            except Exception as e:
                if not self.running:
                    break
                self.status_var.set(f"❌ Error: {e}")
                self.update_device_status("Error")
                time.sleep(5)

            finally:
                if self.conn:
                    try:
                        self.conn.disconnect()
                    except:
                        pass
                    self.conn = None
                if not self.running:
                    self.update_device_status("Disconnected")
                    break

def main():
    root = Tk()
    app = ZKRealtimeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
