# MQTT with Home Assistant

This document covers using garden-of-eden with an MQTT broker and Home Assistant.

You need an MQTT broker either on the Gardyn Pi or on Home Assistant.

---

## Install Mosquitto on the Pi

```bash
sudo apt-get install mosquitto mosquitto-clients
```

---

## Add MQTT broker username and password

```bash
sudo mosquitto_passwd -c /etc/mosquitto/passwd <USERNAME>
```

> **Note:** Make sure to update the `.env` file (used by `config.py` for `mqtt.py`) with the same credentials.

---

## Configure Mosquitto

Run `sudo nano /etc/mosquitto/mosquitto.conf` and set:

```
allow_anonymous false
password_file /etc/mosquitto/passwd
listener 1883
```

Optional settings you can add in `/etc/mosquitto/mosquitto.conf`:

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

Restart the service:

```bash
sudo systemctl restart mosquitto
```

Put the same Mosquitto username and password in your `.env` (as created above in `/etc/mosquitto/passwd`).

---

## Verify configuration

```bash
sudo journalctl -xeu mosquitto.service
```

If you haven't already, run `./bin/setup.sh` to install OS dependencies, Python libs, and start services (pigpiod, mqtt.service).

Ensure these are running:

```bash
sudo systemctl status pigpiod
sudo systemctl status mqtt.service
sudo systemctl status mosquitto
```

---

## Home Assistant

If the broker is on the Gardyn Pi, install the MQTT integration in Home Assistant, then go to **Settings -> Devices & services -> MQTT** and add your Pi host, port, username, and password. The device should then appear in discovery.

---

## Test locally on the Pi

**Light:**

```bash
mosquitto_pub -t "gardyn/light/command" -m "ON" -u gardyn -P "somepassword"
mosquitto_pub -t "gardyn/light/command" -m "OFF" -u gardyn -P "somepassword"
```

**Pump:**

```bash
mosquitto_pub -t "gardyn/pump/command" -m "ON" -u gardyn -P "somepassword"
mosquitto_pub -t "gardyn/pump/command" -m "OFF" -u gardyn -P "somepassword"
```

**Sensors:**

In one terminal:

```bash
mosquitto_sub -t "gardyn/water/level" -u gardyn -P "somepassword"
```

In a second terminal:

```bash
mosquitto_pub -t "gardyn/water/level/get" -m "" -u gardyn -P "somepassword"
```

Replace `gardyn` and `somepassword` with the username and password you configured in `/etc/mosquitto/passwd` and `.env`.
