#!/usr/bin/env python3
"""Launcher para Radio Agent."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from radio.app import main

if __name__ == "__main__":
    raise SystemExit(main())
