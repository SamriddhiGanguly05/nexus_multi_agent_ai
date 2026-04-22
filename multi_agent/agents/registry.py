import importlib
import pkgutil
import os
from typing import Dict, Any, Callable

AGENT_REGISTRY: Dict[str, Dict[str, Any]] = {}

def register_agent(name: str, description: str, is_terminal: bool = False):
    """
    Decorator to register an agent in the A2A registry.
    Enables dynamic capability discovery - no hardcoded routing.
    """
    def decorator(func: Callable):
        AGENT_REGISTRY[name] = {
            "name": name,
            "description": description,
            "func": func,
            "is_terminal": is_terminal
        }
        return func
    return decorator


def get_registered_agents() -> Dict[str, Any]:
    """
    Dynamically loads all agent modules in the package.
    Implements MCP-style capability discovery.
    """
    package_dir = os.path.dirname(__file__)
    skip = {"registry", "state", "planner_agent", "coordinator_agent", "json_utils"}
    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name not in skip:
            try:
                importlib.import_module(f"agents.{module_name}")
            except Exception as e:
                print(f"[Registry] Error loading agent module '{module_name}': {e}")
    return AGENT_REGISTRY
