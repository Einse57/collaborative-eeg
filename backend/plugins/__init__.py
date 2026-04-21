"""
Event Detection Plugin System

This module provides a plugin architecture for event detection algorithms.
Plugins can be added/removed without modifying core application code.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import mne

class DetectionPlugin(ABC):
    """
    Base class for event detection plugins.
    All detection algorithms should inherit from this class.
    """
    
    @property
    @abstractmethod
    def plugin_id(self) -> str:
        """Unique identifier for the plugin (e.g., 'rf', 'cnn')"""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in UI (e.g., 'Random Forest')"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Description of the detection method"""
        pass
    
    @property
    @abstractmethod
    def icon(self) -> str:
        """Emoji or icon for UI display"""
        pass
    
    @property
    def color(self) -> str:
        """CSS color for UI theming (optional)"""
        return "#666666"
    
    @property
    def requires_dependencies(self) -> List[str]:
        """List of required Python packages (for dependency checking)"""
        return []
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if plugin dependencies are installed"""
        pass
    
    @abstractmethod
    def detect(
        self,
        raw: mne.io.Raw,
        segment_duration: float = 2.0,
        threshold: float = 0.5,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Run event detection on EEG data.
        
        Args:
            raw: MNE Raw object containing EEG data
            segment_duration: Length of segments to analyze (seconds)
            threshold: Detection threshold (0-1)
            **kwargs: Additional plugin-specific parameters
            
        Returns:
            List of detections with format:
            [
                {
                    'onset': float (seconds),
                    'duration': float (seconds),
                    'description': str,
                    'confidence': float (0-1),
                    'user': str (plugin_id identifier)
                }
            ]
        """
        pass
    
    def get_config_schema(self) -> Dict[str, Any]:
        """
        Optional: Return JSON schema for plugin-specific configuration.
        Used to generate dynamic UI controls.
        """
        return {
            "segment_duration": {
                "type": "number",
                "default": 2.0,
                "min": 0.5,
                "max": 10.0,
                "label": "Segment Duration (seconds)"
            },
            "threshold": {
                "type": "number",
                "default": 0.5,
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "label": "Detection Threshold"
            }
        }


class PluginRegistry:
    """Registry for managing detection plugins"""
    
    def __init__(self):
        self._plugins: Dict[str, DetectionPlugin] = {}
    
    def register(self, plugin: DetectionPlugin):
        """Register a new plugin"""
        self._plugins[plugin.plugin_id] = plugin
        print(f"✓ Registered detection plugin: {plugin.display_name} ({plugin.plugin_id})")
    
    def unregister(self, plugin_id: str):
        """Unregister a plugin"""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            print(f"✗ Unregistered detection plugin: {plugin_id}")
    
    def get_plugin(self, plugin_id: str) -> Optional[DetectionPlugin]:
        """Get a specific plugin by ID"""
        return self._plugins.get(plugin_id)
    
    def list_plugins(self, available_only: bool = True) -> List[Dict[str, Any]]:
        """
        List all registered plugins with their metadata.
        
        Args:
            available_only: If True, only return plugins with satisfied dependencies
        """
        plugins_info = []
        for plugin_id, plugin in self._plugins.items():
            is_available = plugin.is_available()
            
            if available_only and not is_available:
                continue
            
            plugins_info.append({
                'id': plugin.plugin_id,
                'name': plugin.display_name,
                'description': plugin.description,
                'icon': plugin.icon,
                'color': plugin.color,
                'available': is_available,
                'config_schema': plugin.get_config_schema()
            })
        
        return plugins_info
    
    def detect(
        self,
        plugin_id: str,
        raw: mne.io.Raw,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """Run detection using specified plugin"""
        plugin = self.get_plugin(plugin_id)
        
        if plugin is None:
            raise ValueError(f"Plugin '{plugin_id}' not found")
        
        if not plugin.is_available():
            raise RuntimeError(
                f"Plugin '{plugin_id}' is not available. "
                f"Missing dependencies: {', '.join(plugin.requires_dependencies)}"
            )
        
        return plugin.detect(raw, **kwargs)


# Global plugin registry
plugin_registry = PluginRegistry()
