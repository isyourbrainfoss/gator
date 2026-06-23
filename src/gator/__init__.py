"""Gator – GTK4/Libadwaita frontend for croc.

Re-exports the main entry point for convenience.
"""

from .app import GatorApp, main

__all__ = ["GatorApp", "main"]
