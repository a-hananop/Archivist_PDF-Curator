#!/usr/bin/env python3
"""
main.py
=======
Thin alias for app.py, provided so the project can be launched as either
`python app.py ...` or `python main.py ...` -- both are documented entry
points in the README.
"""

from app import main

if __name__ == "__main__":
    raise SystemExit(main())
