from fastmcp import FastMCP
from .logging_conf import setup_logging

def create_server(name: str) -> FastMCP:
  setup_logging()
  mcp = FastMCP(name=name)
  return mcp