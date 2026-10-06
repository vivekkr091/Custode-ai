#!/usr/bin/env python3
"""Wrapper script to execute CUSTODE demonstration seeder from repository root."""

import os
import sys
import subprocess

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(script_dir, ".."))
    backend_script = os.path.join(repo_root, "backend", "scripts", "seed_demo.py")
    venv_python = os.path.join(repo_root, "backend", ".venv", "bin", "python")

    backend_dir = os.path.join(repo_root, "backend")
    python_bin = venv_python if os.path.exists(venv_python) else sys.executable
    cmd = [python_bin, backend_script] + sys.argv[1:]
    res = subprocess.run(cmd, cwd=backend_dir)
    sys.exit(res.returncode)

if __name__ == "__main__":
    main()
