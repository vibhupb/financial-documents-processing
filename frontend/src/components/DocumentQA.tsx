import { useState, useRef } from 'react';
import { Send, Loader2, MessageSquare } from 'lucide-react';
import clsx from 'clsx';

interface QAEntry {
  question: string;
  answer: string;
  sourcePages: number[];
}

interface DocumentQAProps {
  documentId: string;
  apiBaseUrl: string;
  onPageClick?: (pageNumber: number) => void;
  className?: string;
}

export default function DocumentQA({
  documentId,
  apiBaseUrl,
  onPageClick,
  className,
}: DocumentQAProps) {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [error, setError] = useState('');
  const historyRef = useRef<HTMLDivElement>(null);

  const handleAsk = async () => {
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${apiBaseUrl}/documents/${documentId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q }),
      });
      const data = await resp.json();
      if (data.error) {
        setError(data.error);
      } else {
        setHistory(prev => [...prev, {
          question: q,
          answer: data.answer || 'No answer generated',
          sourcePages: data.sourcePages || [],
        }]);
        setQuestion('');
        // Scroll to bottom
        setTimeout(() => {
          historyRef.current?.scrollTo({ top: historyRef.current.scrollHeight, behavior: 'smooth' });
        }, 100);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={clsx('flex flex-col border-t border-gray-200', className)}>
      {/* Q&A History */}
      {history.length > 0 && (
        <div ref={historyRef} className="max-h-64 overflow-auto px-4 py-2 space-y-3 bg-gray-50">
          {history.map((entry, i) => (
            <div key={i} className="space-y-1">
              <p className="text-sm font-medium text-gray-700">
                <MessageSquare className="w-3.5 h-3.5 inline mr-1 text-primary-500" />
                {entry.question}
              </p>
              <p className="text-sm text-gray-600 pl-5 whitespace-pre-wrap">{entry.answer}</p>
              {entry.sourcePages.length > 0 && (
                <div className="flex gap-1 pl-5 flex-wrap">
                  {entry.sourcePages.map(p => (
                    <button
                      key={p}
                      onClick={() => onPageClick?.(p)}
                      className="text-xs px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded hover:bg-blue-200 transition-colors"
                    >
                      p.{p}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="px-4 py-1.5 bg-red-50 text-red-600 text-xs">{error}</div>
      )}

      {/* Input */}
      <div className="flex items-center gap-2 px-4 py-2.5 bg-white border-t border-gray-100">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAsk()}
          placeholder="Ask a question about this document..."
          className="flex-1 text-sm px-3 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-primary-400 focus:border-primary-400"
          disabled={loading}
        />
        <button
          onClick={handleAsk}
          disabled={!question.trim() || loading}
          className={clsx(
            'p-2 rounded-lg transition-colors',
            question.trim() && !loading
              ? 'bg-primary-600 text-white hover:bg-primary-700'
              : 'bg-gray-100 text-gray-400 cursor-not-allowed'
          )}
        >
          {loading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <Send className="w-4 h-4" />
          )}
        </button>
      </div>
    </div>
  );
}
