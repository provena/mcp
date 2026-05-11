"""Pytest hooks: disable server-side .env loading so tests stay isolated."""

import os

os.environ["PROVENA_MCP_NO_DOTENV"] = "1"
