import json
import os
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_URL = os.getenv("SENSOR_API_URL", "http://127.0.0.1:8000/sensors/ingest")
FARM_ID = os.getenv("FARM_ID", "demo-farm-001").strip()
FARM_NAME = os.getenv("FARM_NAME", "Demo Test Farm").strip()
SENSOR_KEY = (
    os.getenv("FARM_SENSOR_API_KEY")
    or os.getenv("SENSOR_INGEST_API_KEY")
    or ""
).strip()


def send_reading(payload):
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if SENSOR_KEY:
        headers["x-sensor-key"] = SENSOR_KEY

    request = Request(API_URL, data=body, headers=headers, method="POST")

    try:
        with urlopen(request, timeout=15) as response:
            data = response.read().decode("utf-8")
            print(f"\nHTTP {response.status}")
            print(json.dumps(json.loads(data), indent=2))
            return True
    except HTTPError as error:
        print(f"\nHTTP {error.code}")
        print(error.read().decode("utf-8"))
    except URLError as error:
        print(f"\nConnection failed: {error.reason}")
    except TimeoutError:
        print("\nConnection timed out")
    return False


def base_payload(value):
    return {
        "serial_number": "GH-DEMO-TEMP-001",
        "farmID": FARM_ID,
        "farm_name": FARM_NAME,
        "sensortype": "temperature",
        "model_number": "SHT31-GW01",
        "location": "Greenhouse A",
        "value": value,
        "unit": "C",
        "range_min": 18,
        "range_max": 28,
        "warning_min": 15,
        "warning_max": 32,
        "alerts_enabled": True,
        "maintenance_frequency": "Monthly",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "last_maintenance_date": datetime.now(timezone.utc).date().isoformat(),
    }


def main():
    print(f"Testing sensor ingest endpoint: {API_URL}")
    print(f"Farm ID: {FARM_ID}")
    print("Using farm x-sensor-key header:", "yes" if SENSOR_KEY else "no")

    tests = [
        ("normal reading should become Active", 24.6),
        ("outside normal range should become Maintenance", 30.2),
        ("outside warning range should become Faulty", 35.8),
    ]

    for label, value in tests:
        print(f"\nSending {label}: {value}")
        if not send_reading(base_payload(value)):
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
