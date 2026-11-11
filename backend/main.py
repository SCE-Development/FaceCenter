import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.concurrency import run_in_threadpool

from door_serial import DoorError, DoorSerial, DoorTimeout

SERIAL_PORT = os.environ.get("DOOR_SERIAL_PORT", "/dev/tty.usbserial-0001")
API_KEY = os.environ.get("DOOR_API_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not API_KEY:
        raise RuntimeError("DOOR_API_KEY must be set")
    door = DoorSerial(SERIAL_PORT)
    door.open()
    app.state.door = door
    try:
        yield
    finally:
        door.close()


app = FastAPI(lifespan=lifespan)


def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not API_KEY or not secrets.compare_digest(x_api_key.encode(), API_KEY.encode()):
        raise HTTPException(status_code=401, detail="invalid API key")


async def call_door(fn):
    try:
        return await run_in_threadpool(fn)
    except DoorTimeout:
        raise HTTPException(status_code=504, detail="door controller timed out")
    except DoorError as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/health")
async def health():
    door: DoorSerial = app.state.door
    await call_door(door.ping)
    return {"status": "ok"}


@app.post("/unlock", dependencies=[Depends(require_api_key)])
async def unlock():
    door: DoorSerial = app.state.door
    await call_door(door.unlock)
    return {"status": "unlocked", "relock_in_seconds": 5}
