"""Run the router. Add --primary or --secondary to run a mock provider."""

import sys

import uvicorn

from gateways.llm_router.providers import make_app

if __name__ == "__main__":
    if "--primary" in sys.argv:
        uvicorn.run(make_app("primary"), host="127.0.0.1", port=8014)
    elif "--secondary" in sys.argv:
        uvicorn.run(make_app("secondary"), host="127.0.0.1", port=8015)
    else:
        uvicorn.run("gateways.llm_router.app:app", host="127.0.0.1", port=8004)
