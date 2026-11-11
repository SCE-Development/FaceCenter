import threading
import time

import serial

RESPONSES = ("OK", "PONG", "ERR")


class DoorError(Exception):
    pass


class DoorTimeout(DoorError):
    pass


class DoorSerial:
    """Line-based UART link to the door controller (one command, one reply)."""

    def __init__(self, port: str, baud: int = 115200, timeout: float = 2.0):
        self._port = port
        self._baud = baud
        self._timeout = timeout
        self._lock = threading.Lock()
        self._ser: serial.Serial | None = None

    def open(self) -> None:
        # Clear DTR/RTS before opening: asserting them resets the ESP32.
        ser = serial.Serial()
        ser.port = self._port
        ser.baudrate = self._baud
        ser.timeout = 0.1
        ser.dtr = False
        ser.rts = False
        ser.open()
        self._ser = ser

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None

    def send(self, command: str) -> str:
        """Send a command and return the controller's reply line."""
        if self._ser is None:
            raise DoorError("serial port not open")
        with self._lock:
            self._ser.reset_input_buffer()
            self._ser.write(f"{command}\n".encode())
            deadline = time.monotonic() + self._timeout
            while time.monotonic() < deadline:
                raw = self._ser.readline()
                reply = raw.decode(errors="ignore").strip()
                # Skip boot noise / partial garbage.
                if reply.startswith(RESPONSES):
                    return reply
            raise DoorTimeout(f"no reply to {command!r} within {self._timeout}s")

    def ping(self) -> bool:
        return self.send("PING") == "PONG"

    def unlock(self) -> None:
        reply = self.send("UNLOCK")
        if reply != "OK":
            raise DoorError(reply)
