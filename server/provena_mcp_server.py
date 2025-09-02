import sys
import os
import asyncio
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastmcp import FastMCP, Context
from provenaclient import ProvenaClient, Config
from provenaclient.auth import DeviceFlow
from provenaclient.auth.manager import Log
from provenaclient.utils.config import APIOverrides
from ProvenaInterfaces.RegistryAPI import NoFilterSubtypeListRequest, SortOptions

DOMAIN = os.getenv("PROVENA_DOMAIN", "dev.rrap-is.com")
REALM = os.getenv("PROVENA_REALM", "rrap")
CLIENT_ID = os.getenv("MCP_CLIENT_ID", "mcp-client")

API_OVERRIDES = APIOverrides(
    datastore_api_endpoint_override=os.getenv(
        "DATASTORE_API", "https://data-api.dev.rrap-is.com"),
    registry_api_endpoint_override=os.getenv(
        "REGISTRY_API", "https://registry-api.dev.rrap-is.com"),
    prov_api_endpoint_override=os.getenv(
        "PROV_API", "https://prov-api.dev.rrap-is.com"),
    search_api_endpoint_override=os.getenv(
        "SEARCH_API", "https://search-api.dev.rrap-is.com"),
    search_service_endpoint_override=os.getenv(
        "SEARCH_SERVICE", "https://search.dev.rrap-is.com"),
    handle_service_api_endpoint_override=os.getenv(
        "HANDLE_SERVICE", "https://handle.dev.rrap-is.com"),
    jobs_service_api_endpoint_override=os.getenv(
        "JOBS_SERVICE", "https://job-api.dev.rrap-is.com"),
)

mcp = FastMCP("ProvenaConnector")


def tokens_to_dict(tokens_obj) -> Dict[str, Any]:
    """Convert Tokens object to dictionary"""
    if tokens_obj is None:
        return {}

    if isinstance(tokens_obj, dict):
        return tokens_obj

    token_dict = {}

    for attr in ['access_token', 'refresh_token', 'id_token', 'token_type', 'expires_in', 'scope']:
        if hasattr(tokens_obj, attr):
            value = getattr(tokens_obj, attr)
            if value is not None:
                token_dict[attr] = value

    if hasattr(tokens_obj, '__dict__'):
        for key, value in tokens_obj.__dict__.items():
            if not key.startswith('_') and value is not None:
                token_dict[key] = value

    return token_dict


class JSONTokenManager:
    """Handles token storage in .tokens.json file"""

    def __init__(self):
        self.token_file = ".tokens.json"

    def save_tokens(self, tokens_obj) -> bool:
        """Save tokens to JSON file"""
        try:
            token_dict = tokens_to_dict(tokens_obj)

            if not token_dict or 'access_token' not in token_dict:
                return False

            token_dict['saved_at'] = datetime.now().isoformat()

            with open(self.token_file, 'w') as f:
                json.dump(token_dict, f, indent=2)
            return True

        except Exception as e:
            print(f"Error saving tokens: {e}")
            return False

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        """Load tokens from JSON file"""
        try:
            if not os.path.exists(self.token_file):
                return None

            with open(self.token_file, 'r') as f:
                tokens = json.load(f)
            return tokens

        except Exception as e:
            print(f"Error loading tokens: {e}")
            self.clear_tokens()
            return None

    def clear_tokens(self):
        print("Noop")


class ProvenaAuthManager:
    """Manages authentication state and Provena client connections"""

    def __init__(self):
        self.config = Config(
            domain=DOMAIN,
            realm_name=REALM,
            api_overrides=API_OVERRIDES
        )
        self.token_manager = JSONTokenManager()
        self._client: Optional[ProvenaClient] = None
        self._auth: Optional[DeviceFlow] = None

    def _has_stored_tokens(self) -> bool:
        """Check if we have stored tokens"""
        tokens = self.token_manager.load_tokens()
        return tokens is not None and 'access_token' in tokens

    async def authenticate(self) -> Dict[str, Any]:
        """Handle authentication (login)"""
        try:
            if self._has_stored_tokens():
                return {"status": "already_authenticated", "message": "Already authenticated"}

            self._client = None
            self._auth = None

            self._auth = DeviceFlow(
                config=self.config,
                client_id=CLIENT_ID,
                log_level=Log.ERROR
            )

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._auth.start_device_flow)

            if hasattr(self._auth, 'tokens') and self._auth.tokens:
                if self.token_manager.save_tokens(self._auth.tokens):
                    if hasattr(self._auth, 'file_name') and os.path.exists(self._auth.file_name):
                        os.remove(self._auth.file_name)
                    return {
                        "status": "authenticated",
                        "message": "Authentication completed successfully"
                    }
                else:
                    return {
                        "status": "error",
                        "error": "Authentication completed but failed to save tokens"
                    }
            else:
                return {
                    "status": "error",
                    "error": "Device flow completed but no tokens were received"
                }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def get_client(self) -> Optional[ProvenaClient]:
        """Get authenticated Provena client"""
        if not self._has_stored_tokens():
            return None

        if not self._client:
            try:
                stored_tokens = self.token_manager.load_tokens()
                if not stored_tokens:
                    return None

                if not self._auth:
                    self._auth = DeviceFlow(
                        config=self.config,
                        client_id=CLIENT_ID,
                        log_level=Log.ERROR

                    )

                self._client = ProvenaClient(
                    config=self.config, auth=self._auth)

            except Exception as e:
                print(f"Failed to create Provena client: {e}")
                self.token_manager.clear_tokens()
                self._auth = None
                return None

        return self._client

    def logout(self):
        """Clear all authentication state"""
        if self._auth and hasattr(self._auth, 'file_name') and os.path.exists(self._auth.file_name):
            os.remove(self._auth.file_name)

        self._client = None
        self._auth = None
        self.token_manager.clear_tokens()


auth_manager = ProvenaAuthManager()


@mcp.tool()
async def check_authentication_status(ctx: Context) -> Dict[str, Any]:
    """Check current authentication status with Provena."""
    has_tokens = auth_manager._has_stored_tokens()

    status = {
        "authenticated": has_tokens,
        "message": "Authenticated and ready" if has_tokens else "Not authenticated - use login_to_provena"
    }

    await ctx.info(status["message"])
    return status


@mcp.tool()
async def list_datasets(ctx: Context, page_size: int, pagination_key: Dict[str, Any] | None, sort_by: SortOptions) -> Dict[str, Any]:
    """Check current authentication status with Provena."""
    has_tokens = auth_manager._has_stored_tokens()

    status = {
        "authenticated": has_tokens,
        "message": "Authenticated and ready" if has_tokens else "Not authenticated - use login_to_provena"
    }

    client: ProvenaClient = auth_manager.get_client()
    response = await client.datastore.list_datasets(NoFilterSubtypeListRequest(page_size=page_size, pagination_key=pagination_key, sort_by=sort_by))

    return response.model_dump()


@mcp.tool()
async def login_to_provena(ctx: Context) -> Dict[str, Any]:
    """
    Authenticate with Provena using device flow.
    Opens browser automatically and completes authentication.
    """
    await ctx.info("Starting Provena authentication...")

    auth_result = await auth_manager.authenticate()

    if auth_result["status"] == "authenticated":
        await ctx.info("Authentication completed successfully!")
    elif auth_result["status"] == "already_authenticated":
        await ctx.info("Already authenticated")
    else:
        await ctx.error(f"Authentication failed: {auth_result.get('error', 'Unknown error')}")

    return auth_result


@mcp.tool()
async def logout_from_provena(ctx: Context) -> Dict[str, str]:
    """Logout from Provena and clear authentication state."""
    auth_manager.logout()
    await ctx.info("Logged out from Provena")
    return {"message": "Logged out successfully"}


async def require_authentication(ctx: Context) -> Optional[ProvenaClient]:
    """Helper to ensure authentication and return client"""
    client = auth_manager.get_client()
    if not client:
        await ctx.error("Authentication required. Use login_to_provena first.")
        return None
    return client


@mcp.tool()
async def test_authenticated_action(ctx: Context) -> Dict[str, Any]:
    """Test tool to verify authentication is working."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}

    try:
        await ctx.info("Access granted. You are authenticated with Provena.")
        return {"status": "success", "message": "Authenticated and ready to use Provena client."}
    except Exception as e:
        await ctx.error(f"Client test failed: {str(e)}")
        return {"status": "error", "message": f"Client error: {str(e)}"}


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=5000)
    else:
        mcp.run()
