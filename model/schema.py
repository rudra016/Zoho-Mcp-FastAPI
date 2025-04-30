from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class QueryRequest(BaseModel):
    query: str

class QueryResponse(BaseModel):
    response: Optional[str] = None
    messages: List[Dict[str, Any]] = []
    tool_output: Dict[str, Any] = {}
