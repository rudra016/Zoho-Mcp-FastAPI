from langgraph.graph import StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from langchain_mcp_adapters.tools import load_mcp_tools
from config.settings import GEMINI_API_KEY
from static.literature import DEALS_DOC, CONTACTS_DOC, LEADS_DOC
from model.filter import Filter
from pydantic import TypeAdapter
import google.generativeai as genai
from openai import AsyncOpenAI
import json
import re
import os
from dotenv import load_dotenv

load_dotenv()
# Configure APIs
genai.configure(api_key=GEMINI_API_KEY)

client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)

MODULE_DOCS = {
    "Deals": DEALS_DOC,
    "Contacts": CONTACTS_DOC,
    'Leads': LEADS_DOC
}

# server_params = StdioServerParameters(
#     command="/Users/rudrakumar/.local/bin/uv",
#     args=["--directory", "/Users/rudrakumar/Downloads/MCP/Zoho-MCP/server", "run", "app/server.py"]
# )

MCP_SSE_URL = "https://zoho-mcp-server.onrender.com/sse"

async def reasoning_step(query: str):
    full_doc = f"""
    Zoho Module Literature:
    
    Deals:
    {DEALS_DOC}

    Contacts:
    {CONTACTS_DOC}

    Leads:
    {LEADS_DOC}

    User Query:
    {query}
    """.strip()

    prompt = (
        "You are an intelligent assistant that:\n"
        "1. Analyzes a user query against CRM module documentation.\n"
        "2. Determines the Zoho module the query targets (\"Deals\", \"Contacts\", etc.).\n"
        "3. Classifies the query as either \"simple\" or \"complex\".\n"
        "4. Rewrites the query using semantically rich field names from the module docs.\n\n"
        "Respond ONLY with JSON in the format:\n"
        '{\n  "module": "<ModuleName>",\n  "complexity": "<simple|complex>",\n  "semantic_query": "<Rewritten query>"\n}\n\n'
        "Module Documentation:\n"
        f"{full_doc}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes CRM queries and returns structured JSON responses."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        response_text = response.choices[0].message.content
        print("LLM Planning Output:", response_text)

        try:
            json_match = re.search(r"\{[\s\S]*\}", response_text)
            if not json_match:
                raise ValueError("No JSON found in LLM response")

            parsed = json.loads(json_match.group())
            return {
                "module": parsed.get("module", "Deals").strip().title(),
                "complexity": parsed.get("complexity", "simple").lower(),
                "semantic_query": parsed.get("semantic_query", query)
            }

        except Exception as e:
            print(f"Error parsing reasoning output: {e}")
            return {
                "module": "Deals",
                "complexity": "complex",
                "semantic_query": query
            }

    except Exception as e:
        print(f"Error in GPT-4 API call: {e}")
        return {
            "module": "Deals",
            "complexity": "simple",
            "semantic_query": query
        }

async def tool_use_step(query: str, module_name: str, complexity: str):
    async with sse_client(MCP_SSE_URL) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Session initialized")

            tools = await load_mcp_tools(session)
            print("Tools loaded")

            get_descriptor_tool = next(t for t in tools if t.name == "get_filter_descriptors")
            fetch_result_tool = next(t for t in tools if t.name == "fetch_zoho_results")
  
            descriptor_response_raw = await get_descriptor_tool.ainvoke({"question": query, "module": module_name, "complexity": complexity})
            try:
                descriptor_response = json.loads(descriptor_response_raw)
            except Exception as e:
                return {"error": f"Failed to parse descriptor response: {e}", "raw": descriptor_response_raw}
            
            field_hints = descriptor_response.get("pinecone_results", [])
            field_hints_joined = "\n\n".join(field_hints)
            try:
                llm_prompt = f"""
                    You are an assistant to help construct Zoho CRM search queries. Here is the user query:

                    {query}

                    Module: {module_name}

                    Rules: 
                    1. Use only the API names provided below. Do not guess or invent api names unless it is explicitly listed.
                    2. Do not Assume any api name by youself.
                    3. If the query references a field not available in the list, return:
                    {{ "error": "Relevant field not found in context." }}
                    4. Return only JSON, No Notes, No Explaination. 

                    Field Information (from vector search):
                    {field_hints_joined}
                    
                    {descriptor_response["descriptors"]}

                    {descriptor_response["format_instructions"]}
                """
                print("Prompt sent to LLM:\n", llm_prompt)
                
                filter_response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an assistant that helps construct Zoho CRM search queries."},
                        {"role": "user", "content": llm_prompt}
                    ],
                    temperature=0.3
                )
                
                filter_text = filter_response.choices[0].message.content
                print("LLM filter output:", filter_text)

                match = re.search(r"\{[\s\S]*\}", filter_text)
                if not match:
                    print("No valid JSON found in LLM response")
                    return {"error": "LLM did not return valid JSON.", "raw": filter_text}
                
                filters_dict = json.loads(match.group())
                print("Successfully parsed JSON from LLM response")

                adapter = TypeAdapter(list[Filter])
                filters = adapter.validate_python(filters_dict.get("filters", []))
                print("Successfully validated filters")

                criteria_parts = []
                for f in filters:
                    key = f.key
                    val = f.value.value
                    op = f.value.operator.value
                    val_str = ",".join(str(v) for v in val) if isinstance(val, list) else str(val)
                    criteria_parts.append(f"({key}:{op}:{val_str})")

                criteria_string = criteria_parts[0] if len(criteria_parts) == 1 else f"({' and '.join(criteria_parts)})"
                url = f"https://www.zohoapis.com/crm/v7/{module_name}/search?criteria={criteria_string}&per_page=50"
                print("Generated URL:", url)

                result = await fetch_result_tool.ainvoke({"url": url})
      
                print("Raw API response:", result)

                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError as e:
                        return {
                            "error": "Failed to parse JSON response",
                            "raw_response": result
                        }

                if result is None:
                    print("API returned None")
                    return {"error": "API returned None", "url": url}
                
                if isinstance(result, dict) and not result:
                    print("API returned empty dictionary")
                    return {"error": "API returned empty dictionary", "url": url}

                if isinstance(result, dict) and "error" in result:
                    print(f"API returned error: {result['error']}")
                    return {"error": f"API error: {result['error']}", "url": url}

                records = result.get("results", {}).get("data", [])

                if not records:
                    print("API response missing 'data' field or data is empty")
                    return {"error": "API response missing or empty 'data' field", "url": url, "raw_response": result}

                print("API call successful and data received")

                summary = f"""
                You are an assistant that summarizes Zoho CRM results for the user.
                User asked : "{query}"

                Here is the data:

                {json.dumps(records, indent=2)}

                Respond only in context of the user's question.
                """
               

                summary_response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an assistant that summarizes Zoho CRM results."},
                        {"role": "user", "content": summary}
                    ],
                    temperature=0.3
                )
                print("Successfully generated summary")
                summary_text = summary_response.choices[0].message.content

                return {
                    "response": summary_text,
                    "url": url,
                    "tool_output": result
                }

            except Exception as e:
                print(f"Error in API call or processing: {str(e)}")
                print(f"Error type: {type(e).__name__}")
                return {"error": f"Error in API call or processing: {str(e)}", "url": url}

async def build_graph():
    builder = StateGraph(dict)

    async def reasoning_node(state):
        planning = await reasoning_step(state["query"])
        state.update(planning)  
        return state

    async def tool_node(state):
        result = await tool_use_step(state["semantic_query"], state["module"], state["complexity"])
        return result

    builder.add_node("reasoning", reasoning_node)
    builder.add_node("tools", tool_node)

    builder.set_entry_point("reasoning")
    builder.add_edge("reasoning", "tools")
    builder.set_finish_point("tools")

    return builder.compile()
