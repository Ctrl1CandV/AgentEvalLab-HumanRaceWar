"""Direct launch ONLY inside an operator-provided outer sandbox.

The fixed read-only attestation mount is an integration contract, not sandbox
creation or remote attestation. Never silently fall back from bwrap to plain.
"""
import ctypes
import json
import os
from pathlib import Path
import resource
import subprocess
import sys

from .sandbox import ENV, InfrastructureError
from .seccomp import runtime_filter

MARKER = Path('/hrw-outer-sandbox.json')


def install_filter():
    class Program(ctypes.Structure):
        _fields_ = [('length', ctypes.c_ushort), ('filter', ctypes.c_void_p)]
    policy = runtime_filter()
    data = ctypes.create_string_buffer(policy)
    program = Program(len(policy)//8, ctypes.addressof(data))
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong]
    if libc.prctl(38, 1, None, 0, 0) or libc.prctl(22, 2, ctypes.byref(program), 0, 0):
        raise OSError(ctypes.get_errno(), 'cannot install plain runtime filter')


class Plain:
    name = 'plain'

    def __init__(self):
        if not MARKER.is_file() or os.geteuid() == 0:
            raise InfrastructureError('plain requires a non-root outer sandbox and /hrw-outer-sandbox.json attestation')
        if not os.statvfs(MARKER).f_flag & os.ST_RDONLY:
            raise InfrastructureError('outer-sandbox attestation must be a read-only mount')
        contract = json.loads(MARKER.read_text())
        if contract != {'version': 1, 'network': 'disabled', 'files': 'isolated', 'purpose': 'local-tools-only'}:
            raise InfrastructureError('invalid outer-sandbox contract')
        interfaces = {line.split(':',1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]}
        if interfaces != {'lo'}:
            raise InfrastructureError('plain requires an isolated loopback-only network namespace')
        self.runtime = Path(sys.base_prefix).resolve()
        self.python_name = Path(sys.executable).resolve().name
        self.cpus = sorted(os.sched_getaffinity(0))

    def launch(self, bot, sdk, command, cpu, *, build=None, cpu_seconds=40,
               stdout=subprocess.PIPE, stderr=subprocess.PIPE, writable_build=False):
        if cpu not in self.cpus: raise InfrastructureError('CPU outside allocation')
        paths = {'/runtime': self.runtime, '/bot': Path(bot), '/sdk': Path(sdk)}
        if build is not None: paths['/build'] = Path(build)
        def translate(arg):
            if arg == '-I/sdk': return '-I'+str(sdk)
            for prefix, path in paths.items():
                if arg == prefix or arg.startswith(prefix+'/'): return str(path)+arg[len(prefix):]
            return arg
        def limits():
            os.sched_setaffinity(0, {cpu})
            for kind, value in ((resource.RLIMIT_AS, (2048 if writable_build else 512)*1024**2),
                                (resource.RLIMIT_CPU, cpu_seconds), (resource.RLIMIT_NOFILE,64),
                                (resource.RLIMIT_FSIZE,16*1024**2),(resource.RLIMIT_CORE,0)):
                resource.setrlimit(kind,(value,value))
            if not writable_build: install_filter()
        env = {**ENV, 'PYTHONPATH':str(sdk)}
        if writable_build:
            assert build is not None
            scratch = Path(build)/'tmp'; scratch.mkdir(exist_ok=True)
            env.update(TMPDIR=str(scratch), TMP=str(scratch), TEMP=str(scratch))
        mode = 'compile' if writable_build else 'runtime'
        args = [str(self.runtime/'bin'/self.python_name), '-I','-S',
                str(Path(__file__).with_name('sandbox_exec.py')),mode,*map(translate,command)]
        try:
            return subprocess.Popen(args,cwd=bot,stdin=subprocess.PIPE,stdout=stdout,stderr=stderr,
                                    env=env,close_fds=True,start_new_session=True,preexec_fn=limits)
        except (OSError,subprocess.SubprocessError) as error:
            raise InfrastructureError('plain launch failed inside outer sandbox') from error
