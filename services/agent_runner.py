from langgraph.graph_agent import build_graph

async def run_agent(query: str):
    try:
        graph = await build_graph()
        result = await graph.ainvoke({"query": query})  
        return {
            "response": result.get("response"),
            "messages": [],  
            "tool_output": {
                "module": result.get("module"),
                "complexity": result.get("complexity"),
                "semantic_query": result.get("semantic_query"),
                "url": result.get("url"),
                "records_response": result.get("records_response"),
            }
        }

    except Exception as e:
        return {
            "response": "An error occurred.",
            "messages": [],
            "tool_output": {
                "error": str(e),
                "type": type(e).__name__
            }
        }

