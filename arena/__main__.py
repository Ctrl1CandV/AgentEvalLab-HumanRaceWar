"""Local A-stage match/replay tools. No grading or unisolated bot execution."""
import argparse
import json
from pathlib import Path
import sys

from arena.core.replay import ReplayError
from arena.games.outpost.replay import verify
from arena.match import play


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    match = commands.add_parser("match", help="run one bwrap-isolated Outpost match")
    match.add_argument("--a", type=Path, required=True)
    match.add_argument("--b", type=Path, required=True)
    match.add_argument("--map", type=Path, required=True)
    match.add_argument("--out", type=Path, default=Path("runs/matches"))
    match.add_argument("--seeds", nargs=2, type=int, default=[17, 29])
    match.add_argument("--show-stderr", action="store_true", help="display bounded bot stderr (also archived)")
    replay = commands.add_parser("replay")
    replay.add_argument("action", choices=("verify", "show", "summary"))
    replay.add_argument("path", type=Path)
    replay.add_argument("--turn", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.command == "match":
            private = Path(__file__).resolve().parents[1] / "private"
            if args.map.resolve().is_relative_to(private) and not args.out.resolve().is_relative_to(private):
                raise ValueError("hidden map artifacts must stay under private/")
            row = play([args.a, args.b], args.map.read_text(), args.out, args.seeds)
            print(json.dumps(row, indent=2))
            if args.show_stderr:
                for path in sorted(Path(row["directory"]).glob("p*/stderr.txt")):
                    print(f"[{path.parent.name} stderr]", file=sys.stderr)
                    # Escape control characters from untrusted terminal output.
                    text = path.read_text(errors="replace")
                    print("".join(c if c.isprintable() or c in "\n\t" else repr(c)[1:-1] for c in text), file=sys.stderr)
            return 0 if row["status"] == "complete" else 2
        result = verify(args.path, args.turn if args.action == "show" else None)
        if args.action == "show":
            print(result["board"])
        elif args.action == "summary":
            print(json.dumps(result["summary"], indent=2))
        else:
            print(json.dumps({k: result[k] for k in ("verified", "turns", "result")}, indent=2))
        return 0
    except (OSError, ValueError, ReplayError) as error:
        print(f"arena: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
