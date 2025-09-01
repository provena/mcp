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

@mcp.tool()
async def check_authentication_status(ctx: Context) -> Dict[str, Any]:
    """Check current authentication status with Provena."""
    is_authenticated = auth_manager._is_authenticated()
    
    status = {
        "authenticated": is_authenticated,
        "message": "Authenticated and ready" if is_authenticated else "Not authenticated - use login_to_provena"
    }
    
    await ctx.info(status["message"])
    return status

@mcp.tool()
async def diagnose_auth(ctx: Context) -> Dict[str, Any]:
    """Return non-sensitive diagnostics about current auth tokens (helps debug 401s)."""
    tokens_present = bool(getattr(auth_manager._auth, "tokens", None)) if auth_manager._auth else False
    access = auth_manager._get_access_token()
    access_preview = None
    if access:
        access_preview = f"{access[:10]}..."
    header = payload = None
    try:
        if access and access.count(".") == 2:
            import json as _json
            import base64 as _b64

            def _b64url_decode(s: str) -> bytes:
                pad = '=' * (-len(s) % 4)
                return _b64.urlsafe_b64decode(s + pad)

            h, p, _sig = access.split(".")
            try:
                header = _json.loads(_b64url_decode(h))
            except Exception:
                header = {"_error": "failed to decode"}
            try:
                payload = _json.loads(_b64url_decode(p))
            except Exception:
                payload = {"_error": "failed to decode"}
    except Exception:
        pass
    roles_info = {}
    try:
        if isinstance(payload, dict):
            ra = payload.get("resource_access") or {}
            if isinstance(ra, dict):
                for client_id, obj in ra.items():
                    if isinstance(obj, dict):
                        r = obj.get("roles")
                        if isinstance(r, list):
                            if client_id in {"registry-api", "data-store-api", "prov-api", "search", "handle", "job-api", CLIENT_ID}:
                                roles_info[client_id] = r
    except Exception:
        pass

    details = {
        "authenticated": auth_manager._is_authenticated(),
        "tokens_present": tokens_present,
        "access_token_present": bool(access),
        "access_token_preview": access_preview,
        "jwt_like": (access.count(".") == 2) if access else False,
        "client_id": CLIENT_ID,
        "realm": REALM,
        "domain": DOMAIN,
        "claims": {
            "header_typ": (header or {}).get("typ") if isinstance(header, dict) else None,
            "header_alg": (header or {}).get("alg") if isinstance(header, dict) else None,
            "iss": (payload or {}).get("iss") if isinstance(payload, dict) else None,
            "aud": (payload or {}).get("aud") if isinstance(payload, dict) else None,
            "azp": (payload or {}).get("azp") if isinstance(payload, dict) else None,
            "exp": (payload or {}).get("exp") if isinstance(payload, dict) else None,
            "resource_access": roles_info or None,
        }
    }
    await ctx.info("Auth diagnostics generated.")
    return details

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
        subtype_filter: Filter by item subtype (DATASET, MODEL, ORGANISATION, PERSON, STUDY, etc.)
    
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
                search_results.append({
                    "id": result.id,
                    "score": result.score
                })
        
        await ctx.info(f"Found {len(search_results)} results")
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
    """
    Search for datasets in the Provena datastore with full item details loaded.
    
    Args:
        query: The search query string
        limit: Maximum number of results to return (default: 25)
    
    Returns:
        Dictionary containing loaded dataset items, auth errors, and misc errors
    """
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
                "display_name": item.item.display_name,
                "name": item.item.collection_format.dataset_info.name,
                "description": item.item.collection_format.dataset_info.description,
                        "created_timestamp": item.item.created_timestamp,
                "owner_username": item.item.owner_username
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
    """
    Fetch detailed information about a specific dataset.
    
    Args:
        dataset_id: The dataset ID/handle to fetch
    
    Returns:
        Dictionary containing complete dataset information
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        await ctx.info(f"Fetching dataset {dataset_id}")
        
        result = await client.datastore.fetch_dataset(id=dataset_id)
        
        if not result.status.success:
            await ctx.error(f"Fetch failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        dataset = result.item
        
        dataset_info = {
            "id": dataset.id,
            "display_name": dataset.display_name,
            "owner_username": dataset.owner_username,
            "created_timestamp": dataset.created_timestamp,
            "updated_timestamp": dataset.updated_timestamp,
            "item_category": dataset.item_category.value,
            "item_subtype": dataset.item_subtype.value,
            "dataset_details": {
                "name": dataset.collection_format.dataset_info.name,
                "description": dataset.collection_format.dataset_info.description,
                "publisher_id": dataset.collection_format.dataset_info.publisher_id,
                "license": getattr(dataset.collection_format.dataset_info, 'license', None),
                "created_date": dataset.collection_format.dataset_info.created_date.value if dataset.collection_format.dataset_info.created_date and dataset.collection_format.dataset_info.created_date.relevant else None,
                "published_date": dataset.collection_format.dataset_info.published_date.value if dataset.collection_format.dataset_info.published_date and dataset.collection_format.dataset_info.published_date.relevant else None,
            },
            "associations": {
                "organisation_id": dataset.collection_format.associations.organisation_id,
                "data_custodian_id": dataset.collection_format.associations.data_custodian_id,
                "point_of_contact": dataset.collection_format.associations.point_of_contact
            },
            "access_info": {
                "reposited": dataset.collection_format.dataset_info.access_info.reposited,
                "uri": dataset.collection_format.dataset_info.access_info.uri,
                "description": dataset.collection_format.dataset_info.access_info.description
            }
        }
        
        await ctx.info(f"Successfully fetched dataset '{dataset.display_name}'")
        return {
            "status": "success",
            "dataset": dataset_info
        }
        
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

        datasets = []
        for item in result.items:
            datasets.append({
                "id": item.id,
                "display_name": item.display_name,
                "name": item.collection_format.dataset_info.name,
                "description": item.collection_format.dataset_info.description,
                "owner_username": item.owner_username,
                "created_timestamp": item.created_timestamp,
                "updated_timestamp": item.updated_timestamp
            })

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
    """
    Fetch any registry item by ID without needing to know its subtype.
    
    Args:
        item_id: The registry item ID/handle to fetch
    
    Returns:
        Dictionary containing the registry item information
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        await ctx.info(f"Fetching registry item {item_id}")
        
        result = await client.registry.general_fetch_item(id=item_id)
        
        if not result.status.success:
            await ctx.error(f"Fetch failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        item = result.item
        
        item_info = {
            "id": item.get("id"),
            "display_name": item.get("display_name"),
            "item_category": item.get("item_category"),
            "item_subtype": item.get("item_subtype"),
            "owner_username": item.get("owner_username"),
            "created_timestamp": item.get("created_timestamp"),
            "updated_timestamp": item.get("updated_timestamp"),
            "user_metadata": item.get("user_metadata"),
        }
        
        subtype = item.get("item_subtype")
        if subtype == "ORGANISATION":
            item_info.update({
                "name": item.get("name"),
                "ror": item.get("ror")
            })
        elif subtype == "PERSON":
            item_info.update({
                "first_name": item.get("first_name"),
                "last_name": item.get("last_name"),
                "email": item.get("email"),
                "orcid": item.get("orcid")
            })
        elif subtype == "MODEL":
            item_info.update({
                "name": item.get("name"),
                "description": item.get("description"),
                "documentation_url": item.get("documentation_url"),
                "source_url": item.get("source_url")
            })
        elif subtype == "STUDY":
            item_info.update({
                "title": item.get("title"),
                "description": item.get("description"),
                "study_alternative_id": item.get("study_alternative_id")
            })
        
        await ctx.info(f"Successfully fetched {subtype} item '{item.get('display_name')}'")
        return {
            "status": "success",
            "item": item_info
        }
        
    except Exception as e:
        await ctx.error(f"Failed to fetch registry item: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def list_registry_items(ctx: Context, page_size: Optional[int] = 20) -> Dict[str, Any]:
    """
    List general registry items across all subtypes.
    
    Args:
        page_size: Number of items per page (default: 20)
    
    Returns:
        Dictionary containing paginated registry items list
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryAPI import GeneralListRequest
        
        await ctx.info(f"Listing registry items with page_size={page_size}")
        
        list_request = GeneralListRequest(
            filter_by=None,
            sort_by=None,
            pagination_key=None
        )
        
        result = await client.registry.list_general_registry_items(general_list_request=list_request)
        
        if not result.status.success:
            await ctx.error(f"List failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        items = []
        for item in result.items[:page_size]: 
            items.append({
                "id": item.get("id"),
                "display_name": item.get("display_name"),
                "item_category": item.get("item_category"),
                "item_subtype": item.get("item_subtype"),
                "owner_username": item.get("owner_username"),
                        "created_timestamp": item.get("created_timestamp")
            })
        
        total_item_count = getattr(result, "total_item_count", None)
        await ctx.info(
            f"Found {len(items)} items (showing first {page_size} of {total_item_count if total_item_count is not None else 'unknown'} total)"
        )
        
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


@mcp.tool()
async def explore_upstream(ctx: Context, starting_id: str, depth: int = 1) -> Dict[str, Any]:
    """
    Explore upstream lineage from a starting registry ID. 

    Args:
        starting_id: The registry item ID to start from.
        depth: How many hops upstream to traverse (max 10).

    Returns:
        A dictionary with lineage summary and raw response data when available.
    """
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

        success = True
        details = None
        try:
            if hasattr(result, "status") and getattr(result.status, "success", None) is not None:
                success = bool(result.status.success)
                details = getattr(result.status, "details", None)
        except Exception:
            pass

        data = None
        try:
            if hasattr(result, "model_dump"):
                data = result.model_dump()  # pydantic v2
            elif hasattr(result, "dict"):
                data = result.dict()  # pydantic v1
        except Exception:
            data = None

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

        summary = _count_nodes_edges(data or {})

        if not success:
            await ctx.error(f"Upstream exploration failed: {details}")
            return {"status": "error", "message": details or "Unknown error", "starting_id": starting_id, "depth": depth}

        await ctx.info("Upstream exploration complete")
        return {
            "status": "success",
            "starting_id": starting_id,
            "depth": depth,
            "summary": summary,
            "lineage": data,
        }

    except Exception as e:
        await ctx.error(f"Failed to explore upstream: {str(e)}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
async def explore_downstream(ctx: Context, starting_id: str, depth: int = 1) -> Dict[str, Any]:
    """
    Explore downstream lineage from a starting registry ID.

    Args:
        starting_id: The registry item ID to start from.
        depth: How many hops downstream to traverse (max 10).

    Returns:
        A dictionary with lineage summary and raw response data when available.
    """
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

        success = True
        details = None
        try:
            if hasattr(result, "status") and getattr(result.status, "success", None) is not None:
                success = bool(result.status.success)
                details = getattr(result.status, "details", None)
        except Exception:
            pass

        data = None
        try:
            if hasattr(result, "model_dump"):
                data = result.model_dump()
            elif hasattr(result, "dict"):
                data = result.dict()
        except Exception:
            data = None

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

        summary = _count_nodes_edges(data or {})

        if not success:
            await ctx.error(f"Downstream exploration failed: {details}")
            return {"status": "error", "message": details or "Unknown error", "starting_id": starting_id, "depth": depth}

        await ctx.info("Downstream exploration complete")
        return {
            "status": "success",
            "starting_id": starting_id,
            "depth": depth,
            "summary": summary,
            "lineage": data,
        }

    except Exception as e:
        await ctx.error(f"Failed to explore downstream: {str(e)}")
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=5000)
    else:
        mcp.run()