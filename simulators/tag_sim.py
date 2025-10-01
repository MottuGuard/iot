import os, json, time, math, random, threading
import numpy as np
import paho.mqtt.client as mqtt

BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
BROKER_PORT = int(os.environ.get("MQTT_PORT", "1883"))
TAG_ID      = os.environ.get("TAG_ID", "tag01")
SCENARIO    = os.environ.get("SCENARIO", "normal")

ANCHORS = {
    "A1": (0.0, 0.0),
    "A2": (6.0, 0.0),
    "A3": (6.0, 3.5),
    "A4": (0.0, 3.5)
}

state = {
    "x": float(os.environ.get("X0", "1.0")),
    "y": float(os.environ.get("Y0", "1.0")),
    "vx": 0.0,
    "vy": 0.0,
    "find_mode": False,
    "locked": False,
    "online": True
}

RANDOM = random.Random(42 + hash(TAG_ID) % 1000)

def trilaterate_least_squares(ranges, anchors):
    keys = list(ranges.keys())
    if len(keys) < 3:
        return (state["x"], state["y"])

    x1, y1 = anchors[keys[0]]
    r1 = ranges[keys[0]]
    A = []
    b = []
    for k in keys[1:]:
        xi, yi = anchors[k]
        ri = ranges[k]
        A.append([2*(xi - x1), 2*(yi - y1)])
        b.append([ri**2 - r1**2 - xi**2 - yi**2 + x1**2 + y1**2])
    A = np.array(A, dtype=float)
    b = np.array(b, dtype=float)
    try:
        sol, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
        x = float(sol[0][0])
        y = float(sol[1][0])
        return (x, y)
    except Exception:
        return (state["x"], state["y"])

def on_message(client, userdata, msg):
    global state
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        cmd = payload.get("cmd")
        if cmd == "find_on":
            state["find_mode"] = True
        elif cmd == "find_off":
            state["find_mode"] = False
        elif cmd == "lock_on":
            state["locked"] = True
        elif cmd == "lock_off":
            state["locked"] = False
        st = {"find_mode": state["find_mode"], "locked": state["locked"]}
        client.publish(f"mottu/status/{TAG_ID}", json.dumps(st), qos=0, retain=True)
        print(f"[{TAG_ID}] CMD -> {cmd}")
    except Exception as e:
        print("on_message error:", e)

def main():
    global state
    client = mqtt.Client(client_id=f"sim-{TAG_ID}")
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT, 60)
    client.loop_start()
    client.subscribe(f"mottu/act/{TAG_ID}/cmd")

    t0 = time.time()
    last_motion = time.time()

    while True:
        if not state["online"]:
            time.sleep(0.5)
            continue

        dt = 0.1 # 10 Hz
        t = time.time() - t0
        if SCENARIO == "missing" and t > 10:
            state["online"] = False
            print(f"[{TAG_ID}] SIM: offline (missing)")
            continue
        if SCENARIO == "wrong_slot" and 10 < t < 25:
            goal = (4.8, 3.0)
        else:
            goal = (RANDOM.uniform(0.5, 5.5), RANDOM.uniform(0.5, 3.0))

        max_speed = 0.3 if state["locked"] else 1.0
        ax = (goal[0] - state["x"])
        ay = (goal[1] - state["y"])
        dist = math.hypot(ax, ay) + 1e-6
        ax, ay = (ax/dist)*0.5, (ay/dist)*0.5
        state["vx"] = (state["vx"] + ax*dt) * 0.95
        state["vy"] = (state["vy"] + ay*dt) * 0.95
        v = math.hypot(state["vx"], state["vy"])
        if v > max_speed:
            state["vx"] *= max_speed/v
            state["vy"] *= max_speed/v

        oldx, oldy = state["x"], state["y"]
        state["x"] = max(0.1, min(5.9, state["x"] + state["vx"]*dt))
        state["y"] = max(0.1, min(3.4, state["y"] + state["vy"]*dt))

        speed = math.hypot(state["vx"], state["vy"])
        if speed > 0.7 and (time.time()-last_motion)>2.5:
            client.publish(f"mottu/motion/{TAG_ID}", json.dumps({"speed": speed, "ts": time.time()}), qos=0)
            last_motion = time.time()

        ranges = {}
        for aid, (axp, ayp) in ANCHORS.items():
            d = math.hypot(state["x"]-axp, state["y"]-ayp)
            d_noisy = d + RANDOM.gauss(0, 0.05)
            ranges[aid] = round(max(0.0, d_noisy), 3)

        x_est, y_est = trilaterate_least_squares(ranges, ANCHORS)

        client.publish(f"mottu/uwb/{TAG_ID}/ranging", json.dumps({"ranges": ranges, "ts": time.time()}), qos=0)
        client.publish(f"mottu/uwb/{TAG_ID}/position", json.dumps({"x": x_est, "y": y_est, "ts": time.time()}), qos=0)


        client.publish(f"mottu/status/{TAG_ID}", json.dumps({"find_mode": state["find_mode"], "locked": state["locked"]}), qos=0, retain=True)

        time.sleep(dt)

if __name__ == "__main__":
    main()