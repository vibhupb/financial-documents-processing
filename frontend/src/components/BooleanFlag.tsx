interface BooleanFlagProps {
  value: boolean | null | undefined;
  trueLabel?: string;
  falseLabel?: string;
}

export default function BooleanFlag({
  value,
  trueLabel = 'Yes',
  falseLabel = 'No',
}: BooleanFlagProps) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-gray-400">-</span>;
  }

  return value ? (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
      {trueLabel}
    </span>
  ) : (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
      {falseLabel}
    </span>
  );
}
