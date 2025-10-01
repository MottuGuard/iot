#!/usr/bin/env bash
set -euo pipefail

py -m pip install -r simulators/requirements.txt

TAG01_ENV="TAG_ID=tag01 SCENARIO=normal"
TAG02_ENV="TAG_ID=tag02 SCENARIO=wrong_slot"
TAG03_ENV="TAG_ID=tag03 SCENARIO=missing"

export MQTT_HOST=${MQTT_HOST:-localhost}
export MQTT_PORT=${MQTT_PORT:-1883}

if command -v tmux >/dev/null 2>&1; then
  tmux new-session -d -s mottu "env $TAG01_ENV py simulators/tag_sim.py"
  tmux split-window -h "env $TAG02_ENV py simulators/tag_sim.py"
  tmux split-window -v "env $TAG03_ENV py simulators/tag_sim.py"
  tmux attach -t mottu
else
  (env $TAG01_ENV py simulators/tag_sim.py) &
  PID1=$!
  (env $TAG02_ENV py simulators/tag_sim.py) &
  PID2=$!
  (env $TAG03_ENV py simulators/tag_sim.py) &
  PID3=$!
  echo "Simuladores rodando (PIDs: $PID1 $PID2 $PID3). Pressione Ctrl+C para encerrar todos."
  wait
fi