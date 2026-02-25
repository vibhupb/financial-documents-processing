import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDropzone } from 'react-dropzone';
import {
  Upload, Loader2, Save, ArrowLeft, ArrowRight,
  AlertCircle, CheckCircle, Wand2,
} from 'lucide-react';
import clsx from 'clsx';
import { api } from '../services/api';
import WizardSteps from '../components/wizard/WizardSteps';
import FieldEditor, { type FieldDef } from '../components/wizard/FieldEditor';

interface AnalysisResult {
  pages: { page: number; text: string; charCount: number }[];
  pageCount: number;
  text: string;
  forms: Record<string, { value: string; confidence: number }>;
  formFieldCount: number;
  textractError?: string;
}

interface GeneratedConfig {
  pluginId: string;
  name: string;
  description: string;
  keywords: string[];
  fields: FieldDef[];
  promptRules: string[];
  _generation?: { model: string; inputTokens: number; outputTokens: number };
}

type WizardStep = 1 | 2 | 3 | 4;

export default function PluginWizard() {
  const navigate = useNavigate();
  const [step, setStep] = useState<WizardStep>(1);

  // Step 1 state
  const [docName, setDocName] = useState('');
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [uploadError, setUploadError] = useState('');

  // Step 2 state
  const [generating, setGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedConfig | null>(null);
  const [fields, setFields] = useState<FieldDef[]>([]);

  // Step 3 state
  const [pluginId, setPluginId] = useState('');
  const [description, setDescription] = useState('');
  const [keywords, setKeywords] = useState('');
  const [promptRules, setPromptRules] = useState<string[]>([]);

  // Step 4 state
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [saveError, setSaveError] = useState('');

  // --- Step 1: Upload & Analyze ---
  const onDrop = useCallback(async (files: File[]) => {
    const file = files[0];
    if (!file) return;
    setUploadError('');
    setUploading(true);

    try {
      const urlRes = await api.createUploadUrl(file.name);
      await api.uploadFile(urlRes.uploadUrl, urlRes.fields, file);

      setUploading(false);
      setAnalyzing(true);

      const result = await api.analyzeSample({
        s3Key: urlRes.key,
        bucket: '', // backend uses BUCKET_NAME env var as default
      });

      if (result.error) {
        setUploadError(result.error);
      } else {
        setAnalysis(result);
        if (!docName) setDocName(file.name.replace(/\.pdf$/i, ''));
      }
    } catch (err: any) {
      setUploadError(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      setAnalyzing(false);
    }
  }, [docName]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    maxSize: 50 * 1024 * 1024,
    disabled: uploading || analyzing,
  });

  // --- Step 2: AI Generate ---
  async function handleGenerate() {
    if (!analysis) return;
    setGenerating(true);
    try {
      const result = await api.generatePluginConfig({
        text: analysis.text,
        formFields: analysis.forms,
        name: docName,
        pageCount: analysis.pageCount,
      });
      if (result.error) {
        setUploadError(result.error);
      } else {
        setGenerated(result);
        setFields(result.fields || []);
        setPluginId(result.pluginId || '');
        setDescription(result.description || '');
        setKeywords((result.keywords || []).join(', '));
        setPromptRules(result.promptRules || []);
        setStep(2);
      }
    } catch (err: any) {
      setUploadError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  // --- Step 4: Save ---
  async function handleSave() {
    setSaving(true);
    setSaveError('');
    try {
      const config = {
        pluginId,
        name: docName,
        description,
        keywords: keywords.split(',').map((k) => k.trim()).filter(Boolean),
        fields,
        promptRules,
        pageCount: analysis?.pageCount || 1,
        status: 'DRAFT',
      };
      await api.createPluginConfig(config);
      setSaved(true);
      setStep(4);
    } catch (err: any) {
      setSaveError(err.message || 'Save failed');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <button onClick={() => navigate('/config')} className="text-gray-400 hover:text-gray-600">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Plugin Builder</h1>
          <p className="text-sm text-gray-500">
            Upload a sample document and let AI generate the extraction config
          </p>
        </div>
      </div>

      <WizardSteps current={step} />

      {uploadError && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {uploadError}
          <button onClick={() => setUploadError('')} className="ml-auto text-red-400 hover:text-red-600">dismiss</button>
        </div>
      )}

      {/* ========== STEP 1: Upload Sample ========== */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="card">
            <label className="block text-sm font-medium text-gray-700 mb-2">Document Type Name</label>
            <input
              className="w-full px-3 py-2 border border-gray-200 rounded-lg focus:border-primary-400 focus:outline-none"
              placeholder="e.g. Invoice, Tax Return, Insurance Claim..."
              value={docName}
              onChange={(e) => setDocName(e.target.value)}
            />
          </div>

          <div className="card">
            <label className="block text-sm font-medium text-gray-700 mb-3">Upload Sample PDF</label>
            {!analysis ? (
              <div
                {...getRootProps()}
                className={clsx(
                  'border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors',
                  isDragActive ? 'border-primary-400 bg-primary-50' : 'border-gray-200 hover:border-primary-300'
                )}
              >
                <input {...getInputProps()} />
                {uploading || analyzing ? (
                  <div>
                    <Loader2 className="w-10 h-10 text-primary-600 animate-spin mx-auto mb-3" />
                    <p className="text-sm text-gray-600">{uploading ? 'Uploading...' : 'Analyzing document...'}</p>
                  </div>
                ) : (
                  <div>
                    <Upload className="w-10 h-10 text-gray-300 mx-auto mb-3" />
                    <p className="text-sm text-gray-600">Drop a sample PDF here or click to browse</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-green-800">Analysis complete</p>
                    <p className="text-xs text-green-600 mt-0.5">
                      {analysis.pageCount} pages &middot; {analysis.formFieldCount || 0} form fields detected
                      &middot; {(analysis.text?.length || 0).toLocaleString()} chars extracted
                    </p>
                  </div>
                </div>

                {/* Form fields preview */}
                {analysis.forms && Object.keys(analysis.forms).length > 0 && (
                  <div className="mt-3 max-h-40 overflow-y-auto">
                    <p className="text-xs font-medium text-gray-500 mb-1">Detected form fields:</p>
                    <div className="grid grid-cols-2 gap-1">
                      {Object.entries(analysis.forms).slice(0, 20).map(([key, val]) => (
                        <div key={key} className="text-xs bg-white rounded px-2 py-1 border border-green-100">
                          <span className="font-medium text-gray-700">{key}</span>
                          <span className="text-gray-400 ml-1">{val.value?.slice(0, 30)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3">
            <button
              disabled={!analysis || !docName || generating}
              onClick={handleGenerate}
              className={clsx(
                'flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-colors',
                analysis && docName
                  ? 'bg-primary-600 text-white hover:bg-primary-700'
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
              )}
            >
              {generating ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
              ) : (
                <><Wand2 className="w-4 h-4" /> Generate Config with AI</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ========== STEP 2: Review Fields ========== */}
      {step === 2 && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-lg font-semibold text-gray-900">Extraction Fields</h2>
                <p className="text-sm text-gray-500">
                  AI suggested {fields.length} fields. Edit, add, or remove as needed.
                </p>
              </div>
              {generated?._generation && (
                <span className="text-xs text-gray-400">
                  via {generated._generation.model} &middot;{' '}
                  {generated._generation.inputTokens + generated._generation.outputTokens} tokens
                </span>
              )}
            </div>
            <FieldEditor
              fields={fields}
              onChange={setFields}
              formKeys={analysis?.forms}
            />
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(1)} className="btn-secondary flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
            <button
              onClick={() => setStep(3)}
              disabled={fields.length === 0}
              className="btn-primary flex items-center gap-1"
            >
              Next <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* ========== STEP 3: Configure ========== */}
      {step === 3 && (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-gray-900">Plugin Settings</h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Plugin ID</label>
                <input
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none font-mono"
                  value={pluginId}
                  onChange={(e) => setPluginId(e.target.value.replace(/[^a-z0-9_]/g, ''))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Display Name</label>
                <input
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none"
                  value={docName}
                  onChange={(e) => setDocName(e.target.value)}
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Description</label>
              <textarea
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Classification Keywords <span className="text-gray-400 font-normal">(comma-separated)</span>
              </label>
              <input
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:border-primary-400 focus:outline-none"
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Normalization Rules</label>
              <div className="space-y-2">
                {promptRules.map((rule, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="text-xs text-gray-400 mt-2 w-5">{i + 1}.</span>
                    <input
                      className="flex-1 px-3 py-1.5 border border-gray-200 rounded text-sm focus:border-primary-400 focus:outline-none"
                      value={rule}
                      onChange={(e) => {
                        const updated = [...promptRules];
                        updated[i] = e.target.value;
                        setPromptRules(updated);
                      }}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="card bg-gray-50">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Summary</h3>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-500">Fields:</span>{' '}
                <span className="font-medium">{fields.length}</span>
              </div>
              <div>
                <span className="text-gray-500">Keywords:</span>{' '}
                <span className="font-medium">{keywords.split(',').filter((k) => k.trim()).length}</span>
              </div>
              <div>
                <span className="text-gray-500">Pages:</span>{' '}
                <span className="font-medium">{analysis?.pageCount || '?'}</span>
              </div>
            </div>
          </div>

          <div className="flex justify-between">
            <button onClick={() => setStep(2)} className="btn-secondary flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" /> Back
            </button>
            <button
              onClick={handleSave}
              disabled={saving || !pluginId}
              className="btn-primary flex items-center gap-1"
            >
              {saving ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Saving...</>
              ) : (
                <><Save className="w-4 h-4" /> Save as Draft</>
              )}
            </button>
          </div>
        </div>
      )}

      {/* ========== STEP 4: Done ========== */}
      {step === 4 && saved && (
        <div className="card text-center py-12">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-10 h-10 text-green-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Plugin Created</h2>
          <p className="mt-2 text-sm text-gray-500">
            <code className="bg-gray-100 px-2 py-0.5 rounded">{pluginId}</code> saved as DRAFT
          </p>
          <p className="mt-1 text-xs text-gray-400">
            {fields.length} extraction fields configured
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <button onClick={() => navigate('/config')} className="btn-secondary">
              Back to Plugins
            </button>
            <button onClick={() => navigate(`/config/${pluginId}`)} className="btn-primary">
              View Plugin
            </button>
          </div>
        </div>
      )}

      {saveError && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          <AlertCircle className="w-4 h-4 inline mr-1" /> {saveError}
        </div>
      )}
    </div>
  );
}
