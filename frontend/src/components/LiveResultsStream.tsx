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
      className="bg-gray-900 rounded-lg p-4 max-h-96 overflow-y-auto font-mono text-sm leading-relaxed"
    >
      {events.length === 0 ? (
        <div className="text-center py-8">
          <div className="inline-flex items-center gap-2 text-gray-400">
            <div className="h-2 w-2 rounded-full bg-gray-500 animate-pulse" />
            <span>Waiting for processing events...</span>
          </div>
        </div>
      ) : (
        <div className="space-y-1">
          {events.map((event, index) => (
            <div key={index} className="flex gap-2.5">
              <span className="text-gray-500 flex-shrink-0 tabular-nums">
                [{formatElapsedTimestamp(event.ts, startedAt)}]
              </span>
              <span className={clsx('flex-shrink-0 font-semibold uppercase', stageColors[event.stage] || 'text-gray-400')}>
                {event.stage}:
              </span>
              <span className="text-gray-200 break-words">
                {event.message}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
