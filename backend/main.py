import asyncio
import threading

from backend.db import get_conn, init_db
from backend.logger import SessionLogger
from backend.ble_client import DualBLEManager
from backend.api import create_app
from backend.config import DB_PATH

def _run_ble(loop: asyncio.AbstractEventLoop, logger) -> None:
    asyncio.set_event_loop(loop)
    manager = DualBLEManager(logger)
    loop.run_until_complete(manager.run())

def main() -> None:
    conn   = get_conn(DB_PATH)
    init_db(conn)
    logger = SessionLogger(conn)

    loop = asyncio.new_event_loop()
    ble_thread = threading.Thread(
        target=_run_ble, args=(loop, logger), daemon=True
    )
    ble_thread.start()

    app = create_app(db_path=DB_PATH)
    print("PostureMax backend running at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, use_reloader=False)

if __name__ == "__main__":
    main()
