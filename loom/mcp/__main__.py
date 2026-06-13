"""Allow: python -m loom.mcp [--proxy]"""

import sys


def main():
    if "--proxy" in sys.argv:
        from .proxy import proxy_main
        proxy_main()
    else:
        from .server import main as server_main
        server_main()


if __name__ == "__main__":
    main()
