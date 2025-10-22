import time
import json
import threading
from datetime import datetime
from tkinter import Tk, Label, ttk, StringVar, END, Button, Frame, BOTH, RIGHT, LEFT, Y
from zk import ZK
from zk.exception import ZKNetworkError

# === Configuration ===
DEVICES = [
    {"name": "ZKTeco F18", "ip": "192.168.30.199", "port": 4370},
]
PROCESSED_FILE = "processed_logs.json"


# === Utility Functions ===
def connect_device(ip, port):
    zk = ZK(ip, port=port, timeout=10)
    return zk.connect()

def get_log_key(log):
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
        self.root.geometry("1100x550")
        self.root.resizable(False, False)

        self.running = False
        self.conn = None
        self.last_logs = load_processed_logs()
        self.status_var = StringVar(value="🔌 Not connected")

        # === Top Section: Device List ===
        top_frame = Frame(root)
        top_frame.pack(pady=5, padx=10, fill="x")

        Label(top_frame, text="Device List:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.tree_devices = ttk.Treeview(top_frame, columns=("IP", "Port", "Status"), show="headings", height=2)
        self.tree_devices.heading("IP", text="IP Address")
        self.tree_devices.heading("Port", text="Port")
        self.tree_devices.heading("Status", text="Status")
        self.tree_devices.column("IP", width=200)
        self.tree_devices.column("Port", width=100)
        self.tree_devices.column("Status", width=150)
        self.tree_devices.pack(fill="x", pady=5)

        for d in DEVICES:
            self.tree_devices.insert("", END, values=(d["ip"], d["port"], "Disconnected"))

        btn_frame = Frame(top_frame)
        btn_frame.pack(fill="x")
        Button(btn_frame, text="🔗 Connect", command=self.connect_selected_device, width=15, bg="#4CAF50", fg="white").pack(side=LEFT, padx=5)
        Button(btn_frame, text="❌ Disconnect", command=self.disconnect_device, width=15, bg="#f44336", fg="white").pack(side=LEFT, padx=5)

        Label(root, textvariable=self.status_var, font=("Segoe UI", 10, "bold")).pack(pady=5)

        # === Main Frame Split: Left (Logs) + Right (User list) ===
        main_frame = Frame(root)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # ---- Left: Punch Log ----
        left_frame = Frame(main_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)

        Label(left_frame, text="Punch Logs:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        style.map('Treeview', background=[('selected', '#cce5ff')])

        self.tree_logs = ttk.Treeview(left_frame, columns=("User ID", "Name", "Timestamp", "Status"), show='headings')
        self.tree_logs.heading("User ID", text="User ID")
        self.tree_logs.heading("Name", text="Name")
        self.tree_logs.heading("Timestamp", text="Timestamp")
        self.tree_logs.heading("Status", text="Status")

        for col in ("User ID", "Name", "Timestamp", "Status"):
            self.tree_logs.column(col, anchor="center", width=150)

        self.tree_logs.tag_configure('oddrow', background='#f9f9f9')
        self.tree_logs.tag_configure('evenrow', background='#ffffff')

        self.tree_logs.pack(fill=BOTH, expand=True)

        # ---- Right: User List ----
        right_frame = Frame(main_frame, width=300)
        right_frame.pack(side=RIGHT, fill=Y, padx=(10, 0))
        Label(right_frame, text="User List:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        self.tree_users = ttk.Treeview(right_frame, columns=("User ID", "Name"), show='headings', height=20)
        self.tree_users.heading("User ID", text="User ID")
        self.tree_users.heading("Name", text="Name")
        self.tree_users.column("User ID", width=100, anchor="center")
        self.tree_users.column("Name", width=160)
        self.tree_users.pack(fill=BOTH, expand=True)

        # === Auto Connect on Start ===
        self.root.after(1000, self.auto_connect)

    # === Auto Connect ===
    def auto_connect(self):
        first_device = DEVICES[0]
        threading.Thread(target=self.run_listener, args=(first_device["ip"], first_device["port"]), daemon=True).start()

    # === Manual Connect / Disconnect ===
    def connect_selected_device(self):
        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Please select a device.")
            return
        item = self.tree_devices.item(selected[0])
        ip, port = item['values'][0], int(item['values'][1])
        threading.Thread(target=self.run_listener, args=(ip, port), daemon=True).start()

    def disconnect_device(self):
        if not self.running:
            self.status_var.set("ℹ️ Not connected.")
            return
        self.running = False
        if self.conn:
            try:
                self.conn.disconnect()
            except:
                pass
            self.conn = None
        self.update_device_status("Disconnected", color="red")
        self.status_var.set("❌ Disconnected manually.")

    # === UI Helper ===
    def update_device_status(self, status, color="black"):
        for iid in self.tree_devices.get_children():
            ip = self.tree_devices.item(iid, "values")[0]
            if ip == getattr(self, "device_ip", None):
                values = list(self.tree_devices.item(iid, "values"))
                values[2] = status
                self.tree_devices.item(iid, values=values, tags=('status',))
                self.tree_devices.tag_configure('status', foreground=color)

    # === Real-Time Listener ===
    def run_listener(self, ip, port):
        self.device_ip = ip
        self.running = True

        while self.running:
            try:
                self.status_var.set(f"⚙️ Connecting to {ip}...")
                self.update_device_status("Connecting...", color="orange")
                self.conn = connect_device(ip, port)
                self.status_var.set(f"✅ Connected to {ip}")
                self.update_device_status("Connected", color="green")

                users = {u.user_id: u.name for u in self.conn.get_users()}
                self.refresh_user_list(users)

                while self.running:
                    logs = self.conn.get_attendance()
                    if logs:
                        new_entries = [log for log in logs if get_log_key(log) not in self.last_logs]
                        for i, log in enumerate(new_entries):
                            key = get_log_key(log)
                            self.last_logs.add(key)
                            user_name = users.get(log.user_id, "Unknown")
                            tag = 'evenrow' if len(self.tree_logs.get_children()) % 2 == 0 else 'oddrow'

                            self.tree_logs.insert("", END, values=(
                                log.user_id,
                                user_name,
                                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                                "IN" if log.status == 0 else "OUT"
                            ), tags=(tag,))

                            self.status_var.set(f"📢 {user_name} ({log.user_id}) punched at {log.timestamp}")
                            save_processed_logs(self.last_logs)

                    time.sleep(3)

            except ZKNetworkError as e:
                if not self.running:
                    break
                self.status_var.set(f"⚠️ Connection lost: {e}. Retrying...")
                self.update_device_status("Reconnecting...", color="orange")
                time.sleep(5)

            except Exception as e:
                if not self.running:
                    break
                self.status_var.set(f"❌ Error: {e}")
                self.update_device_status("Error", color="red")
                time.sleep(5)

            finally:
                if self.conn:
                    try:
                        self.conn.disconnect()
                    except:
                        pass
                    self.conn = None
                if not self.running:
                    self.update_device_status("Disconnected", color="red")
                    break

    def refresh_user_list(self, users):
        for i in self.tree_users.get_children():
            self.tree_users.delete(i)
        for uid, name in users.items():
            self.tree_users.insert("", END, values=(uid, name))

def main():
    root = Tk()
    app = ZKRealtimeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
