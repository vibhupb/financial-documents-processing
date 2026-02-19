"""Document plugin type definitions.

Each module in this package exports a PLUGIN_CONFIG dict conforming to
document_plugins.contract.DocumentPluginConfig.

The registry auto-discovers all modules via pkgutil.iter_modules.
To add a new document type, create a new .py file in this directory
with a module-level PLUGIN_CONFIG dict.
"""
