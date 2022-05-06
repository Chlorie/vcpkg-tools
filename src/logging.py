import logging
import coloredlogs as clog


class _BraceMessage:
    def __init__(self, fmt: str, *args, **kwargs):
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return self.fmt.format(*self.args, **self.kwargs)


_logger: logging.Logger


def setup_logger():
    global _logger
    _logger = logging.getLogger("Updater")
    clog.install(level=logging.DEBUG,
                 logger=_logger,
                 fmt="[%(asctime)s %(name)s %(levelname)s] %(message)s")


def info(msg: str, *args, **kwargs) -> None:
    _logger.info(_BraceMessage(msg, *args, **kwargs))


def error(msg: str, *args, **kwargs) -> None:
    _logger.error(_BraceMessage(msg, *args, **kwargs))
    exit(1)
