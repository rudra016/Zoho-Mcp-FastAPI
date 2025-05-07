import streamlit as st
import requests
import os
import json
import time
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

TOKEN_FILE = "token_store.json"

# Save token with timestamp
def save_token(token_data):
    token_data["timestamp"] = int(time.time())
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f, indent=2)

# Load token from local file
def load_token():
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    return None

# Refresh token using refresh_token
def refresh_access_token(refresh_token: str):
    refresh_data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    res = requests.post(TOKEN_URL, data=refresh_data)
    token_json = res.json()

    if "access_token" in token_json:
        if "refresh_token" not in token_json:
            token_json["refresh_token"] = refresh_token

        save_token(token_json)
        requests.post(FASTAPI_BACKEND_URL, json=token_json)
        return token_json
    else:
        raise Exception(f"Token refresh failed: {token_json}")

# Handle OAuth callback (when ?code=... is in URL)
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

        if "access_token" in token_json:
            try:
                save_token(token_json)
                requests.post(FASTAPI_BACKEND_URL, json=token_json)
                st.success("Token successfully pushed to FastAPI server!")
                st.rerun()
            except Exception as e:
                st.error(f"Error pushing token: {e}")
        else:
            st.error("Failed to retrieve access token.")

# Main Streamlit app
def main():
    st.set_page_config(page_title="Zoho CRM LangGraph App", layout="wide")
    st.title("Zoho CRM (MCP) Demo")

    token_available = False
    token_json = None

    try:
        res = requests.get("https://zoho-mcp-fastapi.onrender.com/token")
        if res.status_code == 200:
            token_json = res.json()
            if "access_token" in token_json and "refresh_token" in token_json:
                token_available = True

                issued_at = token_json.get("timestamp", int(time.time()))
                expires_in = token_json.get("expires_in", 3600)
                current_time = int(time.time())

                if current_time - issued_at >= expires_in:
                    try:
                        token_json = refresh_access_token(token_json["refresh_token"])
                        st.toast("🔄 Token auto-refreshed", icon="✅")
                    except Exception as e:
                        st.warning(f"Token refresh failed: {e}")
                        token_available = False
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

        st.markdown("Please authenticate first using the link below:")
        st.markdown(f"[Authenticate with Zoho]({auth_url})", unsafe_allow_html=True)

        handle_callback()
    else:
        st.success("You are authenticated with Zoho CRM!")

        st.button("Manually Refresh Token", on_click=lambda: refresh_access_token(token_json["refresh_token"]))

        st.divider()
        st.header("Ask a question about Zoho CRM:")

        user_input = st.text_input("Enter your query:", "Show me deals greater than 10000")

        if st.button("Run Query"):
            with st.spinner("Querying Zoho MCP agent..."):
                try:
                    response = requests.post(API_URL, json={"query": user_input})
                    response.raise_for_status()
                    data = response.json()

                    st.subheader("🧠 Final Response")
                    st.markdown(f"> {data.get('response', 'No final response returned')}")

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
