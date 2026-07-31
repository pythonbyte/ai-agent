"""Compatibility shim — prefer ``ai_agent.entrypoints.cli``."""

from ai_agent.entrypoints.cli import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
