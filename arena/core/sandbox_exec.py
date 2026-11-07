"""Trusted in-sandbox exec handshake; invoked with Python -I -S, not bot imports."""
import os
import sys

os.write(1, b"HRW_SANDBOX_STARTED\n")
try:
    os.execv(sys.argv[1], sys.argv[1:])
except OSError as error:
    print(f"bot exec failed: {error.strerror}", file=sys.stderr)
    sys.exit(126)
