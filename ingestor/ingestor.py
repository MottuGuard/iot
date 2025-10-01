import os, json, time
import psycopg2
import paho.mqtt.client as mqtt

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
PG_DSN    = os.environ.get("PG_DSN", "dbname=mottu user=postgres password=postgres host=localhost port=5432")

GEOF = (0.2, 0.2, 5.8, 3.3) 
last_seen = {}

def db():
    return psycopg2.connect(PG_DSN)

def insert_position(tag, x, y, ts):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("insert into positions(tag_id, x, y, created_at) values(%s,%s,%s, to_timestamp(%s))",
                        (tag, x, y, ts))

def insert_ranging(tag, ranges, ts):
    with db() as conn:
        with conn.cursor() as cur:
            for aid, dist in ranges.items():
                cur.execute("insert into ranging(tag_id, anchor_id, distance_m, created_at) values(%s,%s,%s, to_timestamp(%s))",
                            (tag, aid, dist, ts))

def insert_event(tag, etype, payload):
    with db() as conn:
        with conn.cursor() as cur:
            cur.execute("insert into events(tag_id, type, payload) values(%s,%s,%s::jsonb)", (tag, etype, json.dumps(payload)))

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
            # geofence
            x0,y0,x1,y1 = GEOF
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                ev = {"reason": "geofence_breach", "x": x, "y": y, "ts": ts}
                client.publish(f"mottu/event/{tag}", json.dumps(ev), qos=0)
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
        print("ingestor error:", e)

def offline_watcher(client):
    while True:
        now = time.time()
        for tag, seen in list(last_seen.items()):
            if (now - seen) > 8:
                ev = {"reason":"offline", "last_seen_sec": now-seen, "ts": now}
                client.publish(f"mottu/event/{tag}", json.dumps(ev), qos=0)
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