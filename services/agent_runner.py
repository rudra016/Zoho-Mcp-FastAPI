from langgraph.graph_agent import build_graph

async def run_agent(query: str):
    graph = await build_graph()
    result = await graph.ainvoke({"query": query})  
    return result

