from langgraph.graph_agent import build_graph

async def run_agent(query: str):
    try:
        graph = await build_graph()
        result = await graph.ainvoke({"query": query})  
        return result
    except Exception as e:
        return {
            "response": "An error occurred.",
            "messages": [],
            "tool_output": {
                "error": str(e),
                "type": type(e).__name__
            }
        }

