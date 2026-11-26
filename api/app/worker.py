"""Process pending CSV uploads in a loop or one CronJob pass."""

import argparse
import logging
import os
import signal
from time import sleep

from sqlalchemy.exc import SQLAlchemyError

from .database import SessionLocal
from .services import process_next_ingestion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
stop_requested = False


def request_stop(_signum: int, _frame: object) -> None:
    global stop_requested
    stop_requested = True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    interval = max(1, int(os.getenv("WORKER_INTERVAL_SECONDS", "5")))
    while not stop_requested:
        try:
            with SessionLocal() as session:
                processed = process_next_ingestion(session)
        except SQLAlchemyError:
            logger.exception("Database error during ingestion")
            if args.once:
                raise
            processed = False
        except Exception:
            logger.exception("Unexpected ingestion error")
            if args.once:
                raise
            processed = False
        if args.once and not processed:
            return
        if not processed:
            sleep(interval)


if __name__ == "__main__":
    main()
