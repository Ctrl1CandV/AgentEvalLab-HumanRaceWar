"""Submission validation and a short, real sandbox protocol smoke test."""
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from arena.core.resources import CpuLease
from arena.core.sandbox import Bubblewrap, ROOT, prepare
from arena.core.transport import Connection, exchange
from arena.core.runner import cpu_hard_limit
from arena.games.outpost import Outpost


def check(source: Path, out: Path, *, turns=5, sandbox='bwrap', map_path=None):
    if type(turns) is not int or not 1 <= turns <= 300: raise ValueError('check turns must be in [1,300]')
    if sandbox not in ('bwrap','plain'): raise ValueError('unknown backend')
    private = ROOT/'private'
    map_path = map_path or ROOT/'maps/scrimmage/open-01.map'
    if any(p.resolve().is_relative_to(private) for p in (source,map_path)) and not out.resolve().is_relative_to(private):
        raise ValueError('hidden check artifacts must stay private')
    directory = out.resolve()/uuid4().hex; directory.mkdir(parents=True)
    report = {'schemaVersion':1,'scope':'short protocol check, not a scored match','passed':False,
              'startedAt':datetime.now(timezone.utc).isoformat(),'directory':str(directory),'sandbox':sandbox,'turns':0}
    connection = None
    try:
        with ExitStack() as stack:
            lease = stack.enter_context(CpuLease(1))
            if sandbox == 'bwrap': launcher = Bubblewrap()
            else:
                from arena.core.plain import Plain
                launcher = Plain()
            launcher.cpus = lease.cpus
            bot = prepare(source,directory/'bot',launcher,lease.cpus[0])
            report.update(sha256=bot.digest,compileFault=bot.compile_fault,validationError=bot.validation_error)
            if not bot.compile_fault:
                game = Outpost(); state = game.new_match(map_path.read_text(),{},[17,29])
                connection = Connection(bot,launcher,lease.cpus[0],cpu_hard_limit(game.limits,300))
                stack.callback(connection.close)
                replies = []
                reply = exchange([connection],[game.init_message(state,0)],[2000],[2500],b'READY')[0]
                replies.append(reply.record()); bank = 3000_000_000
                warnings = []
                if not reply.fault:
                    for _ in range(turns):
                        message = [f'BANK {bank//1_000_000}' if line.startswith('BANK ') else line for line in game.observation(state,0)]
                        allowed = 100+bank/1_000_000
                        reply = exchange([connection],[message],[allowed],[allowed+500])[0]
                        replies.append(reply.record()); bank -= max(0,reply.cpu_ns-100_000_000)
                        if reply.fault: break
                        packet, invalid = game.parse_orders(state,0,reply.lines)
                        warnings += [{'line':w.line,'code':w.code} for w in invalid]
                        game.step(state,[packet,game.parse_orders(state,1,[])[0]])
                        report['turns'] += 1
                        if game.result(state): break
                report.update(fault=reply.fault,warnings=warnings,passed=not reply.fault and not warnings,replies=replies)
    except Exception as error:
        report.update(passed=False,status='infra_error',error=type(error).__name__,message=str(error))
    finally:
        (directory/'check.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
