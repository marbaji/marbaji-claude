import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ralph-stack")
    parser.add_argument("command", choices=["run", "resume", "status", "report", "stop"])
    parser.add_argument("plan", nargs="?")
    args = parser.parse_args(argv)
    print(f"ralph-stack {args.command} (not yet implemented)", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
