from http import client
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

@mcp.prompt("deep_lineage_investigation")
def deep_lineage_investigation_prompt(root_id: str) -> str:
    """
    Autonomous deep lineage exploration and reporting prompt. Use this for when a comprehensive summary/explaination of a dataset is needed. Make sure to get the id of the root dataset, you can search for it if needed.
    """
    return f"""
ROLE
You are a meticulous provenance investigator.

OBJECTIVE
Fully map and understand the lineage graph around the focal handle: {root_id}

ALLOWED TOOLS (invoke as needed, iteratively)
1. fetch_registry_item OR fetch_dataset for detailed object retrieval.
2. explore_upstream(starting_id, depth=1..N) to discover inputs / ancestors.
3. explore_downstream(starting_id, depth=1..N) to discover outputs / descendants.

PROCESS
1. Start with root handle {root_id}. Fetch its full details immediately.
2. Maintain:
   - frontier (IDs queued for exploration)
   - visited (all IDs already fully fetched)
3. For each ID:
   a. Explore upstream (depth=1 first; increase only if new nodes still appear and depth justified).
   b. Explore downstream similarly.
   c. Collect every newly discovered ID from lineage edges.
   d. For every newly discovered ID not yet visited:
        - Fetch its full details individually (never rely only on lineage summaries).
        - Add to frontier.
4. Repeat until:
   - No new IDs are discovered, OR
   - A sensible safety cap reached (suggest default max 250 unique nodes unless user directs otherwise), OR
   - Cycles detected with no net expansion.
5. De-duplicate strictly; never refetch an already visited ID.
6. Record for each node:
   - id / handle
   - type / subtype
   - role (input, transformation, output, derivative, unknown)
   - direct upstream IDs
   - direct downstream IDs
   - any temporal / spatial / model / purpose metadata
7. Identify gaps:
   - Missing upstream sources
   - Dangling transforms without outputs
   - Nodes lacking key metadata (temporal / spatial / license / custodian)

REPORT FORMAT
1. Executive Summary (plain language, decision-maker focused)
2. Lineage Overview
   - Node/edge counts
   - High-level flow (inputs → transformations → outputs)
3. Upstream Sources (group similar origins; note provenance depth)
4. Transformation & Processing Steps (ordered chain; highlight models / scripts)
5. Downstream Dependencies & Impacts
6. Data Quality & Metadata Gaps
7. Risk & Uncertainty (missing links, ambiguous roles, unverifiable steps)
8. Recommended Follow-up Actions (prioritised)
9. Appendix
   - Tabulated node catalogue
   - Orphan / terminal nodes
   - Graph statistics

STYLE & CONSTRAINTS
- Prefix EVERY handle with https://hdl.handle.net/
- No hallucinated IDs or fields—only include fetched data.
- Group similar nodes; avoid repeating identical attribute blocks.
- Explicitly flag assumptions.
- Use concise professional tone.

BEGIN NOW:
1. Fetch root item {root_id}.
2. Initialize structures and start iterative exploration.
3. Stop only when termination conditions met.
4. Produce the report as specified.
"""

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

@mcp.prompt("handle_linking")
def handle_linking_prompt() -> str:
    """
    Always provide the full handle URL for any Provena record when the user asks for a link.

    INSTRUCTIONS:
    - If the user requests a link to a record (dataset, person, organisation, etc.), always respond with the full handle URL in the format: https://hdl.handle.net/<id>
    - Replace <id> with the actual record ID.
    - Do not provide just the ID or a partial link—always use the full URL.
    - Example: If the record ID is "12345/abcde", respond with "https://hdl.handle.net/12345/abcde"
    """
    return (
        "If the user asks for a link to a record, always reply with the full handle URL: "
        "https://hdl.handle.net/<id> (replace <id> with the actual record ID)."
    )
@mcp.prompt("dataset_registration_workflow")
def dataset_registration_workflow() -> str:
    """
    Guided DATASET (data store item) registration workflow that ensures complete data collection.

    IMPORTANT: This is for registering DATASETS (actual data in the data store), NOT dataset templates - use the register_entity_workflow prompt.
    For dataset templates, use the register_entity_workflow prompt.

    This prompt creates a systematic process that prevents premature registration
    and ensures all required information is collected and validated.
    """
    return """
    You are a Provena DATASET registration specialist. Follow this EXACT workflow:

    IMPORTANT: This workflow is for registering DATASETS (actual data items), NOT dataset templates.
    Dataset templates are registered using a different process.

    === PHASE 1: INITIALIZATION ===
    1. Check if logged in, if not, stop and ask the user to log in first (do not just use the login tool, engage the user)
    2. Greet user and explain you'll help register a DATASET (actual data, not a template)
    3. Explain the process: collect required info → optional info → summary → confirmation → registration

    === PHASE 2: COLLECT INFORMATION ===
    Look at the register_dataset tool documentation to see all fields.
    Ask for each field conversationally - ENSURE YOU ASK TO COLLECT INFORMATION FOR EVERY SINGLE FIELD. This includes all of the Important, access, approval, metadata, spatial data, temporal data, list, user metadata and people data fields.
    IMPORTANT: You do not need to ask for a specific format, just convert what the user provides into the expected format. Clarify with the user if needed.

    === PHASE 3: VALIDATION & CONFIRMATION ===
    Show complete summary and get explicit confirmation

    === PHASE 4: REGISTRATION ===
    Call register_dataset with ALL collected information

    CRITICAL: Never call register_dataset until ALL required info collected and confirmed.
    """

@mcp.prompt("register_entity_workflow")
def register_entity_workflow() -> str:
    """
    Guided registration workflow that ensures complete data collection for other entities like organizations, persons, models.

    This prompt creates a systematic process that prevents premature registration
    and ensures all required information is collected and validated.
    """
    return """
    You are a Provena registration specialist. Follow this EXACT workflow:

    === PHASE 1: INITIALIZATION ===
    1. Check if logged in, if not, prompt the user to login first (do not just use the login tool, engage the user, stop and ask them to log in)
    2. Greet user and explain you'll help register an entity
    3. Briefly explain the process: collect required info → optional info → summary → confirmation → registration

    === PHASE 2: COLLECT INFORMATION ===
    Look at the relevant tool documentation to see all fields.
    Ask for each field conversationally - ENSURE YOU ASK TO COLLECT INFORMATION FOR EVERY SINGLE FIELD, INCLUDING THE OPTIONAL ONES.

    ENTITY-SPECIFIC GUIDANCE:
    - For Organizations: name, display_name, ror (optional), user_metadata (optional)
    - For Persons: first_name, last_name, email, display_name (optional), orcid (optional), ethics_approved, user_metadata (optional)
    - For Models: name, description, documentation_url, source_url, display_name (optional), user_metadata (optional)

    === PHASE 3: VALIDATION & CONFIRMATION ===
    Show complete summary and get explicit confirmation

    === PHASE 4: REGISTRATION ===
    Call the relevant tool with ALL collected information:
    - create_organisation for organizations
    - create_person for persons
    - create_model for models

    CRITICAL: Never call desired tool until ALL required info collected and confirmed.
    """

@mcp.prompt("dataset_template_workflow")
def dataset_template_workflow() -> str:
    """
    Guided workflow for registering Dataset Templates with resource management.
    
    This prompt creates a systematic process for dataset template registration,
    including the definition of defined and deferred resources.
    """
    return """
    You are a Provena Dataset Template registration specialist. Follow this EXACT workflow:

    === PHASE 1: INITIALIZATION ===
    1. Check if logged in, if not, prompt the user to login first (do not just use the login tool, engage the user by stopping and asking they need to be logged in)
    2. Greet user and explain you'll help register a Dataset Template
    3. Explain what a dataset template is: "A dataset template defines the structure and expected files/resources for datasets used in model runs"
    4. Explain the process: collect basic info → define resources → summary → confirmation → registration

    === PHASE 2: COLLECT INFORMATION ===
    Look at the relevant tool documentation to see all fields.
    Ask for each field conversationally - ENSURE YOU ASK TO COLLECT INFORMATION FOR EVERY SINGLE FIELD, INCLUDING THE OPTIONAL ONES.

    ENTITY-SPECIFIC GUIDANCE:
    - For Dataset Templates: display_name, description (optional), defined_resources, deferred_resources, user_metadata (optional)
    - For defined resources once they provide the first one, ask if they want to add another until they say no, then move on to deferred resources
    - For deferred resources once they provide the first one, ask if they want to add another until they say no, then move on to user_metadata
    MAKE SURE TO ASK FOR ALL FIELDS 

    === PHASE 3: VALIDATION & CONFIRMATION ===
    Show complete summary and get explicit confirmation

    === PHASE 4: REGISTRATION ===
    - create_dataset_template for dataset templates

    === IMPORTANT NOTES ===
    - Keep track of where you are in the workflow
    - Never assume or skip steps
    - Always show the full handle URL: https://hdl.handle.net/{id} for created templates
    - Be patient and methodical when collecting resource definitions
    - Validate that usage_type values are one of: GENERAL_DATA, CONFIG_FILE, FORCING_DATA, PARAMETER_FILE

    CRITICAL: Never call create_dataset_template until ALL required info collected and confirmed.
    """

@mcp.prompt("workflow_template_registration")
def workflow_template_registration() -> str:
    """
    Guided workflow for registering Model Run Workflow Templates with dependency management.
    
    This prompt creates a systematic process that handles the complexity of workflow templates,
    including the potential need to create dependent entities (models and dataset templates).
    """
    return """
    You are a Provena Model Run Workflow Template registration specialist. Follow this EXACT workflow:

    === PHASE 1: INITIALIZATION ===
    1. Check if logged in, if not, prompt the user to login first (do not just use the login tool, engage the user by stopping and asking they need to be logged in)
    2. Greet user and explain you'll help register a Model Run Workflow Template
    3. Explain what a workflow template is: "A workflow template defines the inputs, outputs, and structure for model run activities"
    4. Explain the process: identify/create model → identify/create dataset templates → define annotations → summary → confirmation → registration

    === PHASE 2: COLLECT MODEL INFORMATION ===
    ASK: "Do you have an existing model registered, or do you need to create a new one?"
    
    IF SEARCH FOR EXISTING:
    - Ask them for the model name or keywords to search for
    - Use search_registry with subtype_filter="MODEL"
    - Show results and ask user to select one
    - Record the model_id
    
    IF CREATE NEW:
    - Explain: "Let's create the model first, then we'll come back to the workflow template"
    - Follow the model registration workflow (use register_entity_workflow prompt guidance)
    - Use create_model tool
    - Record the returned model_id
    - Return to workflow template collection

    === PHASE 3: COLLECT INPUT DATASET TEMPLATES ===
    ASK: "Does your model require input datasets?" 
    
    IF YES, FOR EACH INPUT:
    - ASK: "Do you have an existing dataset template, or create a new one?"
    - IF SEARCH: Ask them for the dataset template name or keywords to search for. Use search_registry with subtype_filter="DATASET_TEMPLATE", record ID
    - IF CREATE: Follow dataset_template_workflow
    - ASK: "Is this input optional?" (true/false)
    - Add to input_templates list: {"template_id": "ID", "optional": bool}
    
    Continue until user indicates no more inputs needed.

    === PHASE 4: COLLECT OUTPUT DATASET TEMPLATES ===
    ASK: "Does your model produce output datasets?"
    
    IF YES, FOR EACH OUTPUT:
    - Same process as inputs
    - Add to output_templates list
    
    Continue until user indicates no more outputs needed.

    === PHASE 5: COLLECT ANNOTATIONS ===
    ASK: "Do you want to specify required annotations for model runs?" 
    EXPLAIN: "Required annotations are metadata keys that MUST be provided when someone registers a model run using this template"
    - If yes: collect comma-separated keys (e.g., "experiment_id,run_config")
    
    ASK: "Do you want to specify optional annotations?" 
    EXPLAIN: "Optional annotations are metadata keys that MAY be provided"
    - If yes: collect comma-separated keys

    === PHASE 6: COLLECT OPTIONAL METADATA ===
    ASK: "Do you want to add any custom metadata to this workflow template?" - always ask
    - If yes: collect as JSON object

    === PHASE 7: VALIDATION & CONFIRMATION ===
    Show complete summary:
    - Display name
    - Model ID (with name if available)
    - Number of input templates (list IDs and optional status)
    - Number of output templates (list IDs and optional status)
    - Required annotations (if any)
    - Optional annotations (if any)
    - Custom metadata (if any)
    
    Ask for explicit confirmation: "Does this look correct? Type 'yes' to proceed with registration."

    === PHASE 8: REGISTRATION ===
    ONLY AFTER CONFIRMATION, call create_model_run_workflow_template with:
    - display_name
    - model_id
    - input_template_ids (as JSON string)
    - output_template_ids (as JSON string)
    - required_annotations (comma-separated)
    - optional_annotations (comma-separated)
    - user_metadata (as JSON string)

    === IMPORTANT NOTES ===
    - Keep track of where you are in the workflow
    - If creating dependencies (model/templates), complete those fully before returning to workflow template
    - Never assume or skip steps
    - Always show the full handle URL: https://hdl.handle.net/{id} for created entities
    - Be patient and methodical - this is a complex multi-step process

    CRITICAL: Never call create_model_run_workflow_template until ALL required info collected and confirmed.
    """
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
                try:
                    item_result = await client.registry.general_fetch_item(id=result.id)
                    if item_result.status.success and item_result.item:
                        item_data = _dump(item_result.item)
                        item_data["search_score"] = result.score
                        search_results.append(item_data)
                    else:
                        search_results.append({
                            "id": result.id,
                            "search_score": result.score,
                            "error": "Unable to fetch full item details"
                        })
                except Exception as fetch_error:
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
async def get_current_date(ctx: Context) -> str:
    """
    Get the current date in ISO format (YYYY-MM-DD).
    
    Returns:
        Current date as ISO string
    """
    from datetime import datetime
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    await ctx.info(f"Current date: {current_date}")
    return current_date

@mcp.tool()
async def create_model(
    ctx: Context,
    name: str,
    description: str,
    documentation_url: str,
    source_url: str,
    display_name: Optional[str] = None,
    user_metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    Register a new Model in the Provena registry.
    
    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH field conversationally, one by one
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool
    4. Only call this tool with ALL required information present

    REQUIRED FIELDS:
    - name: The name of the software model (e.g., "Marine and Land Model")
    - description: A description of the model which assists other users in understanding its nature
    - documentation_url: A fully qualified URL to the site which hosts documentation about the model
    - source_url: A URL to the source code or repository for the model

    OPTIONAL FIELDS:
    - display_name: How the model's name should appear when viewed (defaults to name if not provided)
    - user_metadata: Additional key-value metadata as JSON string (e.g., '{"version": "1.0", "author": "John"}')

    Returns:
        Dictionary with registration status and model ID
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryModels import ModelDomainInfo
        
        await ctx.info(f"Registering model '{name}'")
        
        # Parse user_metadata if provided
        parsed_metadata = None
        if user_metadata:
            try:
                import json
                parsed_metadata = json.loads(user_metadata)
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid JSON in user_metadata: {str(e)}"}
        
        # Create the model domain info
        model_info = ModelDomainInfo(
            display_name=display_name or name,
            name=name,
            description=description,
            documentation_url=documentation_url,
            source_url=source_url,
            user_metadata=parsed_metadata
        )
        
        # Register the model
        result = await client.registry.model.create_item(create_item_request=model_info)
        
        if not result.status.success:
            await ctx.error(f"Model registration failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        model_id = result.created_item.id if result.created_item else None
        
        await ctx.info(f"Successfully registered model with ID: {model_id}")
        
        return {
            "status": "success",
            "model_id": model_id,
            "handle_url": f"https://hdl.handle.net/{model_id}" if model_id else None,
            "message": f"Model '{name}' registered successfully"
        }
        
    except Exception as e:
        await ctx.error(f"Failed to register model: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def create_dataset_template(
    ctx: Context,
    display_name: str,
    description: Optional[str] = None,
    defined_resources: Optional[str] = None,
    deferred_resources: Optional[str] = None,
    user_metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    Register a new Dataset Template in the Provena registry.
    
    Dataset templates define the structure/schema for datasets used in model runs.
    They specify what files/resources are expected in a dataset.
    
    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH field conversationally, one by one
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool
    4. Only call this tool with ALL required information present

    REQUIRED FIELDS:
    - display_name: Name for this template

    OPTIONAL FIELDS:
    - description: Description of what this template is for
    - defined_resources: JSON string array of defined resources. Each resource should have:
        * path: File path within dataset
        * description: What this resource is
        * usage_type: One of: GENERAL_DATA, CONFIG_FILE, FORCING_DATA, PARAMETER_FILE
        * optional: boolean (default false)
        * is_folder: boolean (default false)
        Example: '[{"path": "data/input.csv", "description": "Input data", "usage_type": "GENERAL_DATA", "optional": false}]'
    
    - deferred_resources: JSON string array of deferred resources (placeholders filled at runtime). Each should have:
        * key: A unique identifier for this resource placeholder
        * description: What this resource is
        * usage_type: One of: GENERAL_DATA, CONFIG_FILE, FORCING_DATA, PARAMETER_FILE
        * optional: boolean (default false)
        * is_folder: boolean (default false)
        Example: '[{"key": "model_output", "description": "Model output file", "usage_type": "GENERAL_DATA", "optional": false}]'
    
    - user_metadata: Additional key-value metadata as JSON string

    Returns:
        Dictionary with registration status and template ID
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryModels import DatasetTemplateDomainInfo, DefinedResource, DeferredResource, ResourceUsageType
        import json
        
        await ctx.info(f"Registering dataset template '{display_name}'")
        
        # Parse JSON inputs
        parsed_defined = []
        if defined_resources:
            try:
                defined_list = json.loads(defined_resources)
                for res in defined_list:
                    parsed_defined.append(DefinedResource(
                        path=res['path'],
                        description=res['description'],
                        usage_type=ResourceUsageType(res.get('usage_type', 'GENERAL_DATA')),
                        optional=res.get('optional', False),
                        is_folder=res.get('is_folder', False),
                        additional_metadata=res.get('additional_metadata')
                    ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                return {"status": "error", "message": f"Invalid defined_resources format: {str(e)}"}
        
        parsed_deferred = []
        if deferred_resources:
            try:
                deferred_list = json.loads(deferred_resources)
                for res in deferred_list:
                    parsed_deferred.append(DeferredResource(
                        key=res['key'],
                        description=res['description'],
                        usage_type=ResourceUsageType(res.get('usage_type', 'GENERAL_DATA')),
                        optional=res.get('optional', False),
                        is_folder=res.get('is_folder', False),
                        additional_metadata=res.get('additional_metadata')
                    ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                return {"status": "error", "message": f"Invalid deferred_resources format: {str(e)}"}
        
        parsed_metadata = None
        if user_metadata:
            try:
                parsed_metadata = json.loads(user_metadata)
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid JSON in user_metadata: {str(e)}"}
        
        # Create the template domain info
        template_info = DatasetTemplateDomainInfo(
            display_name=display_name,
            description=description,
            defined_resources=parsed_defined if parsed_defined else None,
            deferred_resources=parsed_deferred if parsed_deferred else None,
            user_metadata=parsed_metadata
        )
        
        # Register the template
        result = await client.registry.dataset_template.create_item(create_item_request=template_info)
        
        if not result.status.success:
            await ctx.error(f"Dataset template registration failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        template_id = result.created_item.id if result.created_item else None
        
        await ctx.info(f"Successfully registered dataset template with ID: {template_id}")
        
        return {
            "status": "success",
            "template_id": template_id,
            "handle_url": f"https://hdl.handle.net/{template_id}" if template_id else None,
            "message": f"Dataset template '{display_name}' registered successfully"
        }
        
    except Exception as e:
        await ctx.error(f"Failed to register dataset template: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def create_model_run_workflow_template(
    ctx: Context,
    display_name: str,
    model_id: str,
    input_template_ids: Optional[str] = None,
    output_template_ids: Optional[str] = None,
    required_annotations: Optional[str] = None,
    optional_annotations: Optional[str] = None,
    user_metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    Register a new Model Run Workflow Template in the Provena registry.
    
    Model run workflow templates define the inputs, outputs, and annotations required
    for registering model runs. They act as blueprints for model run activities.
    
    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH field conversationally, one by one
    2. Offer to search for existing entities OR create new ones as needed
    3. Show complete summary of ALL collected information
    4. Get explicit user confirmation before calling this tool
    5. Only call this tool with ALL required information present

    REQUIRED FIELDS:
    - display_name: User-friendly name for this workflow template (e.g., "Simple Coral Model v1.5 Workflow")
    - model_id: The ID of a registered Model entity that this workflow template is for
      * Ask: "Do you want to search for an existing model or create a new one?"
      * If search: Use search_registry with subtype_filter="MODEL"
      * If create new: Use create_model tool first, then come back here

    OPTIONAL FIELDS:
    - input_template_ids: JSON string array of input dataset template IDs with optional flags
      * Ask: "Do you want to specify input dataset templates?"
      * Each template: {"template_id": "10378.1/1234", "optional": false}
      * For each template, ask: "Search for existing or create new dataset template?"
      * If search: Use search_registry with subtype_filter="DATASET_TEMPLATE"
      * If create new: Use register_entity_workflow 
      * Example: '[{"template_id": "10378.1/123", "optional": false}, {"template_id": "10378.1/456", "optional": true}]'
    
    - output_template_ids: JSON string array of output dataset template IDs with optional flags
      * Ask: "Do you want to specify output dataset templates?"
      * Same format and process as input_template_ids
      * Example: '[{"template_id": "10378.1/789", "optional": false}]'
    
    - required_annotations: Comma-separated list of required annotation keys
      * Ask: "Do you want to specify required annotations for model runs?"
      * These are metadata keys that MUST be provided when registering a model run
      * Example: "experiment_id,run_configuration"
    
    - optional_annotations: Comma-separated list of optional annotation keys - these are required
      * Ask: "Do you want to specify optional annotations for model runs?"
      * These are metadata keys that MAY be provided when registering a model run
      * Example: "notes,researcher_name"
    
    - user_metadata: Additional key-value metadata as JSON string
      * Example: '{"version": "1.0", "purpose": "production"}'

    Returns:
        Dictionary with registration status and workflow template ID
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryModels import (
            ModelRunWorkflowTemplateDomainInfo, 
            TemplateResource, 
            WorkflowTemplateAnnotations
        )
        import json
        
        await ctx.info(f"Registering model run workflow template '{display_name}'")
        
        # Parse input templates
        parsed_input_templates = []
        if input_template_ids:
            try:
                input_list = json.loads(input_template_ids)
                for template in input_list:
                    parsed_input_templates.append(TemplateResource(
                        template_id=template['template_id'],
                        optional=template.get('optional', False)
                    ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                return {"status": "error", "message": f"Invalid input_template_ids format: {str(e)}"}
        
        # Parse output templates
        parsed_output_templates = []
        if output_template_ids:
            try:
                output_list = json.loads(output_template_ids)
                for template in output_list:
                    parsed_output_templates.append(TemplateResource(
                        template_id=template['template_id'],
                        optional=template.get('optional', False)
                    ))
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                return {"status": "error", "message": f"Invalid output_template_ids format: {str(e)}"}
        
        # Parse annotations
        annotations = None
        if required_annotations or optional_annotations:
            # Parse and filter out empty strings
            required_list = [k.strip() for k in required_annotations.split(',') if k.strip()] if required_annotations else None
            optional_list = [k.strip() for k in optional_annotations.split(',') if k.strip()] if optional_annotations else None
            
            # Only create annotations if we have actual values (not None)
            if required_list or optional_list:
                # Build kwargs to only include non-None fields
                annotation_kwargs = {}
                if required_list:
                    annotation_kwargs['required'] = required_list
                if optional_list:
                    annotation_kwargs['optional'] = optional_list
                
                annotations = WorkflowTemplateAnnotations(**annotation_kwargs)
        
        # Parse user metadata
        parsed_metadata = None
        if user_metadata:
            try:
                parsed_metadata = json.loads(user_metadata)
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid JSON in user_metadata: {str(e)}"}
        
        # Create the workflow template domain info
        workflow_template_info = ModelRunWorkflowTemplateDomainInfo(
            display_name=display_name,
            software_id=model_id,
            input_templates=parsed_input_templates,  
            output_templates=parsed_output_templates, 
            annotations=annotations,
            user_metadata=parsed_metadata
        )
        
        result = await client.registry.model_run_workflow.create_item(create_item_request=workflow_template_info)
        
        if not result.status.success:
            await ctx.error(f"Workflow template registration failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        template_id = result.created_item.id if result.created_item else None
        
        await ctx.info(f"Successfully registered model run workflow template with ID: {template_id}")
        
        return {
            "status": "success",
            "workflow_template_id": template_id,
            "handle_url": f"https://hdl.handle.net/{template_id}" if template_id else None,
            "message": f"Model run workflow template '{display_name}' registered successfully",
            "summary": {
                "display_name": display_name,
                "model_id": model_id,
                "input_templates_count": len(parsed_input_templates),
                "output_templates_count": len(parsed_output_templates),
                "has_annotations": annotations is not None
            }
        }
        
    except Exception as e:
        await ctx.error(f"Failed to register model run workflow template: {str(e)}")
        return {"status": "error", "message": str(e)}

@mcp.tool()
async def create_dataset(
    ctx: Context,
    name: str,
    description: str,
    publisher_id: str,
    organisation_id: str,
    created_date: str,
    published_date: str,
    license: str,
    # Access info components
    access_reposited: bool = True,
    access_uri: Optional[str] = None,
    access_description: Optional[str] = None,
    # Ethics/approval boolean fields
    ethics_registration_relevant: bool = False,
    ethics_registration_obtained: bool = False,
    ethics_access_relevant: bool = False,
    ethics_access_obtained: bool = False,
    indigenous_knowledge_relevant: bool = False,
    indigenous_knowledge_obtained: bool = False,
    export_controls_relevant: bool = False,
    export_controls_obtained: bool = False,
    # Optional metadata fields
    purpose: Optional[str] = None,
    rights_holder: Optional[str] = None,
    usage_limitations: Optional[str] = None,
    preferred_citation: Optional[str] = None,
    # Spatial info fields (separate parameters)
    spatial_coverage: Optional[str] = None,
    spatial_extent: Optional[str] = None,
    spatial_resolution: Optional[str] = None,
    # Temporal info fields
    temporal_begin_date: Optional[str] = None,
    temporal_end_date: Optional[str] = None,
    temporal_resolution: Optional[str] = None,
    # Arrays for formats and keywords
    formats: Optional[str] = None, 
    keywords: Optional[str] = None, 
    user_metadata: Optional[str] = None, 
    data_custodian_id: Optional[str] = None,
    point_of_contact: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Register a new dataset in the Provena registry.

    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH AND EVERY field conversationally, one by one in the order listed below (mention if it is optional)
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool
    4. Only call this tool with ALL required information present

    ARGUMENTS AND COLLECTION ORDER (mirrors function signature)

    IMPORTANT FIELDS
    - name: Dataset name
    - description: Detailed description
    - publisher_id: publisher ID (must be an organisation - can use search_registry to find if unsure)
    - organisation_id: ORGANISATION ID (record creator - must be an organisation - can use search_registry to find if unsure)
    - created_date: user can provide in any common format, convert to YYYY-MM-DD format
    - published_date: user can provide in any common format, convert to YYYY-MM-DD format
    - license: License URI (e.g., https://creativecommons.org/licenses/by/4.0/)

    ACCESS INFORMATION FIELDS (ensure you ask about these - if reposited is False, you must ask for URI and description, otherwise skip them if reposited is True)
    - access_reposited: Is the data reposited? 
    - access_uri: URI if externally hosted (optional - skip if access_reposited is True)
    - access_description: How to access externally hosted data (optional - skip if access_reposited is True)

    APPROVALS FIELDS (booleans for true or false)
    - ethics_registration_relevant, ethics_registration_obtained (if not relevant, obtained is false, and you do not need to ask)
    - ethics_access_relevant, ethics_access_obtained (if not relevant, obtained is false, and you do not need to ask)
    - indigenous_knowledge_relevant, indigenous_knowledge_obtained (if not relevant, obtained is false, and you do not need to ask)
    - export_controls_relevant, export_controls_obtained (if not relevant, obtained is false, and you do not need to ask)
 
    METADATA FIELDS (ensure you ask about these)
    - purpose: Why the dataset was created (optional, so skip if user does not have one)
    - rights_holder: Who owns/manages rights (optional, so skip if user does not have one)
    - usage_limitations:  Access/use restrictions (optional, so skip if user does not have one)
    - preferred_citation: How to cite this dataset (optional, so skip if user does not have one)

    SPATIAL DATA FIELDS (ensure you ask about these)
    - spatial_info: Ask if they want to provide spatial information, if not, skip all spatial fields
    - spatial_coverage: EWKT with SRID (e.g., SRID=4326;POINT(145.7 -16.2))
    - spatial_extent: EWKT bbox polygon (SRID=4326;POLYGON((minx miny, maxx miny, maxx maxy, minx maxy, minx miny)))
    - spatial_resolution: Decimal degrees string (e.g., "0.01")

    TEMPORAL DATA FIELDS (ensure you ask about these)
    - temporal_info: Ask if they want to provide temporal information, if not, skip all temporal fields
    - temporal_begin_date, temporal_end_date: Collect both or neither - cannot just have one (YYYY-MM-DD)
    - temporal_resolution: ISO8601 duration (e.g., P1D) (if given in a different format, convert to ISO8601)

    LIST DATA FIELDS (ensure you ask about these)
    - formats: Comma-separated format (e.g., "CSV, JSON")(optional, so skip if user does not have one)
    - keywords: Comma-separated format tags - just ask for keywords and convert to proper format (optional, so skip if user does not have one)

    user_metadata DATA FIELDS (ensure you ask about these)
    - JSON object string; values will be stringified (optional, so skip if user does not have one)

    PEOPLE DATA FIELDS (ensure you ask about these)
    - data_custodian_id: PERSON ID (use search_registry) (optional, so skip if user does not have one)
    - point_of_contact: Free-text contact details (e.g., email) (optional, so skip if user does not have one)

    Returns:
        Dict with registration status and dataset_id (handle)
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.RegistryModels import (
            CollectionFormat, CollectionFormatDatasetInfo,
            CollectionFormatAssociations, CollectionFormatApprovals,
            AccessInfo, CreatedDate, PublishedDate,
            CollectionFormatSpatialInfo, CollectionFormatTemporalInfo,
            TemporalDurationInfo
        )
        
        await ctx.info(f"Registering dataset '{name}'...")
        
        access_info = AccessInfo(
            reposited=access_reposited,
            uri=access_uri,
            description=access_description
        )
        
        created_date_obj = CreatedDate(relevant=True, value=created_date)
        published_date_obj = PublishedDate(relevant=True, value=published_date)
        
        dataset_info_data = {
            "name": name,
            "description": description,
            "publisher_id": publisher_id,
            "created_date": created_date_obj,
            "published_date": published_date_obj,
            "license": license,
            "access_info": access_info
        }
        
        optional_fields = {
            "purpose": purpose,
            "rights_holder": rights_holder,
            "usage_limitations": usage_limitations,
            "preferred_citation": preferred_citation,
        }
        
        for field, value in optional_fields.items():
            if value is not None:
                dataset_info_data[field] = value
        
        if any([spatial_coverage, spatial_extent, spatial_resolution]):
            async def _to_ewkt(val: Optional[str], field: str) -> Optional[str]:
                if not val:
                    return val
                s = val.strip()
                if not s:
                    return None
                if not s.upper().startswith("SRID="):
                    await ctx.warn(f"{field} provided without SRID. Assuming EPSG:4326 and converting to EWKT.")
                    s = f"SRID=4326;{s}"
                if len(s) > 50000:
                    await ctx.warn(f"{field} exceeds 50,000 characters and may be rejected by schema constraints.")
                return s

            norm_coverage = await _to_ewkt(spatial_coverage, "spatial_coverage")
            norm_extent = await _to_ewkt(spatial_extent, "spatial_extent")

            if spatial_resolution:
                try:
                    float(spatial_resolution.strip())
                except Exception:
                    await ctx.warn("spatial_resolution should be a decimal degrees string (e.g., '0.01').")

            spatial_info = CollectionFormatSpatialInfo(
                coverage=norm_coverage,
                extent=norm_extent,
                resolution=spatial_resolution
            )
            dataset_info_data["spatial_info"] = spatial_info
        
        if temporal_begin_date and temporal_end_date:
            duration = TemporalDurationInfo(
                begin_date=temporal_begin_date,
                end_date=temporal_end_date
            )
            temporal_info = CollectionFormatTemporalInfo(
                duration=duration,
                resolution=temporal_resolution
            )
            dataset_info_data["temporal_info"] = temporal_info
        
        if formats:
            formats_list = [f.strip() for f in formats.split(',') if f.strip()]
            dataset_info_data["formats"] = formats_list
        
        if keywords:
            keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
            dataset_info_data["keywords"] = keywords_list
        
        if user_metadata:
            try:
                import json
                metadata_dict = json.loads(user_metadata)
                if isinstance(metadata_dict, dict):
                    string_metadata = {k: str(v) for k, v in metadata_dict.items()}
                    dataset_info_data["user_metadata"] = string_metadata
            except json.JSONDecodeError:
                await ctx.warn(f"Invalid JSON in user_metadata, skipping: {user_metadata}")
        
        associations_data = {"organisation_id": organisation_id}
        if data_custodian_id:
            associations_data["data_custodian_id"] = data_custodian_id
        if point_of_contact:
            associations_data["point_of_contact"] = point_of_contact
        
        approvals_data = {
            "ethics_registration": {
                "relevant": ethics_registration_relevant,
                "obtained": ethics_registration_obtained
            },
            "ethics_access": {
                "relevant": ethics_access_relevant,
                "obtained": ethics_access_obtained
            },
            "indigenous_knowledge": {
                "relevant": indigenous_knowledge_relevant,
                "obtained": indigenous_knowledge_obtained
            },
            "export_controls": {
                "relevant": export_controls_relevant,
                "obtained": export_controls_obtained
            }
        }
        
        collection_format = CollectionFormat(
            dataset_info=CollectionFormatDatasetInfo(**dataset_info_data),
            associations=CollectionFormatAssociations(**associations_data),
            approvals=CollectionFormatApprovals(**approvals_data)
        )
        
        
        result = await client.datastore.mint_dataset(dataset_mint_info=collection_format)


        
        if not result.status.success:
            await ctx.error(f"Registration failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        new_id = result.handle
        await ctx.info(f"Dataset registered successfully with ID: {new_id}")
        
        return {
            "status": "success",
            "dataset_id": new_id,
            "message": f"Dataset '{name}' registered successfully",
            "handle_url": f"https://hdl.handle.net/{new_id}"
        }
        
    except Exception as e:
        await ctx.error(f"Registration failed: {str(e)}")
        return {"status": "error", "message": str(e)}
@mcp.tool()
async def create_person(
    ctx: Context,
    first_name: str,
    last_name: str,
    email: str,
    display_name: Optional[str] = None, 
    orcid: Optional[str] = None,
    ethics_approved: bool = True,
    user_metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Register a new person in the Provena registry.

    CRITICAL: Never call this tool until ALL required info collected and confirmed. Do NOT skip any fields and DO NOT make assumptions. - If any required field is missing, ask the user for it. Do not guess or invent values.
    DO NOT USE UNTIL THE USER HAS PROVIDED ALL REQUIRED INFORMATION AND CONFIRMED. Use the prompt register_entity_workflow to guide the user.

    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH AND EVERY field conversationally, one by one
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool

    IMPORTANT FIELDS
    - first_name: Given name(s)
    - last_name: Family name(s)
    - email: Contact email
    - display_name: Display name (optional; defaults to "first_name+last_name")
    - orcid: ORCID iD (optional; can be just the ID or full URL)
    - ethics_approved: Ethics approved for registry (default True) (True/False)
    - user_metadata: Dictionary of additional metadata (string values) - DO NOT STRINGIFY. (optional but still ask)
        - example: 
            user_metadata": {
                "party": "hufflepuff"
            }
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from pydantic import ValidationError
        from ProvenaInterfaces.RegistryModels import PersonDomainInfo
        
        final_display_name = display_name or f"{first_name.strip()} {last_name.strip()}"
        
        orcid_url = None
        if orcid:
            orcid = orcid.strip()
            if orcid and not orcid.startswith("http"):
                orcid_url = f"https://orcid.org/{orcid}"
            else:
                orcid_url = orcid
        
        person_info = PersonDomainInfo(
            display_name=final_display_name,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            email=email.strip(),
            orcid=orcid_url,
            ethics_approved=ethics_approved,
            user_metadata=user_metadata
        )

        result = await client.registry.person.create_item(
            create_item_request=person_info
        )
        
        if not getattr(result.status, "success", False):
            return {
                "status": "error",
                "message": getattr(result.status, "details", "Unknown failure"),
            }

        created_id = result.created_item.id

        await ctx.info(f"Person '{final_display_name}' registered with ID: {created_id}")
        
        return {
            "status": "success",
            "organisation_id": result.created_item.id,
            "message": f"Organisation registered successfully",
            "handle_url": f"https://hdl.handle.net/{result.created_item.id}" if result.created_item.id else None
        }
    
    except ValidationError as ve:
        await ctx.error(f"Validation failed: {ve}")
        return {
            "status": "error",
            "message": "Validation failed",
            "details": [{"field": err["loc"], "message": err["msg"]} for err in ve.errors()]
        }
    except Exception as e:
        await ctx.error(f"Person creation failed: {str(e)}")
        return {"status": "error", "message": str(e)}
    
@mcp.tool()
async def create_organisation(
    ctx: Context,
    name: str,
    display_name: Optional[str] = None, 
    ror: Optional[str] = None,
    user_metadata: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Register a new organisation in the Provena registry.

    DO NOT USE UNTIL THE USER HAS PROVIDED ALL REQUIRED INFORMATION AND CONFIRMED.

    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH AND EVERY field conversationally, one by one in the
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool

    IMPORTANT FIELDS
    - name: Organisation name
    - display_name: Display name (optional; defaults to name)
    - ror: ROR iD or URL (optional; can be just the ID or full URL)
    - user_metadata: Optional dictionary of additional metadata (string values) 
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}

    try:
        from pydantic import ValidationError
        from ProvenaInterfaces.RegistryModels import OrganisationDomainInfo

        final_display_name = display_name.strip() if display_name else name.strip()

        ror_url = ror.strip() if ror else None
        if ror_url and not ror_url.startswith("http"):
            ror_url = f"https://ror.org/{ror_url}"

        org_info = OrganisationDomainInfo(
            display_name=final_display_name,
            name=name,
            ror=ror_url,
            user_metadata=user_metadata
        )

        result = await client.registry.organisation.create_item(
            create_item_request=org_info
        )

        if not result.status.success:
            return {"status": "error", "message": result.status.details}

        return {
            "status": "success",
            "organisation_id": result.created_item.id,
            "message": f"Organisation '{final_display_name}' registered successfully"
        }
    except ValidationError as ve:
        return {"status": "error", "message": "Validation failed", "details": ve.errors()}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=5000)
    else:
        mcp.run()