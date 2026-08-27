"""Tiny launcher so we can run Plate via `python run_plate.py`."""
import uvicorn

from gimbal_plate.http.app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
