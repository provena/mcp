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


# -----------------------------------------------
# Coerce helpers
# -----------------------------------------------
def test_coerce_json_list_accepts_string_and_list():
    assert srv._coerce_json_list('["a","b"]') == ["a", "b"]
    assert srv._coerce_json_list(["a", "b"]) == ["a", "b"]


def test_coerce_json_dict_accepts_string_and_dict():
    assert srv._coerce_json_dict('{"k":"v"}') == {"k": "v"}
    assert srv._coerce_json_dict({"k": "v"}) == {"k": "v"}
    assert srv._coerce_json_dict(None) is None


# -----------------------------------------------
# create_dataset_template
# -----------------------------------------------
@pytest.mark.asyncio
async def test_create_dataset_template_empty_resources(ctx, monkeypatch):
    import types as _types

    class FakeCreated:
        id = "10378.1/50"

    class FakeResult:
        status = DummyStatus(True, "OK")
        created_item = FakeCreated()

    class FakeDTClient:
        async def create_item(self, create_item_request):
            return FakeResult()

    fake = _types.SimpleNamespace(
        registry=_types.SimpleNamespace(dataset_template=FakeDTClient())
    )

    async def _req(_ctx):
        return fake

    monkeypatch.setattr(srv, "require_authentication", _req)
    res = await srv.create_dataset_template.fn(
        ctx,
        display_name="T",
        description="desc",
    )
    assert res["status"] == "success"
    assert res["template_id"] == "10378.1/50"


# -----------------------------------------------
# create_model_run_workflow_template
# -----------------------------------------------
@pytest.mark.asyncio
async def test_create_model_run_workflow_template_accepts_list_params(ctx, monkeypatch):
    import types as _types

    class FakeCreated:
        id = "10378.1/60"

    class FakeResult:
        status = DummyStatus(True, "OK")
        created_item = FakeCreated()

    class FakeWFClient:
        async def create_item(self, create_item_request):
            return FakeResult()

    class FakeModelClient:
        async def fetch_item(self, **_):
            class R:
                status = DummyStatus(True)
                item = _types.SimpleNamespace(id="10378.1/1")
            return R()

    fake = _types.SimpleNamespace(
        registry=_types.SimpleNamespace(
            model_run_workflow=FakeWFClient(),
            model=FakeModelClient(),
        )
    )

    async def _req(_ctx):
        return fake

    monkeypatch.setattr(srv, "require_authentication", _req)
    res = await srv.create_model_run_workflow_template.fn(
        ctx,
        display_name="WFT",
        model_id="10378.1/1",
        input_template_ids=[{"template_id": "10378.1/2"}],
        output_template_ids=[{"template_id": "10378.1/3"}],
    )
    assert res["status"] == "success"
    assert res["workflow_template_id"] == "10378.1/60"


# -----------------------------------------------
# create_model_run (study_id)
# -----------------------------------------------
@pytest.mark.asyncio
async def test_create_model_run_calls_register_model_run(ctx, monkeypatch):
    class FakeProvAPI:
        def __init__(self):
            self.calls = []

        async def register_model_run(self, model_run_payload):
            self.calls.append(model_run_payload)
            class R:
                status = DummyStatus(True, "OK")
                session_id = "session-123"
            return R()

    class FakeRegistry:
        async def general_fetch_item(self, id):
            return DummyFetchResult({
                "input_templates": [{"template_id": "10378.1/2"}],
                "output_templates": [{"template_id": "10378.1/3"}],
            })

    prov_api = FakeProvAPI()
    fake = types.SimpleNamespace(
        registry=FakeRegistry(),
        prov_api=prov_api,
    )

    async def _req(_ctx):
        return fake
    monkeypatch.setattr(srv, "require_authentication", _req)

    res = await srv.create_model_run.fn(
        ctx,
        workflow_template_id="10378.1/10",
        display_name="Run",
        description="desc",
        start_time="2026-01-01T00:00:00Z",
        end_time="2026-01-01T01:00:00Z",
        associations_modeller_id="10378.1/20",
        associations_requesting_organisation_id="10378.1/21",
        input_datasets=["10378.1/30"],
        output_datasets=["10378.1/31"],
    )
    assert res["status"] == "success"
    assert res["session_id"] == "session-123"
    assert len(prov_api.calls) == 1
    assert prov_api.calls[0].study_id is None


@pytest.mark.asyncio
async def test_create_model_run_passes_study_id(ctx, monkeypatch):
    class FakeProvAPI:
        def __init__(self):
            self.calls = []

        async def register_model_run(self, model_run_payload):
            self.calls.append(model_run_payload)
            class R:
                status = DummyStatus(True, "OK")
                session_id = "session-456"
            return R()

    class FakeRegistry:
        async def general_fetch_item(self, id):
            return DummyFetchResult({
                "input_templates": [{"template_id": "10378.1/2"}],
                "output_templates": [{"template_id": "10378.1/3"}],
            })

    prov_api = FakeProvAPI()
    fake = types.SimpleNamespace(
        registry=FakeRegistry(),
        prov_api=prov_api,
    )

    async def _req(_ctx):
        return fake
    monkeypatch.setattr(srv, "require_authentication", _req)

    res = await srv.create_model_run.fn(
        ctx,
        workflow_template_id="10378.1/10",
        display_name="Run with Study",
        description="desc",
        start_time="2026-01-01T00:00:00Z",
        end_time="2026-01-01T01:00:00Z",
        associations_modeller_id="10378.1/20",
        associations_requesting_organisation_id="10378.1/21",
        input_datasets=["10378.1/30"],
        output_datasets=["10378.1/31"],
        study_id="10378.1/99",
    )
    assert res["status"] == "success"
    assert res["session_id"] == "session-456"
    assert len(prov_api.calls) == 1
    assert prov_api.calls[0].study_id == "10378.1/99"


# -----------------------------------------------
# create_study
# -----------------------------------------------
@pytest.mark.asyncio
async def test_create_study_registers_and_returns_id(ctx, monkeypatch):
    class FakeCreatedItem:
        id = "10378.1/999"

    class FakeCreateResult:
        status = DummyStatus(True, "OK")
        created_item = FakeCreatedItem()

    class FakeStudyClient:
        def __init__(self):
            self.calls = []

        async def create_item(self, create_item_request):
            self.calls.append(create_item_request)
            return FakeCreateResult()

    study_client = FakeStudyClient()
    fake = types.SimpleNamespace(
        registry=types.SimpleNamespace(study=study_client),
    )

    async def _req(_ctx):
        return fake
    monkeypatch.setattr(srv, "require_authentication", _req)

    res = await srv.create_study.fn(
        ctx,
        title="Coral Reef Resilience Study",
        description="Investigating recovery patterns after bleaching events.",
        study_alternative_id="RRAP-2026-001",
    )
    assert res["status"] == "success"
    assert res["study_id"] == "10378.1/999"
    assert "handle_url" in res
    assert len(study_client.calls) == 1
    payload = study_client.calls[0]
    assert payload.title == "Coral Reef Resilience Study"
    assert payload.study_alternative_id == "RRAP-2026-001"
    assert payload.display_name == "Coral Reef Resilience Study"
