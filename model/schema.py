from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: Optional[str] = None
    messages: Optional[list] = []
    tool_output: Optional[dict] = None
