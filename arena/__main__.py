"""Local A-stage match/replay tools. No grading or unisolated bot execution."""
import argparse
import json
from pathlib import Path
import sys

from arena.core.replay import ReplayError
from arena.core.benchmark import run_benchmark, workload_digest
from arena.core.timing import Calibration
from arena.core.sandbox import InfrastructureError
from arena.games.outpost.replay import verify
from arena.games.outpost.mapgen import TYPES, generate, inspect_layout
from arena.games.outpost.maps import parse_map
from arena.match import play
from arena.check import check
from arena.tournament import run_tournament


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
    match.add_argument("--timing", type=Path, help="jobs=1 bench result; use its measured CPUs and scaled limits")
    match.add_argument("--sandbox", choices=("bwrap", "plain"), default="bwrap")
    inspect = commands.add_parser("check", help="validate/compile and run a few sandboxed protocol turns")
    inspect.add_argument("bot", type=Path)
    inspect.add_argument("--turns", type=int, default=5)
    inspect.add_argument("--out", type=Path, default=Path("runs/checks"))
    inspect.add_argument("--sandbox", choices=("bwrap", "plain"), default="bwrap")
    tournament = commands.add_parser("tournament", help="immutable swapped-seat batch with resume and raw results")
    tournament.add_argument("--bot", type=Path)
    tournament.add_argument("--opponents", nargs="+", type=Path)
    tournament.add_argument("--bots", nargs="+", type=Path, help="round-robin instead of a focal submission")
    tournament.add_argument("--include-self", nargs="*", default=[])
    tournament.add_argument("--maps", nargs="+", type=Path, required=True)
    tournament.add_argument("--out", type=Path, required=True)
    tournament.add_argument("--jobs", type=int, default=6)
    tournament.add_argument("--seeds", nargs=2, type=int, default=[17,29])
    tournament.add_argument("--reference", type=Path)
    timing_group = tournament.add_mutually_exclusive_group()
    timing_group.add_argument("--freeze-timing", action="store_true", help="benchmark once, then lock this calibration campaign's budgets")
    timing_group.add_argument("--fixed-timing", type=Path, help="reuse a baseline timing-lock.json; never benchmark again")
    tournament.add_argument("--resume", action="store_true")
    tournament.add_argument("--max-tasks", type=int, help="checkpoint after this many new tasks; retains incomplete status")
    tournament.add_argument("--sandbox", choices=("bwrap", "plain"), default="bwrap")
    bench = commands.add_parser("bench", help="measure fixed CPU work at the actual parallel load in bwrap")
    bench.add_argument("--jobs", type=int, default=6)
    bench.add_argument("--sandbox", choices=("bwrap", "plain"), default="bwrap")
    bench.add_argument("--samples", type=int, default=3)
    bench.add_argument("--reference", type=Path, help="idle benchmark result from the evaluation machine")
    bench.add_argument("--sweep", action="store_true", help="also measure 1/2/6/12/16/20 simultaneous workers")
    bench.add_argument("--out", type=Path, default=Path("runs/bench"))
    mapgen = commands.add_parser("mapgen", help="generate a deterministic symmetric map")
    mapgen.add_argument("--type", choices=TYPES, required=True)
    mapgen.add_argument("--size", type=int, default=32)
    mapgen.add_argument("--seed", type=int, required=True)
    mapcheck = commands.add_parser("mapcheck", help="check the default generation profile (not match eligibility)")
    mapcheck.add_argument("path", type=Path)
    replay = commands.add_parser("replay")
    replay.add_argument("action", choices=("verify", "show", "summary"))
    replay.add_argument("path", type=Path)
    replay.add_argument("--turn", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.command == "check":
            result = check(args.bot,args.out,turns=args.turns,sandbox=args.sandbox)
            print(json.dumps(result,indent=2))
            return 0 if result["passed"] else 1
        if args.command == "tournament":
            if args.bots and (args.bot or args.opponents):
                raise ValueError("choose --bots OR --bot/--opponents")
            if not args.bots and not (args.bot and args.opponents):
                raise ValueError("provide --bots or --bot with --opponents")
            sources = args.bots or [args.bot,*args.opponents]
            result = run_tournament(sources,args.maps,args.out,jobs=args.jobs,
                focus=None if args.bots else 0,include_self=args.include_self,seeds=args.seeds,
                reference=args.reference,sandbox=args.sandbox,resume=args.resume,max_tasks=args.max_tasks,
                freeze_timing=args.freeze_timing,fixed_timing=args.fixed_timing)
            print(json.dumps(result,indent=2))
            return 0 if result["status"]=="complete" else 2
        if args.command == "bench":
            result = run_benchmark(args.out, jobs=args.jobs, samples=args.samples,
                                   reference=args.reference, sweep=args.sweep, sandbox=args.sandbox)
            print(json.dumps(result, indent=2))
            return 0 if result["status"] == "complete" else 2
        if args.command == "mapgen":
            generated = generate(args.type, args.size, args.seed)
            print(generated.text, end="")
            print(json.dumps(generated.metadata()), file=sys.stderr)
            return 0
        if args.command == "mapcheck":
            result = inspect_layout(parse_map(args.path.read_text()))
            print(json.dumps(result, indent=2))
            return 0 if result["passed"] else 1
        if args.command == "match":
            private = Path(__file__).resolve().parents[1] / "private"
            if args.map.resolve().is_relative_to(private) and not args.out.resolve().is_relative_to(private):
                raise ValueError("hidden map artifacts must stay under private/")
            calibration = Calibration.load(args.timing, workload_digest(), jobs=1) if args.timing else None
            row = play([args.a, args.b], args.map.read_text(), args.out, args.seeds, calibration=calibration, sandbox=args.sandbox)
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
    except (OSError, ValueError, ReplayError, InfrastructureError) as error:
        print(f"arena: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
