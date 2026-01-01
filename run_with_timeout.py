#!/usr/bin/env python3
"""Wrapper to run commands with timeout."""
import subprocess
import sys
import signal
import os

def timeout_handler(signum, frame):
    print('\n⏱️  TIMEOUT: Command exceeded time limit')
    sys.exit(1)

if __name__ == "__main__":
    timeout_seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 120
    command = sys.argv[2:]
    
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(timeout_seconds)
    
    try:
        result = subprocess.run(command, check=False)
        signal.alarm(0)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        signal.alarm(0)
        sys.exit(1)


