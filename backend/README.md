# Door Lock Backend

FastAPI service that unlocks a door by sending commands over UART (USB serial)
to an ESP32 door controller.

```
HTTP client --> FastAPI (this repo) --USB serial--> ESP32 --GPIO 16--> MOSFET --> door lock
```

## Requirements

- Python 3.12+ and [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- An ESP32 dev board connected to this computer with a **data** USB cable
  (charge-only cables will not show up as a serial port)
- The ESP32 must already be flashed with firmware that speaks the protocol below
  (the firmware is **not** in this repo)

## Connecting to the board

1. Plug the ESP32 into the computer over USB.
2. Install the USB-serial driver if the port does not appear. Most ESP32 dev
   boards use a CP210x or CH340 chip:
   - macOS / Windows: install the
     [CP210x](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers) or
     [CH340](https://www.wch-ic.com/downloads/CH341SER_EXE.html) driver
   - Linux: built in
3. Find the port name:
   - macOS: `ls /dev/tty.usbserial-*` (or `/dev/tty.usbmodem*`)
   - Linux: `ls /dev/ttyUSB* /dev/ttyACM*`
   - Windows: Device Manager > Ports (COM & LPT), e.g. `COM3`
4. Linux only: allow your user to open the port, then log out and back in:
   ```
   sudo usermod -aG dialout $USER
   ```
5. Only one program can use the port at a time. Close the Arduino IDE serial
   monitor, `screen`, etc. before starting the backend.

## Setup and run

```
cd backend
uv sync

export DOOR_API_KEY=<pick-a-secret>
export DOOR_SERIAL_PORT=<port from the step above>   # default: /dev/tty.usbserial-0001

uv run uvicorn main:app --host 127.0.0.1 --port 8000
```

| Variable           | Required | Default                    | Meaning                          |
| ------------------ | -------- | -------------------------- | -------------------------------- |
| `DOOR_API_KEY`     | yes      | -                          | Key clients send in `X-API-Key`  |
| `DOOR_SERIAL_PORT` | no       | `/dev/tty.usbserial-0001`  | Serial port of the ESP32         |

The server refuses to start without `DOOR_API_KEY`. It binds to localhost by
default; only use `--host 0.0.0.0` on a network you trust, since `/unlock`
opens a physical door.

## Testing

```
# Is the board alive?
curl localhost:8000/health
# {"status":"ok"}

# Unlock the door (relocks automatically after 5 seconds)
curl -X POST -H "X-API-Key: $DOOR_API_KEY" localhost:8000/unlock
# {"status":"unlocked","relock_in_seconds":5}
```

Interactive docs are at <http://localhost:8000/docs>.

## Endpoints

| Method | Path      | Auth        | Description                                         |
| ------ | --------- | ----------- | --------------------------------------------------- |
| GET    | `/health` | none        | Sends `PING` to the board, expects `PONG`           |
| POST   | `/unlock` | `X-API-Key` | Sends `UNLOCK`; the board holds the door open 5 s   |

Status codes: `200` ok, `401` bad/missing key, `502` board refused
(e.g. `ERR BUSY` when already unlocked), `504` board did not reply in 2 s.

## UART protocol

115200 baud, 8N1, ASCII, one command per line terminated by `\n`.

| Command  | Reply                           | Meaning                                    |
| -------- | ------------------------------- | ------------------------------------------ |
| `PING`   | `PONG`                          | Health check                               |
| `UNLOCK` | `OK` / `ERR BUSY`               | Drive GPIO 16 HIGH for 5 s, then LOW       |
| other    | `ERR UNKNOWN`                   | Unrecognized command                       |

The backend ignores any line that does not start with `OK`, `PONG` or `ERR`, so
ESP32 boot messages on the same port are harmless.

## Troubleshooting

- **`could not open port` / `No such file or directory`**: wrong
  `DOOR_SERIAL_PORT`, board unplugged, or missing driver. Re-run the port
  lookup above.
- **`Resource busy` / `Permission denied`**: another program holds the port, or
  (Linux) you are not in the `dialout` group.
- **`/health` returns 504**: port opened but the board is not answering. Check
  that the firmware with the protocol above is flashed, then press the board's
  EN (reset) button.
- **`/unlock` returns 502 `ERR BUSY`**: the door is already in its 5 s unlock
  window; retry afterwards.
- The backend deliberately does not toggle DTR/RTS when opening the port, so
  starting it does not reset the board.
