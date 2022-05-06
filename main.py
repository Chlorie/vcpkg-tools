from src.logging import setup_logger
from src.config import Config
from src.updater import Updater


def main():
    setup_logger()
    config = Config.from_cmd_args()
    updater = Updater(config)
    updater.run()


if __name__ == "__main__":
    main()
