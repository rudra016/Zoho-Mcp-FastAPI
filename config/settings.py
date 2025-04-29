import os
from dotenv import load_dotenv

load_dotenv()

MCP_TOOL_DIRECTORY = os.getenv("MCP_TOOL_DIRECTORY")  
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
