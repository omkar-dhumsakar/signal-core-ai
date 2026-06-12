import os
import sys

# Add the backend directory itself to sys.path so 'import models' works
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)
# Also add project root so 'SignalCoreAI' imports work
project_root = os.path.abspath(os.path.join(backend_dir, ".."))
sys.path.insert(0, project_root)
