from zk import ZK, const
import json

def connect_device(ip, port):
    zk = ZK(ip, port=port, timeout=5)
    try:
        conn = zk.connect()
        print(f"Connected to {ip}")
        conn.disable_device()  # Disable device temporarily
        return conn
    except Exception as e:
        print(f"Failed to connect to {ip}: {e}")
        return None

def fetch_users(conn):
    users = conn.get_users()
    print(f"Total users: {len(users)}")
    for user in users:
        print(user.user_id, user.name)
    return users

def fetch_attendance(conn):
    logs = conn.get_attendance()
    print(f"Total logs: {len(logs)}")
    for log in logs:
        print(log.user_id, log.timestamp, log.status)
    return logs

def transfer_users(source_conn, target_conn):
    users = fetch_users(source_conn)
    for user in users:
        try:
            target_conn.set_user(uid=user.user_id, name=user.name, password=user.password, privilege=user.privilege, group_id=user.group_id, user_id=user.user_id)
            print(f"Transferred user {user.user_id}")
        except Exception as e:
            print(f"Failed to transfer {user.user_id}: {e}")

def main():
    # Load devices
    with open("devices.json") as f:
        devices = json.load(f)

    # Connect to devices
    device_a = connect_device(devices["device_a"]["ip"], devices["device_a"]["port"])
    device_b = connect_device(devices["device_b"]["ip"], devices["device_b"]["port"])

    if device_a:
        fetch_users(device_a)
        fetch_attendance(device_a)

    if device_a and device_b:
        transfer_users(device_a, device_b)

    # Enable devices back
    if device_a:
        device_a.enable_device()
        device_a.disconnect()
    if device_b:
        device_b.enable_device()
        device_b.disconnect()

if __name__ == "__main__":
    main()
