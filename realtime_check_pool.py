import time
from zk import ZK, const
from zk.exception import ZKNetworkError

device_ip = '192.168.30.199'

zk = ZK(device_ip, port=4370, timeout=5)
conn = None

try:
    print(f"Connecting to device {device_ip} ...")
    conn = zk.connect()
    print("Connected successfully.")

    last_count = 0
    while True:
        try:
            logs = conn.get_attendance()
            if len(logs) > last_count:
                new_logs = logs[last_count:]
                for log in new_logs:
                    print(f"New punch by {log.user_id} at {log.timestamp}")
                last_count = len(logs)
        except ZKNetworkError as e:
            print("⚠️ Connection lost:", e)
            break

        time.sleep(5)

except Exception as e:
    print("Error:", e)
finally:
    if conn:
        try:
            conn.disconnect()
            print("Disconnected from device.")
        except:
            print("Device connection already closed.")
