"""Small stdlib-only backend for saved effects and Home Assistant sending.

This runs as the gledopto-api service in the same stack as the nginx frontend.
The browser talks only to /api/saved and /api/send, proxied by nginx. Home
Assistant credentials are read from the environment and never reach the browser.
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

# Path of the shared saved-effects JSON file. Configure it in .env.
SAVED_FILE = os.environ.get("SAVED_FILE_PATH", "/data/saved_effects.json")

# Home Assistant endpoint and service used to send Tuya datapoints.
HA_URL = os.environ.get("HA_URL", "").rstrip("/")
HA_TOKEN = os.environ.get("HA_TOKEN", "")
ESPHOME_SERVICE = os.environ.get(
    "ESPHOME_SERVICE", "esphome/led_dimmer_wifi_01_send_tuya_command"
)


def call_ha_service(payload: dict):
    """Call one Home Assistant service with the configured bearer token."""
    if not HA_URL or not HA_TOKEN:
        raise RuntimeError("HA_URL and HA_TOKEN must be set in the .env file")
    url = f"{HA_URL}/api/services/{ESPHOME_SERVICE}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read()


class Handler(BaseHTTPRequestHandler):
    """JSON API used by index.html."""

    def _send_json(self, code: int, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Return the shared saved effects, or an empty list before the first save.
        if self.path == "/api/saved":
            if not os.path.exists(SAVED_FILE):
                self._send_json(200, [])
                return
            with open(SAVED_FILE, "r", encoding="utf-8") as f:
                self._send_json(200, json.load(f))
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            data = json.loads(raw)
        except Exception as e:
            self._send_json(400, {"error": f"Invalid JSON: {e}"})
            return

        if self.path == "/api/saved":
            # Write to a temporary file first so readers never see a half-written file.
            tmp_file = SAVED_FILE + ".tmp"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, SAVED_FILE)
            self._send_json(200, {"ok": True})

        elif self.path == "/api/send":
            hex_val = str(data.get("hex", "")).strip().lower()
            if not hex_val:
                self._send_json(400, {"error": "Empty hex string"})
                return
            try:
                # DP21 selects the raw-string mode, then DP25 carries the effect hex.
                call_ha_service({"datapoint_id": 21, "datapoint_type": "enum", "value": "2"})
                call_ha_service({"datapoint_id": 25, "datapoint_type": "string", "value": hex_val})
                self._send_json(200, {"ok": True})
            except Exception as e:
                self._send_json(502, {"error": str(e)})
        else:
            self._send_json(404, {"error": "Not found"})


if __name__ == "__main__":
    # The port is internal to the stack; only nginx publishes it as /api/.
    HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
