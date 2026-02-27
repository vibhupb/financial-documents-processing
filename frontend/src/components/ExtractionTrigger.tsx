import { useState } from 'react';
import { Play, Loader2, CheckCircle } from 'lucide-react';
import clsx from 'clsx';

interface ExtractionTriggerProps {
  documentId: string;
  apiBaseUrl: string;
  onExtractionStarted?: () => void;
  className?: string;
}

export default function ExtractionTrigger({
  documentId,
  apiBaseUrl,
  onExtractionStarted,
  className,
}: ExtractionTriggerProps) {
  const [status, setStatus] = useState<'idle' | 'triggering' | 'started' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  const handleTrigger = async () => {
    setStatus('triggering');
    setErrorMsg('');
    try {
      const resp = await fetch(`${apiBaseUrl}/documents/${documentId}/extract`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await resp.json();
      if (data.error) {
        setStatus('error');
        setErrorMsg(data.error);
      } else {
        setStatus('started');
        onExtractionStarted?.();
      }
    } catch (e) {
      setStatus('error');
      setErrorMsg(String(e));
    }
  };

  return (
    <div className={clsx('flex flex-col items-center justify-center h-full gap-4 p-8', className)}>
      <div className="text-center max-w-sm">
        <h3 className="text-lg font-medium text-gray-800 mb-2">
          Extraction Not Yet Run
        </h3>
        <p className="text-sm text-gray-500 mb-6">
          This document has been indexed but field extraction has not been performed.
          Extraction uses the document&apos;s tree structure for precise page targeting.
        </p>

        {status === 'idle' && (
          <button
            onClick={handleTrigger}
            className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary-600 text-white rounded-lg font-medium text-sm hover:bg-primary-700 transition-colors shadow-sm"
          >
            <Play className="w-4 h-4" />
            Run Extraction Now
          </button>
        )}

        {status === 'triggering' && (
          <div className="inline-flex items-center gap-2 px-5 py-2.5 bg-gray-100 text-gray-600 rounded-lg font-medium text-sm">
            <Loader2 className="w-4 h-4 animate-spin" />
            Starting extraction...
          </div>
        )}

        {status === 'started' && (
          <div className="inline-flex items-center gap-2 px-5 py-2.5 bg-green-50 text-green-700 rounded-lg font-medium text-sm">
            <CheckCircle className="w-4 h-4" />
            Extraction started — refresh to see progress
          </div>
        )}

        {status === 'error' && (
          <div className="text-center">
            <p className="text-sm text-red-600 mb-3">{errorMsg}</p>
            <button
              onClick={handleTrigger}
              className="inline-flex items-center gap-2 px-4 py-2 bg-red-50 text-red-700 rounded-lg text-sm hover:bg-red-100 transition-colors"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
