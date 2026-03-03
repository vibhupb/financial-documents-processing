export default function ComplianceScoreGauge({ score }: { score: number }) {
  const color =
    score >= 90
      ? 'text-green-600'
      : score >= 50
        ? 'text-yellow-600'
        : 'text-red-600';
  const radius = 40;
  const circ = 2 * Math.PI * radius;
  const offset = circ - (score / 100) * circ;
  return (
    <div className="flex flex-col items-center">
      <svg width="100" height="100" className="-rotate-90">
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#e5e7eb"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth="8"
          strokeDasharray={circ}
          strokeDashoffset={offset}
          className={color}
          strokeLinecap="round"
        />
      </svg>
      <span className={`text-2xl font-bold -mt-16 ${color}`}>{score}%</span>
      <span className="text-xs text-gray-500 mt-1">Compliance</span>
    </div>
  );
}
