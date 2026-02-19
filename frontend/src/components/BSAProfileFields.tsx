import { ChevronDown, ChevronRight, Shield, Users, Building2, FileCheck } from 'lucide-react';
import { useState } from 'react';
import BooleanFlag from './BooleanFlag';
import PIIIndicator from './PIIIndicator';

interface BSAProfileFieldsProps {
  data: Record<string, any>;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}

export default function BSAProfileFields({ data }: BSAProfileFieldsProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['legalEntity', 'riskAssessment', 'beneficialOwners', 'certification'])
  );
  const [expandedOwners, setExpandedOwners] = useState<Set<number>>(new Set([0, 1]));

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

  const le = data?.legalEntity || {};
  const ra = data?.riskAssessment || {};
  const owners = data?.beneficialOwners || [];
  const trust = data?.trustInfo || {};
  const cert = data?.certificationInfo || {};
  const addr = le?.principalAddress || {};

  const isMasked = (val: string | undefined) =>
    typeof val === 'string' && /\*{2,}/.test(val);

  return (
    <div className="space-y-3">
      {/* Legal Entity */}
      <Section
        title="Legal Entity Information"
        icon={<Building2 className="w-4 h-4" />}
        expanded={expandedSections.has('legalEntity')}
        onToggle={() => toggleSection('legalEntity')}
      >
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
          <Field label="Company Name" value={le.companyName} />
          <Field label="DBA Name" value={le.dbaName} />
          <Field label="Entity Type" value={le.entityType} />
          <div>
            <span className="text-gray-500 text-xs">Tax ID:</span>{' '}
            <PIIIndicator value={le.taxId} isMasked={isMasked(le.taxId)} />
          </div>
          <Field label="Tax ID Type" value={le.taxIdType} />
          <Field label="NAICS Code" value={le.naicsCode} />
          <Field label="NAICS Description" value={le.naicsDescription} />
          <Field label="State of Organization" value={le.stateOfOrganization} />
          <Field label="Country" value={le.countryOfOrganization} />
          <Field label="Date Established" value={le.dateOfOrganization} />
          <Field label="Phone" value={le.phoneNumber} />
          <Field label="Email" value={le.emailAddress} />
          <Field label="Fax" value={le.faxNumber} />
          <Field label="Website" value={le.webAddress} />
          <div className="flex items-center gap-1">
            <span className="text-gray-500 text-xs">Publicly Traded:</span>
            <BooleanFlag value={le.isPubliclyTraded} />
          </div>
          <Field label="Ticker" value={le.tickerSymbol} />
          <Field label="Business Description" value={le.businessDescription} className="col-span-2" />
        </div>
        {(addr.street || addr.city) && (
          <div className="mt-2 p-2 bg-gray-50 rounded text-sm">
            <span className="text-gray-500 text-xs font-medium">Principal Address:</span>
            <div className="text-gray-900">
              {addr.street && <div>{addr.street}</div>}
              {(addr.city || addr.state || addr.zipCode) && (
                <div>{[addr.city, addr.state, addr.zipCode].filter(Boolean).join(', ')}</div>
              )}
              {addr.country && addr.country !== 'United States' && <div>{addr.country}</div>}
            </div>
          </div>
        )}
      </Section>

      {/* Risk Assessment */}
      <Section
        title="Risk Assessment"
        icon={<Shield className="w-4 h-4" />}
        expanded={expandedSections.has('riskAssessment')}
        onToggle={() => toggleSection('riskAssessment')}
      >
        <div className="space-y-2 text-sm">
          {ra.overallRiskRating && (
            <div className="flex items-center gap-2">
              <span className="text-gray-500">Risk Rating:</span>
              <RiskBadge level={ra.overallRiskRating} />
            </div>
          )}
          <div className="grid grid-cols-2 gap-x-4 gap-y-1">
            <BoolRow label="Cash Intensive" value={ra.isCashIntensive} />
            <BoolRow label="PEP Association" value={ra.hasPepAssociation} />
            <BoolRow label="AML History" value={ra.hasAmlHistory} />
            <BoolRow label="SAR History" value={ra.hasSarHistory} />
            <BoolRow label="Fraud History" value={ra.hasFraudHistory} />
            <BoolRow label="OFAC List" value={ra.isOnOfacList} />
            <BoolRow label="Money Service Business" value={ra.isMoneyServiceBusiness} />
            <BoolRow label="3rd Party Payment Processor" value={ra.isThirdPartyPaymentProcessor} />
            <BoolRow label="Requires EDD" value={ra.requiresEdd} />
          </div>
          {ra.industryRiskFlags?.length > 0 && (
            <div className="mt-1">
              <span className="text-gray-500 text-xs">Industry Risk Flags:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {ra.industryRiskFlags.map((flag: string, i: number) => (
                  <span key={i} className="px-2 py-0.5 bg-amber-50 text-amber-700 rounded text-xs">
                    {flag}
                  </span>
                ))}
              </div>
            </div>
          )}
          <Field label="EDD Reason" value={ra.eddReason} />
          <Field label="Risk Notes" value={ra.riskNotes} />
        </div>
      </Section>

      {/* Beneficial Owners */}
      {owners.length > 0 && (
        <Section
          title={`Beneficial Owners (${owners.length})`}
          icon={<Users className="w-4 h-4" />}
          expanded={expandedSections.has('beneficialOwners')}
          onToggle={() => toggleSection('beneficialOwners')}
        >
          <div className="space-y-2">
            {owners.map((owner: any, idx: number) => (
              <div key={idx} className="border border-gray-200 rounded-md overflow-hidden">
                <button
                  onClick={() => toggleOwner(idx)}
                  className="w-full flex items-center justify-between p-2.5 bg-gray-50 hover:bg-gray-100 text-sm"
                >
                  <span className="font-medium text-gray-900">
                    {owner.fullName || owner.name || `Owner ${idx + 1}`}
                    {owner.ownershipPercentage != null && (
                      <span className="text-gray-500 ml-2">({owner.ownershipPercentage}%)</span>
                    )}
                    {owner.controlPerson && (
                      <span className="ml-2 px-1.5 py-0.5 bg-blue-100 text-blue-700 rounded text-xs">
                        Control Person
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
                  <div className="p-3 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    <div>
                      <span className="text-gray-500">SSN:</span>{' '}
                      <PIIIndicator value={owner.ssn} isMasked={isMasked(owner.ssn)} />
                    </div>
                    <div>
                      <span className="text-gray-500">Date of Birth:</span>{' '}
                      <PIIIndicator value={owner.dateOfBirth} isMasked={isMasked(owner.dateOfBirth)} />
                    </div>
                    <Field label="Title" value={owner.title || owner.professionalTitle} />
                    <Field label="Citizenship" value={owner.citizenship} />
                    <Field label="Residency" value={owner.residency || owner.countryOfResidency} />
                    <div className="flex items-center gap-1">
                      <span className="text-gray-500">PEP:</span>
                      <BooleanFlag value={owner.isPep} />
                    </div>
                    <Field label="ID Type" value={owner.identificationDocType || owner.idDocumentType} />
                    <div>
                      <span className="text-gray-500">ID Number:</span>{' '}
                      <PIIIndicator
                        value={owner.identificationDocNumber || owner.idDocumentNumber}
                        isMasked={isMasked(owner.identificationDocNumber || owner.idDocumentNumber)}
                      />
                    </div>
                    <Field label="ID Issued" value={owner.identificationDocIssuance || owner.idIssuanceDate} />
                    <Field label="ID Expires" value={owner.identificationDocExpiration || owner.idExpirationDate} />
                    <Field label="Email" value={owner.emailAddress} />
                    <Field label="Phone" value={owner.phone || owner.businessPhone} />
                    {owner.address && (
                      <div className="col-span-2 mt-1 p-1.5 bg-gray-50 rounded">
                        <span className="text-gray-500">Address: </span>
                        {typeof owner.address === 'string' ? (
                          <span>{owner.address}</span>
                        ) : (
                          <span>
                            {owner.address.street}
                            {owner.address.city && `, ${owner.address.city}`}
                            {owner.address.state && `, ${owner.address.state}`}
                            {owner.address.zipCode && ` ${owner.address.zipCode}`}
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Trust Info */}
      {trust && (trust.trustName || trust.trusteeName) && (
        <Section
          title="Trust Information"
          expanded={expandedSections.has('trustInfo')}
          onToggle={() => toggleSection('trustInfo')}
        >
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Field label="Trust Name" value={trust.trustName} />
            <Field label="Trustee" value={trust.trusteeName} />
            <div className="flex items-center gap-1">
              <span className="text-gray-500 text-xs">Is Trust:</span>
              <BooleanFlag value={trust.isTrust} />
            </div>
          </div>
        </Section>
      )}

      {/* Certification */}
      {(cert.signatoryName || cert.certificationDate) && (
        <Section
          title="Certification"
          icon={<FileCheck className="w-4 h-4" />}
          expanded={expandedSections.has('certification')}
          onToggle={() => toggleSection('certification')}
        >
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Field label="Signatory" value={cert.signatoryName} />
            <Field label="Title" value={cert.signatoryTitle} />
            <Field label="Date" value={cert.certificationDate} />
            <Field label="Signature Status" value={cert.signatureStatus} />
          </div>
        </Section>
      )}
    </div>
  );
}

function getValue(field: any): string {
  if (field === null || field === undefined) return '';
  if (typeof field === 'object' && 'value' in field) return String(field.value ?? '');
  return String(field);
}

function Field({ label, value, className = '' }: { label: string; value: any; className?: string }) {
  const v = getValue(value);
  if (!v) return null;
  return (
    <div className={className}>
      <span className="text-gray-500 text-xs">{label}:</span>{' '}
      <span className="text-gray-900 text-sm">{v}</span>
    </div>
  );
}

function BoolRow({ label, value }: { label: string; value: boolean | null | undefined }) {
  if (value === null || value === undefined) return null;
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-gray-500 text-xs">{label}:</span>
      <BooleanFlag value={value} />
    </div>
  );
}

function RiskBadge({ level }: { level: string }) {
  const colors: Record<string, string> = {
    LOW: 'bg-green-100 text-green-800',
    MEDIUM: 'bg-yellow-100 text-yellow-800',
    HIGH: 'bg-red-100 text-red-800',
    PROHIBITED: 'bg-red-200 text-red-900',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[level] || 'bg-gray-100 text-gray-600'}`}>
      {level}
    </span>
  );
}

function Section({
  title,
  icon,
  expanded,
  onToggle,
  children,
}: {
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
