"""
Example Detection Plugin — starter template for developers.

This plugin is fully functional: the loader discovers it, the UI renders
it, and detection runs without error.  It simply returns an empty list
(no detections), so it's safe to ship as a reference.

To create your own plugin:
  1. Copy this folder and rename it (e.g. ``my_detector/``).
  2. Update the metadata properties (plugin_id, display_name, etc.).
  3. Implement your detection logic in ``detect()``.
  4. If you need shared utilities, import from ``from .._shared import ...``
  5. Drop any model checkpoints into a ``checkpoints/`` subfolder and
     reference them via ``Path(__file__).resolve().parent / "checkpoints"``.

The loader auto-discovers any immediate sub-package of ``backend/plugins/``
that contains an ``__init__.py`` exporting a concrete ``DetectionPlugin``
subclass.  Directories starting with ``_`` are skipped by the loader, so
rename this folder (remove the leading underscore) when you're ready to
ship.
"""
import mne
from typing import Dict, List, Any

from .. import DetectionPlugin


class ExamplePlugin(DetectionPlugin):
    """A no-op plugin that registers in the UI but produces no detections."""

    # ── Metadata (shown in the frontend plugin picker) ────────────────────

    @property
    def plugin_id(self) -> str:
        return "example"

    @property
    def display_name(self) -> str:
        return "Example (no-op)"

    @property
    def description(self) -> str:
        return (
            "Starter template — registers in the UI but returns zero "
            "detections.  Copy this folder to build your own plugin."
        )

    @property
    def icon(self) -> str:
        return "🧩"

    @property
    def color(self) -> str:
        return "#9e9e9e"  # grey

    @property
    def requires_dependencies(self) -> List[str]:
        # List any pip packages your plugin needs.
        # The plugin will show as "unavailable" if any are missing.
        return []

    def is_available(self) -> bool:
        # Return False here if a required checkpoint or service is missing.
        return True

    # ── Optional: custom config controls for the UI ───────────────────────

    def get_config_schema(self) -> Dict[str, Any]:
        schema = super().get_config_schema()
        # Add plugin-specific knobs here.  Each key becomes a UI control.
        # Supported types: "number", "string", "select"
        schema["my_param"] = {
            "type": "number",
            "default": 42,
            "min": 0,
            "max": 100,
            "label": "My custom parameter",
        }
        return schema

    # ── Detection entry point ─────────────────────────────────────────────

    def detect(
        self,
        raw: mne.io.Raw,
        segment_duration: float = 2.0,
        threshold: float = 0.5,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """
        Replace this with your actual detection logic.

        Parameters
        ----------
        raw : mne.io.Raw
            The loaded EEG recording.
        segment_duration : float
            Window length in seconds (from the UI slider).
        threshold : float
            Detection threshold 0-1 (from the UI slider).
        **kwargs
            Any extra keys from ``get_config_schema()``, plus an optional
            ``_progress_cb(pct, msg)`` callback for progress reporting.

        Returns
        -------
        list[dict]
            Each dict must contain at minimum:
              onset       – float, seconds from recording start
              duration    – float, seconds
              description – str, event label
              confidence  – float, 0-1
              user        – str, identifies the detector
        """
        # Read your custom param from kwargs:
        # my_param = kwargs.get("my_param", 42)

        # Report progress if the callback is available:
        progress_cb = kwargs.get("_progress_cb")
        if progress_cb:
            progress_cb(50, "Processing…")

        print(f"  🧩 Example plugin called — returning 0 detections")

        if progress_cb:
            progress_cb(100, "Done")

        # Return an empty list (no detections).
        # A real plugin would iterate over windows and append dicts here.
        return []
