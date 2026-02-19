import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { Puzzle, Plus, FileText, Shield, Lock } from 'lucide-react';

interface PluginInfo {
  pluginId: string;
  name: string;
  description: string;
  version: string;
  sections: string[];
  hasPiiFields: boolean;
  requiresSignatures: boolean;
  _source?: string;
}

const statusColors: Record<string, string> = {
  file: 'bg-blue-100 text-blue-700',
  PUBLISHED: 'bg-green-100 text-green-700',
  DRAFT: 'bg-yellow-100 text-yellow-700',
  TESTING: 'bg-purple-100 text-purple-700',
  ARCHIVED: 'bg-gray-100 text-gray-500',
};

export default function PluginList() {
  const [plugins, setPlugins] = useState<Record<string, PluginInfo>>({});
  const [loading, setLoading] = useState(true);

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
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  const pluginList = Object.values(plugins);

  return (
    <div className="max-w-5xl mx-auto">
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
          New Document Type
        </Link>
      </div>

      <div className="grid gap-4">
        {pluginList.map((plugin) => {
          const source = (plugin as any)._source || 'file';
          const status = source === 'file' ? 'file' : ((plugin as any)._dynamodb_item?.status || 'PUBLISHED');

          return (
            <div
              key={plugin.pluginId}
              className="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-1">
                    <h3 className="text-lg font-semibold text-gray-900">{plugin.name}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[status] || statusColors.file}`}>
                      {source === 'file' ? 'Built-in' : status}
                    </span>
                    {plugin.hasPiiFields && (
                      <span className="flex items-center gap-1 text-xs text-amber-600">
                        <Lock className="w-3 h-3" /> PII
                      </span>
                    )}
                    {plugin.requiresSignatures && (
                      <span className="flex items-center gap-1 text-xs text-blue-600">
                        <Shield className="w-3 h-3" /> Signatures
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 mb-2">
                    {plugin.description?.slice(0, 150)}{plugin.description?.length > 150 ? '...' : ''}
                  </p>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span className="flex items-center gap-1">
                      <FileText className="w-3 h-3" />
                      {plugin.sections?.length || 0} section{(plugin.sections?.length || 0) !== 1 ? 's' : ''}
                    </span>
                    <span>ID: <code className="bg-gray-100 px-1 rounded">{plugin.pluginId}</code></span>
                    <span>v{plugin.version}</span>
                  </div>
                </div>
                {source !== 'file' && (
                  <Link
                    to={`/config/${plugin.pluginId}`}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Configure
                  </Link>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {pluginList.length === 0 && (
        <div className="text-center py-12 text-gray-500">
          <Puzzle className="w-12 h-12 mx-auto text-gray-300 mb-3" />
          <p>No document types registered.</p>
        </div>
      )}
    </div>
  );
}
