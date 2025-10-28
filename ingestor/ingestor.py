import os, json, time
import psycopg2
import paho.mqtt.client as mqtt
from dotenv import load_dotenv 

load_dotenv()

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
PG_DSN    = os.environ.get("PG_DSN")
print("Using PG_DSN:", PG_DSN)

GEOF = (0.2, 0.2, 5.8, 3.3) 
last_seen = {}

def db():
    return psycopg2.connect(PG_DSN)

def get_tag_id(tag_eui64):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "Id" FROM "UwbTags" WHERE "Eui64" = %s', (tag_eui64,))
            result = cur.fetchone()
            return result[0] if result else None

def get_moto_id(tag_id):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "MotoId" FROM "UwbTags" WHERE "Id" = %s', (tag_id,))
            result = cur.fetchone()
            return result[0] if result else None

def get_anchor_id(anchor_name):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT "Id" FROM "UwbAnchors" WHERE "Name" = %s', (anchor_name,))
            result = cur.fetchone()
            return result[0] if result else None

def insert_position(tag_eui64, x, y, ts):
    tag_id = get_tag_id(tag_eui64)
    if not tag_id:
        print(f"Tag {tag_eui64} not found in database")
        return

    moto_id = get_moto_id(tag_id)
    if not moto_id:
        print(f"Moto not found for tag {tag_eui64}")
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO "PositionRecords"("MotoId", "X", "Y", "Timestamp") VALUES(%s,%s,%s, to_timestamp(%s))',
                        (moto_id, x, y, ts))

def insert_ranging(tag_eui64, ranges, ts):
    tag_id = get_tag_id(tag_eui64)
    if not tag_id:
        print(f"Tag {tag_eui64} not found in database")
        return

    with db() as conn:
        with conn.cursor() as cur:
            for anchor_name, data in ranges.items():
                anchor_id = get_anchor_id(anchor_name)
                if not anchor_id:
                    print(f"Anchor {anchor_name} not found in database")
                    continue

                if isinstance(data, dict):
                    dist = data.get('distance', data.get('dist'))
                    rssi = data.get('rssi', 0)
                else:
                    dist = data
                    rssi = 0

                cur.execute('INSERT INTO "UwbMeasurements"("UwbTagId", "UwbAnchorId", "Distance", "Rssi", "Timestamp") VALUES(%s,%s,%s,%s, to_timestamp(%s))',
                            (tag_id, anchor_id, dist, rssi, ts))

def insert_event(tag_eui64, etype, payload):
    tag_id = get_tag_id(tag_eui64)
    if not tag_id:
        print(f"Tag {tag_eui64} not found in database")
        return

    with db() as conn:
        with conn.cursor() as cur:
            cur.execute('INSERT INTO "Events"("UwbTagId", "Type", "Payload", "CreatedAt") VALUES(%s,%s,%s::jsonb, NOW())',
                       (tag_id, etype, json.dumps(payload)))

def on_message(client, userdata, msg):
    global last_seen
    topic = msg.topic
    try:
        if topic.startswith("mottu/uwb/") and topic.endswith("/position"):
            tag = topic.split("/")[2]
            p = json.loads(msg.payload.decode("utf-8"))
            x, y, ts = float(p["x"]), float(p["y"]), float(p.get("ts", time.time()))
            insert_position(tag, x, y, ts)
            last_seen[tag] = time.time()
            x0,y0,x1,y1 = GEOF
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                ev = {"reason": "geofence_breach", "x": x, "y": y, "ts": ts}
                client.publish(f"mottu/event/{tag}", json.dumps(ev), qos=1)
                insert_event(tag, "geofence", ev)

        elif topic.startswith("mottu/uwb/") and topic.endswith("/ranging"):
            tag = topic.split("/")[2]
            p = json.loads(msg.payload.decode("utf-8"))
            ranges = p["ranges"]
            ts = float(p.get("ts", time.time()))
            insert_ranging(tag, ranges, ts)
            last_seen[tag] = time.time()

        elif topic.startswith("mottu/motion/"):
            tag = topic.split("/")[2]
            p = json.loads(msg.payload.decode("utf-8"))
            insert_event(tag, "motion", p)
            last_seen[tag] = time.time()

        elif topic.startswith("mottu/status/"):
            tag = topic.split("/")[2]
            p = json.loads(msg.payload.decode("utf-8"))
            insert_event(tag, "status", p)
            last_seen[tag] = time.time()

    except Exception as e:
        raise e

def offline_watcher(client):
    while True:
        now = time.time()
        for tag, seen in list(last_seen.items()):
            if (now - seen) > 8:
                ev = {"reason":"offline", "last_seen_sec": now-seen, "ts": now}
                client.publish(f"mottu/event/{tag}", json.dumps(ev), qos=1)
                insert_event(tag, "offline", ev)
                last_seen[tag] = now 
        time.sleep(2)

def main():
    client = mqtt.Client(client_id="ingestor")
    client.on_message = on_message
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    client.subscribe("mottu/uwb/+/position")
    client.subscribe("mottu/uwb/+/ranging")
    client.subscribe("mottu/motion/+")
    client.subscribe("mottu/status/+")

    import threading
    threading.Thread(target=offline_watcher, args=(client,), daemon=True).start()

    print("Ingestor rodando. CTRL+C para sair.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()