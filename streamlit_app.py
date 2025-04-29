import streamlit as st
import requests
import os
import json
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

# Constants
CLIENT_ID = os.getenv("ZOHO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET")
AUTH_URL = "https://accounts.zoho.com/oauth/v2/auth"
TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
SCOPE = "ZohoCRM.settings.READ,ZohoCRM.modules.READ"
REDIRECT_URL = "https://mcp-cms-demo.streamlit.app/"  

FASTAPI_BACKEND_URL = "https://zoho-mcp-fastapi.onrender.com/save-token"
API_URL = "https://zoho-mcp-fastapi.onrender.com/chat"

# Load token if available
def load_token():
    if os.path.exists("token_store.json"):
        with open("token_store.json", "r") as f:
            return json.load(f)
    return None

# Save token
def save_token(token_data):
    with open("token_store.json", "w") as f:
        json.dump(token_data, f, indent=2)

token_available = False
# Handle OAuth callback
def handle_callback():
    query_params = st.query_params
    if "code" in query_params:
        code = query_params["code"]
        st.success(f"Authorization code received: {code}")
       
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URL,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }

        res = requests.post(TOKEN_URL, data=token_data)
        token_json = res.json()
        st.write(token_json)
        if "access_token" in token_json:
            try:
                res = requests.post(FASTAPI_BACKEND_URL, json=token_json)
                if res.status_code == 200:
                    st.success("Token successfully pushed to FastAPI server!")
                    st.rerun()
                else:
                    st.error("Failed to push token to FastAPI server.")
            except Exception as e:
                st.error(f"Error pushing token: {e}")
        else:
            st.error("Failed to retrieve access token.")

# Main App
def main():
    st.set_page_config(page_title="Zoho CRM LangGraph App", layout="wide")
    st.title("Zoho CRM (MCP) Demo")

    # token_data = load_token()
    token_available = False
    try:
        res = requests.get("https://zoho-mcp-fastapi.onrender.com/token")
        if res.status_code == 200 and "access_token" in res.json():
            token_available = True
    except Exception as e:
        st.error(f"Error checking token status: {e}")

    if not token_available:
        st.subheader("🔐 Authenticate with Zoho CRM")
        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "scope": SCOPE,
            "redirect_uri": REDIRECT_URL,
            "access_type": "offline",
            "prompt": "consent"
        }
        auth_url = f"{AUTH_URL}?{urlencode(params)}"

        st.markdown(f"📢 Please authenticate first using below link:")
        st.markdown(f"[🔗 Authenticate with Zoho]({auth_url})", unsafe_allow_html=True)

        handle_callback()

    else:
        st.success("✅ You are authenticated with Zoho CRM!")
        
        st.divider()
        st.header("Ask a question about Zoho CRM deals:")

        user_input = st.text_input("Enter your query:", "Show me deals greater than 10000")

        if st.button("Run Query"):
            with st.spinner("Querying Zoho MCP agent..."):
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

if __name__ == "__main__":
    main()
