from dataclasses import dataclass
from argparse import ArgumentParser
from pathlib import Path


@dataclass
class Config:
    name: str
    ports_path: Path
    push: bool = False
    fix: bool = False

    @classmethod
    def from_cmd_args(cls) -> "Config":
        parser = ArgumentParser()
        parser.add_argument("name", type=str, help="Name of the port to update")
        parser.add_argument("-p", "--path", type=str,
                            help="Path to the ports repo, defaults to ./",
                            default="./")
        parser.add_argument("-a", "--auto-push", action="store_true", default=False,
                            help="Automatically push the updated port to the remote")
        parser.add_argument("-f", "--fix-failed-update", action="store_true", default=False,
                            help="Try to fix former failed port update by amending latest commit")
        args = parser.parse_args()
        return cls(args.name, Path(args.path), args.auto_push, args.fix_failed_update)
