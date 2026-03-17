"""
Plugin Loader

Automatically discovers and registers detection plugins.
"""
from pathlib import Path
from . import plugin_registry

def load_plugins():
    """
    Auto-discover and register all available plugins.
    Plugins are only registered if their dependencies are satisfied.
    """
    print("\n🔌 Loading detection plugins...")
    
    # Try to load Random Forest plugin
    try:
        from .rf_plugin import RandomForestPlugin
        rf_plugin = RandomForestPlugin()
        plugin_registry.register(rf_plugin)
    except Exception as e:
        print(f"⚠ Could not load RF plugin: {e}")
    
    # Try to load CNN plugin
    try:
        from .cnn_plugin import CNNPlugin
        cnn_plugin = CNNPlugin()
        plugin_registry.register(cnn_plugin)
    except Exception as e:
        print(f"⚠ Could not load CNN plugin: {e}")
    
    # Try to load REVE-Large foundation model plugin
    try:
        from .reve_plugin import REVEPlugin
        reve_plugin = REVEPlugin()
        plugin_registry.register(reve_plugin)
    except Exception as e:
        print(f"⚠ Could not load REVE plugin: {e}")
    
    # Future plugins can be added here, or discovered dynamically
    # from a plugins directory
    
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
