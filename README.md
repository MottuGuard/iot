# MottuGuard • Sprint 4 (IoT)

Protótipo funcional (simulado) demonstrando **integração IoT via MQTT**, **dashboard em tempo real**, **persistência (Postgres)** e **testes de casos de uso**.

## Arquitetura

- **Mosquitto** (broker MQTT) com **WebSockets** (dashboard no navegador).
- **Simuladores de tags UWB** (3 dispositivos) publicam:
  - `mottu/uwb/<TAG_ID>/ranging` (distâncias por âncora, com ruído)
  - `mottu/uwb/<TAG_ID>/position` (posição estimada via trilateração)
  - `mottu/status/<TAG_ID>` (find_mode/lock)
  - `mottu/motion/<TAG_ID>` (eventos de movimento)
- **Dashboard Web** (HTML+JS) consome MQTT via WebSockets em tempo real e permite **enviar comandos**:
  - `mottu/act/<TAG_ID>/cmd` com `{ "cmd": "find_on|find_off|lock_on|lock_off" }`.
- **Ingestor** (Python) assina os tópicos e **persiste** no Postgres. Também emite **eventos** de alto nível (`offline`, `geofence_breach`).


## Subir a stack

1) **Pré-requisitos**: Docker + Docker Compose instalados.
2) `docker compose up -d`  
   - Broker MQTT: `mqtt://localhost:1883` • WebSockets: `ws://localhost:8080`
   - Postgres: `localhost:5432` (usuario `postgres`/ senha `postgres`)  
   - Dashboard: http://localhost:8081
3) Em outro terminal, rode os **simuladores**:
   ```bash
   ./scripts/run_tags.sh

(isso instala dependências locais e inicia tag01, tag02 e tag03 com cenários diferentes).

4) Opcional Inicie o ingestor (persistência):

	- py -m pip install -r ingestor/requirements.txt
	- PG_DSN='dbname=mottu user=postgres password=postgres host=localhost port=5432' \
	- py ingestor/ingestor.py