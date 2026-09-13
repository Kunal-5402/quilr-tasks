# Task 5 — missing from the source document

## Status

The overview in the PDF says the assessment has 5 tasks. It names
"troubleshooting zero-trust network deployments" as a focus area. The document
contains Task 1 to Task 4 only. Task 5 has no problem statement.

## Decision on 2026-09-13

Task 5 is out of scope. The deliverable covers task 1 to task 4.
The outline below stays as a record of the gap.

## Action

1. Ask the assessment contact for the text of Task 5. Do this first, because
   the answer can change the 2-day plan.
2. Until an answer arrives, write a troubleshooting runbook from the focus
   area name. The runbook is short and costs about 1 hour.

## Runbook outline, to write on Day 2 evening

A zero-trust deployment breaks an MCP or an LLM gateway in a small number of
ways. The runbook lists the symptom, the cause, and the check for each one.

| Symptom | Likely cause | Check |
| --- | --- | --- |
| The stdio MCP server starts and then stops at once. | An egress policy blocks the process, or the parent closed stdin. | Read stderr. Run the server alone with a piped `initialize` request. |
| The gateway gets an `SSLCertVerificationError`. | A TLS inspection proxy uses a private certificate authority. | Set `SSL_CERT_FILE` to the corporate bundle. Do not turn verification off. |
| The stream arrives in one block at the end. | A reverse proxy buffers the response. | Send `X-Accel-Buffering: no`. Turn the proxy buffer off. |
| A request works from a laptop and fails in the cluster. | An egress allowlist misses the provider host. | Test with `curl` from inside the pod. Read the deny log of the proxy. |
| The token is valid but the gateway returns 401. | A service mesh strips or rewrites the `Authorization` header. | Log the received headers at the gateway edge. |
| The call works and then fails after about 60 seconds. | An idle timeout in the mesh or the load balancer. | Send an SSE keep-alive comment every 15 seconds. |
| The MCP gateway cannot reach the downstream server by name. | A split DNS or a namespace policy. | Resolve the name inside the pod. Test the service IP address directly. |

The runbook also states the standard evidence to collect: the request
identifier, the gateway stderr log, the proxy access log, and the output of
`curl -v` from the same network position.
