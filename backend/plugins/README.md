# Detection Plugins

This directory contains modular event detection plugins for the EEG analysis system.

## Directory Structure

```
plugins/
├── README.md           # This file
└── detection/          # Detection plugin implementations
    ├── __init__.py     # Base classes and registry
    ├── loader.py       # Auto-discovery loader
    ├── rf_plugin.py    # Random Forest plugin
    └── cnn_plugin.py   # CNN plugin
```

## Creating a New Plugin

To create a new detection plugin:

1. **Create a new file** in `detection/` (e.g., `my_plugin.py`)

2. **Import the base class**:
   ```python
   from . import DetectionPlugin, plugin_registry
   ```

3. **Implement the DetectionPlugin interface**:
   ```python
   class MyPlugin(DetectionPlugin):
       @property
       def plugin_id(self) -> str:
           return "my_plugin"
       
       @property
       def display_name(self) -> str:
           return "My Detection Method"
       
       @property
       def description(self) -> str:
           return "Description of what this plugin does"
       
       @property
       def icon(self) -> str:
           return "🔮"  # Choose an emoji icon
       
       @property
       def color(self) -> str:
           return "#ff6b6b"  # CSS color for the button
       
       @property
       def requires_dependencies(self) -> list:
           return ["dependency1", "dependency2"]
       
       def is_available(self) -> bool:
           """Check if required dependencies are installed"""
           try:
               import dependency1
               import dependency2
               return True
           except ImportError:
               return False
       
       def detect(self, raw, segment_duration: float = 1.0, 
                  threshold: float = 0.5, config: dict = None) -> list:
           """
           Perform detection on the EEG data.
           
           Args:
               raw: MNE Raw object
               segment_duration: Duration of segments to analyze (seconds)
               threshold: Detection threshold (0-1)
               config: Optional plugin-specific configuration
           
           Returns:
               List of detection dictionaries with keys:
               - onset: Start time in seconds
               - duration: Duration in seconds
               - description: Annotation description
           """
           # Your detection logic here
           detections = []
           # ... process data ...
           return detections
   ```

4. **Register in loader.py**:
   ```python
   # In loader.py, add to load_plugins():
   try:
       from .my_plugin import MyPlugin
       my_plugin = MyPlugin()
       plugin_registry.register(my_plugin)
   except Exception as e:
       print(f"⚠ Could not load MyPlugin: {e}")
   ```

5. **Install dependencies** (if any):
   ```bash
   pip install dependency1 dependency2
   ```

## Plugin Features

- **Automatic Discovery**: Plugins are auto-loaded on server start
- **Dependency Checking**: Plugins gracefully handle missing dependencies
- **Dynamic UI**: Plugin buttons appear automatically in the frontend
- **Customizable Appearance**: Each plugin can define its icon and color
- **Configuration Support**: Plugins can accept custom configuration parameters

## Available Plugins

### Random Forest (`rf_plugin.py`)
- **ID**: `rf`
- **Icon**: 🌲
- **Color**: Green (#2e7d32)
- **Dependencies**: pywavelets, scipy, scikit-learn
- **Method**: Discrete Wavelet Transform (DWT) feature extraction with Random Forest classification

### CNN (`cnn_plugin.py`)
- **ID**: `cnn`
- **Icon**: 🔷
- **Color**: Blue (#1565c0)
- **Dependencies**: torch, huggingface-hub, pillow, torchvision, safetensors
- **Method**: Spectrogram analysis with pre-trained CNN model from HuggingFace

## API Endpoints

The plugin system automatically exposes these endpoints:

- `GET /api/detection/plugins` - List all available plugins
- `POST /api/detection/{dataset_id}/detect` - Run detection with specified plugin

## Testing Your Plugin

1. Restart the backend server
2. Check console output for plugin registration messages
3. Navigate to the frontend and load a dataset
4. Your plugin button should appear in the Event Detection section
5. Click the button to test detection

## Best Practices

- ✅ Handle missing dependencies gracefully in `is_available()`
- ✅ Provide clear, descriptive error messages
- ✅ Validate input parameters in `detect()`
- ✅ Return consistent detection format (onset, duration, description)
- ✅ Use appropriate thresholds and segment durations
- ✅ Document expected data formats and preprocessing requirements
- ✅ Consider performance for long recordings
- ✅ Test with various EEG data formats and channel configurations
