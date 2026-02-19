# Hardware Overview

Depending on the system you have, here is a breakdown of the hardware.

**Note:** GPIO number is different from physical pin number. See [pinout.xyz](https://pinout.xyz/).

---

## Air Temp & Humidity Sensor

- Temp/humidity sensor **DHT20** at I²C address `0x38` (used on Gardyn 3.0 and newer; older Gardyn 1.0/2.0 use AM2320 at a different address).

---

## Pump Power Monitor

- Motor power usage sensor **INA219** at I²C address `0x40`.

---

## PCB Temp Sensor

- PCB temp sensor **PCT2075** at I²C address `0x48`.

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

---

## Lights

LED full-spectrum lights.

- **Method:** PWM duty cycle, 8 kHz frequency.
- **Pin:** [GPIO-18 | PIN-12](https://pinout.xyz/pinout/pin12_gpio18/).

---

## Pump

- **Method:** PWM, max duty 30%, 50 Hz. Current sensor measures pump draw; overtemp sensor uses PCB temp.
- **Pin:** [GPIO-24 | PIN-18](https://pinout.xyz/pinout/pin18_gpio24/).

Pump duty cycle is limited; full on may draw too much current.

---

## Camera

Two USB cameras.

- **Method:** Image capture with `fswebcam`.
- **Devices:** Default upper `/dev/video0`, lower `/dev/video2`. Override with `UPPER_CAMERA_DEVICE` and `LOWER_CAMERA_DEVICE` in `.env`. The process must be able to read the camera devices (e.g. add user to `video` group: `sudo usermod -aG video $USER`).

---

## Water Level Sensor

Ultrasonic distance sensor **DYP-A01-V2.0**.

- **Pins:**
  - [GPIO-19 | PIN-35](https://pinout.xyz/pinout/pin35_gpio19/): trigger
  - [GPIO-26 | PIN-37](https://pinout.xyz/pinout/pin37_gpio26/): echo
- **Method:** Time between echo and response is used to compute distance.

**References:**

- [DYP-A01-V2.0 search](https://www.google.com/search?q=DYP-A01-V2.0)
- [A02 Datasheet (PDF)](https://www.dypcn.com/uploads/A02-Datasheet.pdf)

---

## Momentary Button

`<section incomplete>`

---

## Electrical Diagrams

For troubleshooting.

### Sensors

![Sensors](pcb1.png)

### Power and Header

![Power and Header](pcb2.png)

---

## Recommendations

### Upgrading the Pi Zero 2

For better performance, the Pi Zero can be replaced with a Pi Zero 2. This enables using VS Code Remote Server to edit and debug the Python code remotely (OpenSSH; minimum architecture ARMv7).

> Buy one **without** a header; you will need to solder one on in the opposite direction.
