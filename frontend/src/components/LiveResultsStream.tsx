import { useEffect, useRef } from 'react';
import clsx from 'clsx';
import type { ProcessingEvent } from '../types';

interface LiveResultsStreamProps {
  events: ProcessingEvent[];
  startedAt?: string;
}

const stageColors: Record<ProcessingEvent['stage'], string> = {
  trigger: 'text-gray-400',
  router: 'text-blue-400',
  extractor: 'text-green-400',
  normalizer: 'text-purple-400',
};

function formatElapsedTimestamp(eventTs: string, startedAt?: string): string {
  if (!startedAt) return '--:--';
  const start = new Date(startedAt).getTime();
  const event = new Date(eventTs).getTime();
  const diffMs = Math.max(0, event - start);
  const totalSeconds = Math.floor(diffMs / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export default function LiveResultsStream({ events, startedAt }: LiveResultsStreamProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events.length]);

  return (
    <div
      ref={scrollRef}
      className="bg-gray-900 rounded-lg p-3 max-h-64 overflow-y-auto font-mono text-xs leading-relaxed"
    >
      {events.length === 0 ? (
        <p className="text-gray-500 text-center py-4">
          Waiting for processing events...
        </p>
      ) : (
        <div className="space-y-0.5">
          {events.map((event, index) => (
            <div key={index} className="flex gap-2">
              <span className="text-gray-600 flex-shrink-0">
                [{formatElapsedTimestamp(event.ts, startedAt)}]
              </span>
              <span className={clsx('flex-shrink-0', stageColors[event.stage] || 'text-gray-400')}>
                {event.stage}:
              </span>
              <span className="text-gray-300 break-words">
                {event.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
