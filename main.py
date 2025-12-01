from __future__ import annotations

import threading
from queue import Queue

from listen import create_listener_app
from logger import logger
from message_router import MessageRouter
from settings import load_settings, SettingsError


def start_workers(queue: Queue, router: MessageRouter, worker_count: int) -> None:
    def worker_loop() -> None:
        while True:
            event = queue.get()
            try:
                router.process_event(event)
            except Exception as exc:  # pragma: no cover
                logger.error("Worker crashed: %s", exc)
            finally:
                queue.task_done()

    for idx in range(worker_count):
        thread = threading.Thread(target=worker_loop, name=f"bot-worker-{idx}", daemon=True)
        thread.start()
        logger.success("Started worker thread %s", thread.name)


def main() -> None:
    try:
        settings = load_settings()
    except SettingsError as exc:
        logger.error("Unable to start bot: %s", exc)
        return

    queue: Queue = Queue()
    router = MessageRouter(settings)
    worker_count = settings.get("workers", 4)
    start_workers(queue, router, worker_count)

    app = create_listener_app(queue, settings)
    host = settings.get("ip", "127.0.0.1")
    port = int(settings.get("listen", 8080))
    logger.info("HTTP listener starting on %s:%s", host, port)
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
