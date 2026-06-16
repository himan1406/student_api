import logging
import sys
import os


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ── Console handler (always on) ──────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ── Logtail handler (only if token is set) ───────────────────────────
    logtail_token = os.getenv("LOGTAIL_TOKEN")
    if logtail_token:
        try:
            from logtail import LogtailHandler
            logtail_handler = LogtailHandler(source_token=logtail_token)
            logtail_handler.setLevel(logging.DEBUG)
            logger.addHandler(logtail_handler)
        except ImportError:
            logger.warning("logtail-python not installed — remote logging disabled")

    return logger