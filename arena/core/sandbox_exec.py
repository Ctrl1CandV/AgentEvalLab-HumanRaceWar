"""Trusted in-sandbox exec handshake; invoked with Python -I -S, not bot imports."""
import os
import resource
import sys

# Set the per-user-namespace task limit AFTER bwrap has created that namespace.
# Setting it on the host before bwrap forks would count unrelated host tasks.
mode, command = sys.argv[1], sys.argv[2:]
if mode == "runtime":
    resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
elif mode != "compile":
    raise RuntimeError("unknown trusted launch mode")
os.write(1, b"HRW_SANDBOX_STARTED\n")
try:
    os.execv(command[0], command)
except OSError as error:
    print(f"bot exec failed: {error.strerror}", file=sys.stderr)
    sys.exit(126)
