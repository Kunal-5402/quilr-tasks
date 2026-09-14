# Runbook — a gateway inside a zero-trust network

A zero-trust network breaks a gateway in a small number of ways. This runbook
lists the symptom, the likely cause, and the check.

> The entries below are field guidance. The repository does not test them,
> because they depend on the network that you deploy into.

## Symptom table

| Symptom | Likely cause | Check |
| --- | --- | --- |
| The stdio MCP server starts and then stops at once. | An egress policy blocks the process, or the parent closed stdin. | Read stderr. Run the server alone with a piped `initialize` request. |
| The gateway reports `SSLCertVerificationError`. | A TLS inspection proxy uses a private certificate authority. | Set `SSL_CERT_FILE` to the corporate bundle. Never turn verification off. |
| The stream arrives in one block at the end. | A reverse proxy buffers the response. | Send `X-Accel-Buffering: no`. Turn the proxy buffer off. |
| A request works from a laptop and fails in the cluster. | An egress allowlist misses the provider host. | Run `curl` from inside the pod. Read the deny log of the proxy. |
| The token is valid but the gateway returns 401. | A service mesh strips or rewrites the `Authorization` header. | Log the received headers at the gateway edge. |
| The call works and then fails after about 60 seconds. | An idle timeout in the mesh or the load balancer. | Send an SSE keep-alive comment every 15 seconds. |
| The MCP gateway cannot reach the downstream server by name. | A split DNS, or a namespace policy. | Resolve the name inside the pod. Test the service IP address directly. |

SSE means Server-Sent Events. TLS means Transport Layer Security.

## Evidence to collect

Collect these 4 items before you escalate.

1. The `request_id` from the client response, or from the `X-Request-Id` header.
2. The gateway stderr log for that `request_id`.
3. The access log of the proxy or the mesh, for the same time.
4. The output of `curl -v`, run from the same network position as the gateway.

## What the code already does

- Every gateway writes its logs to stderr, so a container log driver collects them.
- The model router returns `X-Request-Id` on every response.
- The stream guard sends `X-Accel-Buffering: no`, which stops the most common
  buffering problem at a reverse proxy.
- The model router names the provider that answered in `X-Gateway-Provider`,
  which separates a provider fault from a network fault.
