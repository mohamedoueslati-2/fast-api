"""Execution boundary for FFmpeg and FFprobe."""

import subprocess


def run(command: list[str], *, check: bool = True, **options):
    return subprocess.run(command, check=check, **options)
