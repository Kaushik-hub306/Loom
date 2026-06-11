"""Allow: python -m loom.mcp"""
import asyncio
from .server import main

asyncio.run(main())
