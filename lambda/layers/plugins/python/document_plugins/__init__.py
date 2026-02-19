"""Document Plugins - Plugin-based architecture for financial document processing.

This package provides the plugin registry and configuration contracts for all
supported document types. Each document type is a self-contained config dict
in the types/ subpackage.

Usage:
    from document_plugins.registry import get_plugin, get_all_plugins

    # Get a specific plugin
    plugin = get_plugin("credit_agreement")
    queries = plugin["sections"]["agreementInfo"]["queries"]

    # Get all plugins for dynamic classification
    plugins = get_all_plugins()

    # Get classification hints for router
    from document_plugins.registry import get_classification_hints
    hints = get_classification_hints()
"""

from document_plugins.registry import (
    get_plugin,
    get_all_plugins,
    get_plugin_ids,
    get_classification_hints,
    get_plugin_for_document_type,
)

__all__ = [
    "get_plugin",
    "get_all_plugins",
    "get_plugin_ids",
    "get_classification_hints",
    "get_plugin_for_document_type",
]
