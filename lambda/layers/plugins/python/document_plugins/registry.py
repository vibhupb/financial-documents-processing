"""Plugin Registry - Dual-source auto-discovery of document type plugins.

Two sources, loaded in order:
  1. File-based plugins (types/ subpackage) -- immutable baseline, always win on collision
  2. DynamoDB dynamic plugins (PUBLISHED status) -- created via self-service wizard

Adding a new document type:
  - Developer: create types/{doc}.py + prompts/{doc}.txt (file-based)
  - Analyst: use the plugin builder UI (DynamoDB-backed, no code needed)
"""

import importlib
import json
import os
import pkgutil
from typing import Dict, List, Optional

from document_plugins import types as _types_pkg
from document_plugins.contract import DocumentPluginConfig, ClassificationConfig

# Module-level registry, populated once on first import
_REGISTRY: Dict[str, DocumentPluginConfig] = {}
_DISCOVERED: bool = False

# DynamoDB table for dynamic plugins (set via Lambda env var)
PLUGIN_CONFIGS_TABLE = os.environ.get("PLUGIN_CONFIGS_TABLE", "document-plugin-configs")


def _discover_plugins() -> None:
    """Two-phase plugin discovery: files first, then DynamoDB.

    File-based plugins are the immutable baseline. DynamoDB dynamic plugins
    (PUBLISHED status) are loaded second and cannot override file-based ones.
    """
    global _DISCOVERED
    if _DISCOVERED:
        return

    # Phase 1: File-based plugins (existing behavior, always loaded)
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
                config["_source"] = "file"
                _REGISTRY[plugin_id] = config
        except Exception as e:
            print(f"WARNING: Failed to load plugin from document_plugins.types.{modname}: {e}")

    # Phase 2: DynamoDB dynamic plugins (PUBLISHED only, graceful degradation)
    _discover_dynamic_plugins()

    _DISCOVERED = True


def _discover_dynamic_plugins() -> None:
    """Load PUBLISHED plugins from DynamoDB. File-based plugins always win on collision."""
    try:
        import boto3
        from boto3.dynamodb.conditions import Key

        table = boto3.resource("dynamodb").Table(PLUGIN_CONFIGS_TABLE)

        # Query all PUBLISHED items
        response = table.query(
            IndexName="StatusIndex",
            KeyConditionExpression=Key("status").eq("PUBLISHED"),
        )

        for item in response.get("Items", []):
            plugin_id = item.get("pluginId", "")
            if not plugin_id:
                continue

            # File-based plugins always win
            if plugin_id in _REGISTRY:
                if _REGISTRY[plugin_id].get("_source") == "file":
                    print(f"INFO: Dynamic plugin '{plugin_id}' skipped (file-based plugin takes priority)")
                    continue

            config = item.get("config", {})
            if isinstance(config, str):
                config = json.loads(config)

            config["_source"] = "dynamic"
            config["_version"] = str(item.get("version", "v1"))
            config["_dynamodb_item"] = {
                "pluginId": plugin_id,
                "version": str(item.get("version", "v1")),
                "status": item.get("status"),
                "createdBy": item.get("createdBy", ""),
                "updatedAt": item.get("updatedAt", ""),
            }

            # Store prompt template separately (not in the plugin config dict)
            if "promptTemplate" in item:
                config["_prompt_template_text"] = item["promptTemplate"]

            _REGISTRY[plugin_id] = config

    except ImportError:
        pass  # boto3 not available (local testing without AWS)
    except Exception as e:
        print(f"INFO: Dynamic plugin discovery skipped: {e}")
        # Graceful degradation: file-based plugins still work


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
