import json

import pytest

from gateways.mcp_tool_server.schemas import GetCustomerRecordInput

METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602


@pytest.mark.req("T1-R1", "T1-R2", "T1-R3")
def test_tools_list_advertises_both_tools(session):
    result = session.request("tools/list")["result"]
    names = {tool["name"] for tool in result["tools"]}
    assert names == {"get_customer_record", "trigger_refund"}


@pytest.mark.req("T1-R4")
def test_advertised_schema_matches_the_enforced_schema(session):
    tools = {t["name"]: t for t in session.request("tools/list")["result"]["tools"]}
    assert tools["get_customer_record"]["inputSchema"] == GetCustomerRecordInput.model_json_schema()


@pytest.mark.req("T1-R1")
def test_valid_customer_id_is_accepted(session):
    result = session.call_tool("get_customer_record", {"customer_id": "CUST-A1B2C"})["result"]
    assert result["structuredContent"]["name"] == "Ada Lovelace"
    assert result["isError"] is False


@pytest.mark.req("T1-R1")
def test_unknown_customer_is_a_result_not_an_error(session):
    result = session.call_tool("get_customer_record", {"customer_id": "CUST-00000"})["result"]
    assert result["structuredContent"] == {"found": False, "customer_id": "CUST-00000"}


@pytest.mark.req("T1-R2")
def test_valid_refund_is_accepted(session):
    arguments = {"customer_id": "CUST-A1B2C", "amount": 12.5, "reason": "duplicate charge"}
    result = session.call_tool("trigger_refund", arguments)["result"]
    assert result["structuredContent"]["status"] == "pending"
    assert result["structuredContent"]["refund_id"].startswith("REF-")


@pytest.mark.req("T1-R1", "T1-R5")
@pytest.mark.parametrize(
    "customer_id", ["cust-a1b2c", "CUST-A1B2", "CUST-A1B2CD", "CUSTA1B2C", "", "CUST-a1b2c"]
)
def test_malformed_customer_id_returns_invalid_params(session, customer_id):
    response = session.call_tool("get_customer_record", {"customer_id": customer_id})
    assert response["error"]["code"] == INVALID_PARAMS


@pytest.mark.req("T1-R4", "T1-R5")
@pytest.mark.parametrize(
    "arguments",
    [
        {"customer_id": "CUST-A1B2C", "amount": 0, "reason": "duplicate charge"},
        {"customer_id": "CUST-A1B2C", "amount": -5.0, "reason": "duplicate charge"},
        {"customer_id": "CUST-A1B2C", "amount": "10", "reason": "duplicate charge"},
        {"customer_id": "CUST-A1B2C", "amount": 10.0, "reason": "too short"},
        {"customer_id": "CUST-A1B2C", "amount": 10.0},
        {"customer_id": "CUST-A1B2C", "amount": 10.0, "reason": "duplicate charge", "x": 1},
    ],
)
def test_malformed_refund_arguments_return_invalid_params(session, arguments):
    response = session.call_tool("trigger_refund", arguments)
    assert response["error"]["code"] == INVALID_PARAMS


@pytest.mark.req("T1-R5")
def test_the_error_data_reports_the_field_but_not_the_value(session):
    response = session.call_tool("get_customer_record", {"customer_id": "secret-value"})
    errors = response["error"]["data"]["errors"]
    assert errors[0]["field"] == "customer_id"
    assert "secret-value" not in json.dumps(response)


@pytest.mark.req("T1-R5")
def test_unknown_tool_returns_method_not_found(session):
    response = session.call_tool("no_such_tool", {})
    assert response["error"]["code"] == METHOD_NOT_FOUND


@pytest.mark.req("T1-R6", "T1-R7")
def test_stdout_holds_only_json_rpc_messages(session):
    session.request("tools/list")
    session.call_tool("get_customer_record", {"customer_id": "CUST-A1B2C"})
    session.call_tool("get_customer_record", {"customer_id": "bad"})
    lines, _ = session.close()

    assert lines
    for line in lines:
        message = json.loads(line)
        assert message["jsonrpc"] == "2.0"


@pytest.mark.req("T1-R8")
def test_logs_go_to_stderr(session):
    session.request("tools/list")
    _, stderr = session.close()
    assert "mcp server starting on stdio" in stderr
