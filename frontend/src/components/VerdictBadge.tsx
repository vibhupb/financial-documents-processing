const colors: Record<string, string> = {
  PASS: 'bg-green-100 text-green-700',
  FAIL: 'bg-red-100 text-red-700',
  PARTIAL: 'bg-yellow-100 text-yellow-700',
  NOT_FOUND: 'bg-gray-100 text-gray-500',
};

export default function VerdictBadge({ verdict }: { verdict: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-medium ${
        colors[verdict] || 'bg-gray-100'
      }`}
    >
      {verdict}
    </span>
  );
}
