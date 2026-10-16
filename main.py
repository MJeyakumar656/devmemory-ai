from __future__ import annotations

import argparse
import sys
import uvicorn
from demo import run_milestone_demo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MediMemory AI — A Persistent Health Companion (FalkorDB Track 2)"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the terminal milestone demonstration instead of the web server",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the web server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the web server to (default: 8000)",
    )
    args = parser.parse_args()

    if args.cli:
        run_milestone_demo()
    else:
        print(f"Starting MediMemory AI web dashboard at http://{args.host}:{args.port}")
        print("Tip: Pass --cli to run the terminal multi-agent demonstration instead.")
        uvicorn.run("web.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
