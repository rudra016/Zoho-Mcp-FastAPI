import streamlit as st
import requests
import json

st.set_page_config(page_title="Zoho CRM LangGraph Chat", layout="wide")
st.title("💬 Zoho CRM (MCP)")


API_URL = "http://localhost:8000/chat" 

# User input
user_input = st.text_input("Ask something about Zoho CRM deals:", "Show me deals greater than 10000")

if st.button("Run Query"):
    with st.spinner("Querying MCP agent and Zoho..."):
        try:
            response = requests.post(API_URL, json={"query": user_input})
            response.raise_for_status()
            data = response.json()

            st.subheader("🧠 Final Response")
            st.markdown(f"> {data.get('response', 'No final response returned')} ")

            st.divider()
            st.subheader("🧪 Debug Info")

            if "messages" in data:
                for msg in data["messages"]:
                    role = msg.get("role", "system")
                    content = msg.get("content", "[no content]")
                    st.markdown(f"**{role.title()}:** {content}")

            if "tool_output" in data:
                st.write("**Tool Output:**")
                st.json(data["tool_output"])

        except requests.exceptions.RequestException as e:
            st.error(f"Request failed: {str(e)}")
        except json.JSONDecodeError:
            st.error("Invalid JSON response from the API.")