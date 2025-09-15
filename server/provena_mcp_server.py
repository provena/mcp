import sys
import os
import asyncio
import json
from typing import Optional, Dict, Any
from typing import Tuple

from fastmcp import FastMCP, Context
from provenaclient import ProvenaClient, Config
from provenaclient.auth import DeviceFlow
from provenaclient.auth.manager import Log
from provenaclient.utils.config import APIOverrides

DOMAIN = os.getenv("PROVENA_DOMAIN", "dev.rrap-is.com")
REALM = os.getenv("PROVENA_REALM", "rrap")
CLIENT_ID = os.getenv("MCP_CLIENT_ID", "mcp-client")

API_OVERRIDES = APIOverrides(
    datastore_api_endpoint_override=os.getenv("DATASTORE_API", "https://data-api.dev.rrap-is.com"),
    registry_api_endpoint_override=os.getenv("REGISTRY_API", "https://registry-api.dev.rrap-is.com"),
    prov_api_endpoint_override=os.getenv("PROV_API", "https://prov-api.dev.rrap-is.com"),
    search_api_endpoint_override=os.getenv("SEARCH_API", "https://search.dev.rrap-is.com"),
    search_service_endpoint_override=os.getenv("SEARCH_SERVICE", "https://search.dev.rrap-is.com"),
    handle_service_api_endpoint_override=os.getenv("HANDLE_SERVICE", "https://handle.dev.rrap-is.com"),
    jobs_service_api_endpoint_override=os.getenv("JOBS_SERVICE", "https://job-api.dev.rrap-is.com"),
)

mcp = FastMCP("ProvenaConnector")

# @mcp.prompt("deep_lineage_investigation")
# def deep_lineage_investigation_prompt(root_id: str) -> str:
#     """Prompt for autonomous deep lineage exploration of a registry/dataset handle.

#     The agent should:
#     1. Fetch the item details for root_id.
#     2. Explore upstream and downstream lineage (multiple hops) until terminal nodes.
#     3. For each discovered node, fetch its details using the ids obtained to build a complete picture.
#     4. Produce a comprehensive decision-maker report tailored for reef stakeholders, clearly explaining provenance, inputs, outputs, transformations, and any models/templates.
#     5. Prefix every handle reference with https://hdl.handle.net/ so it is clickable.
#     6. Avoid needless repetition; group similar nodes; highlight gaps or missing links.
#     7. Provide a concise executive summary, then a detailed section, and finally a risk/uncertainty notes section.
#     """
#     return (
#         "As our lead provenance investigator, you take a thorough and relentless approach to fully exploring the graph and its nodes to deeply understand datasets, their inputs, models, templates, upstream and downstream. "
#         "Today you are going to investigate {id}. Start by fetching its details, then explore upstream and downstream. For all connected nodes, use the ID's obtained to fetch their details, and explore them further in that direction. Repeat this process until you reach terminal nodes and have explored all connections. "
#         "Once you have all of this data, summarise it into a comprehensive report. Tailor this report for a decision maker on the reef who is looking to deeply understand the lineage of this dataset. "
#         "Prefix handles, as you refer to them in the report, with the prefix https://hdl.handle.net/ so that they are directly clickable. "
#         "Provide: Executive Summary; Lineage Overview; Upstream Sources; Transformation & Processing Steps; Downstream Dependencies & Impacts; Data Quality & Gaps; Risk & Uncertainty; Recommended Follow-up Actions. "
#     ).format(id=root_id)

class ProvenaAuthManager:
    """Manages authentication state and Provena client connections"""
    
    def __init__(self):
        self.config = Config(
            domain=DOMAIN, 
            realm_name=REALM,
            api_overrides=API_OVERRIDES
        )
        self._client: Optional[ProvenaClient] = None
        self._auth: Optional[DeviceFlow] = None
    
    def _get_access_token(self) -> Optional[str]:
        """Safely extract an access token string from the auth tokens if available."""
        if not self._auth or not hasattr(self._auth, "tokens"):
            return None
        tokens = self._auth.tokens
        if not tokens:
            return None
        try:
            if isinstance(tokens, dict):
                return tokens.get("access_token") or tokens.get("access") or tokens.get("accessToken")
            return getattr(tokens, "access_token", None) or getattr(tokens, "access", None) or getattr(tokens, "accessToken", None)
        except Exception:
            return None

    def _is_authenticated(self) -> bool:
        """Check if we have a usable access token (non-empty, JWT-like)."""
        access = self._get_access_token()
        return bool(access) and access.count(".") == 2
    
    async def authenticate(self) -> Dict[str, Any]:
        """Handle authentication (login)"""
        try:
            if self._is_authenticated():
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
            
            if self._is_authenticated():
                return {
                    "status": "authenticated",
                    "message": "Authentication completed successfully"
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
        if not self._is_authenticated():
            return None
        
        if not self._client:
            try:
                self._client = ProvenaClient(config=self.config, auth=self._auth)
            except Exception as e:
                print(f"Failed to create Provena client: {e}")
                self._auth = None
                return None
        
        return self._client
    
    def logout(self):
        """Clear all authentication state"""
        if self._auth and hasattr(self._auth, 'file_name') and os.path.exists(self._auth.file_name):
            try:
                os.remove(self._auth.file_name)
            except Exception:
                pass
        
        self._client = None
        self._auth = None

auth_manager = ProvenaAuthManager()

def _dump(obj):
    """Uniform pydantic v2 serialisation helper returning JSON-safe primitives.
    Supports model instances, lists/tuples of models, or already-serialisable values."""
    if isinstance(obj, (list, tuple)):
        return [_dump(o) for o in obj]
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj

# @mcp.tool()
# async def check_authentication_status(ctx: Context) -> Dict[str, Any]:
#     """Check current authentication status with Provena."""
#     is_authenticated = auth_manager._is_authenticated()
    
#     status = {
#         "authenticated": is_authenticated,
#         "message": "Authenticated and ready" if is_authenticated else "Not authenticated - use login_to_provena"
#     }
    
#     await ctx.info(status["message"])
#     return status

# @mcp.tool()
# async def diagnose_auth(ctx: Context) -> Dict[str, Any]:
#     """Return non-sensitive diagnostics about current auth tokens (helps debug 401s)."""
#     tokens_present = bool(getattr(auth_manager._auth, "tokens", None)) if auth_manager._auth else False
#     access = auth_manager._get_access_token()
#     access_preview = None
#     if access:
#         access_preview = f"{access[:10]}..."
#     header = payload = None
#     try:
#         if access and access.count(".") == 2:
#             import json as _json
#             import base64 as _b64

#             def _b64url_decode(s: str) -> bytes:
#                 pad = '=' * (-len(s) % 4)
#                 return _b64.urlsafe_b64decode(s + pad)

#             h, p, _sig = access.split(".")
#             try:
#                 header = _json.loads(_b64url_decode(h))
#             except Exception:
#                 header = {"_error": "failed to decode"}
#             try:
#                 payload = _json.loads(_b64url_decode(p))
#             except Exception:
#                 payload = {"_error": "failed to decode"}
#     except Exception:
#         pass
#     roles_info = {}
#     try:
#         if isinstance(payload, dict):
#             ra = payload.get("resource_access") or {}
#             if isinstance(ra, dict):
#                 for client_id, obj in ra.items():
#                     if isinstance(obj, dict):
#                         r = obj.get("roles")
#                         if isinstance(r, list):
#                             if client_id in {"registry-api", "data-store-api", "prov-api", "search", "handle", "job-api", CLIENT_ID}:
#                                 roles_info[client_id] = r
#     except Exception:
#         pass

#     details = {
#         "authenticated": auth_manager._is_authenticated(),
#         "tokens_present": tokens_present,
#         "access_token_present": bool(access),
#         "access_token_preview": access_preview,
#         "jwt_like": (access.count(".") == 2) if access else False,
#         "client_id": CLIENT_ID,
#         "realm": REALM,
#         "domain": DOMAIN,
#         "claims": {
#             "header_typ": (header or {}).get("typ") if isinstance(header, dict) else None,
#             "header_alg": (header or {}).get("alg") if isinstance(header, dict) else None,
#             "iss": (payload or {}).get("iss") if isinstance(payload, dict) else None,
#             "aud": (payload or {}).get("aud") if isinstance(payload, dict) else None,
#             "azp": (payload or {}).get("azp") if isinstance(payload, dict) else None,
#             "exp": (payload or {}).get("exp") if isinstance(payload, dict) else None,
#             "resource_access": roles_info or None,
#         }
#     }
#     await ctx.info("Auth diagnostics generated.")
#     return details

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


@mcp.tool()
async def search_registry(ctx: Context, query: str, limit: Optional[int] = 25, subtype_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Search the Provena registry for items matching a query.
    
    Args:
        query: The search query string
        limit: Maximum number of results to return (default: 25)
        subtype_filter: Filter by item subtype (ORGANISATION, PERSON, DATASET...)
    
    Returns:
        Dictionary containing search results with ids and scores
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryModels import ItemSubType
        
        subtype_enum = None
        if subtype_filter:
            try:
                subtype_enum = ItemSubType(subtype_filter.upper())
            except ValueError:
                valid_subtypes = [item.value for item in ItemSubType]
                return {
                    "status": "error", 
                    "message": f"Invalid subtype_filter. Valid options: {valid_subtypes}"
                }
        
        await ctx.info(f"Searching registry for '{query}' with limit {limit}")
        
        results = await client.search.search_registry(
            query=query,
            limit=limit,
            subtype_filter=subtype_enum
        )
        
        if not results.status.success:
            await ctx.error(f"Search failed: {results.status.details}")
            return {"status": "error", "message": results.status.details}
        
        search_results = []
        if results.results:
            for result in results.results:
                # Fetch the full item and dump all its information
                try:
                    item_result = await client.registry.general_fetch_item(id=result.id)
                    if item_result.status.success and item_result.item:
                        item_data = _dump(item_result.item)
                        # Add the search score to the dumped data
                        item_data["search_score"] = result.score
                        search_results.append(item_data)
                    else:
                        # Fallback if fetch fails
                        search_results.append({
                            "id": result.id,
                            "search_score": result.score,
                            "error": "Unable to fetch full item details"
                        })
                except Exception as fetch_error:
                    # Include the result even if fetching details fails
                    search_results.append({
                        "id": result.id,
                        "search_score": result.score,
                        "error": f"Fetch error: {str(fetch_error)}"
                    })
        
        await ctx.info(f"Found {len(search_results)} results with details")
        return {
            "status": "success",
            "query": query,
            "total_results": len(search_results),
            "results": search_results
        }
        
    except Exception as e:
        await ctx.error(f"Search failed: {str(e)}")
        return {"status": "error", "message": str(e)}
@mcp.tool()
async def search_datasets(ctx: Context, query: str, limit: Optional[int] = 25) -> Dict[str, Any]:
    """Search for datasets and return full loaded dataset objects plus scores."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    try:
        await ctx.info(f"Searching datasets for '{query}' with limit {limit}")
        results = await client.datastore.search_datasets(query=query, limit=limit)
        loaded_datasets = []
        for item in results.items:
            loaded_datasets.append({
                "id": item.id,
                "score": item.score,
                "dataset": _dump(item.item)
            })
        auth_errors = [{"id": err.id, "score": err.score} for err in results.auth_errors]
        misc_errors = [{"id": err.id, "score": err.score, "error": err.error_info} for err in results.misc_errors]
        await ctx.info(f"Found {len(loaded_datasets)} datasets, {len(auth_errors)} auth errors, {len(misc_errors)} other errors")
        return {
            "status": "success",
            "query": query,
            "loaded_datasets": loaded_datasets,
            "auth_errors": auth_errors,
            "misc_errors": misc_errors,
            "summary": {
                "successful_items": len(loaded_datasets),
                "auth_error_items": len(auth_errors),
                "misc_error_items": len(misc_errors),
                "total_items": len(loaded_datasets) + len(auth_errors) + len(misc_errors)
            }
        }
    except Exception as e:
        await ctx.error(f"Dataset search failed: {str(e)}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def fetch_dataset(ctx: Context, dataset_id: str) -> Dict[str, Any]:
    """Fetch detailed information about a specific dataset and return full object."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    try:
        await ctx.info(f"Fetching dataset {dataset_id}")
        result = await client.datastore.fetch_dataset(id=dataset_id)
        if not result.status.success:
            await ctx.error(f"Fetch failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        dataset_dict = _dump(result.item)
        await ctx.info(f"Successfully fetched dataset '{dataset_dict.get('display_name')}'")
        return {"status": "success", "dataset": dataset_dict}
    except Exception as e:
        await ctx.error(f"Failed to fetch dataset: {str(e)}")
        return {"status": "error", "message": str(e)}
    
@mcp.tool()
async def list_datasets(ctx: Context, page_size: Optional[int] = 10, sort_ascending: Optional[bool] = True, sort_by: Optional[str] = "DISPLAY_NAME") -> Dict[str, Any]:
    """
    List datasets from the datastore with pagination.

    Args:
        page_size: Number of datasets per page (default: 10)
        sort_ascending: Sort in ascending order (default: True)
        sort_by: Sort field - DISPLAY_NAME, CREATED_TIME, UPDATED_TIME, RELEASE_TIMESTAMP (aliases CREATED_DATE/UPDATED_DATE also accepted)

    Returns:
        Dictionary containing paginated dataset list
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}

    try:
        from ProvenaInterfaces.RegistryAPI import NoFilterSubtypeListRequest, SortOptions, SortType

        raw_map = {
            "DISPLAY_NAME": getattr(SortType, "DISPLAY_NAME", None),
            "CREATED_TIME": getattr(SortType, "CREATED_TIME", None),
            "UPDATED_TIME": getattr(SortType, "UPDATED_TIME", None),
            "RELEASE_TIMESTAMP": getattr(SortType, "RELEASE_TIMESTAMP", None),
        }
        valid_sort_types = {}
        for key, member in raw_map.items():
            if member is not None:
                valid_sort_types[key] = member
        if "CREATED_TIME" in valid_sort_types:
            valid_sort_types["CREATED_DATE"] = valid_sort_types["CREATED_TIME"]
        if "UPDATED_TIME" in valid_sort_types:
            valid_sort_types["UPDATED_DATE"] = valid_sort_types["UPDATED_TIME"]

        if sort_by not in valid_sort_types:
            return {
                "status": "error",
                "message": f"Invalid sort_by '{sort_by}'. Valid options: {list(valid_sort_types.keys())}"
            }

        await ctx.info(f"Listing datasets with page_size={page_size}, sort_ascending={sort_ascending}, sort_by={sort_by}")

        sort_criteria = NoFilterSubtypeListRequest(
            sort_by=SortOptions(
                sort_type=valid_sort_types[sort_by],
                ascending=sort_ascending,
                begins_with=None
            ),
            pagination_key=None,
            page_size=page_size
        )

        result = await client.datastore.list_datasets(list_dataset_request=sort_criteria)

        if not result.status.success:
            await ctx.error(f"List failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}

        datasets = [_dump(item) for item in result.items]

        await ctx.info(f"Found {len(datasets)} datasets (complete={getattr(result, 'complete_item_count', None)}, total={getattr(result, 'total_item_count', None)})")

        return {
            "status": "success",
            "datasets": datasets,
            "pagination": {
                "page_size": page_size,
                "complete_item_count": getattr(result, "complete_item_count", None),
                "total_item_count": getattr(result, "total_item_count", None),
                "has_pagination_key": getattr(result, "pagination_key", None) is not None
            }
        }

    except Exception as e:
        await ctx.error(f"Failed to list datasets: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def fetch_registry_item(ctx: Context, item_id: str) -> Dict[str, Any]:
    """Fetch any registry item by ID and return full raw object."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    try:
        await ctx.info(f"Fetching registry item {item_id}")
        result = await client.registry.general_fetch_item(id=item_id)
        if not result.status.success:
            await ctx.error(f"Fetch failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        item_dict = _dump(result.item)
        await ctx.info(f"Successfully fetched {item_dict.get('item_subtype')} item '{item_dict.get('display_name')}'")
        return {"status": "success", "item": item_dict}
    except Exception as e:
        await ctx.error(f"Failed to fetch registry item: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def list_registry_items(ctx: Context, page_size: Optional[int] = 20) -> Dict[str, Any]:
    """List general registry items returning full raw objects (first page_size)."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    try:
        from ProvenaInterfaces.RegistryAPI import GeneralListRequest
        await ctx.info(f"Listing registry items page_size={page_size}")
        list_request = GeneralListRequest(filter_by=None, sort_by=None, pagination_key=None)
        result = await client.registry.list_general_registry_items(general_list_request=list_request)
        if not result.status.success:
            await ctx.error(f"List failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        raw_items = result.items[:page_size]
        items = [_dump(item) for item in raw_items]
        total_item_count = getattr(result, "total_item_count", None)
        await ctx.info(f"Returning {len(items)} of {total_item_count if total_item_count is not None else 'unknown'} items")
        return {
            "status": "success",
            "items": items,
            "pagination": {
                "shown_items": len(items),
                "total_item_count": total_item_count,
                "complete_item_count": getattr(result, "complete_item_count", None),
                "has_pagination_key": getattr(result, "pagination_key", None) is not None
            }
        }
    except Exception as e:
        await ctx.error(f"Failed to list registry items: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_registry_items_count(ctx: Context) -> Dict[str, Any]:
    """
    Get count of all registry items by subtype.
    
    Returns:
        Dictionary containing item counts by subtype
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        await ctx.info("Getting registry items count by subtype")
        
        counts = await client.registry.list_registry_items_with_count()
        
        readable_counts = {}
        total_count = 0
        for subtype, count in counts.items():
            readable_counts[subtype.lower()] = count
            total_count += count
        
        await ctx.info(f"Found {total_count} total items across {len(readable_counts)} subtypes")
        
        return {
            "status": "success",
            "total_items": total_count,
            "counts_by_subtype": readable_counts,
            "subtypes": list(readable_counts.keys())
        }
        
    except Exception as e:
        await ctx.error(f"Failed to get registry counts: {str(e)}")
        return {"status": "error", "message": str(e)}


def _get_prov_client(client: ProvenaClient):
    return getattr(client, "prov_api", None)



def _status_success(result) -> Tuple[bool, Optional[str]]:
    try:
        status = getattr(result, "status", None)
        if status is not None and getattr(status, "success", None) is not None:
            return bool(status.success), getattr(status, "details", None)
    except Exception:
        pass
    return True, None


def _count_nodes_edges(d: Dict[str, Any]) -> Dict[str, Optional[int]]:
    if not isinstance(d, dict):
        return {"nodes": None, "edges": None}
    nodes = None
    edges = None
    try:
        if isinstance(d.get("nodes"), list):
            nodes = len(d["nodes"])
        if isinstance(d.get("edges"), list):
            edges = len(d["edges"])
        graph = d.get("graph")
        if isinstance(graph, dict):
            if nodes is None and isinstance(graph.get("nodes"), list):
                nodes = len(graph["nodes"])
            if edges is None and isinstance(graph.get("edges"), list):
                edges = len(graph["edges"])
    except Exception:
        pass
    return {"nodes": nodes, "edges": edges}


@mcp.tool()
async def explore_upstream(ctx: Context, starting_id: str, depth: int = 1) -> Dict[str, Any]:
    """Explore upstream lineage with full dumped response."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    prov_client = _get_prov_client(client)
    if prov_client is None:
        await ctx.error("ProvenaClient.prov not available. Please upgrade the provenaclient package or ensure provenance support is enabled.")
        return {"status": "error", "message": "ProvenaClient.prov not available"}
    try:
        await ctx.info(f"Exploring upstream from {starting_id} depth={depth}")
        result = await prov_client.explore_upstream(starting_id=starting_id, depth=depth)
        success, details = _status_success(result)
        data = _dump(result)
        summary = _count_nodes_edges(data or {}) if isinstance(data, dict) else {"nodes": None, "edges": None}
        if not success:
            await ctx.error(f"Upstream exploration failed: {details}")
            return {"status": "error", "message": details or "Unknown error", "starting_id": starting_id, "depth": depth}
        await ctx.info("Upstream exploration complete")
        return {"status": "success", "starting_id": starting_id, "depth": depth, "summary": summary, "lineage": data}
    except Exception as e:
        await ctx.error(f"Failed to explore upstream: {str(e)}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def explore_downstream(ctx: Context, starting_id: str, depth: int = 1) -> Dict[str, Any]:
    """Explore downstream lineage with full dumped response."""
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    prov_client = _get_prov_client(client)
    if prov_client is None:
        await ctx.error("ProvenaClient.prov not available. Please upgrade the provenaclient package or ensure provenance support is enabled.")
        return {"status": "error", "message": "ProvenaClient.prov not available"}
    try:
        await ctx.info(f"Exploring downstream from {starting_id} depth={depth}")
        result = await prov_client.explore_downstream(starting_id=starting_id, depth=depth)
        success, details = _status_success(result)
        data = _dump(result)
        summary = _count_nodes_edges(data or {}) if isinstance(data, dict) else {"nodes": None, "edges": None}
        if not success:
            await ctx.error(f"Downstream exploration failed: {details}")
            return {"status": "error", "message": details or "Unknown error", "starting_id": starting_id, "depth": depth}
        await ctx.info("Downstream exploration complete")
        return {"status": "success", "starting_id": starting_id, "depth": depth, "summary": summary, "lineage": data}
    except Exception as e:
        await ctx.error(f"Failed to explore downstream: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def get_dataset_registration_schema(ctx: Context) -> Dict[str, Any]:
    """
    Get the complete schema and requirements for dataset registration.
    
    This tool dynamically extracts the schema from Provena's actual data models
    to provide current field requirements and validation rules for dataset registration.
    
    Returns:
        Dictionary containing complete registration schema extracted from Provena models
    """
    await ctx.info("Extracting dataset registration schema from Provena models...")
    
    from ProvenaInterfaces.RegistryModels import (
        CollectionFormatDatasetInfo, 
        CollectionFormatAssociations, 
        CollectionFormatApprovals
    )
    from typing import get_origin
        
    
    def extract_all_fields(model_class) -> Dict[str, Any]:
        """Extract all field information from a Pydantic model dynamically"""
        fields_info = {}
            # Get the model schema/fields
        if hasattr(model_class, 'model_fields'):
            fields = model_class.model_fields
            for field_name, field in fields.items():
                field_info = {
                    "type": "string",  
                    "description": "",
                    "required": field.is_required(),
                    "default": None 
                }
                
                # Handle default value safely
                if hasattr(field, 'default'):
                    default_val = field.default
                    if hasattr(default_val, '__class__') and 'PydanticUndefined' in str(default_val.__class__):
                        field_info["default"] = None
                    elif default_val is not None:
                        # Try to serialize the default value
                        try:
                            import json
                            json.dumps(default_val)  # Test if it's JSON serializable 
                            field_info["default"] = default_val
                        except (TypeError, ValueError):
                            field_info["default"] = str(default_val)
                    else:
                        field_info["default"] = None
                
                field_info["description"] = field.description or ""
                
                # Extract type information
                if hasattr(field, 'annotation'):
                    annotation = field.annotation
                    if annotation == str:
                        field_info["type"] = "string"
                    elif annotation == int:
                        field_info["type"] = "integer"
                    elif annotation == float:
                        field_info["type"] = "number"
                    elif annotation == bool:
                        field_info["type"] = "boolean"
                    elif hasattr(annotation, '__origin__'):
                        origin = get_origin(annotation)
                        if origin is list:
                            field_info["type"] = "array"
                        elif origin is dict:
                            field_info["type"] = "object"
                    else:
                        field_info["type"] = str(annotation).replace('<class \'', '').replace('\'>', '')
                
                fields_info[field_name] = field_info
        return fields_info

    dataset_info_fields = extract_all_fields(CollectionFormatDatasetInfo)
    association_fields = extract_all_fields(CollectionFormatAssociations)
    approval_fields = extract_all_fields(CollectionFormatApprovals)
    
    schema = {
        "model_info": {
            "source": "Dynamically extracted from ProvenaInterfaces.RegistryModels",
            "models_used": [
                "CollectionFormatDatasetInfo",
                "CollectionFormatAssociations", 
                "CollectionFormatApprovals"
            ]
        },
        "dataset_info_fields": dataset_info_fields,
        "association_fields": association_fields,
        "approval_fields": approval_fields,
        
        "validation_guidance": {
            "publisher_id": "Must be valid ORGANISATION ID - use search_registry with subtype_filter='ORGANISATION'",
            "organisation_id": "Must be valid ORGANISATION ID - use search_registry with subtype_filter='ORGANISATION'",
            "data_custodian_id": "Must be valid PERSON ID - use search_registry with subtype_filter='PERSON'", 
            "point_of_contact": "Must be valid PERSON ID - use search_registry with subtype_filter='PERSON'",
            "created_date": "ISO format YYYY-MM-DD",
            "published_date": "ISO format YYYY-MM-DD"
        },
        
        "examples": {
            "display_name": "Climate Temperature Dataset 2025",
            "description": "Daily temperature readings from weather stations across Australia for climate research",
            "publisher_id": "10378.1/1963720",
            "created_date": "2025-09-15",
            "published_date": "2025-09-15",
            "keywords": "climate, temperature, weather, australia",
            "spatial_info": '{"coverage": "Australia", "coordinates": {"lat": -25, "lon": 135}}',
            "temporal_info": '{"start_date": "2024-01-01", "end_date": "2024-12-31"}',
            "formats": '{"primary_format": "CSV", "also_available": ["JSON", "NetCDF"]}',
            "access_info": '{"access_type": "open", "download_url": "https://example.com/data"}'
        },
        
        "ai_guidance": {
            "conversation_approach": [
                "Iteratively step through all fields by asking the user to provide the information",
                "Summarize before final registration"
            ],
            "search_tips": [
                "When user mentions organization name, offer to search for it in the registry",
                "Present search results clearly with numbers for selection - ensure you get the info surrounding the ID for UX",
                "If search returns no results, suggest alternative search terms",
                "Always verify the selected ID is the correct type (ORGANISATION vs PERSON)"
            ],
        }
    }
    
    await ctx.info("Successfully extracted schema from Provena models")
    
    return {
        "status": "success",
        "schema": schema,
        "message": "Use this to guide dataset registration - Ask the user step-by-step for each field (including ethics) starting with display name, until all fields are complete"
    }
        

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=5000)
    else:
        mcp.run()