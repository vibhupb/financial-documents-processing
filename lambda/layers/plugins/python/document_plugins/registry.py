"""Plugin Registry - Auto-discovery of document type plugins.

Uses importlib + pkgutil.iter_modules to discover all plugin configs
in the types/ subpackage. Adding a new document type = creating one
file in types/ with a PLUGIN_CONFIG dict. No registration boilerplate.

Same pattern as Django management commands.
"""

import importlib
import pkgutil
from typing import Dict, List, Optional

from document_plugins import types as _types_pkg
from document_plugins.contract import DocumentPluginConfig, ClassificationConfig

# Module-level registry, populated once on first import
_REGISTRY: Dict[str, DocumentPluginConfig] = {}
_DISCOVERED: bool = False


def _discover_plugins() -> None:
    """Scan the types/ subpackage for modules exporting PLUGIN_CONFIG.

    Each module must have a module-level PLUGIN_CONFIG dict with at least
    a 'plugin_id' key. Invalid or missing configs are logged and skipped.
    """
    global _DISCOVERED
    if _DISCOVERED:
        return

    for _importer, modname, _ispkg in pkgutil.iter_modules(_types_pkg.__path__):
        if modname.startswith("_"):
            continue
        try:
            module = importlib.import_module(f"document_plugins.types.{modname}")
            config = getattr(module, "PLUGIN_CONFIG", None)
            if config and isinstance(config, dict) and "plugin_id" in config:
                plugin_id = config["plugin_id"]
                if plugin_id in _REGISTRY:
                    print(
                        f"WARNING: Duplicate plugin_id '{plugin_id}' in "
                        f"document_plugins.types.{modname} - skipping"
                    )
                    continue
                _REGISTRY[plugin_id] = config
            else:
                # Module exists but has no valid PLUGIN_CONFIG - not an error,
                # could be a helper module
                pass
        except Exception as e:
            print(f"WARNING: Failed to load plugin from document_plugins.types.{modname}: {e}")

    _DISCOVERED = True


def get_plugin(plugin_id: str) -> DocumentPluginConfig:
    """Get a plugin configuration by its ID.

    Args:
        plugin_id: The unique plugin identifier (e.g., "credit_agreement")

    Returns:
        The plugin configuration dict

    Raises:
        KeyError: If the plugin_id is not found in the registry
    """
    _discover_plugins()
    if plugin_id not in _REGISTRY:
        raise KeyError(
            f"Unknown plugin: '{plugin_id}'. "
            f"Available plugins: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[plugin_id]


def get_all_plugins() -> Dict[str, DocumentPluginConfig]:
    """Get all registered plugin configurations.

    Returns:
        Dict mapping plugin_id to DocumentPluginConfig
    """
    _discover_plugins()
    return dict(_REGISTRY)


def get_plugin_ids() -> List[str]:
    """Get all registered plugin IDs.

    Returns:
        List of plugin_id strings
    """
    _discover_plugins()
    return list(_REGISTRY.keys())


def get_classification_hints() -> Dict[str, ClassificationConfig]:
    """Get classification hints from all registered plugins.

    Used by the router Lambda to build a dynamic classification prompt
    from all available plugins instead of hardcoded DOCUMENT_TYPES dict.

    Returns:
        Dict mapping plugin_id to ClassificationConfig
    """
    _discover_plugins()
    return {
        plugin_id: config["classification"]
        for plugin_id, config in _REGISTRY.items()
        if "classification" in config
    }


def get_plugin_for_document_type(document_type: str) -> Optional[DocumentPluginConfig]:
    """Find a plugin that handles the given document type string.

    Checks plugin_id directly, then checks legacy_section_map for
    backward compatibility with existing document type strings.

    Args:
        document_type: Document type string (e.g., "CREDIT_AGREEMENT", "credit_agreement")

    Returns:
        Matching plugin config or None
    """
    _discover_plugins()
    normalized = document_type.lower()

    # Direct match on plugin_id
    if normalized in _REGISTRY:
        return _REGISTRY[normalized]

    # Check legacy mappings
    for plugin_id, config in _REGISTRY.items():
        legacy_map = config.get("legacy_section_map", {})
        if normalized in legacy_map or document_type in legacy_map:
            return config

    return None


# Trigger discovery on module import so plugins are available immediately
_discover_plugins()
