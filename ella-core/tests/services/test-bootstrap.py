"""Compatibility entry point for the consolidated bootstrap fixture tests."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parents[2]/'ella-stack/tests/test-bootstrap.py'),run_name='__main__')
