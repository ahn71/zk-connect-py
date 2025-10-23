# zk_realtime_gui_v5.py
import time
import json
import threading
from datetime import datetime
from tkinter import Tk, Label, ttk, StringVar, END, Button, Frame, BOTH, RIGHT, LEFT, Y, Checkbutton, IntVar
from zk import ZK
from zk.exception import ZKNetworkError

# Config files
PROCESSED_FILE = "processed_logs.json"
DEVICES_FILE = "devices.json"

def load_devices():
    try:
        with open(DEVICES_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {DEVICES_FILE}: {e}")
        return []

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

class ZKRealtimeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZKTeco Multi-Device Monitor (v5)")
        self.root.geometry("1300x680")
        self.root.resizable(False, False)

        self.devices = load_devices()
        self.connections = {}
        self.device_threads = {}
        self.running_flags = {}
        self.last_logs = load_processed_logs()
        self.status_var = StringVar(value="🔌 Waiting...")
        self.sl_counter = 0

        # Auto-connect option
        self.auto_connect_var = IntVar(value=1)

        # Top frame: Device list + buttons
        top_frame = Frame(root)
        top_frame.pack(padx=10, pady=6, fill="x")

        Label(top_frame, text="Devices:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cols = ("Name", "IP", "Port", "Users", "Punches", "Status")
        self.tree_devices = ttk.Treeview(top_frame, columns=cols, show="headings", height=6, selectmode="extended")
        for c in cols:
            self.tree_devices.heading(c, text=c)
            width = 220 if c == "Name" else 140
            if c in ("Users","Punches","Port","Status"):
                width = 100
            self.tree_devices.column(c, width=width, anchor="center")
        self.tree_devices.pack(fill="x", pady=5)

        # Populate device rows
        for d in self.devices:
            name = d.get("name", d.get("ip"))
            ip = d.get("ip")
            port = d.get("port", 4370)
            self.tree_devices.insert("", END, values=(name, ip, port, "-", "-", "Disconnected"))

        # Buttons
        btn_frame = Frame(top_frame)
        btn_frame.pack(fill="x", pady=4)
        Button(btn_frame, text="Connect Selected", command=self.connect_selected, width=18, bg="#4CAF50", fg="white").pack(side=LEFT, padx=4)
        Button(btn_frame, text="Disconnect Selected", command=self.disconnect_selected, width=18, bg="#f44336", fg="white").pack(side=LEFT, padx=4)
        Button(btn_frame, text="Clear Logs", command=self.clear_logs, width=12).pack(side=LEFT, padx=12)
        Checkbutton(btn_frame, text="Auto-connect on startup", variable=self.auto_connect_var).pack(side=LEFT, padx=20)

        Label(top_frame, textvariable=self.status_var, font=("Segoe UI", 9, "bold")).pack(anchor="e")

        # Main split: left logs, right users
        main_frame = Frame(root)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=6)

        # Punch logs
        left_frame = Frame(main_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)
        Label(left_frame, text="Punch Logs:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        log_cols = ("SL", "User ID", "Name", "Timestamp", "Punch Type", "Device Name")
        self.tree_logs = ttk.Treeview(left_frame, columns=log_cols, show="headings")
        for c in log_cols:
            self.tree_logs.heading(c, text=c)
            self.tree_logs.column(c, anchor="center", width=140 if c!="Device Name" else 180)
        self.tree_logs.pack(fill=BOTH, expand=True)
        self.tree_logs.tag_configure('oddrow', background='#f8f8f8')
        self.tree_logs.tag_configure('evenrow', background='#ffffff')

        # User list
        right_frame = Frame(main_frame, width=320)
        right_frame.pack(side=RIGHT, fill=Y, padx=(10,0))
        Label(right_frame, text="User List (Selected Device):", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.tree_users = ttk.Treeview(right_frame, columns=("User ID","Name"), show="headings", height=25)
        self.tree_users.heading("User ID", text="User ID")
        self.tree_users.heading("Name", text="Name")
        self.tree_users.column("User ID", width=90, anchor="center")
        self.tree_users.column("Name", width=200)
        self.tree_users.pack(fill=Y, expand=True)

        # Auto-connect all devices at startup
        if self.auto_connect_var.get():
            self.root.after(800, self.auto_connect_all)

    # Update device row
    def set_device_row(self, ip, users="-", punches="-", status="Disconnected", color="black"):
        for iid in self.tree_devices.get_children():
            vals = list(self.tree_devices.item(iid, "values"))
            if vals[1] == ip:
                vals[3] = users
                vals[4] = punches
                vals[5] = status
                self.tree_devices.item(iid, values=vals, tags=('status',))
                self.tree_devices.tag_configure('status', foreground=color)
                break

    # Add punch log row
    def add_log_row(self, device_name, log, user_name):
        self.sl_counter += 1
        tag = 'evenrow' if self.sl_counter % 2 == 0 else 'oddrow'
        ts = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        self.tree_logs.insert("", END, values=(self.sl_counter, log.user_id, user_name, ts, "IN" if log.status==0 else "OUT", device_name), tags=(tag,))
        self.tree_logs.yview_moveto(1)

    def refresh_user_panel(self, users_dict):
        def do():
            for i in self.tree_users.get_children():
                self.tree_users.delete(i)
            for uid, name in users_dict.items():
                self.tree_users.insert("", END, values=(uid, name))
        self.root.after(0, do)

    # Connect/Disconnect selected devices
    def connect_selected(self):
        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Select device(s) to connect.")
            return
        for iid in selected:
            vals = self.tree_devices.item(iid, "values")
            ip = vals[1]
            port = int(vals[2])
            if ip in self.device_threads and self.device_threads[ip].is_alive():
                continue
            t = threading.Thread(target=self.run_listener, args=(vals[0], ip, port), daemon=True)
            self.device_threads[ip] = t
            t.start()

    def disconnect_selected(self):
        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Select device(s) to disconnect.")
            return
        for iid in selected:
            vals = self.tree_devices.item(iid, "values")
            ip = vals[1]
            self.running_flags[ip] = False
            if ip in self.connections:
                try:
                    self.connections[ip].disconnect()
                except:
                    pass
                del self.connections[ip]
            self.set_device_row(ip, status="Disconnected", color="red")
        self.status_var.set("🔌 Selected devices disconnected.")

    def clear_logs(self):
        for i in self.tree_logs.get_children():
            self.tree_logs.delete(i)
        self.sl_counter = 0
        self.status_var.set("🧹 Punch logs cleared (UI only).")

    def auto_connect_all(self):
        for d in self.devices:
            name = d.get("name", d.get("ip"))
            ip = d.get("ip")
            port = d.get("port", 4370)
            t = threading.Thread(target=self.run_listener, args=(name, ip, port), daemon=True)
            self.device_threads[ip] = t
            t.start()

    def run_listener(self, device_name, ip, port):
        self.running_flags[ip] = True
        while self.running_flags.get(ip, False):
            try:
                self.root.after(0, lambda: self.set_device_row(ip, status="Connecting...", color="orange"))
                self.root.after(0, lambda: self.status_var.set(f"⚙️ Connecting to {device_name} ({ip})..."))

                conn = connect_device(ip, port)
                self.connections[ip] = conn
                self.root.after(0, lambda: self.set_device_row(ip, status="Connected", color="green"))
                self.root.after(0, lambda: self.status_var.set(f"✅ Connected: {device_name} ({ip})"))

                users = {u.user_id: u.name for u in conn.get_users()}
                logs = conn.get_attendance()
                self.root.after(0, lambda users=users: self.refresh_user_panel(users))
                self.root.after(0, lambda: self.set_device_row(ip, users=len(users), punches=len(logs), status="Connected", color="green"))

                while self.running_flags.get(ip, False):
                    logs = conn.get_attendance()
                    if logs:
                        new_entries = [lg for lg in logs if get_log_key(lg) not in self.last_logs]
                        if new_entries:
                            try:
                                users = {u.user_id: u.name for u in conn.get_users()}
                                self.root.after(0, lambda users=users: self.refresh_user_panel(users))
                                self.root.after(0, lambda: self.set_device_row(ip, users=len(users), punches=len(logs), status="Connected", color="green"))
                            except:
                                pass
                            for log in new_entries:
                                key = get_log_key(log)
                                self.last_logs.add(key)
                                user_name = users.get(log.user_id, "Unknown")
                                self.root.after(0, lambda device_name=device_name, log=log, user_name=user_name: self.add_log_row(device_name, log, user_name))
                            save_processed_logs(self.last_logs)
                    time.sleep(3)

            except ZKNetworkError:
                self.root.after(0, lambda: self.set_device_row(ip, status="Disconnected", color="red"))
                self.root.after(0, lambda: self.status_var.set(f"⚠️ {device_name} ({ip}) connection error. Retrying..."))
                time.sleep(5)
            except Exception as e:
                self.root.after(0, lambda: self.set_device_row(ip, status="Error", color="red"))
                self.root.after(0, lambda: self.status_var.set(f"❌ {device_name} ({ip}) error: {e}"))
                time.sleep(5)
            finally:
                try:
                    if ip in self.connections:
                        self.connections[ip].disconnect()
                except:
                    pass
                if not self.running_flags.get(ip, False):
                    self.root.after(0, lambda: self.set_device_row(ip, status="Disconnected", color="red"))
                    break

def main():
    root = Tk()
    app = ZKRealtimeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
