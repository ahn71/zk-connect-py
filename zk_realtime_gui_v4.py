# zk_realtime_gui_v8_final.py
import time, json, threading
from datetime import datetime
from tkinter import Tk, Label, ttk, StringVar, END, Button, Frame, BOTH, RIGHT, LEFT, Y, Checkbutton, IntVar, Toplevel, Listbox, MULTIPLE, Entry,font
from tkcalendar import DateEntry
from zk import ZK
from zk.exception import ZKNetworkError

PROCESSED_FILE = "processed_logs.json"
DEVICES_FILE = "devices.json"
MAX_LOGS = 100  # max punches to show in real-time table

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
    return f"{log.user_id}_{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

def load_processed_logs():
    try:
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))
    except:
        return set()

def save_processed_logs(logs):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(logs), f)

def get_punch_type(log):
    punch_map = {0:"Finger",1:"Finger",2:"Card",3:"Face",4:"Password",5:"Palm",255:"Finger"}
    return punch_map.get(log.punch, f"Unknown({log.punch})")

class ZKRealtimeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CW-ZK-Connect (v4)")
        self.root.geometry("1400x750")
        self.root.resizable(False, False)

        self.devices = load_devices()
        self.connections = {}
        self.device_threads = {}
        self.running_flags = {}
        self.last_logs = load_processed_logs()
        self.status_var = StringVar(value="🔌 Waiting...")
        self.sl_counter = 0
        self.auto_connect_var = IntVar(value=1)
        self.uid_name_map = {}  # track all users

        # --- Top Frame: Devices ---
        top_frame = Frame(root)
        top_frame.pack(padx=10, pady=6, fill="x")
        Label(top_frame, text="Devices:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        cols = ("Name","IP","Port","Users","Punches","Status")
        self.tree_devices = ttk.Treeview(top_frame, columns=cols, show="headings", height=6, selectmode="extended")
        for c in cols:
            self.tree_devices.heading(c, text=c)
            width = 220 if c=="Name" else 140
            if c in ("Users","Punches","Port","Status"): width = 100
            self.tree_devices.column(c, width=width, anchor="center")
        self.tree_devices.pack(fill="x", pady=5)
        for d in self.devices:
            name, ip, port = d.get("name"), d.get("ip"), d.get("port",4370)
            self.tree_devices.insert("", END, values=(name, ip, port, "-", "-", "Disconnected"))

        btn_frame = Frame(top_frame)
        btn_frame.pack(fill="x", pady=4)
        Button(btn_frame, text="Connect Selected", command=self.connect_selected, width=18, bg="#4CAF50", fg="white").pack(side=LEFT, padx=4)
        Button(btn_frame, text="Disconnect Selected", command=self.disconnect_selected, width=18, bg="#f44336", fg="white").pack(side=LEFT, padx=4)
        Button(btn_frame, text="Clear Logs", command=self.clear_logs, width=12).pack(side=LEFT, padx=12)
        Button(btn_frame, text="Punch Logs", command=self.open_filtered_window, width=18, bg="#2196F3", fg="white").pack(side=LEFT, padx=8)
        Checkbutton(btn_frame, text="Auto-connect on startup", variable=self.auto_connect_var).pack(side=LEFT, padx=20)
        Label(top_frame, textvariable=self.status_var, font=("Segoe UI", 9, "bold")).pack(anchor="e")

        # --- Main Frame ---
        main_frame = Frame(root)
        main_frame.pack(fill=BOTH, expand=True, padx=10, pady=6)

        # --- Left: Real-time Punch Logs ---
        left_frame = Frame(main_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)
        Label(left_frame, text="Real-time Punch:", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        log_cols = ("SL","User ID","Name","Timestamp","Punch Type","Device Name")
        self.tree_logs = ttk.Treeview(left_frame, columns=log_cols, show="headings")
        for c in log_cols:
            self.tree_logs.heading(c, text=c)
            self.tree_logs.column(c, anchor="center", width=140 if c!="Device Name" else 180)
        self.tree_logs.pack(fill=BOTH, expand=True)
        self.tree_logs.tag_configure('oddrow', background='#f8f8f8')
        self.tree_logs.tag_configure('evenrow', background='#ffffff')

        # --- Right: User List ---
        right_frame = Frame(main_frame, width=320)
        right_frame.pack(side=RIGHT, fill=Y, padx=(10,0))
        Label(right_frame, text="User List (Selected Device):", font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.tree_users = ttk.Treeview(right_frame, columns=("User ID","Name"), show="headings", height=25)
        self.tree_users.heading("User ID", text="User ID")
        self.tree_users.heading("Name", text="Name")
        self.tree_users.column("User ID", width=90, anchor="center")
        self.tree_users.column("Name", width=200)
        self.tree_users.pack(fill=Y, expand=True)

        if self.auto_connect_var.get():
            self.root.after(800, self.auto_connect_all)

    # --- Device Table ---
    def set_device_row(self, ip, users="-", punches="-", status="Disconnected", color="black"):
        for iid in self.tree_devices.get_children():
            vals = list(self.tree_devices.item(iid, "values"))
            if vals[1]==ip:
                vals[3], vals[4], vals[5] = users, punches, status
                self.tree_devices.item(iid, values=vals, tags=('status',))
                self.tree_devices.tag_configure('status', foreground=color)
                break

    # --- Real-time Punch Log ---
    def add_log_row(self, device_name, log, user_name):
        self.sl_counter += 1
        tag = 'evenrow' if self.sl_counter % 2 == 0 else 'oddrow'
        ts = log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        p_type = get_punch_type(log)
        self.tree_logs.insert("", END, values=(self.sl_counter, log.user_id, user_name, ts, p_type, device_name), tags=(tag,))
        # Keep only latest MAX_LOGS entries
        all_items = self.tree_logs.get_children()
        if len(all_items) > MAX_LOGS:
            self.tree_logs.delete(all_items[0])
        self.tree_logs.yview_moveto(1)

    def refresh_user_panel(self, users_dict):
        self.uid_name_map.update(users_dict)
        def do():
            for i in self.tree_users.get_children(): self.tree_users.delete(i)
            for uid, name in users_dict.items():
                self.tree_users.insert("", END, values=(uid, name))
        self.root.after(0, do)

    # --- Connect / Disconnect ---
    def connect_selected(self):
        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Select device(s) to connect.")
            return
        for iid in selected:
            vals = self.tree_devices.item(iid, "values")
            ip = vals[1]
            port = int(vals[2])
            if ip in self.device_threads and self.device_threads[ip].is_alive(): continue
            t = threading.Thread(target=self.run_listener, args=(vals[0], ip, port), daemon=True)
            self.device_threads[ip] = t
            t.start()

    def disconnect_selected(self):
        selected = self.tree_devices.selection()
        if not selected:
            self.status_var.set("⚠️ Select device(s) to disconnect.")
            return
        for iid in selected:
            vals = self.tree_devices.item(iid,"values")
            ip = vals[1]
            self.running_flags[ip] = False
            if ip in self.connections:
                try: self.connections[ip].disconnect()
                except: pass
                del self.connections[ip]
            self.set_device_row(ip, status="Disconnected", color="red")
        self.status_var.set("🔌 Selected devices disconnected.")

    def clear_logs(self):
        for i in self.tree_logs.get_children(): self.tree_logs.delete(i)
        self.sl_counter = 0
        self.status_var.set("🧹 Punch logs cleared (UI only).")

    # --- Filtered / Searchable Punch Log Window ---
    def open_filtered_window(self):
        win = Toplevel(self.root)
        win.title("Punch Logs")
        win.geometry("900x600")

        # --- User Selection ---
        Label(win, text="Select Users:").pack(anchor="w", padx=10, pady=2)
        user_listbox = Listbox(win, selectmode=MULTIPLE, height=10)
        user_listbox.pack(fill="x", padx=10)

        all_users = []
        for conn_name, conn in self.connections.items():
            try:
                users = conn.get_users()  # Make sure this returns a list of user objects
                print(f"{conn_name} returned {len(users)} users")  # Debug
                for u in users:
                    all_users.append(f"{u.user_id} - {u.name}")
            except Exception as e:
                print(f"Error getting users from {conn_name}: {e}")

        # Insert into listbox
        for u in sorted(all_users):
            user_listbox.insert(END, u)

        # --- Date/Time Filters + Buttons ---
        date_frame = Frame(win)
        date_frame.pack(fill="x", padx=10, pady=4)

        # From Date/Time
        Label(date_frame, text="From Date:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        from_cal = DateEntry(date_frame, width=12)
        from_cal.grid(row=0, column=1, padx=5)
        Label(date_frame, text="From Time (HH:MM):").grid(row=0, column=2, padx=5)
        from_time = Entry(date_frame, width=8)
        from_time.insert(0, "00:00")
        from_time.grid(row=0, column=3, padx=5)

        # To Date/Time
        Label(date_frame, text="To Date:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        to_cal = DateEntry(date_frame, width=12)
        to_cal.grid(row=1, column=1, padx=5)
        Label(date_frame, text="To Time (HH:MM):").grid(row=1, column=2, padx=5)
        to_time = Entry(date_frame, width=8)
        to_time.insert(0, "23:59")
        to_time.grid(row=1, column=3, padx=5)

        # --- Treeview for Logs ---
        cols = ("SL","User ID","Name","Timestamp","Punch Type","Device Name")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c)
            tree.column(c, width=140 if c != "Device Name" else 180)
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Search Function ---
        def search():
            tree.delete(*tree.get_children())
            selected_users = [user_listbox.get(i).split(" - ")[0] for i in user_listbox.curselection()]
            from_dt = datetime.strptime(f"{from_cal.get_date()} {from_time.get()}:00", "%Y-%m-%d %H:%M:%S")
            to_dt = datetime.strptime(f"{to_cal.get_date()} {to_time.get()}:59", "%Y-%m-%d %H:%M:%S")
            sl = 0
            for log_key in self.last_logs:
                uid, ts_str = log_key.split("_")
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                if uid in selected_users and from_dt <= ts <= to_dt:
                    sl += 1
                    name = self.uid_name_map.get(uid, uid)
                    tree.insert("", END, values=(sl, uid, name, ts_str, "Unknown", "Unknown"))

        # --- Buttons in same row as To Date/Time ---
        bold_font = font.Font(weight="bold")
        Button(date_frame, text="Search", command=search, font=bold_font).grid(row=1, column=4, padx=10)
        Button(date_frame, text="Clear", command=lambda: tree.delete(*tree.get_children()), font=bold_font).grid(row=1, column=5, padx=10)

        
    # --- Auto-connect ---
    def auto_connect_all(self):
        for d in self.devices:
            name,ip,port=d.get("name"),d.get("ip"),d.get("port",4370)
            t = threading.Thread(target=self.run_listener,args=(name,ip,port),daemon=True)
            self.device_threads[ip] = t
            t.start()

    # --- Listener Thread ---
    def run_listener(self, device_name, ip, port):
        self.running_flags[ip] = True
        while self.running_flags.get(ip, False):
            try:
                self.root.after(0, lambda: self.set_device_row(ip,status="Connecting...",color="orange"))
                self.root.after(0, lambda: self.status_var.set(f"⚙️ Connecting to {device_name} ({ip})..."))
                conn = connect_device(ip, port)
                self.connections[ip] = conn
                self.root.after(0, lambda: self.set_device_row(ip,status="Connected",color="green"))
                self.root.after(0, lambda: self.status_var.set(f"✅ Connected: {device_name} ({ip})"))

                users = {u.user_id:u.name for u in conn.get_users()}
                self.root.after(0, lambda users=users: self.refresh_user_panel(users))

                while self.running_flags.get(ip, False):
                    logs = conn.get_attendance()
                    if logs:
                        new_entries = [lg for lg in logs if get_log_key(lg) not in self.last_logs]
                        if new_entries:
                            for log in new_entries:
                                key = get_log_key(log)
                                self.last_logs.add(key)
                                user_name = users.get(log.user_id, "Unknown")
                                self.root.after(0, lambda device_name=device_name, log=log, user_name=user_name: self.add_log_row(device_name, log, user_name))
                            save_processed_logs(self.last_logs)
                    self.root.after(0, lambda: self.set_device_row(ip, users=len(users), punches=len(logs), status="Connected", color="green"))
                    time.sleep(3)

            except ZKNetworkError:
                self.root.after(0, lambda: self.set_device_row(ip,status="Disconnected",color="red"))
                self.root.after(0, lambda: self.status_var.set(f"⚠️ Connection lost: {device_name} ({ip})"))
                time.sleep(5)
            except Exception as e:
                self.root.after(0, lambda: self.set_device_row(ip,status="Disconnected",color="red"))
                self.root.after(0, lambda: self.status_var.set(f"❌ Error {device_name} ({ip}): {e}"))
                time.sleep(5)
            finally:
                try: conn.disconnect()
                except: pass
                if ip in self.connections: del self.connections[ip]
                time.sleep(2)

def main():
    root = Tk()
    app = ZKRealtimeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
