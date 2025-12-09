"""Probe-based detection modules for internal state analysis.

These modules implement detection techniques from Anthropic's
"Probes Catch Sleeper Agents" research, providing direct visibility
into model internal states to catch deceptive behaviors that
behavioral analysis alone might miss.
"""

from .causal_debugger import CausalDebugger
from .feature_discovery import FeatureDiscovery
from .probe_detector import ProbeDetector

__all__ = ["FeatureDiscovery", "ProbeDetector", "CausalDebugger"]
