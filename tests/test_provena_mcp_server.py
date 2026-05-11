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

class DummyFetchResult:
    def __init__(self, item, success=True, details="OK"):
        self.item = item
        self.status = DummyStatus(success=success, details=details)

class DummyRegistrySearchResults:
    def __init__(self, items):
        self.status = DummyStatus(True, "OK")
        self.results = items

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
def test_comprehensive_entity_research_prompt_contains_entity():
    text = srv.comprehensive_entity_research_prompt.fn("12345/ROOT", "general")
    assert "12345/ROOT" in text
    assert "research_entity" in text

def test_dataset_registration_workflow_prompt():
    txt = srv.dataset_registration_workflow.fn()
    assert "WORKFLOW" in txt
    assert "register_dataset" in txt

# ------------------------
# Tool tests
# ------------------------

@pytest.mark.asyncio
async def test_search_registry(ctx, fake_client):
    res = await srv.search_registry.fn(ctx, query="reef", limit=5, subtype_filter=None)
    assert res["status"] == "success"
    assert res["total_results"] == 2
    for r in res["results"]:
        assert "search_score" in r

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
        return {"status": "authenticated", "message": "ok", "mode": "device"}

    monkeypatch.setattr(srv.auth_manager, "authenticate", mock_authenticate)

    res = await srv.login_to_provena.fn(ctx)
    assert res["status"] == "authenticated"

@pytest.mark.asyncio
async def test_logout_from_provena(monkeypatch, ctx):
    def mock_logout():
        pass

    monkeypatch.setattr(srv.auth_manager, "logout", mock_logout)

    res = await srv.logout_from_provena.fn(ctx)
    assert res["message"] == "Logged out successfully"

@pytest.mark.asyncio
async def test_list_registry_items(ctx, fake_client):
    res = await srv.list_registry_items.fn(ctx, page_size=10)
    assert res["status"] == "success"
    assert res["items"] == []
    assert res["pagination"]["shown_items"] == 0

@pytest.mark.asyncio
async def test_list_provena_instances_tool(ctx, monkeypatch):
    monkeypatch.setattr(
        srv.pr,
        "list_provena_instances",
        lambda: {"instances": {}, "config_file": None, "tokens_file": None},
    )
    res = await srv.list_provena_instances.fn(ctx)
    assert res["instances"] == {}

@pytest.mark.asyncio
async def test_get_provena_offline_token_instructions_tool(ctx):
    res = await srv.get_provena_offline_token_instructions.fn(ctx)
    assert "steps" in res

@pytest.mark.asyncio
async def test_get_provena_connection_info_tool(ctx, monkeypatch):
    monkeypatch.setattr(
        srv.pr,
        "list_provena_instances",
        lambda: {"instances": {}, "config_file": "/x/pi.json", "tokens_file": "/x/pt.json"},
    )
    monkeypatch.setattr(
        srv.auth_manager,
        "reload_connection_settings",
        lambda: {"domain": "d", "realm": "r", "instance": None, "token": ""},
    )
    monkeypatch.setattr(srv.auth_manager, "auth_mode", lambda: "none")
    res = await srv.get_provena_connection_info.fn(ctx)
    assert res["domain"] == "d"
    assert res["auth_mode"] == "none"
    assert res["config_file"] == "/x/pi.json"
