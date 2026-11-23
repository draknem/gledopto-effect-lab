This is a vibecoded tool for decoding, visualising and editing effect strings,
sent to DPID 25 on tuyamcu on Gledopto GL-C-201W LED dimmer. The tool also implements measurement
of actual time between led color switches by using a webcam, or an IP camera, or an android phone
running IP Webcam (disable autofocus, auto white balance and auto exposure for more accurate results,
pick lower resolution and faster frame times for more accuracy)

The 

# Gledopto Effect Lab

A standalone browser tool for Gledopto GL-C-201W LED controller, flashed with an ESPHome.
The device uses TuyaMCU. It decodes DP25 effect strings, designs new ones, previews them,
measures timing with a camera, saves presets, and can send hex to Home Assistant.

It is a normal web page served by nginx. No HACS custom card is created.

## Features

- **Decode / Explore** — paste a DP25 hex string and inspect frames, colors,
  timelines, and FADE waveforms.
- **Design / Edit** — build or edit effects up to 8 frames / 210 hex characters,
  with HSV controls and live preview.
- **Library** — the captured factory effects plus malformed captures kept for reference.
- **Hypothesis Check** — change one field at a time and regenerate hex.
- **Timing calibration** — separate JUMP and FADE models, manual measurements,
  and camera auto-timing.
- **Saved effects** — shared JSON storage through `/api/saved`, with a
  browser `localStorage` fallback.
- **Send to Strip** — posts hex to `/api/send`; the Python backend calls Home
  Assistant with DP21 = `2` and DP25 = the generated hex string.

## Repository structure

| File                    | Purpose                                                                |
|-------------------------|------------------------------------------------------------------------|
| `index.html`            | Single-page application.                                               |
| `gledopto_effects.json` | Effect library captured from the MCU serial link.                      |
| `saved_effects.json`    | Included sample saved presets used by `/api/saved`.                    |
| `nginx.conf.template`   | nginx config; `${CAMERA_URL}` and `${API_UPSTREAM}` are rendered at    |
|                         | startup.                                                               |
| `Dockerfile`            | Builds the nginx image. Only the template is baked in.                 |
| `portainer-stack.yml`   | Portainer stack / Compose file with both nginx and the API service.    |
| `server.py`             | Stdlib-only JSON API for saved effects and Home Assistant sending; runs|
|                         | in the same stack.                                                     |
| `.env.example`          | Committed template with all supported variables.                       |

## Configuration: `.env`

Copy `.env.example` to `.env` and fill it in before deployment:

```bash
cp .env.example .env
```
`.env` is listed in `.gitignore`. The repository must never contain a real
Home Assistant token or an internal camera address.

| Variable             | Used for                                                      |
|----------------------|---------------------------------------------------------------|
| `APP_PORT`           | Host port published by nginx. Stack default is `8085`.        |
| `CONTAINER_NAME`     | Docker container name for nginx.                              |
| `API_CONTAINER_NAME` | Docker container name for the API service in the same stack.  |
| `IMAGE_NAME`         | Locally built nginx image name.                               |
| `HTML_HOST_PATH`     | Host folder bind-mounted at `/usr/share/nginx/html`. It must  |
|                      | contain `index.html` and `gledopto_effects.json`.             |
| `CAMERA_URL`         | MJPEG stream URL reachable from the Docker host. nginx exposes|
|                      | it at same-origin `/camera`.                                  |
| `API_UPSTREAM`       | Same-stack service address `http://gledopto-api:8000/api/`;   |
|                      | nginx proxies `/api/` to it.                                  |
| `HA_URL`             | Home Assistant base URL. Used only by `server.py`.            |
| `HA_TOKEN`           | Home Assistant long-lived access token. Used only by          |
|                      | `server.py`. Secret.                                          |
| `ESPHOME_SERVICE`    | ESPHome service path called by `server.py`.                   |
| `SAVED_FILE_PATH`    | JSON file used by `server.py` for shared saved effects.       |

`NGINX_ENVSUBST_FILTER` is fixed to `^(CAMERA_|API_)` so the official nginx
entrypoint substitutes only those variables and leaves nginx variables such as
`$host` untouched.

## Quick start with Docker Compose

```bash
git clone <REPOSITORY_URL> /opt/gledopto-effects
cd /opt/gledopto-effects
cp .env.example .env
# Edit .env: set CAMERA_URL, HA_URL and HA_TOKEN. API_UPSTREAM already points
# to the gledopto-api service in this stack.
docker build -t gledopto-effect-lab:latest .
docker compose --env-file .env -f portainer-stack.yml up -d
```

This starts two containers: nginx on `APP_PORT` and the API on the internal
stack network only. To access the tool, open `http://<DOCKER_HOST_IP>:8085`
(or the value of `APP_PORT`).

The same host folder is bind-mounted into both containers: nginx reads
`index.html` and `gledopto_effects.json` from `/usr/share/nginx/html`, while
`server.py` and `saved_effects.json` are used from `/data`. 

## Portainer

1. Build the image once on the Portainer host from this folder:

   ```bash
   docker build -t gledopto-effect-lab:latest .
   ```

2. In Portainer, add a stack from `portainer-stack.yml`. It creates both
   `gledopto-effects` (nginx) and `gledopto-api` (Python).
3. The web editor does not read the local `.env` file. Add the same variables
   manually in the stack environment, especially `HA_URL` and `HA_TOKEN`.
   `API_UPSTREAM` should remain `http://gledopto-api:8000/api/`.
4. Deploy / redeploy after changing `CAMERA_URL`, `HA_URL` or `HA_TOKEN`.

The API service needs no published host port: nginx reaches it as
`http://gledopto-api:8000` on the stack network. Changing `CAMERA_URL` only
needs a redeploy. Changing `nginx.conf.template` needs `docker build` again.

## Backend and Home Assistant

`server.py` runs as the `gledopto-api` service in the same Compose stack as
nginx. It uses `python:3.12-alpine`, needs no extra packages, and listens on
port 8000 inside the stack only. nginx proxies `/api/` to
`http://gledopto-api:8000/api/`.

The service receives these variables from the stack environment:

```text
HA_URL=<Home Assistant base URL>
HA_TOKEN=<long-lived access token>
ESPHOME_SERVICE=esphome/led_dimmer_wifi_01_send_tuya_command
SAVED_FILE_PATH=/data/saved_effects.json
```

The Home Assistant token is never sent to the browser. The page only calls
same-origin `/api/saved` and `/api/send`.

If the API is unavailable, the page still works: saved effects fall back to
`localStorage`, and the **Send to Strip** button reports an error.

### ESPHome action used by the backend

`server.py` calls an ESPHome Home Assistant service with these arguments:

```yaml
datapoint_id: int
datapoint_type: string
value: string
```

The service maps the value to the TuyaMCU datapoint using the ESPHome
`tuya_hub` `set_*_datapoint_value` methods. Sending an effect performs:

1. DP21 = `2`, type `enum` — raw string mode.
2. DP25 = lowercase effect hex, type `string`.

When declaring the action in ESPHome, use lowercase hex on the controller side
(`color_type_lowercase: true`) because the MCU's ASCII parser only accepts
lowercase `a`–`f`.

## Camera auto-timing

Point the camera at some white or grey object and place the green ROI box over it. 
The tool reads the same-origin `/camera` MJPEG stream with `fetch()`, extracts JPEG 
frames, and samples the ROI about 60 times per second.

- **JUMP** — accepts one event per hard color switch and waits until the new
  color settles. This prevents one switch from crossing the threshold several
  times. The plot still shows the real RGB distance.
- **FADE — ramp** — measures the duration from the start of the smooth
  transition to its peak.
- **FADE — continuous crossings (legacy)** — uses threshold crossings, a previous
  attempt at fade duration calibration, not working, kept for the story).

The **Change threshold** is an RGB distance. It must sit below the peaks of the
signal, around one third of its height. Use **Auto threshold from signal** to
set it from captured data. The first partial interval after **Start measuring**
is discarded.

Keep the MJPEG URL as `/camera`. A direct external URL will be blocked by
browser CORS rules. Webcam mode needs HTTPS(not implemented) or opening .html on
localhost, which will of course break saving to server and home assistant access.

## Effect string format

Confirmed on the Gledopto GL-C-201W. A string has one header byte followed by
`N` frames of 13 bytes each.
| Offset |  Size  | Field            |    Range | Real behaviour on GL-C-201W                      |
|--------|--------|------------------|----------|--------------------------------------------------|
| Header | 1 byte | Scene ID         | `00..ff` | Scene identifier, for example `04` or `1c`.      |
| Byte 0 | 1 byte | Unknown / unused | `00..ff` | Ignored by the MCU in JUMP and FADE. Kept only   |
|        |        |                  |          | for the 13-byte Tuya frame layout; Tool uses `50`|
|        |        |                  |          | (`0x32`) or `70` (`0x46`) as in factory scenes by|
|        |        |                  |          | default.                                         |     
| Byte 1 | 1 byte | Frame duration / | `00..ff` | The only working timer. In **JUMP mode**:        |
|        |        | Hold time        |          |`0..107` → `(108 - byte) × 0.1035s` (11.18–0.10s);|
|        |        |                  |          |`108` → fast strobe (~0.10 s after a ~32.7 s start|
|        |        |                  |          | up delay); `109..255` → 16-bit millisecond       |
|        |        |                  |          | counter undeflows (65.536 s), 65.43–50.17 s.     |
|        |        |                  |          | In **FADE**: full frame period ≈ `(108 - byte) × |
|        |        |                  |          | 0.207 s`; byte `< 65` → static color for approxi-|
|        |        |                  |          | mately JUMP*2-8.4s, then ~8.4 s of fade;         |
|        |        |                  |          | `65` → continuous fade ramp with no hold;        |
|        |        |                  |          | `66..85` → frames start overlapping (less than   |
|        |        |                  |          | 8.4s per frame) and jump to second color at the  |
|        |        |                  |          | end of ramp.                                     |
|        |        |                  |          | `85..107` → same as previos, but no jump detected|
|        |        |                  |          | (by phone camera at least). The max amplitude    |
|        |        |                  |          | Seems to fall with faster fades.                 |
| Byte 2 | 1 byte | Style            | `00..03` | `00` static, `01` jump (hard switch), `02` fade  |
|        |        |                  |          | (smooth transition), `03` strobe/flash.          |
| Bytes 3–4   | 2 bytes | Hue               | `0000..0168` | Hue angle in degrees, big-endian.     |
| Bytes 5–6   | 2 bytes | Saturation        | `0000..03e8` | Saturation, 0–100%, big-endian.       |
| Bytes 7–8   | 2 bytes | RGB value         | `0000..03e8` | Brightness of the colour LEDs, 0–100%,|
|             |         |                   |              | big-endian.                           |
| Bytes 9–10  | 2 bytes | White brightness  | `0000..03e8` | White channel brightness, used in     |
|             |         |                   |              | white presets with Style = `00`.      |
| Bytes 11–12 | 2 bytes | White temperature | `0000..03e8` | Warm → cold white, big-endian.        |

Byte 0 has no timing role, at least on my device, byte 1 controls timing in both
JUMP and FADE. The timing models are empirical fits from hardware measurements, 
not manufacturer documentation. Byte 107 flashes rapidly, byte 108 is the fast-strobe 
boundary, and byte 109 starts the long ~65 s sequence.

