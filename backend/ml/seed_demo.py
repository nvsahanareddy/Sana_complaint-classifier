"""Forwarding runner for seed_demo to support 'python -m ml.seed_demo'."""
import sys
from pathlib import Path

# Add backend directory to sys.path if not present
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import seed_demo

if __name__ == "__main__":
    seed_demo.main()
