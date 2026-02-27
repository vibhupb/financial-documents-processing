import { useState } from 'react';
import { Wand2, Loader2, CornerDownLeft } from 'lucide-react';
import clsx from 'clsx';
import { api } from '../../services/api';

interface AiRefineBarProps {
  /** Current plugin config to send as context */
  getConfig: () => Record<string, any>;
  /** Called when AI returns an updated config */
  onRefined: (updated: Record<string, any>) => void;
  /** Placeholder text for the input */
  placeholder?: string;
  className?: string;
}

export default function AiRefineBar({
  getConfig,
  onRefined,
  placeholder = 'Describe changes in plain English... e.g. "Add a tracking number field" or "Remove insurance fields"',
  className,
}: AiRefineBarProps) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [lastInstruction, setLastInstruction] = useState('');

  async function handleRefine() {
    const text = instruction.trim();
    if (!text || loading) return;

    setLoading(true);
    setError('');
    try {
      const result = await api.refinePluginConfig({
        config: getConfig(),
        instruction: text,
      });

      if (result.error) {
        setError(result.error);
      } else {
        setLastInstruction(text);
        setInstruction('');
        onRefined(result);
      }
    } catch (err: any) {
      setError(err.message || 'Refinement failed');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleRefine();
    }
  }

  return (
    <div className={clsx('space-y-2', className)}>
      <div className="flex items-center gap-2">
        <Wand2 className="w-4 h-4 text-violet-500 flex-shrink-0" />
        <span className="text-sm font-medium text-gray-700">AI Refine</span>
        {lastInstruction && (
          <span className="text-xs text-gray-400 truncate max-w-xs" title={lastInstruction}>
            Last: "{lastInstruction}"
          </span>
        )}
      </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <input
            className="w-full px-3 py-2.5 pr-10 border border-gray-200 rounded-lg text-sm focus:border-violet-400 focus:ring-1 focus:ring-violet-200 focus:outline-none disabled:bg-gray-50 disabled:cursor-not-allowed"
            placeholder={placeholder}
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          {!loading && instruction.trim() && (
            <div className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-300">
              <CornerDownLeft className="w-4 h-4" />
            </div>
          )}
        </div>
        <button
          onClick={handleRefine}
          disabled={loading || !instruction.trim()}
          className={clsx(
            'flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap',
            instruction.trim() && !loading
              ? 'bg-violet-600 text-white hover:bg-violet-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          )}
        >
          {loading ? (
            <><Loader2 className="w-4 h-4 animate-spin" /> Refining...</>
          ) : (
            <><Wand2 className="w-4 h-4" /> Refine</>
          )}
        </button>
      </div>

      {error && (
        <p className="text-xs text-red-500">{error}</p>
      )}
    </div>
  );
}
