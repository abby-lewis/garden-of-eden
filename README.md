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
    - [MQTT with HomeAssistant](#mqtt-with-homeassistant)
    - [Testing](#testing)
    - [Controlling Individual Sensors](#controlling-individual-sensors)
    - [REST API](#rest-api)
      - [Dashboard deployment and passkey auth](#dashboard-deployment-and-passkey-auth)
      - [Postman](#postman)
    - [Run on startup (Raspberry Pi)](#run-on-startup-raspberry-pi)
  - [Hardware Overview](#hardware-overview)
    - [Air Temp \& Humidity Sensor](#air-temp--humidity-sensor)
    - [Pump Power Monitor](#pump-power-monitor)
    - [PCB Temp Sensor](#pcb-temp-sensor)
    - [Lights](#lights)
      - [Method](#method)
      - [Pins](#pins)
    - [Pump](#pump)
      - [Method](#method-1)
      - [Pins](#pins-1)
    - [Camera](#camera)
      - [Method](#method-2)
      - [Devices](#devices)
    - [Water Level Sensor](#water-level-sensor)
      - [Pins](#pins-2)
      - [Method](#method-3)
      - [References](#references)
    - [Momentary Button](#momentary-button)
    - [Electrical Diagrams](#electrical-diagrams)
      - [Sensors](#sensors)
      - [Power and Header](#power-and-header)
    - [Recommendations](#recommendations)
      - [Upgrading the Pi Zero 2](#upgrading-the-pi-zero-2)
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

## Quick Toggle Guide

> Ensure your press is quick and within the time frame for the action to register correctly. The press time window can be modified directly in the `mqtt.py` file.

- **One Press** (within 1 second): 
  - **Action**: Toggles the **Lights** on or off. 
  - **Description**: A single, swift press will illuminate or darken your space with ease.

- **Two Presses** (within 1 second): 
  - **Action**: Toggles the **Pump** on or off.
  - **Description**: Need to water the garden or fill up the pool? Double tap for action!


### MQTT with HomeAssistant

For homeassistant:

You need a mqtt broker either on the gardyn pi or homeassistant.

To install on the pi run

```
sudo apt-get install mosquitto mosquitto-clients
```

Add mqtt-broker username and password:

`sudo mosquitto_passwd -c /etc/mosquitto/passwd <USERNAME>`

> Note: make sure to update the .env file which is used by `config.py` for `mqtt.py`

Run `sudo nano /etc/mosquitto/mosquitto.conf` and change the following lines to match:

```
allow_anonymous false
password_file /etc/mosquitto/passwd
listener 1883
```


Here are some additional options that you could set in `/etc/mosquitto/mosquitto.conf`:

```
pid_file /run/mosquitto/mosquitto.pid

persistence true
persistence_location /var/lib/mosquitto/

log_dest file /var/log/mosquitto/mosquitto.log

listener 1883 0.0.0.0

allow_anonymous false
password_file /etc/mosquitto/passwd

include_dir /etc/mosquitto/conf.d
```


Restart the service

```
sudo systemctl restart mosquitto
```

you just need to edit the `.env` with the mosquitto username and password created above in /etc/mosquitto/passwd.


Check the configuration works:

`sudo journalctl -xeu mosquitto.service`


If you havent already, run `./bin/setup.sh`, this will install all OS dependencies, install the python libs, and run services pigpiod, mqtt.service

Ensure the pigpiod, mqtt, and broker daemon is running

```
sudo systemctl status pigpiod
sudo systemctl status mqtt.service
sudo systemctl status mosquitto
```

Go to your homeassistant instance:
If your broker is on the gardyn pi, make sure to install the service mqtt, go to settings->devices&services->mqtt and add your gardyn pi host, port, username and password.
The device should then appear in your homeassistant discovery settings.

To test locally on gardyn pi:

Light:

```
mosquitto_pub -t "gardyn/light/command" -m "ON" -u gardyn -P "somepassword"
mosquitto_pub -t "gardyn/light/command" -m "OFF" -u gardyn -P "somepassword"
```

Pump:

```
mosquitto_pub -t "gardyn/pump/command" -m "ON" -u gardyn -P "somepassword"
mosquitto_pub -t "gardyn/pump/command" -m "OFF" -u gardyn -P "somepassword"
```

Sensors:

Open two terminals on the gardyn pi, in one run:

`mosquitto_sub -t "gardyn/water/level" -u gardyn -P "somepassword"`

In the second gardyn pi terminal, run:

`mosquitto_pub -t "gardyn/water/level/get" -m ""-r  -u gardyn -P "somepassword"`

```

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

### Controlling Individual Sensors

Activate python venv `source venv/bin/activate`

Examples:

```bash
python app/sensors/distance/distance.py
python app/sensors/humidity/humidity.py
python app/sensors/light/light.py [--on] [--off] [--brightness INT%]
python app/sensors/pcb_temp/pcb_temp.py
python app/sensors/pump/pump.py [--on] [--off] [--speed INT%] [--factory-host STR%] [--factory-port INT%]
python app/sensors/temperature/temperature.py
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

The API URL stays the same (e.g. `https://manliestben.zapto.org:8444`). In Netlify (or your host), set the build env var **VITE_GARDYN_API_URL** to that API URL so the dashboard knows where to send requests.

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

Depending on the system you have, here is a breakdown of the hardware.

Notes:

- GPIO num is different than pin number. See (<https://pinout.xyz/>)

### Air Temp & Humidity Sensor

- temp/humidity sensor AM2320 at address of `0x38`

### Pump Power Monitor

- motor power usage sensor INA219 at address of `0x40`

### PCB Temp Sensor

- pcb temp sensor PCT2075 at address `pf 0x48`

When you run `sudo i2cdetect -y 1`, you should see something like:

```
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- -- -- -- -- -- -- -- -- -- -- -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- 38 -- -- -- -- -- -- --
40: 40 -- -- -- -- -- -- -- 48 -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```

### Lights

LED full spectrum lights.

#### Method

- Lights are driven by PWM duty and a frequency of 8 kHz.

#### Pins

- [GPIO-18 | PIN-12](https://pinout.xyz/pinout/pin12_gpio18/)

### Pump

#### Method

- The pump is driven by PWM with max duty of 30% and frequency of 50 Hz
- There is a current sensor to measure pump draw and a overtemp sensor to determine if board monitor PCB temp.

#### Pins

- [GPIO-24 | PIN-18](https://pinout.xyz/pinout/pin18_gpio24/)

Notes:

- Pump duty cycle is limited, likely full on is too much current draw for the system.

### Camera

Two USB cameras.

#### Method

- image capture with fswebcam

#### Devices

- Default: `/dev/video0` (upper), `/dev/video2` (lower). Override with `UPPER_CAMERA_DEVICE` and `LOWER_CAMERA_DEVICE` in `.env`.
- The process running the app must be able to read the camera devices (e.g. add the user to the `video` group: `sudo usermod -aG video $USER`).

### Water Level Sensor

Uses the ultrasonic distance sensor DYP-A01-V2.0.

#### Pins

- [GPIO-19 | PIN-35](https://pinout.xyz/pinout/pin35_gpio19/): water level in (trigger)
- [GPIO-26 | PIN-37](https://pinout.xyz/pinout/pin37_gpio26/): water level out (echo)

#### Method

- Uses time between the echo and response to deterine the distances.

#### References

- <https://www.google.com/search?q=DYP-A01-V2.0>
- <https://www.dypcn.com/uploads/A02-Datasheet.pdf>

### Momentary Button

`<section incomplete>`

### Electrical Diagrams

Incase you need to troubleshoot any problems with your system.

#### Sensors

<img src="docs/pcb1.png" width="800px">

#### Power and Header

<img src="docs/pcb2.png" width="800px">

### Recommendations

#### Upgrading the Pi Zero 2

For better performance, the Pi Zero can be replaced with a Pi Zero 2. This will enable the use of VS Code Remote Server to edit files and debug the python code remotely. The VS Code remote server uses OpenSSH and the minimum architecture is ARMv7.

> Buy one **without** a header, you will need to solder one on in the opposite direction.

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
