import time
from datetime import datetime
from zk import ZK, const
from zk.exception import ZKNetworkError

DEVICE_IP = '192.168.30.199'
PORT = 4370

def connect_device():
    """Connects to ZKTeco device and returns connection object"""
    zk = ZK(DEVICE_IP, port=PORT, timeout=10)
    return zk.connect()

def get_log_key(log):
    """Creates a unique key for a punch (user + timestamp)"""
    return f"{log.user_id}_{log.timestamp}"

def main():
    print("🔄 Starting ZK F18 Realtime Monitor...")
    last_logs = set()
    conn = None

    while True:
        try:
            if not conn:
                print(f"⚙️ Connecting to device {DEVICE_IP} ...")
                conn = connect_device()
                print("✅ Connected successfully.")

            logs = conn.get_attendance()
            if logs:
                new_entries = [log for log in logs if get_log_key(log) not in last_logs]

                for log in new_entries:
                    key = get_log_key(log)
                    last_logs.add(key)
                    print(f"📢 New Punch Detected: User {log.user_id} at {log.timestamp}")
                    print("📢 Full log:", vars(log))

            time.sleep(3)  # check every 3 seconds

        except ZKNetworkError as e:
            print(f"⚠️ Connection error: {e}")
            print("🔁 Reconnecting in 5 seconds...")
            time.sleep(5)
            conn = None

        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            conn = None
            time.sleep(5)

        finally:
            if conn:
                try:
                    conn.disconnect()
                except:
                    pass
                conn = None

if __name__ == "__main__":
    main()
