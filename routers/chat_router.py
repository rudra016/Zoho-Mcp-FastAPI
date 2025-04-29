from fastapi import APIRouter
from model.schema import QueryRequest, QueryResponse
from services.agent_runner import run_agent
import json

router = APIRouter()

@router.post("/chat", response_model=QueryResponse)
async def chat_endpoint(request: QueryRequest):
    result = await run_agent(request.query)

    tool_output = result.get("tool_output", {})
    print(tool_output)
    if isinstance(tool_output, str):
        try:
            tool_output = json.loads(tool_output)
        except json.JSONDecodeError:
            tool_output = {"raw": tool_output, "error": "Failed to parse tool_output JSON"}

    return QueryResponse(
        response=result.get("response"),
        messages=result.get("messages", []),
        tool_output=tool_output
    )
