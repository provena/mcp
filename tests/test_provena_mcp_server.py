import re
import types
import pytest
import server.provena_mcp_server as srv

# ------------------------
# Dummy helper structures
# ------------------------
class DummyStatus:
    def __init__(self, success=True, details="OK"):
        self.success = success
        self.details = details

class DummyMintResult:
    def __init__(self, handle="10378.1/FAKE123", success=True, details="OK"):
        self.handle = handle
        self.status = DummyStatus(success=success, details=details)

class DummyFetchResult:
    def __init__(self, item, success=True, details="OK"):
        self.item = item
        self.status = DummyStatus(success=success, details=details)

class DummyRegistrySearchResults:
    def __init__(self, items):
        self.status = DummyStatus(True, "OK")
        self.results = items

class DummyDatasetSearchItem:
    def __init__(self, _id, score, dataset_obj):
        self.id = _id
        self.score = score
        self.item = dataset_obj

class DummyDatasetSearchResults:
    def __init__(self, items=None, auth_errors=None, misc_errors=None):
        self.items = items or []
        self.auth_errors = auth_errors or []
        self.misc_errors = misc_errors or []

# ------------------------
# Fixtures
# ------------------------
@pytest.fixture
def ctx():
    class Ctx:
        async def info(self, *_, **__): pass
        async def warn(self, *_, **__): pass
        async def error(self, *_, **__): pass
    return Ctx()

@pytest.fixture
def fake_client(monkeypatch):
    class FakeDatastore:
        def __init__(self):
            self.last_mint_payload = None
            self.fetch_calls = []
            self.list_calls = []
            self.search_calls = []
        async def mint_dataset(self, dataset_mint_info):
            self.last_mint_payload = dataset_mint_info
            return DummyMintResult()
        async def fetch_dataset(self, id: str):
            self.fetch_calls.append(id)
            return DummyFetchResult({"display_name": "Test Dataset", "id": id})
        async def list_datasets(self, list_dataset_request):
            self.list_calls.append(list_dataset_request)
            class R:
                def __init__(self):
                    self.status = DummyStatus(True, "OK")
                    self.items = []
                    self.complete_item_count = 0
                    self.total_item_count = 0
            return R()
        async def search_datasets(self, query: str, limit: int):
            self.search_calls.append((query, limit))
            ds = DummyDatasetSearchItem("DS1", 0.95, {"display_name": "DS1", "id": "DS1"})
            return DummyDatasetSearchResults(items=[ds])

    class FakeRegistry:
        def __init__(self):
            self.fetch_calls = []
        async def general_fetch_item(self, id: str):
            self.fetch_calls.append(id)
            return DummyFetchResult({"display_name": "Org X", "item_subtype": "ORGANISATION", "id": id})
        async def list_general_registry_items(self, general_list_request):
            class R:
                def __init__(self):
                    self.status = DummyStatus(True, "OK")
                    self.items = []
                    self.total_item_count = 0
                    self.complete_item_count = 0
            return R()
        async def list_registry_items_with_count(self):
            return {"DATASET": 3, "PERSON": 2}

    class FakeSearch:
        def __init__(self):
            self.registry_search_calls = []
        async def search_registry(self, query, limit, subtype_filter):
            self.registry_search_calls.append((query, limit, subtype_filter))
            return DummyRegistrySearchResults([
                types.SimpleNamespace(id="ORG.1", score=0.9),
                types.SimpleNamespace(id="PERS.1", score=0.85),
            ])

    class FakeProvAPI:
        async def explore_upstream(self, starting_id: str, depth: int):
            class R:
                def __init__(self):
                    self.status = DummyStatus(True, "OK")
                    self.nodes = []
                    self.edges = []
            return R()
        async def explore_downstream(self, starting_id: str, depth: int):
            class R:
                def __init__(self):
                    self.status = DummyStatus(True, "OK")
                    self.nodes = []
                    self.edges = []
            return R()

    fake = types.SimpleNamespace(
        datastore=FakeDatastore(),
        registry=FakeRegistry(),
        search=FakeSearch(),
        prov_api=FakeProvAPI()
    )

    async def _req(_ctx):
        return fake
    monkeypatch.setattr(srv, "require_authentication", _req)
    return fake

# ------------------------
# Prompt tests
# ------------------------
def test_deep_lineage_prompt_contains_root():
    # Access the underlying function from the FunctionPrompt wrapper
    text = srv.deep_lineage_investigation_prompt.fn("12345/ROOT")
    assert "12345/ROOT" in text
    assert "Fully map and understand" in text

def test_dataset_registration_workflow_prompt():
    # Access the underlying function from the FunctionPrompt wrapper
    txt = srv.dataset_registration_workflow.fn()
    assert "PHASE 1" in txt
    assert "register_dataset" in txt

# ------------------------
# Tool tests
# ------------------------

@pytest.mark.asyncio
async def test_register_dataset_comprehensive_fields(ctx, fake_client):
    """Test registration with many optional fields filled out"""
    res = await srv.register_dataset.fn(
        ctx=ctx,
        # Required fields
        name="Comprehensive Dataset",
        description="Full test with many fields",
        publisher_id="ORG.1",
        organisation_id="ORG.1", 
        created_date="2024-01-01",
        published_date="2024-02-01",
        license="https://creativecommons.org/licenses/by/4.0/",
        # Access fields
        access_reposited=False,
        access_uri="https://external-data.example.com",
        access_description="Download from external repository",
        # Approval fields
        ethics_registration_relevant=True,
        ethics_registration_obtained=True,
        indigenous_knowledge_relevant=True,
        indigenous_knowledge_obtained=True,
        # Metadata fields  
        purpose="Research into coral bleaching patterns",
        rights_holder="Marine Research Institute",
        usage_limitations="Academic use only",
        preferred_citation="Smith et al. (2024)",
        # Spatial fields
        spatial_coverage="SRID=4326;POINT(145.7 -16.2)",
        spatial_extent="SRID=4326;POLYGON((145.0 -17.0, 146.0 -17.0, 146.0 -16.0, 145.0 -16.0, 145.0 -17.0))",
        spatial_resolution="0.01",
        # Temporal fields
        temporal_begin_date="2023-01-01",
        temporal_end_date="2023-12-31", 
        temporal_resolution="P1D",
        # List fields
        formats="CSV, NetCDF, JSON",
        keywords="coral, bleaching, temperature, marine",
        # Metadata and people
        user_metadata='{"project": "Great Barrier Reef", "version": "1.0"}',
        data_custodian_id="PERS.1",
        point_of_contact="researcher@marine.org"
    )
    
    assert res["status"] == "success"
    assert res["dataset_id"].startswith("10378.")
    
    payload = fake_client.datastore.last_mint_payload
    assert payload.dataset_info.name == "Comprehensive Dataset"
    assert payload.dataset_info.purpose == "Research into coral bleaching patterns"
    assert payload.dataset_info.spatial_info is not None
    assert payload.dataset_info.temporal_info is not None
    assert payload.associations.data_custodian_id == "PERS.1"

@pytest.mark.asyncio
async def test_register_dataset_minimal_required_only(ctx, fake_client):
    """Test registration with only required fields"""
    res = await srv.register_dataset.fn(
        ctx=ctx,
        name="Minimal Dataset",
        description="Just required fields",
        publisher_id="ORG.1",
        organisation_id="ORG.1",
        created_date="2024-01-01", 
        published_date="2024-02-01",
        license="https://example.com/license"
    )
    
    assert res["status"] == "success"
    payload = fake_client.datastore.last_mint_payload
    assert payload.dataset_info.name == "Minimal Dataset"
    assert payload.dataset_info.spatial_info is None
    assert payload.dataset_info.temporal_info is None
@pytest.mark.asyncio
async def test_register_dataset_failure_status(monkeypatch, ctx, fake_client):
    async def fail_mint(dataset_mint_info):
        return DummyMintResult(handle=None, success=False, details="Denied")
    monkeypatch.setattr(fake_client.datastore, "mint_dataset", fail_mint)
    res = await srv.register_dataset.fn(
        ctx=ctx,
        name="Fail",
        description="Should fail",
        publisher_id="ORG.1",
        organisation_id="ORG.1",
        created_date="2024-01-01",
        published_date="2024-02-01",
        license="https://example.com/license"
    )
    assert res["status"] == "error"
    assert "Denied" in res["message"]

@pytest.mark.asyncio
async def test_search_registry(ctx, fake_client):
    res = await srv.search_registry.fn(ctx, query="reef", limit=5, subtype_filter=None)
    assert res["status"] == "success"
    assert res["total_results"] == 2
    for r in res["results"]:
        assert "search_score" in r

@pytest.mark.asyncio
async def test_search_datasets(ctx, fake_client):
    res = await srv.search_datasets.fn(ctx, query="coral", limit=3)
    assert res["status"] == "success"
    assert res["summary"]["successful_items"] == 1

@pytest.mark.asyncio
async def test_fetch_dataset(ctx, fake_client):
    res = await srv.fetch_dataset.fn(ctx, dataset_id="DS1")
    assert res["status"] == "success"
    assert res["dataset"]["display_name"] == "Test Dataset"

@pytest.mark.asyncio
async def test_explore_upstream(ctx, fake_client):
    res = await srv.explore_upstream.fn(ctx, starting_id="ROOT", depth=1)
    assert res["status"] == "success"
    assert res["starting_id"] == "ROOT"

@pytest.mark.asyncio
async def test_explore_downstream(ctx, fake_client):
    res = await srv.explore_downstream.fn(ctx, starting_id="ROOT", depth=2)
    assert res["status"] == "success"
    assert res["depth"] == 2

@pytest.mark.asyncio
async def test_get_registry_items_count(ctx, fake_client):
    res = await srv.get_registry_items_count.fn(ctx)
    assert res["status"] == "success"
    assert res["counts_by_subtype"]["dataset"] == 3

@pytest.mark.asyncio
async def test_get_current_date(ctx):
    date_str = await srv.get_current_date.fn(ctx)
    assert re.match(r"\d{4}-\d{2}-\d{2}", date_str)

@pytest.mark.asyncio
async def test_login_to_provena(monkeypatch, ctx):
    async def mock_authenticate():
        return {"status": "authenticated", "message": "Authentication completed successfully"}
    
    monkeypatch.setattr(srv.auth_manager, "authenticate", mock_authenticate)
    
    res = await srv.login_to_provena.fn(ctx)
    assert res["status"] == "authenticated"
    assert "Authentication completed successfully" in res["message"]

@pytest.mark.asyncio
async def test_logout_from_provena(monkeypatch, ctx):
    def mock_logout():
        pass
    
    monkeypatch.setattr(srv.auth_manager, "logout", mock_logout)
    
    res = await srv.logout_from_provena.fn(ctx)
    assert res["message"] == "Logged out successfully"

@pytest.mark.asyncio
async def test_test_authenticated_action(ctx, fake_client):
    res = await srv.test_authenticated_action.fn(ctx)
    assert res["status"] == "success"
    assert "Authenticated and ready" in res["message"]

@pytest.mark.asyncio
async def test_list_datasets(ctx, fake_client):
    res = await srv.list_datasets.fn(ctx, page_size=5, sort_ascending=True, sort_by="DISPLAY_NAME")
    assert res["status"] == "success"
    assert res["datasets"] == []
    assert res["pagination"]["page_size"] == 5

@pytest.mark.asyncio
async def test_list_registry_items(ctx, fake_client):
    res = await srv.list_registry_items.fn(ctx, page_size=10)
    assert res["status"] == "success"
    assert res["items"] == []
    assert res["pagination"]["shown_items"] == 0