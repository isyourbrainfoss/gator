"""Croc GUI – GTK4/Libadwaita frontend for croc.

Re-exports the main entry point for convenience.
"""

from .app import CrocGUI, main

__all__ = ["CrocGUI", "main"]
