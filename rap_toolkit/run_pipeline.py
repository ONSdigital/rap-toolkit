from __future__ import annotations

from .runner import main

"""
This line of code establishes the function that must be called 
for the Pipeline to run. main() is parsed to SystemExit as once 
the main() function is run, this will then exit the system.
"""
if __name__ == "__main__":
    raise SystemExit(main())
