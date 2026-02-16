<img src="docs/_banner.svg" width="800px">

# Garden of Eden

Truly own that which is yours!

If you are interested in collaborating please review the [CONTRIBUTORS](CONTRIBUTORS.md) for commit styling guides.

## Project Status & Milestones

Work in progress. We should be picking up some steam here to give the DYI community the features you deserve.

[Milestones](https://github.com/iot-root/garden-of-eden/milestones)

![image](https://github.com/user-attachments/assets/403248f5-b7d4-4cb1-921a-0458f515f387)


## Table of Contents

- [Garden of Eden](#garden-of-eden)
  - [Project Status \& Milestones](#project-status--milestones)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
  - [Usage](#usage)
    - [Quick Toggle Guide](#quick-toggle-guide)
    - [MQTT with Home Assistant](#mqtt-with-homeassistant)
    - [Testing](#testing)
    - [REST API](#rest-api)
      - [Dashboard deployment and passkey auth](#dashboard-deployment-and-passkey-auth)
      - [Postman](#postman)
    - [Run on startup (Raspberry Pi)](#run-on-startup-raspberry-pi)
  - [Hardware Overview](#hardware-overview)
  - [Design Decisions](#design-decisions)
    - [Python Version 3.6 \>=](#python-version-36-)
    - [Delays in Reading Temp/Humidity data](#delays-in-reading-temphumidity-data)
    - [GPIO](#gpio)
  - [Folder Structure](#folder-structure)

## Getting Started

### Prerequisites

Start with a clean install of Linux. Use the [RaspberryPi Imager](https://www.raspberrypi.com/software/). Ensure ssh and wifi is setup. Once the image is written, pop the SDcard into the pi and ssh into it.

```bash
# clone repo
git clone git@github.com:iot-root/garden-of-eden.git
cd garden-of-eden 
```

Update the `.env` with mqtt broker info

```
cp .env-dist .env
nano .env
```

Install dependencies, and run services pigpiod, mqtt.service

```bash
./bin/setup.sh
```

Ensure the pigpiod daemon is running

```
sudo systemctl status pigpiod
sudo systemctl status mqtt.service
```

## Usage

### Quick Toggle Guide

> Ensure your press is quick and within the time frame for the action to register correctly. The press time window can be modified directly in the `mqtt.py` file.

- **One Press** (within 1 second): 
  - **Action**: Toggles the **Lights** on or off. 
  - **Description**: A single, swift press will illuminate or darken your space with ease.

- **Two Presses** (within 1 second): 
  - **Action**: Toggles the **Pump** on or off.
  - **Description**: Need to water the garden or fill up the pool? Double tap for action!

You can use the button to control lights and pump during app development when the API or dashboard are not available.


### MQTT with Home Assistant

For broker setup, Home Assistant integration, and local testing, see **[docs/MQTT.md](docs/MQTT.md)**.

### Testing

Activate python venv `source venv/bin/activate`

Start the Flask REST API `python run.py`

Test options:

```bash
# REST endpoints
./bin/api-test.sh

# unit test
python -m unittest -v

# individual tests
python tests/test_distance.py
```

### REST API

Activate the venv and run the server:

```bash
source venv/bin/activate
python run.py
```

The API listens on `0.0.0.0:5000` and prints the Pi IP. It exposes sensors (distance, humidity, temperature, PCB temp), light and pump control, camera snapshots and saved photos, and schedule rules.

**API reference for developers:** Full endpoint documentation — request/response shapes, status codes, and examples — is in [docs/REST-API.md](docs/REST-API.md). Use that when building a frontend or any API client.

**HTTPS setup:** Step-by-step guide for exposing the API over HTTPS (e.g. from outside your network): [docs/HTTPS-Setup.md](docs/HTTPS-Setup.md).

#### Dashboard deployment and passkey auth

The **API** runs on the Pi (e.g. `https://your-ddns-hostname:8444`). The **dashboard** (frontend) can be deployed elsewhere — for example Netlify — so users open the dashboard at a different URL (e.g. `https://your-app.netlify.app`), and the dashboard calls your API over the network.

When passkey auth is enabled, the Pi must know the **dashboard’s** origin (where the user is when they sign in):

| Where the dashboard runs | Set on the **Pi** `.env` |
|--------------------------|---------------------------|
| **Local dev** (e.g. Vite at `http://localhost:5173`) | `WEBAUTHN_RP_ID=localhost` and `WEBAUTHN_ORIGIN=http://localhost:5173` |
| **Netlify** (e.g. `https://your-app.netlify.app`) | `WEBAUTHN_RP_ID=your-app.netlify.app` and `WEBAUTHN_ORIGIN=https://your-app.netlify.app` |
| **Custom domain on Netlify** (e.g. `https://garden.example.com`) | `WEBAUTHN_RP_ID=garden.example.com` and `WEBAUTHN_ORIGIN=https://garden.example.com` |

- **WEBAUTHN_RP_ID** = hostname of the dashboard only (no port). The Pi strips any `:port` if you add it.
- **WEBAUTHN_ORIGIN** = full origin of the dashboard (scheme + host, plus port if not 443).

The API URL stays the same (e.g. `https://your-pi-hostname:8444`). In Netlify (or your host), set the build env var **VITE_GARDYN_API_URL** to that API URL so the dashboard knows where to send requests.

> **Note:** If `run.py` errors with `AttributeError: module 'dotenv' has no attribute 'find_dotenv'`, run `pip uninstall python-dotenv` and try again.

#### Postman

Export this [Postman collection](https://www.postman.com/orange-shadow-8689/workspace/garden-of-eden/collection/8244324-e9d8f79e-d3f2-423e-b0d1-a4ca5b1b08ca?action=share&creator=8244324&active-environment=8244324-861384b4-b4e3-48a3-8da1-181705bd2d8c), add to your private workspace, add the `pi-ip` env variable and you should be good to go.

### Run on startup (Raspberry Pi)

To have the API (venv + `run.py`) start automatically on boot on a Raspberry Pi Zero 2W (or any Pi), use **systemd**.

1. **Edit the service file**  
   Copy the example unit file and set your project path and user:
   ```bash
   sudo cp docs/garden-of-eden.service /etc/systemd/system/
   sudo nano /etc/systemd/system/garden-of-eden.service
   ```
   Update `User=` and the paths in `WorkingDirectory=` and `ExecStart=` if your repo is not under `/home/pi/garden-of-eden` (e.g. use `/home/gardyn/projects/garden-of-eden` and `User=gardyn` if that matches your setup).

2. **Enable and start the service**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable garden-of-eden
   sudo systemctl start garden-of-eden
   ```

3. **Check status and logs**
   ```bash
   sudo systemctl status garden-of-eden
   journalctl -u garden-of-eden -f
   ```

The service runs after the network is up (`network-online.target`), restarts on failure, and logs to the system journal.

## Hardware Overview

Sensors, pins, cameras, and diagrams are documented in **[docs/Hardware-Overview.md](docs/Hardware-Overview.md)**.

## Design Decisions

### Python Version 3.6 >=

Minimum python version of 3.6 to support `printf()`

### Delays in Reading Temp/Humidity data

Reading sensor values  with inherently long delays and responding to the REST API. To minimize the delay in subsequent readings the value is cached and given if another read occurs within two seconds.

### GPIO

Using `gpiozero` to leverage `pigpio` daemon which is hardware driven and more efficient.This ensures better accuracy of the distance sensor and is less cpu intensive when using PWMs.

## Folder Structure

```text
garden-of-eden/
├── run.py
├── config.py
├── mqtt.py
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── models.py
│   ├── lib/
│   │   ├── __init__.py
│   │   └── lib.py
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── middleware.py
│   │   └── routes.py
│   ├── schedules/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── scheduler.py
│   │   └── store.py
│   └── sensors/
│       ├── __init__.py
│       ├── temp_humidity_shared.py
│       ├── camera/
│       │   ├── __init__.py
│       │   ├── camera.py
│       │   └── routes.py
│       ├── distance/
│       │   ├── __init__.py
│       │   ├── distance.py
│       │   └── routes.py
│       ├── humidity/
│       │   ├── __init__.py
│       │   ├── humidity.py
│       │   └── routes.py
│       ├── light/
│       │   ├── __init__.py
│       │   ├── light.py
│       │   └── routes.py
│       ├── pcb_temp/
│       │   ├── __init__.py
│       │   ├── pcb_temp.py
│       │   ├── over_temp_monitor.py
│       │   └── routes.py
│       ├── pump/
│       │   ├── __init__.py
│       │   ├── pump.py
│       │   ├── pump_power.py
│       │   └── routes.py
│       └── temperature/
│           ├── __init__.py
│           ├── temperature.py
│           └── routes.py
├── bin/
│   ├── setup.sh
│   ├── api-test.sh
│   ├── get-sensor-data.sh
│   └── ...
├── docs/
│   ├── REST-API.md
│   ├── HTTPS-Setup.md
│   ├── garden-of-eden.service
│   └── ...
├── services/
└── tests/
    ├── __init__.py
    ├── test_api.py
    ├── test_distance.py
    ├── test_light.py
    └── test_pump.py
```
