"""Run the Node evidence-RAG regression suite in the incremental pipeline."""
from __future__ import annotations
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
def main():
    node = shutil.which("node")
    if not node:
        print("Node.js runtime is required for RAG evaluation")
        return 2
    return subprocess.run([node, str(ROOT / "server/evaluate-rag.js")], cwd=ROOT).returncode
if __name__ == "__main__": raise SystemExit(main())
