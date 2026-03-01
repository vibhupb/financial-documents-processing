import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { Puzzle, Plus, FileText, Shield, Lock, ChevronDown, ChevronUp, DollarSign, Search, Pencil } from 'lucide-react';

interface PluginInfo {
  pluginId: string;
  name: string;
  description: string;
  version: string;
  sections: string[];
  hasPiiFields: boolean;
  requiresSignatures: boolean;
  _source?: string;
  _dynamodb_item?: { status?: string };
  classification?: { keywords?: string[] };
  outputSchema?: Record<string, any>;
  costBudget?: { max_cost_usd?: number; warn_cost_usd?: number };
  cost_budget?: { max_cost_usd?: number; warn_cost_usd?: number };
}

const statusColors: Record<string, string> = {
  file: 'bg-blue-100 text-blue-700',
  PUBLISHED: 'bg-green-100 text-green-700',
  DRAFT: 'bg-yellow-100 text-yellow-700',
  TESTING: 'bg-purple-100 text-purple-700',
  ARCHIVED: 'bg-gray-100 text-gray-500',
};

function countQueries(plugin: PluginInfo): number {
  // Attempt to count queries from outputSchema properties as a proxy
  // The API returns sections as string[], not the full config with queries
  // Use outputSchema top-level property count as a reasonable field/query estimate
  const schema = plugin.outputSchema;
  if (!schema?.properties) return 0;
  let count = 0;
  for (const sectionKey of Object.keys(schema.properties)) {
    const section = schema.properties[sectionKey];
    if (section?.properties) {
      count += Object.keys(section.properties).length;
    }
  }
  return count;
}

function getStatusInfo(plugin: PluginInfo): { label: string; key: string } {
  const source = plugin._source || 'file';
  if (source === 'file') return { label: 'Built-in', key: 'file' };
  const status = plugin._dynamodb_item?.status || 'PUBLISHED';
  return { label: status, key: status };
}

export default function PluginList() {
  const [plugins, setPlugins] = useState<Record<string, PluginInfo>>({});
  const [loading, setLoading] = useState(true);
  const [expandedSchema, setExpandedSchema] = useState<string | null>(null);

  useEffect(() => {
    loadPlugins();
  }, []);

  async function loadPlugins() {
    try {
      const data = await api.getPlugins();
      setPlugins(data.plugins || {});
    } catch (err) {
      console.error('Failed to load plugins', err);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="h-full overflow-auto p-8 flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const pluginList = Object.values(plugins);

  return (
    <div className="h-full overflow-auto p-8 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Puzzle className="w-7 h-7 text-primary-600" />
            Document Type Plugins
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            {pluginList.length} registered document types. Add new types with 2 files or use the plugin builder.
          </p>
        </div>
        <Link
          to="/config/new"
          className="flex items-center gap-2 px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium"
        >
          <Plus className="w-4 h-4" />
          Create New Plugin
        </Link>
      </div>

      {pluginList.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          <Puzzle className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p>No document types registered.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {pluginList.map((plugin) => {
            const { label: statusLabel, key: statusKey } = getStatusInfo(plugin);
            const sectionCount = plugin.sections?.length || 0;
            const queryCount = countQueries(plugin);
            const budget = plugin.cost_budget || plugin.costBudget;
            const isExpanded = expandedSchema === plugin.pluginId;

            return (
              <div
                key={plugin.pluginId}
                className="bg-white border border-gray-200 rounded-lg hover:shadow-md transition-shadow flex flex-col"
              >
                {/* Card Header */}
                <div className="p-5 flex-1">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-base font-semibold text-gray-900 leading-tight pr-2">
                      {plugin.name}
                    </h3>
                    <span className="text-xs text-gray-400 whitespace-nowrap font-mono">
                      v{plugin.version}
                    </span>
                  </div>

                  {/* Status + PII badges */}
                  <div className="flex items-center gap-2 mb-3">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[statusKey] || statusColors.file}`}
                    >
                      {statusLabel}
                    </span>
                    {plugin.hasPiiFields && (
                      <span className="flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-1.5 py-0.5 rounded-full">
                        <Lock className="w-3 h-3" /> PII
                      </span>
                    )}
                    {plugin.requiresSignatures && (
                      <span className="flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded-full">
                        <Shield className="w-3 h-3" /> Sig
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  <p className="text-sm text-gray-500 mb-3 line-clamp-2">
                    {plugin.description || 'No description'}
                  </p>

                  {/* Stats row */}
                  <div className="flex items-center gap-3 text-xs text-gray-400">
                    <span className="flex items-center gap-1" title="Sections">
                      <FileText className="w-3.5 h-3.5" />
                      {sectionCount} section{sectionCount !== 1 ? 's' : ''}
                    </span>
                    {queryCount > 0 && (
                      <span className="flex items-center gap-1" title="Extraction fields">
                        <Search className="w-3.5 h-3.5" />
                        {queryCount} fields
                      </span>
                    )}
                    {budget?.max_cost_usd != null && (
                      <span className="flex items-center gap-1" title="Cost budget">
                        <DollarSign className="w-3.5 h-3.5" />
                        ${budget.max_cost_usd.toFixed(2)}
                      </span>
                    )}
                  </div>
                </div>

                {/* Card Footer Actions */}
                <div className="border-t border-gray-100 px-5 py-3 flex items-center justify-between">
                  <Link
                    to={`/config/${plugin.pluginId}`}
                    className="flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    <Pencil className="w-3.5 h-3.5" /> {statusKey === 'DRAFT' ? 'Edit Draft' : 'Edit'}
                  </Link>
                  <button
                    onClick={() => setExpandedSchema(isExpanded ? null : plugin.pluginId)}
                    className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-600 transition-colors"
                  >
                    View Schema
                    {isExpanded ? (
                      <ChevronUp className="w-3.5 h-3.5" />
                    ) : (
                      <ChevronDown className="w-3.5 h-3.5" />
                    )}
                  </button>
                </div>

                {/* Expandable Schema */}
                {isExpanded && plugin.outputSchema && (
                  <div className="border-t border-gray-100 px-5 py-3 bg-gray-50">
                    <pre className="text-xs text-gray-600 overflow-x-auto max-h-60 overflow-y-auto whitespace-pre-wrap">
                      {JSON.stringify(plugin.outputSchema, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
