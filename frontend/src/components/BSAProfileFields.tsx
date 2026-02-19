import { ChevronDown, ChevronRight, Shield, Users, Building2 } from 'lucide-react';
import { useState } from 'react';
import BooleanFlag from './BooleanFlag';
import PIIIndicator from './PIIIndicator';

interface BSAProfileFieldsProps {
  data: Record<string, any>;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}

/**
 * Renders BSA Profile (Bank Secrecy Act / KYC) extracted data.
 * Handles: legal entity info, risk assessment, beneficial owners, trust info.
 */
export default function BSAProfileFields({ data, onFieldClick }: BSAProfileFieldsProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['legalEntity', 'riskAssessment'])
  );
  const [expandedOwners, setExpandedOwners] = useState<Set<number>>(new Set([0]));

  const toggleSection = (id: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleOwner = (idx: number) => {
    setExpandedOwners((prev) => {
      const next = new Set(prev);
      next.has(idx) ? next.delete(idx) : next.add(idx);
      return next;
    });
  };

  const legalEntity = data?.legalEntity || data?.legalEntityInfo || {};
  const riskAssessment = data?.riskAssessment || {};
  const beneficialOwners = data?.beneficialOwners || [];
  const trustInfo = data?.trustInfo || {};
  const certification = data?.certification || {};

  const isMasked = (val: string | undefined) =>
    typeof val === 'string' && /\*{2,}/.test(val);

  return (
    <div className="space-y-3">
      {/* Legal Entity Information */}
      <CollapsibleSection
        id="legalEntity"
        title="Legal Entity Information"
        icon={<Building2 className="w-4 h-4" />}
        expanded={expandedSections.has('legalEntity')}
        onToggle={() => toggleSection('legalEntity')}
      >
        <div className="grid grid-cols-2 gap-2 text-sm">
          <Field label="Entity Name" value={legalEntity.entityName} />
          <Field label="Entity Type" value={legalEntity.entityType} />
          <Field label="Address" value={legalEntity.address} />
          <Field label="City" value={legalEntity.city} />
          <Field label="State" value={legalEntity.state} />
          <Field label="ZIP" value={legalEntity.zipCode} />
          <div>
            <span className="text-gray-500">Tax ID:</span>{' '}
            <PIIIndicator value={legalEntity.taxId} isMasked={isMasked(legalEntity.taxId)} />
          </div>
          <Field label="SOS Number" value={legalEntity.sosNumber} />
          <Field label="Established" value={legalEntity.establishmentDate} />
        </div>
      </CollapsibleSection>

      {/* Risk Assessment */}
      <CollapsibleSection
        id="riskAssessment"
        title="Risk Assessment"
        icon={<Shield className="w-4 h-4" />}
        expanded={expandedSections.has('riskAssessment')}
        onToggle={() => toggleSection('riskAssessment')}
      >
        <div className="space-y-2 text-sm">
          {riskAssessment.riskLevel && (
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Risk Level:</span>
              <RiskBadge level={riskAssessment.riskLevel} />
            </div>
          )}
          <Field label="Industry" value={riskAssessment.industryClassification} />
          {riskAssessment.riskFactors?.length > 0 && (
            <div>
              <span className="text-gray-500 text-xs">Risk Factors:</span>
              <ul className="mt-1 space-y-0.5">
                {riskAssessment.riskFactors.map((f: any, i: number) => (
                  <li key={i} className="flex items-center gap-2 text-xs">
                    <span className={f.selected ? 'text-red-600' : 'text-gray-400'}>
                      {f.selected ? '✓' : '○'}
                    </span>
                    <span>{f.factor}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CollapsibleSection>

      {/* Beneficial Owners */}
      {beneficialOwners.length > 0 && (
        <CollapsibleSection
          id="beneficialOwners"
          title={`Beneficial Owners (${beneficialOwners.length})`}
          icon={<Users className="w-4 h-4" />}
          expanded={expandedSections.has('beneficialOwners')}
          onToggle={() => toggleSection('beneficialOwners')}
        >
          <div className="space-y-2">
            {beneficialOwners.map((owner: any, idx: number) => (
              <div key={idx} className="border border-gray-200 rounded-md overflow-hidden">
                <button
                  onClick={() => toggleOwner(idx)}
                  className="w-full flex items-center justify-between p-2 bg-gray-50 hover:bg-gray-100 text-sm"
                >
                  <span className="font-medium text-gray-900">
                    {getValue(owner.name) || `Owner ${idx + 1}`}
                    {owner.ownershipPercentage && (
                      <span className="text-gray-500 ml-2">
                        ({getValue(owner.ownershipPercentage)}%)
                      </span>
                    )}
                  </span>
                  {expandedOwners.has(idx) ? (
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  ) : (
                    <ChevronRight className="w-4 h-4 text-gray-400" />
                  )}
                </button>
                {expandedOwners.has(idx) && (
                  <div className="p-2 grid grid-cols-2 gap-1 text-xs">
                    <div>
                      <span className="text-gray-500">SSN:</span>{' '}
                      <PIIIndicator value={getValue(owner.ssn)} isMasked={isMasked(getValue(owner.ssn))} />
                    </div>
                    <div>
                      <span className="text-gray-500">DOB:</span>{' '}
                      <PIIIndicator value={getValue(owner.dateOfBirth)} isMasked={isMasked(getValue(owner.dateOfBirth))} />
                    </div>
                    <Field label="Ownership Type" value={owner.ownershipType} />
                    <div>
                      <span className="text-gray-500">Gov ID:</span>{' '}
                      <PIIIndicator
                        value={getValue(owner.governmentIdNumber)}
                        isMasked={isMasked(getValue(owner.governmentIdNumber))}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </CollapsibleSection>
      )}

      {/* Trust Info */}
      {trustInfo.isTrust && (
        <CollapsibleSection
          id="trustInfo"
          title="Trust Information"
          expanded={expandedSections.has('trustInfo')}
          onToggle={() => toggleSection('trustInfo')}
        >
          <div className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <span className="text-gray-500">Is Trust:</span>{' '}
              <BooleanFlag value={trustInfo.isTrust} />
            </div>
            <Field label="Trust Name" value={trustInfo.trustName} />
            <Field label="Trustee" value={trustInfo.trusteeNames} />
          </div>
        </CollapsibleSection>
      )}

      {/* Certification */}
      {(certification.authorizedRepName || certification.signatureDate) && (
        <CollapsibleSection
          id="certification"
          title="Certification"
          expanded={expandedSections.has('certification')}
          onToggle={() => toggleSection('certification')}
        >
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Field label="Representative" value={certification.authorizedRepName} />
            <Field label="Title" value={certification.authorizedRepTitle} />
            <Field label="Signature Date" value={certification.signatureDate} />
          </div>
        </CollapsibleSection>
      )}
    </div>
  );
}

// Helper to extract value from ExtractedField<T> or plain value
function getValue(field: any): string {
  if (field === null || field === undefined) return '';
  if (typeof field === 'object' && 'value' in field) return String(field.value ?? '');
  return String(field);
}

function Field({ label, value }: { label: string; value: any }) {
  const v = getValue(value);
  if (!v) return null;
  return (
    <div>
      <span className="text-gray-500">{label}:</span>{' '}
      <span className="text-gray-900">{v}</span>
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-green-100 text-green-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    HIGH: 'bg-red-100 text-red-800',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || 'bg-gray-100 text-gray-600'}`}>
      {level}
    </span>
  );
}

function CollapsibleSection({
  id,
  title,
  icon,
  expanded,
  onToggle,
  children,
}: {
  id: string;
  title: string;
  icon?: React.ReactNode;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100"
      >
        <div className="flex items-center gap-2">
          {icon}
          <span className="font-medium text-gray-900 text-sm">{title}</span>
        </div>
        {expanded ? (
          <ChevronDown className="w-4 h-4 text-gray-400" />
        ) : (
          <ChevronRight className="w-4 h-4 text-gray-400" />
        )}
      </button>
      {expanded && (
        <div className="p-3 border-t border-gray-200">{children}</div>
      )}
    </div>
  );
}
