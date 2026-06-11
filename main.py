#!/usr/bin/env python3
"""Convenience entry point — delegates to the img_converter package."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from img_converter.__main__ import main

if __name__ == "__main__":
    main()
