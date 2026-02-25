import { useNavigate } from 'react-router-dom';
import { AlertTriangle, PlusCircle, RefreshCw } from 'lucide-react';

interface UnknownTypePromptProps {
  documentId: string;
  bestGuess?: string;
  confidence?: number;
}

export default function UnknownTypePrompt({
  documentId,
  bestGuess,
  confidence,
}: UnknownTypePromptProps) {
  const navigate = useNavigate();

  return (
    <div className="max-w-md mx-auto text-center">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-6">
        <div className="w-12 h-12 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <AlertTriangle className="w-6 h-6 text-amber-600" />
        </div>

        <h3 className="text-lg font-semibold text-amber-900">
          Unknown Document Type
        </h3>

        <p className="mt-2 text-sm text-amber-700">
          The classification engine could not determine the document type.
        </p>

        {bestGuess && (
          <p className="mt-3 text-sm text-amber-800 bg-amber-100 rounded-md px-3 py-2 inline-block">
            Best guess: <span className="font-medium">{bestGuess}</span>
            {confidence != null && (
              <span className="ml-1 text-amber-600">at {confidence}%</span>
            )}
          </p>
        )}

        <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() =>
              navigate(`/config/new?sampleDoc=${encodeURIComponent(documentId)}`)
            }
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-600 text-white text-sm font-medium hover:bg-amber-700 transition-colors"
          >
            <PlusCircle className="w-4 h-4" />
            Set Up New Plugin
          </button>

          <button
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-white border border-amber-300 text-amber-700 text-sm font-medium hover:bg-amber-50 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
            Retry Classification
          </button>
        </div>
      </div>
    </div>
  );
}
