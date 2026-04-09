"""
Plugin Loader

Dynamically discovers and registers detection plugins.
Each immediate subdirectory of this package that contains an __init__.py
is treated as a plugin package.  Directories starting with '_' (e.g.
_shared) are skipped.  All concrete DetectionPlugin subclasses found in
each package's namespace are instantiated and registered.
"""
import importlib
import inspect
from pathlib import Path

from . import plugin_registry, DetectionPlugin

_PLUGIN_DIR = Path(__file__).parent


def load_plugins():
    """
    Auto-discover plugin sub-packages, instantiate all concrete
    DetectionPlugin subclasses, and register them.
    """
    print("\n🔌 Loading detection plugins...")

    for candidate in sorted(_PLUGIN_DIR.iterdir()):
        # Skip non-directories, private/shared dirs, and __pycache__
        if not candidate.is_dir():
            continue
        if candidate.name.startswith("_"):
            continue
        if not (candidate / "__init__.py").exists():
            continue

        qualified = f"{__package__}.{candidate.name}"

        try:
            mod = importlib.import_module(qualified)
        except Exception as e:
            print(f"⚠ Could not import {candidate.name}: {e}")
            continue

        for attr_name, obj in inspect.getmembers(mod, inspect.isclass):
            if (
                issubclass(obj, DetectionPlugin)
                and obj is not DetectionPlugin
                and not inspect.isabstract(obj)
            ):
                try:
                    plugin_registry.register(obj())
                except Exception as e:
                    print(f"⚠ Could not register {attr_name} from {candidate.name}: {e}")

    available_plugins = plugin_registry.list_plugins(available_only=True)
    unavailable_plugins = [
        p for p in plugin_registry.list_plugins(available_only=False)
        if not p['available']
    ]

    print(f"\n✓ {len(available_plugins)} detection plugin(s) available:")
    for p in available_plugins:
        print(f"  {p['icon']} {p['name']} ({p['id']})")

    if unavailable_plugins:
        print(f"\n⚠ {len(unavailable_plugins)} plugin(s) unavailable (missing dependencies):")
        for p in unavailable_plugins:
            print(f"  {p['icon']} {p['name']} ({p['id']})")

    print()
