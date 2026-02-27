import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Save, Loader2, AlertCircle, Trash2, Rocket,
  Pencil, Plus, X, Tag, FileText, Settings, BookOpen,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import FieldEditor, { type FieldDef } from '../components/wizard/FieldEditor';
import AiRefineBar from '../components/wizard/AiRefineBar';

type EditorTab = 'overview' | 'fields' | 'rules' | 'schema';

interface PluginVersion {
  pluginId: string;
  version: string;
  status: string;
  name?: string;
  description?: string;
  config?: Record<string, any>;
  promptTemplate?: string;
  createdAt?: string;
  updatedAt?: string;
  publishedBy?: string;
}

export default function PluginEditor() {
  const { pluginId } = useParams<{ pluginId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<EditorTab>('overview');

  // Plugin data
  const [versions, setVersions] = useState<PluginVersion[]>([]);
  const [latest, setLatest] = useState<PluginVersion | null>(null);
  const [isFilePlugin, setIsFilePlugin] = useState(false);

  // Editable fields
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState('');
  const [fields, setFields] = useState<FieldDef[]>([]);
  const [promptRules, setPromptRules] = useState<string[]>([]);
  // Full config (preserves extraction pipeline config: sections, classification, etc.)
  const [fullConfig, setFullConfig] = useState<Record<string, any>>({});

  // Actions
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    if (pluginId) loadPlugin();
  }, [pluginId]);

  async function loadPlugin() {
    setLoading(true);
    setError('');
    try {
      const data = await api.getPluginConfig(pluginId!);
      if (data.error) {
        setError(`Plugin "${pluginId}" not found`);
      } else {
        // API returns versions for both DynamoDB and file-based plugins
        setIsFilePlugin(data._source === 'file');
        setVersions(data.versions || []);
        const latestVer = data.versions?.[0];
        setLatest(latestVer || null);
        if (latestVer) {
          populateFromVersion(latestVer);
        }
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load plugin');
    } finally {
      setLoading(false);
    }
  }

  function populateFromVersion(ver: PluginVersion) {
    const config = ver.config || {};
    setFullConfig(config);
    setName(ver.name || config.name || '');
    setDescription(ver.description || config.description || '');
    setKeywords((config.keywords || config.classification?.keywords || []).join(', '));
    setFields(config.fields || []);
    setPromptRules(config.promptRules || []);
    setDirty(false);
  }

  function markDirty() {
    if (!dirty) setDirty(true);
    if (successMsg) setSuccessMsg('');
  }

  /** Build the config for save — overlays wizard edits onto the full extraction config. */
  function buildSaveConfig() {
    return {
      ...fullConfig,
      name,
      description,
      keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
      fields,
      promptRules,
    };
  }

  // --- Save ---
  async function handleSave() {
    setSaving(true);
    setError('');
    setSuccessMsg('');
    try {
      const config = buildSaveConfig();
      await api.updatePluginConfig(pluginId!, { name, description, config });
      setDirty(false);
      setSuccessMsg('Changes saved');
      // Reload to get updated version info
      await loadPlugin();
    } catch (err: any) {
      setError(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  // --- Publish ---
  async function handlePublish() {
    setPublishing(true);
    setError('');
    setSuccessMsg('');
    try {
      // Save first if dirty
      if (dirty) {
        const config = buildSaveConfig();
        await api.updatePluginConfig(pluginId!, { name, description, config });
      }
      await api.publishPlugin(pluginId!);
      setSuccessMsg('Plugin published successfully');
      setDirty(false);
      await loadPlugin();
    } catch (err: any) {
      setError(err.message || 'Publish failed');
    } finally {
      setPublishing(false);
    }
  }

  // --- Delete ---
  async function handleDelete() {
    setDeleting(true);
    setError('');
    try {
      await api.deletePlugin(pluginId!);
      navigate('/config');
    } catch (err: any) {
      setError(err.message || 'Delete failed');
      setDeleting(false);
    }
  }

  const isEditable = true; // All plugins are editable — file-based plugins get a DynamoDB override on save
  const isDraft = latest?.status === 'DRAFT';

  const tabs: { id: EditorTab; label: string; icon: typeof Settings }[] = [
    { id: 'overview', label: 'Overview', icon: Settings },
    { id: 'fields', label: 'Fields', icon: FileText },
    { id: 'rules', label: 'Rules', icon: BookOpen },
    { id: 'schema', label: 'Raw Config', icon: Tag },
  ];

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/config')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-gray-900">
              <Pencil className="w-5 h-5 inline mr-2 text-primary-600" />
              {name || pluginId}
            </h1>
            {latest && (
              <span
                className={clsx(
                  'px-2 py-0.5 rounded-full text-xs font-medium',
                  latest.status === 'PUBLISHED' ? 'bg-green-100 text-green-700' :
                  latest.status === 'DRAFT' ? 'bg-yellow-100 text-yellow-700' :
                  'bg-gray-100 text-gray-500'
                )}
              >
                {latest.status}
              </span>
            )}
            {isFilePlugin && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700">
                Built-in
              </span>
            )}
            {dirty && (
              <span className="text-xs text-amber-500 font-medium">Unsaved changes</span>
            )}
          </div>
          <p className="text-sm text-gray-500 mt-0.5">
            <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs">{pluginId}</code>
            {latest?.version && <span className="ml-2 text-gray-400">({latest.version})</span>}
            {isFilePlugin && !dirty && <span className="ml-2 text-blue-600">Edits create a customized override</span>}
          </p>
        </div>

        {/* Action Buttons */}
        {isEditable && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleSave}
              disabled={saving || !dirty}
              className={clsx(
                'flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                dirty
                  ? 'bg-primary-600 text-white hover:bg-primary-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              )}
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
              Save
            </button>
            {isDraft && (
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="flex items-center gap-1.5 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors disabled:opacity-50"
              >
                {publishing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Rocket className="w-4 h-4" />}
                Publish
              </button>
            )}
          </div>
        )}
      </div>

      {/* Error / Success */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-600">dismiss</button>
        </div>
      )}
      {successMsg && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {successMsg}
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b border-gray-200 mb-6">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={clsx(
                'flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px',
                activeTab === tab.id
                  ? 'border-primary-600 text-primary-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              )}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ========== OVERVIEW TAB ========== */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Plugin Settings</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plugin ID</label>
                <input
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm font-mono bg-gray-50 cursor-not-allowed"
                  value={pluginId || ''}
                  disabled
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                <input
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none disabled:bg-gray-50 disabled:cursor-not-allowed"
                  value={name}
                  onChange={(e) => { setName(e.target.value); markDirty(); }}
                  disabled={!isEditable}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none disabled:bg-gray-50 disabled:cursor-not-allowed"
                rows={3}
                value={description}
                onChange={(e) => { setDescription(e.target.value); markDirty(); }}
                disabled={!isEditable}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Classification Keywords <span className="text-gray-400 font-normal">(comma-separated)</span>
              </label>
              <input
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none disabled:bg-gray-50 disabled:cursor-not-allowed"
                value={keywords}
                onChange={(e) => { setKeywords(e.target.value); markDirty(); }}
                disabled={!isEditable}
              />
              {keywords && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {keywords.split(',').map((k) => k.trim()).filter(Boolean).map((kw, i) => (
                    <span key={i} className="inline-flex items-center gap-1 bg-gray-100 text-gray-600 text-xs px-2 py-0.5 rounded-full">
                      <Tag className="w-3 h-3" />
                      {kw}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Version History */}
          {versions.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">Version History</h3>
              <div className="space-y-2">
                {versions.map((ver) => (
                  <div key={ver.version} className="flex items-center justify-between text-sm border-b border-gray-50 pb-2 last:border-0">
                    <div className="flex items-center gap-2">
                      <code className="text-xs bg-gray-100 px-1.5 py-0.5 rounded">{ver.version}</code>
                      <span
                        className={clsx(
                          'px-2 py-0.5 rounded-full text-xs font-medium',
                          ver.status === 'PUBLISHED' ? 'bg-green-100 text-green-700' :
                          ver.status === 'DRAFT' ? 'bg-yellow-100 text-yellow-700' :
                          'bg-gray-100 text-gray-500'
                        )}
                      >
                        {ver.status}
                      </span>
                    </div>
                    <span className="text-xs text-gray-400">
                      {ver.updatedAt ? new Date(ver.updatedAt).toLocaleString() : ver.createdAt ? new Date(ver.createdAt).toLocaleString() : ''}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========== FIELDS TAB ========== */}
      {activeTab === 'fields' && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Extraction Fields</h2>
                <p className="text-sm text-gray-500">
                  {fields.length} fields configured for Textract extraction
                </p>
              </div>
            </div>
            {isEditable ? (
              <FieldEditor
                fields={fields}
                onChange={(newFields) => { setFields(newFields); markDirty(); }}
              />
            ) : (
              // Read-only field display for file-based plugins
              <div className="space-y-2">
                <div className="grid grid-cols-12 gap-2 text-xs font-medium text-gray-500 px-1">
                  <div className="col-span-3">Field Name</div>
                  <div className="col-span-3">Label</div>
                  <div className="col-span-2">Type</div>
                  <div className="col-span-4">Query</div>
                </div>
                {fields.map((field, i) => (
                  <div key={i} className="grid grid-cols-12 gap-2 items-center bg-gray-50 border border-gray-100 rounded-lg p-2 text-sm">
                    <code className="col-span-3 text-xs text-gray-700">{field.name}</code>
                    <span className="col-span-3 text-gray-600">{field.label}</span>
                    <span className="col-span-2 text-gray-500">{field.type}</span>
                    <span className="col-span-4 text-gray-400 text-xs">{field.query || '-'}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {isEditable && (
            <AiRefineBar
              getConfig={() => ({
                ...fullConfig,
                pluginId,
                name,
                description,
                keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
                fields,
                promptRules,
              })}
              onRefined={(updated) => {
                // Update full config (preserves sections, classification, etc.)
                setFullConfig((prev) => ({ ...prev, ...updated }));
                if (updated.fields) { setFields(updated.fields); markDirty(); }
                if (updated.promptRules) { setPromptRules(updated.promptRules); markDirty(); }
                if (updated.keywords) { setKeywords(updated.keywords.join(', ')); markDirty(); }
                if (updated.description) { setDescription(updated.description); markDirty(); }
                if (updated.name) { setName(updated.name); markDirty(); }
              }}
              placeholder='e.g. "Add a tracking number field" or "Split address into street, city, state, zip"'
            />
          )}
        </div>
      )}

      {/* ========== RULES TAB ========== */}
      {activeTab === 'rules' && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Normalization Rules</h2>
            <p className="text-sm text-gray-500 mb-4">
              Rules that guide how the LLM normalizes extracted data.
            </p>
            <div className="space-y-2">
              {promptRules.map((rule, i) => (
                <div key={i} className="flex gap-2 items-start">
                  <span className="text-xs text-gray-400 mt-2.5 w-5 shrink-0">{i + 1}.</span>
                  {isEditable ? (
                    <>
                      <input
                        className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none"
                        value={rule}
                        onChange={(e) => {
                          const updated = [...promptRules];
                          updated[i] = e.target.value;
                          setPromptRules(updated);
                          markDirty();
                        }}
                      />
                      <button
                        onClick={() => {
                          setPromptRules(promptRules.filter((_, idx) => idx !== i));
                          markDirty();
                        }}
                        className="text-gray-400 hover:text-red-500 mt-2"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </>
                  ) : (
                    <p className="flex-1 text-sm text-gray-600 bg-gray-50 px-3 py-2 rounded-lg">
                      {rule}
                    </p>
                  )}
                </div>
              ))}
              {promptRules.length === 0 && (
                <p className="text-sm text-gray-400 italic">No normalization rules configured</p>
              )}
            </div>
            {isEditable && (
              <button
                onClick={() => {
                  setPromptRules([...promptRules, '']);
                  markDirty();
                }}
                className="flex items-center gap-1.5 text-sm text-primary-600 hover:text-primary-700 font-medium mt-3"
              >
                <Plus className="w-4 h-4" /> Add Rule
              </button>
            )}
          </div>

          {isEditable && (
            <AiRefineBar
              getConfig={() => ({
                ...fullConfig,
                pluginId,
                name,
                description,
                keywords: keywords.split(',').map(k => k.trim()).filter(Boolean),
                fields,
                promptRules,
              })}
              onRefined={(updated) => {
                // Update full config (preserves sections, classification, etc.)
                setFullConfig((prev) => ({ ...prev, ...updated }));
                if (updated.fields) { setFields(updated.fields); markDirty(); }
                if (updated.promptRules) { setPromptRules(updated.promptRules); markDirty(); }
                if (updated.keywords) { setKeywords(updated.keywords.join(', ')); markDirty(); }
                if (updated.description) { setDescription(updated.description); markDirty(); }
                if (updated.name) { setName(updated.name); markDirty(); }
              }}
              placeholder='e.g. "Add a rule to mask all SSN fields" or "Normalize currency to 2 decimal places"'
            />
          )}
        </div>
      )}

      {/* ========== RAW CONFIG TAB ========== */}
      {activeTab === 'schema' && (
        <div className="space-y-6">
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Raw Configuration</h2>
            <pre className="text-xs text-gray-600 bg-gray-50 border border-gray-200 rounded-lg p-4 overflow-x-auto max-h-[600px] overflow-y-auto whitespace-pre-wrap">
              {JSON.stringify(
                latest || { pluginId, name, description, keywords: keywords.split(',').map(k => k.trim()).filter(Boolean), fields, promptRules },
                null,
                2
              )}
            </pre>
          </div>
        </div>
      )}

      {/* Danger Zone */}
      {isEditable && (
        <div className="mt-8 card border-red-100">
          <h3 className="text-sm font-semibold text-red-600 mb-2">Danger Zone</h3>
          {!confirmDelete ? (
            <button
              onClick={() => setConfirmDelete(true)}
              className="flex items-center gap-1.5 text-sm text-red-500 hover:text-red-700 font-medium"
            >
              <Trash2 className="w-4 h-4" /> {isFilePlugin ? 'Revert to built-in defaults' : 'Delete this plugin'}
            </button>
          ) : (
            <div className="flex items-center gap-3">
              <p className="text-sm text-red-600">
                {isFilePlugin
                  ? <>This will remove all customizations and revert <strong>{pluginId}</strong> to its built-in defaults. Are you sure?</>
                  : <>This will permanently delete all versions of <strong>{pluginId}</strong>. Are you sure?</>
                }
              </p>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-50"
              >
                {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                {isFilePlugin ? 'Confirm Revert' : 'Confirm Delete'}
              </button>
              <button
                onClick={() => setConfirmDelete(false)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
