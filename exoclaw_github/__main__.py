"""Entry point: python -m exoclaw_github"""

import asyncio
import sys

from exoclaw_github.app import run


def main() -> None:
    asyncio.run(run())
    import os
    os._exit(0)


if __name__ == "__main__":
    main()
