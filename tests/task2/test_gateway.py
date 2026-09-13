import pytest

from tests.task2.conftest import ADMIN, VIEWER

UNAUTHORIZED = -32001
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
INVALID_PARAMS = -32602


def call(name: str, request_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {"name": name, "arguments": {}},
    }


@pytest.mark.req("T2-R3")
async def test_tools_list_is_forwarded_transparently(gateway, stats):
    body = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    response = await gateway.post("/mcp", json=body, headers=VIEWER)

    assert response.json()["result"]["tools"][0]["name"] == "get_customer_record"
    assert stats["requests"] == 1


@pytest.mark.req("T2-R4")
async def test_a_normal_tool_call_is_forwarded(gateway, stats):
    response = await gateway.post("/mcp", json=call("get_customer_record"), headers=VIEWER)

    assert "result" in response.json()
    assert stats["tool_calls"] == 1


@pytest.mark.req("T2-R5", "T2-R6")
async def test_an_admin_tool_with_a_viewer_token_is_denied(gateway):
    response = await gateway.post("/mcp", json=call("admin_reset_key"), headers=VIEWER)
    error = response.json()["error"]

    assert error["code"] == UNAUTHORIZED
    assert error["message"] == "Unauthorized Tool Call"
    assert error["data"]["tool"] == "admin_reset_key"


@pytest.mark.req("T2-R7")
async def test_a_denied_call_never_reaches_the_downstream_server(gateway, stats):
    await gateway.post("/mcp", json=call("admin_reset_key"), headers=VIEWER)
    assert stats == {"requests": 0, "tool_calls": 0}


@pytest.mark.req("T2-R5")
async def test_an_admin_tool_with_an_admin_token_is_forwarded(gateway, stats):
    response = await gateway.post("/mcp", json=call("admin_reset_key"), headers=ADMIN)

    assert "result" in response.json()
    assert stats["tool_calls"] == 1


@pytest.mark.req("T2-R2")
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer unknown"},
        {"Authorization": "Basic admin-token"},
        {"Authorization": "Bearer "},
    ],
)
async def test_a_bad_token_is_rejected(gateway, stats, headers):
    response = await gateway.post("/mcp", json=call("get_customer_record"), headers=headers)

    assert response.json()["error"]["code"] == UNAUTHORIZED
    assert stats["requests"] == 0


@pytest.mark.req("T2-R1")
async def test_a_body_that_is_not_json_returns_a_parse_error(gateway):
    response = await gateway.post(
        "/mcp", content=b"{not json", headers={**VIEWER, "Content-Type": "application/json"}
    )
    assert response.json()["error"]["code"] == PARSE_ERROR


@pytest.mark.req("T2-R4")
async def test_a_tool_call_without_a_name_returns_invalid_params(gateway):
    body = {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {}}
    response = await gateway.post("/mcp", json=body, headers=VIEWER)

    assert response.json()["error"]["code"] == INVALID_PARAMS


@pytest.mark.req("T2-R1")
async def test_a_member_without_a_method_is_an_invalid_request(gateway):
    response = await gateway.post("/mcp", json={"jsonrpc": "2.0", "id": 4}, headers=VIEWER)
    assert response.json()["error"]["code"] == INVALID_REQUEST


@pytest.mark.req("T2-R1")
async def test_the_response_id_matches_the_request_id(gateway):
    body = call("admin_reset_key", request_id=99)
    response = await gateway.post("/mcp", json=body, headers=VIEWER)
    assert response.json()["id"] == 99


@pytest.mark.req("T2-R1", "T2-R7")
async def test_a_batch_splits_into_forwarded_and_denied_members(gateway, stats):
    body = [
        call("get_customer_record", 1),
        call("admin_reset_key", 2),
        {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    ]
    answers = (await gateway.post("/mcp", json=body, headers=VIEWER)).json()

    by_id = {item["id"]: item for item in answers}
    assert set(by_id) == {1, 2, 3}
    assert "result" in by_id[1]
    assert by_id[2]["error"]["code"] == UNAUTHORIZED
    assert stats["tool_calls"] == 1


@pytest.mark.req("T2-R1")
async def test_a_notification_gets_no_response(gateway, stats):
    body = [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
    response = await gateway.post("/mcp", json=body, headers=VIEWER)

    assert response.json() == []
    assert stats["requests"] == 1
