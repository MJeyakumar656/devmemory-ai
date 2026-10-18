from __future__ import annotations

import argparse
import os
import subprocess
import sys
import uvicorn
from demo import run_milestone_demo


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DevMemory AI — Persistent Knowledge Graph Teammate (FalkorDB Track 2)"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the terminal milestone demonstration (Milestones 1-5)",
    )
    parser.add_argument(
        "--streamlit",
        action="store_true",
        help="Launch the Streamlit user interface",
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
    elif args.streamlit:
        print("Launching DevMemory AI Streamlit Dashboard...")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "streamlit_app.py"])
    else:
        print("=" * 70)
        print("  DevMemory AI — Persistent Knowledge Graph Teammate")
        print(f"  Web Dashboard running at: http://{args.host}:{args.port}/devmemory")
        print(f"  API Docs available at:    http://{args.host}:{args.port}/docs")
        print("  Tip: Pass --cli to run the terminal milestone demo instead.")
        print("=" * 70)
        uvicorn.run("web.app:app", host=args.host, port=args.port, reload=False)


if __name__ == "__main__":
    main()
