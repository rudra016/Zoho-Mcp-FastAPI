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
        "You are an intelligent CRM assistant that interprets user queries in natural language and identifies the relevant Zoho CRM module and query type.\n\n"
        "Your responsibilities:\n"
        "1. Analyze the user's query using the CRM module documentation.\n"
        "2. Identify the most appropriate module: Deals, Contacts, or Leads.\n"
        "3. Classify the query as either 'simple' or 'complex'.\n"
        "4. Rewrite the user query into a clear, well-structured paragraph (minimum 2–3 lines) that communicates the original intent accurately.\n\n"
        "Mandatory Guidelines for rewriting the query:\n"
        "- DO NOT add any information that is not explicitly or implicitly present in the original query.\n"
        "- Use CRM terminology and field names only if they are clearly mentioned or strongly implied.\n"
        "- DO NOT invent filters, stages, fields, or conditions that were not mentioned.\n"
        "- The rewritten query MUST be written as a paragraph of at least **two full sentences**.\n"
        "- Maintain the specificity and structure of the original query without oversimplifying or altering intent.\n"
        "- If the query is vague or high-level, retain that vagueness in the rewritten form.\n\n"
        "Respond ONLY with valid JSON in the following format:\n"
        '{\n'
        '  "module": "<ModuleName>",\n'
        '  "complexity": "<simple|complex>",\n'
        '  "semantic_query": "<A paragraph with at least 2 sentences explaining the user\'s intent>",\n'
        '}\n\n'
        "Module Documentation:\n"
        f"{full_doc}"
    )

    try:
        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": "You are a CRM expert that understands natural language queries, rewrites them into a paragraph form and maps them to appropriate modules."},
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
                "semantic_query": parsed.get("semantic_query", query),
            }

        except Exception as e:
            print(f"Error parsing reasoning output: {e}")
            return {
                "module": "Deals",
                "complexity": "simple",
                "semantic_query": query,
            }

    except Exception as e:
        print(f"Error in GPT-4.1-mini API call: {e}")
        return {
            "module": "Deals",
            "complexity": "simple",
            "semantic_query": query,
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
                    4. Follow the format Instructions strictly.
                    4. Return only JSON, No Notes, No Explaination. 

                    Api Fields Information (from vector search):
                    {field_hints_joined}

                    {descriptor_response["descriptors"]}

                    {descriptor_response["format_instructions"]}
                """
                print("Prompt sent to LLM:\n", llm_prompt)

                filter_response = await client.chat.completions.create(
                    model="gpt-4.1-mini",
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
                url = f"https://www.zohoapis.com/crm/v7/{module_name}/search?criteria={criteria_string}&per_page=15"
                print("Generated URL:", url)

                result = await fetch_result_tool.ainvoke({"url": url})

                # print("Raw API response:", result)

                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError as e:
                        return {
                            "error": "Failed to parse JSON response",
                            "raw_response": result
                        }

                return {
                    "records_response": result,
                    "url": url,
                    "semantic_query": query
                }

            except Exception as e:
                print(f"Error in API call or processing: {str(e)}")
                print(f"Error type: {type(e).__name__}")
                return {
                    "error": f"Error in API call or processing: {str(e)}",
                    "type": type(e).__name__
                }


async def summarization_step(data: dict):
    if data.get("error") or not data.get("records_response"):
        return data

    records = data["records_response"].get("results", {}).get("data", [])
    if not records:
        return {"response": "I couldn't find any matching records for your query.", **data}

  
    query = data["semantic_query"].lower()

    # Simple intent classification 
    is_search = any(t in query for t in ["show", "find", "list", "get", "search", "display"])
    is_count = any(t in query for t in ["how many", "count", "number of"])
    is_specific = any(t in query for t in ["who", "what", "which", "when", "where", "highest", "lowest", "top"])
    is_summary = any(t in query for t in ["summary", "overview", "insight", "analyze"])

    intent_flags = {
        "search": is_search,
        "count": is_count,
        "specific": is_specific,
        "summary": is_summary
    }

    summary_prompt = f"""
    You are a helpful CRM assistant that provides natural, conversational responses to user queries about Zoho CRM data.
    
    The user asked: "{data['semantic_query']}"
    
    Here is the relevant data:
    {json.dumps(records, indent=2)}

    Rules for your response:
    1. Be conversational and natural - don't sound like a robot listing data
    2. If the user is searching for specific information, focus on answering their question directly
    3. If they're looking for a list, organize the information in a way that makes sense for their query
    4. If they're asking about counts or numbers, provide the count in a natural way
    5. Use appropriate context from the query to frame your response
    6. Don't just list the data - explain what it means in relation to their question
    7. If there are multiple records, group or summarize them meaningfully
    8. Use natural language to describe relationships between data points
    9. Avoid technical jargon unless the user's query specifically asks for it

    Intent flags: {json.dumps(intent_flags)}

    Respond as if you're having a conversation with the user, not just listing data.
    """

    summary_response = await client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a helpful CRM assistant that provides natural, conversational responses about CRM data."},
            {"role": "user", "content": summary_prompt}
        ],
        temperature=0.7  
    )

    data["response"] = summary_response.choices[0].message.content
    return data


async def build_graph():
    builder = StateGraph(dict)

    async def reasoning_node(state):
        planning = await reasoning_step(state["query"])
        state.update(planning)
        return state

    async def tool_node(state):
        tool_data = await tool_use_step(state["semantic_query"], state["module"], state["complexity"])
        state.update(tool_data)
        return state

    async def summary_node(state):
        state = await summarization_step(state)
        return state

    builder.add_node("reasoning", reasoning_node)
    builder.add_node("tools", tool_node)
    builder.add_node("summary", summary_node)

    builder.set_entry_point("reasoning")
    builder.add_edge("reasoning", "tools")
    builder.add_edge("tools", "summary")
    builder.set_finish_point("summary")

    return builder.compile()
