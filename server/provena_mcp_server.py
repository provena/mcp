"""Provena MCP server tools and prompts.

This module wires Provena client calls into FastMCP tools and prompts.
The file is intentionally conservative about behaviour changes: edits here
are limited to small quality / typing fixes and correctness adjustments.
"""

import sys
import os
import asyncio
import json
from typing import Optional, Dict, Any, Tuple

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

@mcp.prompt("comprehensive_entity_research")
def comprehensive_entity_research_prompt(entity_id: str, research_focus: str = "general") -> str:
    """Generate comprehensive research report for a single entity."""
    
    focus_params = {
        "general": "max_depth=3, include all aspects",
        "provenance": "max_depth=4, emphasize lineage graphs",
        "quality": "max_depth=2, focus on metadata gaps",
        "impact": "include_downstream=True, include_upstream=False",
        "sources": "include_upstream=True, include_downstream=False"
    }
    
    params = focus_params.get(research_focus, focus_params["general"])
    
    return f"""Research entity {entity_id} with focus: {research_focus}

**Tool**: research_entity(entity_id="{entity_id}", {params})

This automatically gathers: entity details, upstream/downstream lineage, related entities, statistics, and recommendations.

**Report Structure**:
1. Executive Summary - key findings
2. Entity Overview - type, name, metadata, handle URL
3. Lineage Analysis - upstream sources and downstream derivatives  
4. Related Entities - people, orgs, models (with counts by type)
5. Quality Assessment - metadata completeness and gaps
6. Recommendations - prioritized action items

Present findings with:
- Clear markdown headings
- Tables for structured data
- Handle URLs as links: [Name](https://hdl.handle.net/{{id}})
- Bullet lists for recommendations
- **Bold** for important insights

Adjust depth parameter (1-5) based on how deep to trace lineage. Default 3 is balanced.
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
        try:
            # model_dump() returns Python primitives (dict/list) in pydantic v2.
            return obj.model_dump()
        except TypeError:
            # Fallback to json-compatible dump
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
    """
    return """When user asks for a link to a record, provide the full handle URL:

https://hdl.handle.net/{id}

Replace {id} with the actual record ID. Always use the full URL, never just the ID.

Example: https://hdl.handle.net/12345/abcde
"""

@mcp.prompt("batch_query_guide")
def batch_query_guide() -> str:
    """Guide for efficiently querying many entities at once."""
    return """For queries returning many results (10+ entities), use efficient tools:

**list_entities_summary** - List entities by type
- Example: list_entities_summary(subtype_filter="MODEL_RUN", search_query="CSIRO", limit=50)
- Returns: Lightweight summaries with key metadata only

**find_related_entities** - Find connected entities  
- Example: find_related_entities(entity_id="X", relationship_type="upstream")
- Returns: Related entities with relationship info

**get_entity_associations** - Quick association lookup
- Example: get_entity_associations(entity_id="X")
- Returns: People/org associations with resolved names

**Workflow**: Summary list → User selects → research_entity for details

Avoid: Calling research_entity in loops (very slow for multiple entities)
"""

@mcp.prompt("discover_entities")
def discover_entities_prompt() -> str:
    """Guide for exploring and discovering entities in Provena."""
    return """**Entity Discovery Tools:**

**search_registry** - Search by keywords
- Use when: User knows part of the name or has keywords
- Example: search_registry(query="coral reef", subtype_filter="DATASET")

**list_entities_summary** - Browse all entities of a type
- Use when: User wants to see what's available
- Example: list_entities_summary(subtype_filter="MODEL", limit=50)

**find_related_entities** - Navigate relationships  
- Use when: User wants to explore connections from a known entity
- Example: find_related_entities(entity_id="X", relationship_type="downstream")

**get_registry_items_count** - Get overview statistics
- Use when: User wants to understand scope
- Returns: Count of each entity type in the system

**research_entity** - Deep dive on single entity
- Use when: User wants comprehensive details on ONE specific entity
- Returns: Full lineage, relationships, metadata

**Progressive disclosure pattern:**
1. Start broad (counts/search) → 2. Show summaries → 3. Offer detailed research

When uncertain about user intent, ask clarifying questions before executing queries.
"""

@mcp.prompt("dataset_registration_workflow")
def dataset_registration_workflow() -> str:
    """
    Guided DATASET (data store item) registration workflow that ensures complete data collection.
    
    For DATASETS (actual data), NOT dataset templates (use register_entity_workflow for templates).
    """
    return """You are a Provena DATASET registration specialist.

IMPORTANT: This is for DATASETS (actual data items), NOT dataset templates.

=== WORKFLOW ===

1. **INITIALIZATION**
   - Check login status (if not logged in, stop and ask user to log in first)
   - Greet and explain you'll help register a DATASET (actual data)
   - Process: collect fields → summary → confirm → register

2. **COLLECT INFORMATION** (Ask conversationally, accept any format)
   Reference register_dataset tool documentation for all fields:
   
   Convert user input to expected formats (e.g., YYYY-MM-DD for dates).
   For IDs (publisher, organisation, custodian), offer to search if needed.

3. **VALIDATION & CONFIRMATION**
   Show formatted summary of all collected fields.
   ASK: "Does this look correct? Type 'yes' to register."
   WAIT for explicit confirmation.

4. **REGISTRATION**
   ONLY after confirmation: register_dataset(all collected data)
   Show success with handle URL: https://hdl.handle.net/{id}

=== CRITICAL ===
- Ask for EVERY field (including optional ones)
- Never call register_dataset until confirmed
- If searching entities, show results with display names
"""

@mcp.prompt("register_entity_workflow")
def register_entity_workflow() -> str:
    """
    Guided registration workflow for Organizations, Persons, and Models.
    """
    return """You are a Provena entity registration specialist.

=== WORKFLOW ===

1. **INITIALIZATION**
   - Check login status (if not logged in, stop and ask user to log in first)
   - Greet and identify entity type (Organisation, Person, or Model)
   - Process: collect fields → summary → confirm → register

2. **COLLECT INFORMATION** (Ask conversationally for EVERY field)
   

3. **VALIDATION & CONFIRMATION**
   Show formatted summary of all collected fields.
   ASK: "Does this look correct? Type 'yes' to register."
   WAIT for explicit confirmation.

4. **REGISTRATION**
   ONLY after confirmation, call appropriate tool:
   - create_organisation (organisations)
   - create_person (persons)
   - create_model (models)
   
   Show success with handle URL: https://hdl.handle.net/{id}

=== CRITICAL ===
- Ask for ALL fields including optional ones
- Never call tool until confirmed
"""

@mcp.prompt("dataset_template_workflow")
def dataset_template_workflow() -> str:
    """
    Guided workflow for registering Dataset Templates with resource management.
    """
    return """You are a Provena Dataset Template registration specialist.

=== WORKFLOW ===

1. **INITIALIZATION**
   - Check login status (if not logged in, stop and ask user to log in first)
   - Greet and explain: "A dataset template defines structure and expected files/resources for datasets used in model runs"
   - Process: basic info → resources → summary → confirm → register

2. **COLLECT INFORMATION**
   
   **BASIC:**
   - display_name (required)
   - description (optional)
   
   **DEFINED RESOURCES** (optional - pre-defined file paths):
   For each resource:
   - path (file path in dataset)
   - description (what this file is)
   - usage_type (one of: GENERAL_DATA, CONFIG_FILE, FORCING_DATA, PARAMETER_FILE)
   - is_folder (boolean)
   - additional_metadata (optional JSON)
   
   Ask: "Add another defined resource?" (repeat until no)
   
   **DEFERRED RESOURCES** (optional - user-defined later):
   For each resource:
   - key (unique identifier)
   - description (what will be provided)
   - usage_type (same as above)
   - is_folder (boolean)
   - additional_metadata (optional JSON)
   
   Ask: "Add another deferred resource?" (repeat until no)
   
   **METADATA:**
   - user_metadata (optional - custom JSON)

3. **VALIDATION & CONFIRMATION**
   Show formatted summary:
   - Display name and description
   - Defined resources count and list
   - Deferred resources count and list
   - Custom metadata
   
   ASK: "Does this look correct? Type 'yes' to register."
   WAIT for explicit confirmation.

4. **REGISTRATION**
   ONLY after confirmation: create_dataset_template(all collected data)
   Show success with handle URL: https://hdl.handle.net/{id}

=== VALIDATION ===
- usage_type MUST be: GENERAL_DATA, CONFIG_FILE, FORCING_DATA, or PARAMETER_FILE
- At least one resource (defined or deferred) recommended

=== CRITICAL ===
Never call create_dataset_template until confirmed.
"""

@mcp.prompt("workflow_template_registration")
def workflow_template_registration() -> str:
    """
    Guided workflow for registering Model Run Workflow Templates with dependency management.
    """
    return """You are a Provena Model Run Workflow Template registration specialist.

=== WORKFLOW ===

1. **INITIALIZATION**
   - Greet and explain: "A workflow template defines inputs, outputs, and structure for model run activities"
   - Process: model → input templates → output templates → annotations → confirm → register

2. **MODEL** (REQUIRED)
   - Ask: "Do you have an existing model ID, or need to search/create?"
   - IF SEARCH: search_registry(subtype_filter="MODEL"), show results, record ID
   - IF CREATE: "Let's create the model first" → use register_entity_workflow
   - Record model_id

3. **BASIC INFO**
   - display_name: "What name for this workflow template?"

4. **INPUT DATASET TEMPLATES** (optional)
   - Ask: "Does your model require input dataset templates?"
   - IF YES, for each input:
     * "Have existing template ID, or search/create?"
     * IF SEARCH: search_registry(subtype_filter="DATASET_TEMPLATE"), show results
     * IF CREATE: Use dataset_template_workflow
     * Ask: "Is this input optional?" (true/false)
     * Add to list: {"template_id": "ID", "optional": bool}
     * Ask: "Add another input?" (repeat until no)

5. **OUTPUT DATASET TEMPLATES** (optional)
   - Ask: "Does your model produce output dataset templates?"
   - IF YES, same process as inputs
   - Add to output_templates list

6. **ANNOTATIONS** (optional)
   - Ask: "Specify required annotations?" 
     * Explain: "Metadata keys that MUST be provided when registering model runs"
     * If yes: collect comma-separated keys (e.g., "experiment_id,run_config")
   
   - Ask: "Specify optional annotations?"
     * Explain: "Metadata keys that MAY be provided"
     * If yes: collect comma-separated keys

7. **METADATA** (optional)
   - Ask: "Add custom metadata to this template?"
   - If yes: collect as JSON object

8. **VALIDATION & CONFIRMATION**
   Show formatted summary:
   - Display name
   - Model ID (with name if available)
   - Input templates count (list IDs and optional status)
   - Output templates count (list IDs and optional status)
   - Required annotations (if any)
   - Optional annotations (if any)
   - Custom metadata (if any)
   
   ASK: "Does this look correct? Type 'yes' to register."
   WAIT for explicit confirmation.

9. **REGISTRATION**
   ONLY after confirmation: create_model_run_workflow_template with:
   - display_name
   - model_id
   - input_template_ids (JSON string)
   - output_template_ids (JSON string)
   - required_annotations (comma-separated)
   - optional_annotations (comma-separated)
   - user_metadata (JSON string)
   
   Show success with handle URL: https://hdl.handle.net/{id}

=== CRITICAL ===
- If creating dependencies (model/templates), complete fully before returning
- Track workflow position carefully
- Never call create_model_run_workflow_template until confirmed
- If searching, show results with display names
"""

@mcp.prompt("model_run_registration")
def model_run_registration() -> str:
    """
    Guided workflow for registering Model Runs with validation and dependency checking.
    
    Model runs document actual executions of computational models, linking input datasets
    to output datasets through a specific model version, creating the provenance graph.
    """
    return """You are a Provena Model Run registration specialist.

CRITICAL: Ask ONE question per message. User can provide any format - convert as needed.

=== WORKFLOW ===

1. **INITIALIZATION**
   - Greet and explain model runs create provenance graph linking inputs→model→outputs
   - Process: template → details → datasets → annotations → confirm → register

2. **WORKFLOW TEMPLATE** (REQUIRED)
   - Ask: "Do you have a workflow template ID, or need to search?"
   - IF SEARCH: search_registry(subtype_filter="MODEL_RUN_WORKFLOW_TEMPLATE"), show results
   - IF NEW: Explain "Need template first" → use workflow_template_registration prompt
   - Fetch template to check input/output/annotation requirements

3. **BASIC INFO**
   - display_name: "What name for this model run?" (unique identifier)
   - description: "Describe this run" (purpose, parameters, conditions)
   - model_version: "Different version than template?" (optional)

4. **TEMPORAL** (ISO 8601 required: YYYY-MM-DDTHH:MM:SSZ)
   - start_time: "When did execution start?" (accept any format, convert)
   - end_time: "When did it finish?" (validate: must be after start_time)

5. **ASSOCIATIONS** (REQUIRED - search or provide IDs)
   - modeller_id: "Who ran this?" → search_registry(subtype_filter="PERSON")
   - requesting_organisation_id: "Which org requested?" → search_registry(subtype_filter="ORGANISATION")
   - Offer to create new if not found

6. **INPUT DATASETS** (optional but recommended)
   - "Which datasets were inputs?" (reference template requirements)
   - For each: search or provide ID, add to list
   - "Add another?" (repeat)

7. **OUTPUT DATASETS** (optional but recommended)
   - "Which datasets were outputs?" (reference template requirements)
   - Same process as inputs

8. **ANNOTATIONS** (check template requirements)
   - IF required_annotations: "Template requires: {list}" → collect each
   - IF optional_annotations: "Provide optional? {list}" → collect if yes
   - Format: {"key": "value"}

9. **USER METADATA** (optional)
   - "Add custom metadata?" → collect as key-value pairs, format as JSON

10. **CONFIRMATION**
    Show summary:
    - All collected fields with values
    - Input/output counts
    - Annotations
    ASK: "Does this look correct? Type 'yes' to register."
    WAIT for explicit "yes"

11. **REGISTRATION**
    ONLY after confirmation: create_model_run(all collected data)

12. **POST-REGISTRATION**
    - Success message
    - Show handle URL: https://hdl.handle.net/{id}
    - Explain provenance graph created

=== VALIDATION ===
- Timestamps: ISO 8601 with Z timezone
- end_time after start_time
- All IDs valid handle format
- Required annotations present
- Never hallucinate IDs/timestamps

=== CRITICAL ===
Never call create_model_run until ALL required info collected and explicitly confirmed.
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


def _get_prov_client(client: ProvenaClient) -> Optional[Any]:
    """Return the provenance API client if available on a ProvenaClient instance."""
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
async def research_entity(
    ctx: Context,
    entity_id: str,
    max_depth: int = 3,
    include_upstream: bool = True,
    include_downstream: bool = True,
    include_related_agents: bool = True
) -> Dict[str, Any]:
    """
    Comprehensive entity research tool that automatically gathers ALL related information.
    
    This tool performs a complete investigation of a Provena entity, gathering:
    - Full entity details (metadata, properties, associations)
    - Upstream lineage (inputs, dependencies, contributing datasets/agents)
    - Downstream lineage (outputs, derivatives, effected datasets/agents)
    - All related entities (people, organisations, models, templates)
    - Provenance graph structure and relationships
    
    Use this tool when you need complete context about a dataset, model run, or any registry entity.
    Perfect for generating reports, understanding data provenance, or investigating relationships.
    
    Args:
        entity_id: The handle/ID of the entity to research (e.g., "10378.1/1234567")
        max_depth: Maximum depth for lineage traversal (default: 3, recommended range: 1-5)
        include_upstream: Include upstream lineage exploration (default: True)
        include_downstream: Include downstream lineage exploration (default: True)
        include_related_agents: Include related people/organisations (default: True)
    
    Returns:
        Comprehensive dictionary containing:
        - entity: Full entity details
        - entity_type: Type and subtype of entity
        - upstream_lineage: Upstream graph with all contributing entities
        - downstream_lineage: Downstream graph with all derived entities
        - related_entities: All connected entities with full details
        - statistics: Summary counts and metrics
        - recommendations: Suggested follow-up actions
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    prov_client = _get_prov_client(client)
    
    try:
        await ctx.info(f"Starting comprehensive research for entity {entity_id}")
        
        # Step 1: Fetch the root entity details
        await ctx.info("Fetching root entity details...")
        root_entity_result = await client.registry.general_fetch_item(id=entity_id)
        
        if not root_entity_result.status.success:
            await ctx.error(f"Failed to fetch root entity: {root_entity_result.status.details}")
            return {
                "status": "error",
                "message": f"Failed to fetch entity: {root_entity_result.status.details}",
                "entity_id": entity_id
            }
        
        root_entity = _dump(root_entity_result.item)
        entity_subtype = root_entity.get('item_subtype', 'UNKNOWN')
        entity_category = root_entity.get('item_category', 'UNKNOWN')
        
        await ctx.info(f"Root entity type: {entity_category}/{entity_subtype}")
        
        # Initialize result structure
        result = {
            "status": "success",
            "entity_id": entity_id,
            "entity": root_entity,
            "entity_type": {
                "category": entity_category,
                "subtype": entity_subtype
            },
            "statistics": {
                "total_related_entities": 0,
                "upstream_entities": 0,
                "downstream_entities": 0,
                "datasets": 0,
                "model_runs": 0,
                "people": 0,
                "organisations": 0,
                "models": 0,
                "templates": 0
            },
            "recommendations": []
        }
        
        # Step 2: Explore upstream lineage
        if include_upstream and prov_client:
            await ctx.info(f"Exploring upstream lineage (depth={max_depth})...")
            try:
                upstream_result = await prov_client.explore_upstream(
                    starting_id=entity_id,
                    depth=max_depth
                )
                upstream_data = _dump(upstream_result)
                result["upstream_lineage"] = upstream_data
                
                # Count upstream nodes
                upstream_summary = _count_nodes_edges(upstream_data or {})
                result["statistics"]["upstream_entities"] = upstream_summary.get("nodes", 0) or 0
                
                await ctx.info(f"Found {result['statistics']['upstream_entities']} upstream entities")
            except Exception as e:
                await ctx.warn(f"Upstream exploration failed: {str(e)}")
                result["upstream_lineage"] = {"error": str(e)}
        
        # Step 3: Explore downstream lineage
        if include_downstream and prov_client:
            await ctx.info(f"Exploring downstream lineage (depth={max_depth})...")
            try:
                downstream_result = await prov_client.explore_downstream(
                    starting_id=entity_id,
                    depth=max_depth
                )
                downstream_data = _dump(downstream_result)
                result["downstream_lineage"] = downstream_data
                
                # Count downstream nodes
                downstream_summary = _count_nodes_edges(downstream_data or {})
                result["statistics"]["downstream_entities"] = downstream_summary.get("nodes", 0) or 0
                
                await ctx.info(f"Found {result['statistics']['downstream_entities']} downstream entities")
            except Exception as e:
                await ctx.warn(f"Downstream exploration failed: {str(e)}")
                result["downstream_lineage"] = {"error": str(e)}
        
        # Step 4: For datasets and model runs, get specialized lineage
        if entity_subtype in ['DATASET', 'MODEL_RUN'] and prov_client:
            await ctx.info("Fetching specialized lineage for dataset/model run...")
            
            # Contributing datasets
            try:
                contrib_datasets = await prov_client.get_contributing_datasets(
                    starting_id=entity_id,
                    depth=max_depth
                )
                result["contributing_datasets"] = _dump(contrib_datasets)
                await ctx.info("Retrieved contributing datasets")
            except Exception as e:
                await ctx.warn(f"Contributing datasets query failed: {str(e)}")
            
            # Effected datasets
            try:
                effected_datasets = await prov_client.get_effected_datasets(
                    starting_id=entity_id,
                    depth=max_depth
                )
                result["effected_datasets"] = _dump(effected_datasets)
                await ctx.info("Retrieved effected datasets")
            except Exception as e:
                await ctx.warn(f"Effected datasets query failed: {str(e)}")
            
            # Related agents
            if include_related_agents:
                try:
                    contrib_agents = await prov_client.get_contributing_agents(
                        starting_id=entity_id,
                        depth=max_depth
                    )
                    result["contributing_agents"] = _dump(contrib_agents)
                    await ctx.info("Retrieved contributing agents")
                except Exception as e:
                    await ctx.warn(f"Contributing agents query failed: {str(e)}")
                
                try:
                    effected_agents = await prov_client.get_effected_agents(
                        starting_id=entity_id,
                        depth=max_depth
                    )
                    result["effected_agents"] = _dump(effected_agents)
                    await ctx.info("Retrieved effected agents")
                except Exception as e:
                    await ctx.warn(f"Effected agents query failed: {str(e)}")
        
        # Step 5: Collect and fetch all unique entity IDs from graphs
        await ctx.info("Collecting all unique entity IDs from lineage graphs...")
        unique_entity_ids = set()
        
        # Extract IDs from all graph responses
        for key in ['upstream_lineage', 'downstream_lineage', 'contributing_datasets', 
                    'effected_datasets', 'contributing_agents', 'effected_agents']:
            if key in result and isinstance(result[key], dict):
                graph_data = result[key].get('graph', {})
                if isinstance(graph_data, dict) and 'nodes' in graph_data:
                    for node in graph_data.get('nodes', []):
                        if isinstance(node, dict) and 'id' in node:
                            unique_entity_ids.add(node['id'])
        
        # Remove the root entity from the set
        unique_entity_ids.discard(entity_id)
        
        await ctx.info(f"Found {len(unique_entity_ids)} unique related entities")
        
        # Step 6: Fetch full details for all related entities
        related_entities = {}
        entity_types_count = {}
        
        if unique_entity_ids:
            await ctx.info("Fetching full details for all related entities...")
            
            for related_id in list(unique_entity_ids)[:100]:  # Limit to 100 to avoid overwhelming
                try:
                    related_result = await client.registry.general_fetch_item(id=related_id)
                    if related_result.status.success:
                        related_entity = _dump(related_result.item)
                        related_entities[related_id] = related_entity
                        
                        # Count by type
                        subtype = related_entity.get('item_subtype', 'UNKNOWN')
                        entity_types_count[subtype] = entity_types_count.get(subtype, 0) + 1
                except Exception as e:
                    await ctx.warn(f"Failed to fetch entity {related_id}: {str(e)}")
                    continue
        
        result["related_entities"] = related_entities
        result["statistics"]["total_related_entities"] = len(related_entities)
        
        # Update statistics with type counts
        result["statistics"]["datasets"] = entity_types_count.get('DATASET', 0)
        result["statistics"]["model_runs"] = entity_types_count.get('MODEL_RUN', 0)
        result["statistics"]["people"] = entity_types_count.get('PERSON', 0)
        result["statistics"]["organisations"] = entity_types_count.get('ORGANISATION', 0)
        result["statistics"]["models"] = entity_types_count.get('MODEL', 0)
        result["statistics"]["templates"] = (
            entity_types_count.get('DATASET_TEMPLATE', 0) +
            entity_types_count.get('MODEL_RUN_WORKFLOW_TEMPLATE', 0)
        )
        
        await ctx.info(f"Statistics: {result['statistics']}")
        
        # Step 7: Generate recommendations
        await ctx.info("Generating recommendations...")
        
        if result["statistics"]["upstream_entities"] == 0 and entity_subtype == 'DATASET':
            result["recommendations"].append({
                "priority": "medium",
                "action": "Investigate data provenance",
                "details": "This dataset has no recorded upstream lineage. Consider documenting its sources or creation process."
            })
        
        if result["statistics"]["downstream_entities"] == 0 and entity_category == 'ACTIVITY':
            result["recommendations"].append({
                "priority": "low",
                "action": "Check for outputs",
                "details": "This activity has no recorded downstream entities. Verify if outputs were registered."
            })
        
        if result["statistics"]["total_related_entities"] > 50:
            result["recommendations"].append({
                "priority": "low",
                "action": "Complex lineage detected",
                "details": "This entity has many relationships. Consider using visualization tools to understand the full graph."
            })
        
        await ctx.info(f"Research complete! Found {result['statistics']['total_related_entities']} related entities")
        
        return result
        
    except Exception as e:
        await ctx.error(f"Entity research failed: {str(e)}")
        return {
            "status": "error",
            "message": str(e),
            "entity_id": entity_id
        }
    
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
async def find_related_entities(
    ctx: Context,
    entity_id: str,
    relationship_type: str = "all",
    entity_types: Optional[str] = None
) -> Dict[str, Any]:
    """
    Find entities related to a specific entity through various relationship types.
    Returns lightweight summaries, not full details.
    DO NOT AUTOMATICALLY FETCH FULL DETAILS FOR ALL ENTITIES, ASK FIRST IF NEEDED.
    Just use all for relationship_type regarding people or organisations
    If nothing returns, the entity likely has no such relationships.
    
    Use cases:
    - "Find all datasets used by this model run"
    - "Show all model runs by this person"
    - "List all entities created by this organisation"
    - "What datasets did this model run produce?"
    
    Args:
        entity_id: The entity to find relationships for
        relationship_type: Type of relationship
            - "all": All related entities (default)
            - "upstream": Entities this depends on (inputs/sources)
            - "downstream": Entities that depend on this (outputs/derivatives)
            - "uses": Entities this uses (for MODEL_RUN/MODEL)
            - "used_by": Entities that use this (for DATASET/MODEL)
        entity_types: Comma-separated entity types to filter (e.g., "DATASET,MODEL_RUN")
    
    Returns:
        Lightweight list of related entities with id, name, type, and relationship
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    prov_client = _get_prov_client(client)
    
    try:
        await ctx.info(f"Finding {relationship_type} relationships for {entity_id}")
        
        # Fetch the root entity to understand its type
        root_result = await client.registry.general_fetch_item(id=entity_id)
        if not root_result.status.success:
            return {"status": "error", "message": f"Failed to fetch entity: {root_result.status.details}"}
        
        root_entity = _dump(root_result.item)
        root_subtype = root_entity.get('item_subtype', 'UNKNOWN')
        
        # Parse entity type filter
        type_filter = set()
        if entity_types:
            type_filter = set(t.strip().upper() for t in entity_types.split(','))
        
        related_entities = []
        
        # Gather entity IDs based on relationship type
        entity_ids = set()
        
        if relationship_type in ["all", "upstream"] and prov_client:
            try:
                upstream = await prov_client.explore_upstream(starting_id=entity_id, depth=2)
                upstream_data = _dump(upstream)
                graph = upstream_data.get('graph', {})
                for node in graph.get('nodes', []):
                    node_id = node.get('id')
                    if node_id and node_id != entity_id:
                        entity_ids.add((node_id, 'upstream'))
            except Exception as e:
                await ctx.info(f"Upstream exploration failed: {str(e)}")
        
        if relationship_type in ["all", "downstream"] and prov_client:
            try:
                downstream = await prov_client.explore_downstream(starting_id=entity_id, depth=2)
                downstream_data = _dump(downstream)
                graph = downstream_data.get('graph', {})
                for node in graph.get('nodes', []):
                    node_id = node.get('id')
                    if node_id and node_id != entity_id:
                        entity_ids.add((node_id, 'downstream'))
            except Exception as e:
                await ctx.info(f"Downstream exploration failed: {str(e)}")
        
        # Validate created_by is only used for PERSON/ORGANISATION
        if relationship_type == "created_by" and root_subtype not in ["PERSON", "ORGANISATION"]:
            return {
                "status": "error",
                "message": f"'created_by' relationship type is only valid for PERSON or ORGANISATION entities. "
                          f"Entity {entity_id} is of type {root_subtype}. "
                          f"For {root_subtype} entities, try 'used_by', 'upstream', or 'downstream' instead."
            }
        
        # Special handling for PERSON/ORGANISATION - find created entities
        if relationship_type in ["all", "created_by"] and root_subtype in ["PERSON", "ORGANISATION"]:
            # Search for entities that reference this person/org
            from ProvenaInterfaces.RegistryAPI import GeneralListRequest
            list_request = GeneralListRequest(filter_by=None, sort_by=None, pagination_key=None)
            list_result = await client.registry.list_general_registry_items(general_list_request=list_request)
            
            if list_result.status.success:
                await ctx.info(f"Checking {len(list_result.items[:200])} items for associations with {entity_id}")
                for item in list_result.items[:200]:  # Check first 200 items
                    try:
                        # Get the item ID - handle both object and dict formats
                        item_id = item.id if hasattr(item, 'id') else item.get('id') if isinstance(item, dict) else None
                        if not item_id:
                            continue
                        
                        # IMPORTANT: Fetch full entity details to get complete associations data
                        # The list API returns lightweight objects without nested fields
                        full_item_result = await client.registry.general_fetch_item(id=item_id)
                        if not full_item_result.status.success:
                            continue
                        
                        # Now work with the full entity data
                        item_data = _dump(full_item_result.item)
                        
                        # Check various association fields based on entity type
                        if root_subtype == "PERSON":
                            # Check MODEL_RUN associations
                            associations = item_data.get('associations', {})
                            if (associations.get('modeller_id') == entity_id or
                                associations.get('data_custodian_id') == entity_id):
                                entity_ids.add((item_id, 'created_by'))
                            
                            # For datasets, check collection_format associations
                            cf = item_data.get('collection_format', {})
                            if cf:
                                cf_assoc = cf.get('associations', {})
                                if (cf_assoc.get('data_custodian_id') == entity_id or
                                    cf_assoc.get('point_of_contact') == entity_id):
                                    entity_ids.add((item_id, 'created_by'))

                        # Additional: templates (dataset or workflow templates) often don't
                        # populate the same association fields as datasets/model_runs.
                        # Check common top-level creator fields and user_metadata so
                        # templates created by a person/org are included in results.
                        item_subtype = item_data.get('item_subtype', '')
                        if item_subtype in [
                            'DATASET_TEMPLATE',
                            'MODEL_RUN_WORKFLOW_TEMPLATE'
                        ]:
                            # common explicit creator fields
                            creator_fields = [
                                'created_by', 'creator', 'creator_id', 'created_by_id',
                                'owner_id', 'record_creator', 'record_creator_organisation'
                            ]
                            for cf in creator_fields:
                                try:
                                    if item_data.get(cf) == entity_id:
                                        entity_ids.add((item_id, 'created_by'))
                                        break
                                except Exception:
                                    pass

                            # associations object on templates (if present)
                            tpl_assoc = item_data.get('associations', {})
                            if isinstance(tpl_assoc, dict):
                                for k, v in tpl_assoc.items():
                                    if v == entity_id:
                                        entity_ids.add((item_id, 'created_by'))
                                        break

                            # user_metadata may contain references to the creator
                            um = item_data.get('user_metadata') or {}
                            if isinstance(um, dict):
                                for v in um.values():
                                    if v == entity_id:
                                        entity_ids.add((item_id, 'created_by'))
                                        break
                        
                        elif root_subtype == "ORGANISATION":
                            # Check MODEL_RUN associations
                            associations = item_data.get('associations', {})
                            if (associations.get('organisation_id') == entity_id or
                                associations.get('requesting_organisation_id') == entity_id):
                                entity_ids.add((item_id, 'created_by'))
                            
                            # For datasets, check collection_format associations and publisher
                            cf = item_data.get('collection_format', {})
                            if cf:
                                ds_info = cf.get('dataset_info', {})
                                if ds_info.get('publisher_id') == entity_id:
                                    entity_ids.add((item_id, 'created_by'))
                                
                                cf_assoc = cf.get('associations', {})
                                if cf_assoc.get('organisation_id') == entity_id:
                                    entity_ids.add((item_id, 'created_by'))
                                
                    except Exception as e:
                        # Use item_id if available, otherwise try to extract from item
                        error_id = item_id if 'item_id' in locals() else (item.get('id') if isinstance(item, dict) else 'unknown')
                        await ctx.info(f"Error checking item {error_id}: {str(e)}")
                        continue
        
        await ctx.info(f"Found {len(entity_ids)} related entity IDs")
        
        # Fetch minimal info for each related entity
        for rel_id, rel_type in entity_ids:
            try:
                result = await client.registry.general_fetch_item(id=rel_id)
                if result.status.success:
                    entity = _dump(result.item)
                    entity_subtype = entity.get('item_subtype', 'UNKNOWN')
                    
                    # Apply type filter
                    if type_filter and entity_subtype not in type_filter:
                        continue
                    
                    summary = {
                        "id": rel_id,
                        "handle_url": f"https://hdl.handle.net/{rel_id}",
                        "display_name": entity.get('display_name', 'N/A'),
                        "type": entity_subtype,
                        "relationship": rel_type,
                        "created_timestamp": entity.get('created_timestamp')
                    }
                    
                    related_entities.append(summary)
                    
            except Exception as e:
                await ctx.warn(f"Failed to fetch {rel_id}: {str(e)}")
                continue
        
        # Group by relationship type
        grouped = {}
        for entity in related_entities:
            rel_type = entity['relationship']
            if rel_type not in grouped:
                grouped[rel_type] = []
            grouped[rel_type].append(entity)
        
        await ctx.info(f"Successfully found {len(related_entities)} related entities")
        
        return {
            "status": "success",
            "entity_id": entity_id,
            "root_entity_type": root_subtype,
            "relationship_type": relationship_type,
            "type_filter": list(type_filter) if type_filter else None,
            "total_count": len(related_entities),
            "grouped_by_relationship": grouped,
            "all_entities": related_entities
        }
        
    except Exception as e:
        await ctx.error(f"Failed to find related entities: {str(e)}")
        return {"status": "error", "message": str(e)}



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
    
    - Use the register_entity_workflow prompt for detailed guidance on gathering information.

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

    - Use the dataset_template_workflow prompt for detailed guidance on gathering information. 

    Dataset templates define the structure/schema for datasets used in model runs.
    They specify what files/resources are expected in a dataset.
    
    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH field conversationally, one by one
    2. Show complete summary of ALL collected information
    3. Get explicit user confirmation before calling this tool
    4. Only call this tool with ALL required information present

    REQUIRED FIELDS:
    - display_name: Name for this template

    OPTIONAL FIELDS (ALWAYS ASK FOR THESE TOO):
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
    
    - Use the workflow_template_registration prompt for detailed guidance on gathering information.

    Model run workflow templates define the inputs, outputs, and annotations required
    for registering model runs. They act as blueprints for model run activities.

    REQUIRED FIELDS:
    - display_name: User-friendly name for this workflow template (e.g., "Simple Coral Model v1.5 Workflow")
    - model_id: The ID of a registered Model entity that this workflow template is for

    OPTIONAL FIELDS (ALWAYS ASK FOR THESE TOO):
    - input_template_ids: JSON string array of input dataset template IDs with optional flags
    
    - output_template_ids: JSON string array of output dataset template IDs with optional flags
    
    - required_annotations: Comma-separated list of required annotation keys
    
    - optional_annotations: Comma-separated list of optional annotation keys - these are required
    
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

    - Use the dataset_registration_workflow prompt for detailed guidance on gathering information.

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
            "person_id": created_id,
            "message": f"Person '{final_display_name}' registered successfully",
            "handle_url": f"https://hdl.handle.net/{created_id}" if created_id else None
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


@mcp.tool()
async def create_model_run(
    ctx: Context,
    workflow_template_id: str,
    display_name: str,
    description: str,
    start_time: str, 
    end_time: str,   
    associations_modeller_id: str, 
    associations_requesting_organisation_id: str, 
    model_version: Optional[str] = None,
    input_datasets: Optional[str] = None, 
    output_datasets: Optional[str] = None,
    annotations: Optional[str] = None,
    user_metadata: Optional[str] = None
) -> Dict[str, Any]:
    """
    Register a model run activity that documents an actual execution of a model.
    DO NOT USE UNTIL THE USER HAS PROVIDED ALL REQUIRED INFORMATION AND CONFIRMED. Use the prompt register_workflow to guide the user.

    - Use the model_run_registration prompt for detailed guidance on gathering information.

    IMPORTANT WORKFLOW - Follow this exact process:
    1. Ask user for EACH field conversationally, one by one - ENSURE YOU ASK TO COLLECT INFORMATION FOR EVERY SINGLE FIELD, INCLUDING THE OPTIONAL ONES
    2. Validate workflow template exists and fetch its requirements
    3. Collect annotations matching template's required/optional keys
    4. Show complete summary of ALL collected information
    5. Get explicit user confirmation before calling this tool
    6. Only call this tool with ALL required information present
    
    This creates a provenance record linking:
    - Input datasets → Model execution → Output datasets
    - Following the structure defined by a workflow template
    
    REQUIRED FIELDS:
    - workflow_template_id: The workflow template this run follows (search with subtype_filter="MODEL_RUN_WORKFLOW_TEMPLATE")
    -- If asked to create, follow the create_model_run_workflow_template tool first and then provide the returned workflow_template_id here, and continue to the next step
    - display_name: User-friendly name for this run (e.g., "Coral Model Run - Jan 2024")
    - description: What this model run was for
    - start_time: When execution started (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)
    - end_time: When execution completed (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)
    - associations_modeller_id: PERSON ID of who ran the model 
    - associations_requesting_organisation_id: ORGANISATION ID 
    
    OPTIONAL FIELDS:
    - model_version: Version string if different from template's model (e.g., "v1.5.2")
    - input_datasets: JSON array of input dataset IDs used
    -- If asked to create, follow the prompt register_dataset to create datasets first and then provide the returned dataset_ids here and continue to the next step
    - output_datasets: JSON array of output dataset IDs produced
    -- If asked to create, follow the prompt register_dataset to create datasets first and then provide the returned dataset_ids here and continue to the next step
    - annotations: JSON object with metadata matching template requirements
      - Example: '{"experiment_id": "EXP001", "run_config": "standard"}'
      - MUST include all keys from workflow template's required_annotations
      - MAY include keys from workflow template's optional_annotations
    - user_metadata: Additional custom metadata as JSON string
    
    Returns:
        Dictionary with registration status and model run ID
    """
    client = await require_authentication(ctx)
    if not client:
        return {"status": "error", "message": "Authentication required"}
    
    try:
        from ProvenaInterfaces.ProvenanceModels import (
            ModelRunRecord,
            AssociationInfo,
            TemplatedDataset,
            DatasetType
        )
        import json
        from datetime import datetime
        
        await ctx.info(f"Registering model run '{display_name}'")
        
        # Validate workflow template exists and get template info
        try:
            template_result = await client.registry.general_fetch_item(id=workflow_template_id)
            if not template_result.status.success:
                return {
                    "status": "error", 
                    "message": f"Workflow template {workflow_template_id} not found: {template_result.status.details}"
                }
            template = template_result.item
            
            # The template is returned as a dictionary, so access it accordingly
            if isinstance(template, dict):
                template_dict = template
                await ctx.info(f"Workflow template keys: {list(template_dict.keys())}")
            else:
                # Fallback for object types
                if hasattr(template, 'model_dump'):
                    template_dict = template.model_dump()
                elif hasattr(template, 'dict'):
                    template_dict = template.dict()
                else:
                    template_dict = vars(template) if hasattr(template, '__dict__') else {}
                await ctx.info(f"Workflow template fields: {list(template_dict.keys())}")
            
            # Extract input/output template info from workflow template
            # Try multiple possible field names
            input_templates = (
                template_dict.get('input_templates') or 
                template_dict.get('input_template_resources') or
                template_dict.get('inputs') or
                []
            )
            output_templates = (
                template_dict.get('output_templates') or 
                template_dict.get('output_template_resources') or
                template_dict.get('outputs') or
                []
            )
            
            await ctx.info(f"Workflow template has {len(input_templates)} input templates and {len(output_templates)} output templates")
            
        except Exception as e:
            return {"status": "error", "message": f"Failed to fetch workflow template: {str(e)}"}
        
        # Parse and convert timestamps to Unix epoch (integers)
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            if end_dt <= start_dt:
                return {"status": "error", "message": "end_time must be after start_time"}
            
            # Convert to Unix timestamps (integers)
            start_timestamp = int(start_dt.timestamp())
            end_timestamp = int(end_dt.timestamp())
            
        except ValueError as e:
            return {"status": "error", "message": f"Invalid timestamp format: {str(e)}. Use ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)"}
        
        # Parse input datasets and create TemplatedDataset objects
        parsed_inputs = []
        if input_datasets:
            try:
                inputs_list = json.loads(input_datasets)
                if not isinstance(inputs_list, list):
                    return {"status": "error", "message": "input_datasets must be a JSON array"}
                
                # Create TemplatedDataset for each input
                for idx, dataset_id in enumerate(inputs_list):
                    # Use corresponding template if available
                    if not input_templates or len(input_templates) == 0:
                        # Try to provide helpful debug info
                        debug_info = str(template_dict)[:500] if 'template_dict' in locals() else "unknown"
                        return {
                            "status": "error", 
                            "message": f"No input template found for dataset {dataset_id}. Workflow template must define input templates. Template structure (first 500 chars): {debug_info}"
                        }
                    
                    template_obj = input_templates[idx] if idx < len(input_templates) else input_templates[0]
                    
                    # Extract template_id - handle both dict and object types
                    if isinstance(template_obj, dict):
                        template_id = template_obj.get('template_id') or template_obj.get('id')
                    else:
                        template_id = getattr(template_obj, 'template_id', None) or getattr(template_obj, 'id', None)
                    
                    if not template_id:
                        return {"status": "error", "message": f"Could not extract template_id from input template at index {idx}. Template object: {template_obj}"}
                    
                    templated_dataset = TemplatedDataset(
                        dataset_template_id=template_id,
                        dataset_id=str(dataset_id).strip(),
                        dataset_type=DatasetType.DATA_STORE,
                        resources=None
                    )
                    parsed_inputs.append(templated_dataset)
                    
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid input_datasets JSON: {str(e)}"}
        
        # Parse output datasets and create TemplatedDataset objects
        parsed_outputs = []
        if output_datasets:
            try:
                outputs_list = json.loads(output_datasets)
                if not isinstance(outputs_list, list):
                    return {"status": "error", "message": "output_datasets must be a JSON array"}
                
                # Create TemplatedDataset for each output
                for idx, dataset_id in enumerate(outputs_list):
                    # Use corresponding template if available
                    if not output_templates or len(output_templates) == 0:
                        return {
                            "status": "error", 
                            "message": f"No output template found for dataset {dataset_id}. Workflow template must define output templates. Available template fields: {list(vars(template).keys()) if hasattr(template, '__dict__') else 'unknown'}"
                        }
                    
                    template_obj = output_templates[idx] if idx < len(output_templates) else output_templates[0]
                    
                    # Extract template_id - handle both dict and object types
                    if isinstance(template_obj, dict):
                        template_id = template_obj.get('template_id') or template_obj.get('id')
                    else:
                        template_id = getattr(template_obj, 'template_id', None) or getattr(template_obj, 'id', None)
                    
                    if not template_id:
                        return {"status": "error", "message": f"Could not extract template_id from output template at index {idx}. Template object: {template_obj}"}
                    
                    templated_dataset = TemplatedDataset(
                        dataset_template_id=template_id,
                        dataset_id=str(dataset_id).strip(),
                        dataset_type=DatasetType.DATA_STORE,
                        resources=None
                    )
                    parsed_outputs.append(templated_dataset)
                    
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid output_datasets JSON: {str(e)}"}
        
        # Parse annotations
        parsed_annotations = None
        if annotations:
            try:
                parsed_annotations = json.loads(annotations)
                if not isinstance(parsed_annotations, dict):
                    return {"status": "error", "message": "annotations must be a JSON object"}
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid annotations JSON: {str(e)}"}
        
        # Parse user_metadata
        parsed_user_metadata = None
        if user_metadata:
            try:
                parsed_user_metadata = json.loads(user_metadata)
                if not isinstance(parsed_user_metadata, dict):
                    return {"status": "error", "message": "user_metadata must be a JSON object"}
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"Invalid user_metadata JSON: {str(e)}"}
        
        # Create association info
        associations = AssociationInfo(
            modeller_id=associations_modeller_id,
            requesting_organisation_id=associations_requesting_organisation_id
        )
        
        # Create model run record
        model_run = ModelRunRecord(
            workflow_template_id=workflow_template_id,
            model_version=model_version,
            inputs=parsed_inputs,
            outputs=parsed_outputs,
            annotations=parsed_annotations,
            display_name=display_name,
            description=description,
            study_id=None,  # Can be added as optional parameter if needed
            associations=associations,
            start_time=start_timestamp,
            end_time=end_timestamp,
            user_metadata=parsed_user_metadata
        )
        
        # Register the model run
        result = await client.prov_api.create_model_run(model_run_payload=model_run)

        if not result.status.success:
            await ctx.error(f"Model run registration failed: {result.status.details}")
            return {"status": "error", "message": result.status.details}
        
        run_id = result.session_id if hasattr(result, 'session_id') else None
        
        await ctx.info(f"Successfully registered model run with ID: {run_id}")
        
        return {
            "status": "success",
            "session_id": run_id,
            "message": f"Model run '{display_name}' registration initiated successfully. Use the session_id to track progress.",
            "note": "Model run registration is asynchronous. Check the job status using the session_id.",
            "summary": {
                "display_name": display_name,
                "workflow_template_id": workflow_template_id,
                "start_time": start_time,
                "end_time": end_time,
                "input_count": len(parsed_inputs),
                "output_count": len(parsed_outputs),
                "has_annotations": parsed_annotations is not None
            }
        }
        
    except Exception as e:
        await ctx.error(f"Failed to register model run: {str(e)}")
        return {"status": "error", "message": str(e)}



if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="sse", host="127.0.0.1", port=5000)
    else:
        mcp.run()