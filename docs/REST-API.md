# REST API Reference

This document describes every HTTP endpoint exposed by the garden-of-eden Flask API. Use it when building a frontend, CLI, or any client that talks to the device.

## Conventions

- **Base URL**: `http://<pi-ip>:5000` — replace `<pi-ip>` with the Raspberry Pi’s IP (e.g. `192.168.1.181`). The server binds to `0.0.0.0:5000`.
- **Request headers**: For endpoints that accept JSON bodies, send `Content-Type: application/json`.
- **Response format**: Success responses are JSON unless noted (e.g. binary image/jpeg). Error responses are JSON with an `error` key (string message), unless the endpoint documents a different error shape (e.g. `message` for some validation errors).
- **CORS**: CORS is enabled so browser clients on other origins (e.g. a deployed dashboard) can call the API.
- **Sensor/hardware errors**: Endpoints that depend on hardware (sensors, light, pump, camera) may return `400` with a JSON body if the sensor is not initialized or unavailable.
- **Authentication**: When `AUTH_ENABLED` is true, all endpoints except `/auth/*` require a JWT in the header: `Authorization: Bearer <token>`. The token is obtained by completing passkey (WebAuthn) login via `POST /auth/login`. Unauthenticated requests receive `401` with `{ "error": "Authentication required" }`.

---

## 0. Authentication (Passkey / WebAuthn)

When auth is enabled, use these endpoints to register a passkey and sign in. After signing in, send the returned JWT as `Authorization: Bearer <token>` on every request to other endpoints.

### GET /auth/register/options

Returns options for creating a new passkey. Used by the client with `navigator.credentials.create()`.

| | |
|--|--|
| **Request** | Query: `email` (required when `ALLOWED_EMAILS` is set). No auth required. |
| **Success 200** | JSON object suitable for `PublicKeyCredentialCreationOptions` (challenge, rp, user, pubKeyCredParams, etc.). Binary fields are base64url-encoded. |
| **Error 400** | `{ "error": "Email is required" }` when `ALLOWED_EMAILS` is set and `email` is missing. |
| **Error 403** | `{ "error": "This email is not allowed to register" }` when the email is not in `ALLOWED_EMAILS`. |

### POST /auth/register

Verifies the credential created by the client and stores it. Call after `navigator.credentials.create()`.

| | |
|--|--|
| **Request** | `{ "credential": <WebAuthn credential object>, "email": string (optional, required when ALLOWED_EMAILS is set) }` — the credential from the browser (binary fields base64url-encoded) and the same email used in register/options. |
| **Success 200** | `{ "ok": true, "message": "Passkey registered" }` |
| **Error 400** | `{ "error": string }` — e.g. invalid or expired challenge, verification failed. |
| **Error 403** | `{ "error": "This email is not allowed to register" }` when the email is not in `ALLOWED_EMAILS`. |

### GET /auth/login/options

Returns options for signing in with a passkey. Used by the client with `navigator.credentials.get()`.

| | |
|--|--|
| **Request** | No body. No auth required. |
| **Success 200** | JSON object suitable for `PublicKeyCredentialRequestOptions` (challenge, allowCredentials, etc.). |

### POST /auth/login

Verifies the assertion from the client and returns a JWT. Call after `navigator.credentials.get()`.

| | |
|--|--|
| **Request** | `{ "credential": <WebAuthn assertion object> }` — the credential from the browser, with binary fields base64url-encoded. |
| **Success 200** | `{ "token": string, "user": { "id": number, "name": string } }` — use `token` in `Authorization: Bearer <token>`. |
| **Error 400** | `{ "error": string }` — e.g. unknown credential, verification failed. |

### GET /auth/me

Returns the current user when the request includes a valid JWT. Optional; useful for checking session validity.

| | |
|--|--|
| **Request** | Header: `Authorization: Bearer <token>`. |
| **Success 200** | `{ "user": { "id": number, "name": string } }` |
| **Error 401** | `{ "error": string }` — missing or invalid token. |

---

## 1. Sensors

### GET /distance

One-shot distance measurement from the ultrasonic sensor to the water surface. **Higher value = emptier tank.**

| | |
|--|--|
| **Request** | No body. No query parameters. |
| **Success 200** | `{ "distance": number }` — distance in **centimeters**. |
| **Error 400** | `{ "error": string }` — e.g. "Distance are not initialized". |

**Example response:** `{"distance": 42.5}`

---

### GET /humidity

Current relative humidity from the AM2320 sensor.

| | |
|--|--|
| **Request** | No body. No query parameters. |
| **Success 200** | `{ "humidity": string }` — numeric string with 2 decimal places (e.g. `"45.00"`). **Parse as float** for calculations. |
| **Error 400** | `{ "error": string }` — e.g. "Humidity are not initialized". |

---

### GET /temperature

Current air temperature from the AM2320 sensor.

| | |
|--|--|
| **Request** | No body. No query parameters. |
| **Success 200** | `{ "temperature": string }` — **Celsius**, 2 decimal places (e.g. `"22.50"`). Parse as float for calculations. |
| **Error 400** | `{ "error": string }` |

---

### GET /pcb-temp

PCB temperature from the PCT2075 sensor (board temperature monitoring).

| | |
|--|--|
| **Request** | No body. No query parameters. |
| **Success 200** | `{ "pcb-temp": string }` — **Celsius**, 2 decimal places (e.g. `"35.20"`). Parse as float. Note: key is `pcb-temp` (hyphen). |
| **Error 400** | `{ "error": string }` |

---

## 2. Light

### POST /light/on

Turn the light on (full brightness unless changed via `/light/brightness`).

| | |
|--|--|
| **Request** | No body required. Optional `Content-Type: application/json`. |
| **Success 200** | `{ "message": "Light turned on" }` |
| **Error 400** | `{ "error": string }` — e.g. "Light are not initialized". |

---

### POST /light/off

Turn the light off.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "message": "Light turned off" }` |
| **Error 400** | `{ "error": string }` |

---

### GET /light/brightness

Get current light brightness (0–100). Value is a float (duty cycle percentage).

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "value": number }` — 0–100. |
| **Error 400** | `{ "error": string }` |

---

### POST /light/brightness

Set light brightness. If the light was off, it is turned on at the given brightness.

| | |
|--|--|
| **Request** | `Content-Type: application/json`. Body: `{ "value": number }` — integer or float, **0–100**. If omitted, defaults to 50. |
| **Success 200** | `{ "message": "Light adjusted to <value>%" }` |
| **Error 400** | `{ "message": string }` — e.g. "Speed must be between 0 and 100" (validation), or `{ "error": string }` for sensor failure. |

**Example:** `POST /light/brightness` with body `{"value": 75}`

---

## 3. Pump

### POST /pump/on

Turn the pump on (100% duty).

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "message": "Pump turned on!" }` |
| **Error 400** | `{ "error": string }` |

---

### POST /pump/off

Turn the pump off.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "message": "Pump turned off!" }` |
| **Error 400** | `{ "error": string }` |

---

### GET /pump/speed

Get current pump speed (0–100).

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "value": number }` — 0–100. |
| **Error 400** | `{ "error": string }` |

---

### POST /pump/speed

Set pump speed. Does not turn the pump on by itself; combine with `POST /pump/on` if needed.

| | |
|--|--|
| **Request** | `Content-Type: application/json`. Body: `{ "value": number }` — **0–100**. If omitted, defaults to 30. |
| **Success 200** | `{ "message": "Pump adjusted to <value>% speed!" }` |
| **Error 400** | `{ "message": string }` — e.g. "Speed must be between 0 and 1" (validation), or `{ "error": string }` for sensor failure. |

---

### GET /pump/stats

Pump power stats from the INA219 sensor (when present). Useful for monitoring current draw.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | JSON object. Keys may include: `BusVoltage` (number), `BusCurrent` (number), `Power` (number), `ShuntVoltage` (number). If the sensor is not found or out of range: `{ "error": string }` (still 200). |
| **Error 400** | `{ "error": string }` — pump/sensor not initialized. |

**Example response:** `{"BusVoltage": 12.1, "BusCurrent": 0.5, "Power": 6.05, "ShuntVoltage": 0.04}`

---

## 4. Camera

All camera endpoints require the Camera sensor to be initialized (fswebcam and configured USB devices). There is no authentication. Times are device local.

### GET /camera/upper

Take a snapshot from the upper camera and return it as JPEG.

| | |
|--|--|
| **Request** | No body. No query parameters. |
| **Success 200** | Response body is **binary JPEG**. Header: `Content-Type: image/jpeg`. |
| **Error 503** | `{ "error": string }` — capture failed (e.g. device busy, fswebcam error). |

Use this URL in an `<img src="...">` or fetch and display via a blob URL. Poll periodically for a “live-ish” view (there is no MJPEG or video stream).

---

### GET /camera/lower

Same as `/camera/upper` but for the lower camera.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | Binary JPEG, `Content-Type: image/jpeg`. |
| **Error 503** | `{ "error": string }` |

---

### GET /camera/devices

List configured camera devices (id, device path, name).

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "devices": [ { "id": number, "device": string, "name": string }, ... ] }` — e.g. `{"id": 0, "device": "/dev/video0", "name": "upper"}`. |
| **Error 400** | `{ "error": string }` |

---

### POST /camera/capture

Take a picture from the specified camera. Either return the image immediately (binary) or save to disk and return JSON.

**Parameters** (either query or JSON body; body overrides query when present):

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| device | number or string | 0 | `0` or `"upper"` = upper camera; `1` or `"lower"` = lower camera. |
| save | boolean or string | false | If truthy (`true`, `1`, `"true"`, `"yes"`), save to `CAMERA_PHOTOS_DIR` and return JSON; otherwise return image/jpeg. |

| | |
|--|--|
| **Request** | `Content-Type: application/json` recommended. Body: `{ "device": number \| string, "save": boolean }`. Query alternatives: `?device=0&save=1`. |
| **Success 200 (save=false)** | Response body is **binary JPEG**. Header: `Content-Type: image/jpeg`. |
| **Success 200 (save=true)** | JSON: `{ "message": "Photo saved", "path": string, "filename": string, "url": string }`. `url` is **relative** (e.g. `/camera/photos/camera_0_1234567890.jpg`). Prepend base URL to fetch or display. |
| **Error 400** | `{ "error": string }` — e.g. invalid device. |
| **Error 503** | `{ "error": string }` — capture failed. |

**Examples:**

- Return JPEG: `POST /camera/capture` body `{"device": 0, "save": false}`
- Save and get URL: `POST /camera/capture` body `{"device": "lower", "save": true}`

---

### GET /camera/photos

List saved photo filenames and relative URLs. Requires `CAMERA_PHOTOS_DIR` (or default `photos` in project root) to exist. Returns an empty list if the directory does not exist yet.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "photos": [ { "filename": string, "url": string }, ... ], "message": string (optional) }`. `url` is **relative** (e.g. `/camera/photos/photo.jpg`). Only `.jpg`/`.jpeg` files are listed, sorted newest first. If directory is missing: `photos: []`, optional `message: "Photo directory does not exist yet"`. |
| **Error 503** | `{ "error": string }` — e.g. filesystem error. |

---

### GET /camera/photos/<filename>

Serve a saved photo as JPEG. The filename must not contain `..` or path separators (security).

| | |
|--|--|
| **Path** | **filename** — basename of a file in the photos directory (e.g. `camera_0_1234567890.jpg`). URL-encode the filename if it contains special characters. |
| **Request** | No body. |
| **Success 200** | Binary JPEG, `Content-Type: image/jpeg`. |
| **Error 400** | `{ "error": "Invalid filename" }` |
| **Error 404** | `{ "error": "Photo directory not available" }` or `{ "error": "Not found" }` |

**Full URL example:** `http://<pi-ip>:5000/camera/photos/camera_0_1234567890.jpg`

---

### DELETE /camera/photos/<filename>

Delete a saved photo by filename. The filename must not contain `..` or path separators.

| | |
|--|--|
| **Path** | **filename** — basename of the file to delete. |
| **Request** | No body. |
| **Success 204** | No response body. |
| **Error 400** | `{ "error": "Invalid filename" }` |
| **Error 404** | `{ "error": "Photo directory not available" }` or `{ "error": "Not found" }` |
| **Error 500** | `{ "error": string }` — e.g. filesystem error on delete. |

---

## 5. Schedule rules

Rule-based scheduling for lights and pump. A background scheduler runs **every minute** on the device and applies rules whose times match the current **device local time**. Set the Pi timezone (e.g. `America/Chicago`) so rule times match your intended schedule. All rule IDs are UUIDs generated by the server.

**Rule types:**

- **Light**: Start time (and optional end time) with a brightness percentage. Or “set and stay” (no end time): at start time set brightness and leave it (use brightness 0 for “turn off at this time”). Last matching rule wins if multiple apply.
- **Pump**: At a given time, turn pump on at 100% for a fixed duration (minutes), then turn off.

**Rule object shapes (in responses):**

- **Light**: `{ "id": string, "type": "light", "start_time": string, "end_time": string | null, "brightness_pct": number, "enabled": boolean, "paused": boolean }`
- **Pump**: `{ "id": string, "type": "pump", "time": string, "duration_minutes": number, "enabled": boolean, "paused": boolean }`

Times are normalized to **HH:MM** (24-hour, e.g. `"09:30"`). Rules with `enabled: false` or `paused: true` are not applied.

---

### GET /schedule/rules

List all rules.

| | |
|--|--|
| **Request** | No body. |
| **Success 200** | `{ "rules": [ rule, ... ] }` — array of rule objects (see shapes above). |

---

### GET /schedule/rules/<rule_id>

Get a single rule by ID.

| | |
|--|--|
| **Path** | **rule_id** — UUID string returned when the rule was created. |
| **Request** | No body. |
| **Success 200** | Single rule object. |
| **Error 404** | `{ "error": "Rule not found" }` |

---

### POST /schedule/rules

Create a new rule. Body must include `type` and all required fields for that type.

**Light rule body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | yes | Must be `"light"`. |
| start_time | string | yes | Time in 24h format **HH:MM** (e.g. `"06:00"`, `"9:30"`). Normalized to HH:MM. |
| end_time | string or null | no | If set: end of range in HH:MM; at this time the light is turned off. If null or omitted: “set and stay” — at start_time the light is set to brightness and left that way (use brightness 0 for “turn off at start_time”). |
| brightness_pct | number | yes | 0–100. |
| enabled | boolean | no | Default `true`. If `false`, rule is not applied. |
| paused | boolean | no | Default `false`. If `true`, rule is not applied (separate from enabled). |

**Pump rule body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | yes | Must be `"pump"`. |
| time | string | yes | Time in 24h **HH:MM** when the pump should turn on. |
| duration_minutes | number | yes | 1–120. Pump runs at 100% for this many minutes, then turns off. |
| enabled | boolean | no | Default `true`. |
| paused | boolean | no | Default `false`. |

| | |
|--|--|
| **Request** | `Content-Type: application/json`. Body: one of the shapes above. |
| **Success 201** | Created rule object, including generated **id** (UUID). |
| **Error 400** | `{ "error": string }` — e.g. "start_time is required (HH:MM)", "brightness_pct must be 0-100", "duration_minutes must be 1-120", "type must be 'light' or 'pump'". |

**Examples:**

- Light, time range: `{"type":"light","start_time":"09:00","end_time":"17:00","brightness_pct":70}`
- Light, set and stay (turn off at 20:00): `{"type":"light","start_time":"20:00","end_time":null,"brightness_pct":0}`
- Pump: `{"type":"pump","time":"09:30","duration_minutes":5}`

---

### PUT /schedule/rules/<rule_id>

Update an existing rule. Send only fields you want to change; the existing rule is merged with the body. The rule’s type cannot be changed; validation uses the rule’s current type (or type in body if provided).

| | |
|--|--|
| **Path** | **rule_id** — UUID of the rule to update. |
| **Request** | `Content-Type: application/json`. Body: partial or full rule. For light: start_time, end_time, brightness_pct, enabled, paused. For pump: time, duration_minutes, enabled, paused. |
| **Success 200** | Updated rule object. |
| **Error 400** | `{ "error": string }` — validation error. |
| **Error 404** | `{ "error": "Rule not found" }` |

**Example (pause a rule):** `PUT /schedule/rules/<id>` body `{"paused": true}`

---

### DELETE /schedule/rules/<rule_id>

Delete a rule permanently.

| | |
|--|--|
| **Path** | **rule_id** — UUID of the rule to delete. |
| **Request** | No body. |
| **Success 204** | No response body. |
| **Error 404** | `{ "error": "Rule not found" }` |
