import { useState } from 'react';
import {
  DollarSign,
  FileText,
  User,
  Home,
  Briefcase,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  AlertCircle,
  CheckCircle,
  Info,
  PenTool,
  XCircle,
} from 'lucide-react';
import clsx from 'clsx';
import type {
  LoanData,
  ExtractedField,
  PromissoryNoteData,
  ClosingDisclosureData,
  Form1003Data,
  ValidationResult,
  DocumentClassification,
  CreditAgreement,
  LoanAgreementData,
  ProcessingCost,
  ProcessingTime,
  SignatureValidation,
} from '../types';
import ProcessingMetricsPanel from './ProcessingMetricsPanel';

interface ExtractedValuesPanelProps {
  data: LoanData | null;
  validation?: ValidationResult;
  signatureValidation?: SignatureValidation;
  classification?: DocumentClassification;
  processingCost?: ProcessingCost;
  processingTime?: ProcessingTime;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
  className?: string;
}

export default function ExtractedValuesPanel({
  data,
  validation,
  signatureValidation,
  classification,
  processingCost,
  processingTime,
  onFieldClick,
  className,
}: ExtractedValuesPanelProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['promissoryNote', 'closingDisclosure', 'form1003', 'creditAgreement', 'loanAgreement'])
  );

  const toggleSection = (section: string) => {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  if (!data) {
    return (
      <div className={clsx('flex flex-col h-full bg-white', className)}>
        <div className="flex-1 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
            <p>No extracted data available</p>
            <p className="text-sm mt-1">Upload a document to see extracted values</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('flex flex-col h-full bg-white overflow-hidden', className)}>
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 bg-gray-50">
        <h2 className="text-lg font-semibold text-gray-900">Extracted Data</h2>
        <p className="text-sm text-gray-500 mt-0.5">
          Click any field to jump to that page in the document
        </p>
      </div>

      {/* Validation Summary */}
      {validation && (
        <div
          className={clsx(
            'mx-4 mt-4 p-3 rounded-lg flex items-start gap-3',
            validation.isValid ? 'bg-green-50' : 'bg-yellow-50'
          )}
        >
          {validation.isValid ? (
            <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          )}
          <div className="flex-1">
            <p
              className={clsx(
                'text-sm font-medium',
                validation.isValid ? 'text-green-800' : 'text-yellow-800'
              )}
            >
              {validation.isValid ? 'Document Validated' : 'Review Required'}
            </p>
            <p className="text-xs mt-0.5 text-gray-600">
              Confidence: <span className="font-medium">{validation.confidence}</span>
            </p>
          </div>
        </div>
      )}

      {/* Signature Validation */}
      {signatureValidation && (
        <div
          className={clsx(
            'mx-4 mt-3 p-3 rounded-lg flex items-start gap-3',
            signatureValidation.validationStatus === 'SIGNED'
              ? 'bg-green-50'
              : signatureValidation.validationStatus === 'PARTIAL'
                ? 'bg-yellow-50'
                : 'bg-red-50'
          )}
        >
          {signatureValidation.validationStatus === 'SIGNED' ? (
            <PenTool className="w-5 h-5 text-green-600 flex-shrink-0" />
          ) : signatureValidation.validationStatus === 'PARTIAL' ? (
            <PenTool className="w-5 h-5 text-yellow-600 flex-shrink-0" />
          ) : (
            <XCircle className="w-5 h-5 text-red-600 flex-shrink-0" />
          )}
          <div className="flex-1">
            <p
              className={clsx(
                'text-sm font-medium',
                signatureValidation.validationStatus === 'SIGNED'
                  ? 'text-green-800'
                  : signatureValidation.validationStatus === 'PARTIAL'
                    ? 'text-yellow-800'
                    : 'text-red-800'
              )}
            >
              {signatureValidation.validationStatus === 'SIGNED'
                ? 'Document Signed'
                : signatureValidation.validationStatus === 'PARTIAL'
                  ? 'Low Confidence Signatures'
                  : 'No Signatures Detected'}
            </p>
            <p className="text-xs mt-0.5 text-gray-600">
              {signatureValidation.signatureCount > 0 ? (
                <>
                  {signatureValidation.highConfidenceCount} high-confidence,{' '}
                  {signatureValidation.lowConfidenceCount} low-confidence
                  {signatureValidation.pagesWithSignatures.length > 0 && (
                    <span className="ml-1">
                      on page{signatureValidation.pagesWithSignatures.length > 1 ? 's' : ''}{' '}
                      {signatureValidation.pagesWithSignatures.slice(0, 5).join(', ')}
                      {signatureValidation.pagesWithSignatures.length > 5 && '...'}
                    </span>
                  )}
                </>
              ) : (
                'Document may be unsigned - review required'
              )}
            </p>
          </div>
        </div>
      )}

      {/* Processing Metrics */}
      {(processingCost || processingTime) && (
        <div className="mx-4 mt-4">
          <ProcessingMetricsPanel
            processingCost={processingCost}
            processingTime={processingTime}
          />
        </div>
      )}

      {/* Extracted Sections */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {/* Promissory Note */}
        {data.promissoryNote && (
          <Section
            title="Promissory Note"
            icon={<DollarSign className="w-5 h-5 text-primary-600" />}
            isExpanded={expandedSections.has('promissoryNote')}
            onToggle={() => toggleSection('promissoryNote')}
            pageNumber={classification?.promissoryNote}
            onPageClick={onFieldClick}
          >
            <PromissoryNoteFields
              data={data.promissoryNote}
              onFieldClick={onFieldClick}
            />
          </Section>
        )}

        {/* Closing Disclosure */}
        {data.closingDisclosure && (
          <Section
            title="Closing Disclosure"
            icon={<FileText className="w-5 h-5 text-blue-600" />}
            isExpanded={expandedSections.has('closingDisclosure')}
            onToggle={() => toggleSection('closingDisclosure')}
            pageNumber={classification?.closingDisclosure}
            onPageClick={onFieldClick}
          >
            <ClosingDisclosureFields
              data={data.closingDisclosure}
              onFieldClick={onFieldClick}
            />
          </Section>
        )}

        {/* Form 1003 */}
        {data.form1003 && (
          <Section
            title="Uniform Residential Loan Application (1003)"
            icon={<User className="w-5 h-5 text-green-600" />}
            isExpanded={expandedSections.has('form1003')}
            onToggle={() => toggleSection('form1003')}
            pageNumber={classification?.form1003}
            onPageClick={onFieldClick}
          >
            <Form1003Fields data={data.form1003} onFieldClick={onFieldClick} />
          </Section>
        )}

        {/* Credit Agreement */}
        {data.creditAgreement && (
          <Section
            title="Credit Agreement"
            icon={<Briefcase className="w-5 h-5 text-purple-600" />}
            isExpanded={expandedSections.has('creditAgreement')}
            onToggle={() => toggleSection('creditAgreement')}
            onPageClick={onFieldClick}
          >
            <CreditAgreementFields data={data.creditAgreement} onFieldClick={onFieldClick} />
          </Section>
        )}

        {/* Loan Agreement (simple business/personal loans) */}
        {data.loanAgreement && (
          <Section
            title="Loan Agreement"
            icon={<DollarSign className="w-5 h-5 text-amber-600" />}
            isExpanded={expandedSections.has('loanAgreement')}
            onToggle={() => toggleSection('loanAgreement')}
            onPageClick={onFieldClick}
          >
            <LoanAgreementFields data={data.loanAgreement} onFieldClick={onFieldClick} />
          </Section>
        )}

        {/* Validation Notes */}
        {validation?.validationNotes && validation.validationNotes.length > 0 && (
          <div className="mt-4 p-3 bg-gray-50 rounded-lg">
            <h4 className="text-sm font-medium text-gray-700 flex items-center gap-2 mb-2">
              <Info className="w-4 h-4" />
              Validation Notes
            </h4>
            <ul className="space-y-1.5">
              {validation.validationNotes.map((note, i) => (
                <li
                  key={i}
                  className="text-xs text-gray-600 flex items-start gap-2"
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400 mt-1.5 flex-shrink-0" />
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

// Section component with collapsible functionality
interface SectionProps {
  title: string;
  icon: React.ReactNode;
  isExpanded: boolean;
  onToggle: () => void;
  pageNumber?: number;
  onPageClick?: (pageNumber: number, fieldName: string) => void;
  children: React.ReactNode;
}

function Section({
  title,
  icon,
  isExpanded,
  onToggle,
  pageNumber,
  onPageClick,
  children,
}: SectionProps) {
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          {icon}
          <span className="font-medium text-gray-900">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          {pageNumber && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onPageClick?.(pageNumber, title);
              }}
              className="text-xs text-primary-600 hover:text-primary-700 flex items-center gap-1"
            >
              Page {pageNumber}
              <ExternalLink className="w-3 h-3" />
            </button>
          )}
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-400" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-400" />
          )}
        </div>
      </button>
      {isExpanded && <div className="p-3 space-y-2">{children}</div>}
    </div>
  );
}

// Clickable field row
interface FieldRowProps {
  label: string;
  value: string | number | null | undefined;
  pageNumber?: number;
  confidence?: number;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}

function FieldRow({ label, value, pageNumber, confidence, onFieldClick }: FieldRowProps) {
  const displayValue = value ?? '-';
  const hasPageRef = pageNumber !== undefined && pageNumber > 0;

  return (
    <div
      className={clsx(
        'flex justify-between items-center py-2 px-2 rounded-md transition-colors',
        hasPageRef && 'cursor-pointer hover:bg-primary-50 group'
      )}
      onClick={() => hasPageRef && onFieldClick?.(pageNumber, label)}
    >
      <span className="text-sm text-gray-500">{label}</span>
      <div className="flex items-center gap-2">
        <span
          className={clsx(
            'text-sm font-medium',
            hasPageRef ? 'text-primary-700 group-hover:text-primary-800' : 'text-gray-900'
          )}
        >
          {displayValue}
        </span>
        {hasPageRef && (
          <ExternalLink className="w-3.5 h-3.5 text-primary-400 opacity-0 group-hover:opacity-100 transition-opacity" />
        )}
        {confidence !== undefined && (
          <span
            className={clsx(
              'text-xs px-1.5 py-0.5 rounded',
              confidence >= 0.9
                ? 'bg-green-100 text-green-700'
                : confidence >= 0.7
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-red-100 text-red-700'
            )}
          >
            {Math.round(confidence * 100)}%
          </span>
        )}
      </div>
    </div>
  );
}

// Helper to get value from ExtractedField or plain value
function getFieldValue<T>(field: ExtractedField<T> | T | undefined): T | undefined {
  if (field === undefined || field === null) return undefined;
  if (typeof field === 'object' && 'value' in field) {
    return field.value;
  }
  return field as T;
}

function getFieldPageNumber<T>(field: ExtractedField<T> | T | undefined): number | undefined {
  if (field === undefined || field === null) return undefined;
  if (typeof field === 'object' && 'pageNumber' in field) {
    return field.pageNumber;
  }
  return undefined;
}

function getFieldConfidence<T>(field: ExtractedField<T> | T | undefined): number | undefined {
  if (field === undefined || field === null) return undefined;
  if (typeof field === 'object' && 'confidence' in field) {
    return field.confidence;
  }
  return undefined;
}

// Promissory Note Fields
function PromissoryNoteFields({
  data,
  onFieldClick,
}: {
  data: PromissoryNoteData;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}) {
  const formatCurrency = (val: number | undefined) =>
    val !== undefined ? `$${val.toLocaleString()}` : undefined;
  const formatPercent = (val: number | undefined) =>
    val !== undefined ? `${(val * 100).toFixed(3)}%` : undefined;

  const defaultPage = data.pageNumber;

  return (
    <>
      <FieldRow
        label="Principal Amount"
        value={formatCurrency(getFieldValue(data.principalAmount))}
        pageNumber={getFieldPageNumber(data.principalAmount) ?? defaultPage}
        confidence={getFieldConfidence(data.principalAmount)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Interest Rate"
        value={formatPercent(getFieldValue(data.interestRate))}
        pageNumber={getFieldPageNumber(data.interestRate) ?? defaultPage}
        confidence={getFieldConfidence(data.interestRate)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Borrower"
        value={getFieldValue(data.borrowerName)}
        pageNumber={getFieldPageNumber(data.borrowerName) ?? defaultPage}
        confidence={getFieldConfidence(data.borrowerName)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Co-Borrower"
        value={getFieldValue(data.coBorrowerName)}
        pageNumber={getFieldPageNumber(data.coBorrowerName) ?? defaultPage}
        confidence={getFieldConfidence(data.coBorrowerName)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Monthly Payment"
        value={formatCurrency(getFieldValue(data.monthlyPayment))}
        pageNumber={getFieldPageNumber(data.monthlyPayment) ?? defaultPage}
        confidence={getFieldConfidence(data.monthlyPayment)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Maturity Date"
        value={getFieldValue(data.maturityDate)}
        pageNumber={getFieldPageNumber(data.maturityDate) ?? defaultPage}
        confidence={getFieldConfidence(data.maturityDate)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="First Payment Date"
        value={getFieldValue(data.firstPaymentDate)}
        pageNumber={getFieldPageNumber(data.firstPaymentDate) ?? defaultPage}
        confidence={getFieldConfidence(data.firstPaymentDate)}
        onFieldClick={onFieldClick}
      />
    </>
  );
}

// Closing Disclosure Fields
function ClosingDisclosureFields({
  data,
  onFieldClick,
}: {
  data: ClosingDisclosureData;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}) {
  const formatCurrency = (val: number | undefined) =>
    val !== undefined ? `$${val.toLocaleString()}` : undefined;

  const defaultPage = data.pageNumber;

  return (
    <>
      <FieldRow
        label="Loan Amount"
        value={formatCurrency(getFieldValue(data.loanAmount))}
        pageNumber={getFieldPageNumber(data.loanAmount) ?? defaultPage}
        confidence={getFieldConfidence(data.loanAmount)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Interest Rate"
        value={
          getFieldValue(data.interestRate) !== undefined
            ? `${(getFieldValue(data.interestRate)! * 100).toFixed(3)}%`
            : undefined
        }
        pageNumber={getFieldPageNumber(data.interestRate) ?? defaultPage}
        confidence={getFieldConfidence(data.interestRate)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Monthly P&I"
        value={formatCurrency(getFieldValue(data.monthlyPrincipalAndInterest))}
        pageNumber={getFieldPageNumber(data.monthlyPrincipalAndInterest) ?? defaultPage}
        confidence={getFieldConfidence(data.monthlyPrincipalAndInterest)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Total Monthly Payment"
        value={formatCurrency(getFieldValue(data.estimatedTotalMonthlyPayment))}
        pageNumber={getFieldPageNumber(data.estimatedTotalMonthlyPayment) ?? defaultPage}
        confidence={getFieldConfidence(data.estimatedTotalMonthlyPayment)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Closing Costs"
        value={formatCurrency(getFieldValue(data.closingCosts))}
        pageNumber={getFieldPageNumber(data.closingCosts) ?? defaultPage}
        confidence={getFieldConfidence(data.closingCosts)}
        onFieldClick={onFieldClick}
      />
      <FieldRow
        label="Cash to Close"
        value={formatCurrency(getFieldValue(data.cashToClose))}
        pageNumber={getFieldPageNumber(data.cashToClose) ?? defaultPage}
        confidence={getFieldConfidence(data.cashToClose)}
        onFieldClick={onFieldClick}
      />
    </>
  );
}

// Form 1003 Fields
function Form1003Fields({
  data,
  onFieldClick,
}: {
  data: Form1003Data;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}) {
  const defaultPage = data.pageNumber;

  return (
    <div className="space-y-4">
      {/* Borrower Info */}
      {data.borrowerInfo && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <User className="w-3.5 h-3.5" />
            Borrower Information
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-gray-100">
            <FieldRow
              label="Name"
              value={getFieldValue(data.borrowerInfo.name)}
              pageNumber={getFieldPageNumber(data.borrowerInfo.name) ?? data.borrowerInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.borrowerInfo.name)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Phone"
              value={getFieldValue(data.borrowerInfo.phone)}
              pageNumber={getFieldPageNumber(data.borrowerInfo.phone) ?? data.borrowerInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.borrowerInfo.phone)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Email"
              value={getFieldValue(data.borrowerInfo.email)}
              pageNumber={getFieldPageNumber(data.borrowerInfo.email) ?? data.borrowerInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.borrowerInfo.email)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Date of Birth"
              value={getFieldValue(data.borrowerInfo.dateOfBirth)}
              pageNumber={getFieldPageNumber(data.borrowerInfo.dateOfBirth) ?? data.borrowerInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.borrowerInfo.dateOfBirth)}
              onFieldClick={onFieldClick}
            />
          </div>
        </div>
      )}

      {/* Property Address */}
      {data.propertyAddress && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <Home className="w-3.5 h-3.5" />
            Property Address
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-gray-100">
            <FieldRow
              label="Street"
              value={getFieldValue(data.propertyAddress.street)}
              pageNumber={getFieldPageNumber(data.propertyAddress.street) ?? data.propertyAddress.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.propertyAddress.street)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="City"
              value={getFieldValue(data.propertyAddress.city)}
              pageNumber={getFieldPageNumber(data.propertyAddress.city) ?? data.propertyAddress.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.propertyAddress.city)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="State"
              value={getFieldValue(data.propertyAddress.state)}
              pageNumber={getFieldPageNumber(data.propertyAddress.state) ?? data.propertyAddress.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.propertyAddress.state)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="ZIP Code"
              value={getFieldValue(data.propertyAddress.zipCode)}
              pageNumber={getFieldPageNumber(data.propertyAddress.zipCode) ?? data.propertyAddress.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.propertyAddress.zipCode)}
              onFieldClick={onFieldClick}
            />
          </div>
        </div>
      )}

      {/* Employment Info */}
      {data.employmentInfo && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <Briefcase className="w-3.5 h-3.5" />
            Employment Information
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-gray-100">
            <FieldRow
              label="Employer"
              value={getFieldValue(data.employmentInfo.employerName)}
              pageNumber={getFieldPageNumber(data.employmentInfo.employerName) ?? data.employmentInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.employmentInfo.employerName)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Position"
              value={getFieldValue(data.employmentInfo.position)}
              pageNumber={getFieldPageNumber(data.employmentInfo.position) ?? data.employmentInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.employmentInfo.position)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Years Employed"
              value={
                getFieldValue(data.employmentInfo.yearsEmployed) !== undefined
                  ? `${getFieldValue(data.employmentInfo.yearsEmployed)} years`
                  : undefined
              }
              pageNumber={getFieldPageNumber(data.employmentInfo.yearsEmployed) ?? data.employmentInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.employmentInfo.yearsEmployed)}
              onFieldClick={onFieldClick}
            />
            <FieldRow
              label="Monthly Income"
              value={
                getFieldValue(data.employmentInfo.monthlyIncome) !== undefined
                  ? `$${getFieldValue(data.employmentInfo.monthlyIncome)!.toLocaleString()}`
                  : undefined
              }
              pageNumber={getFieldPageNumber(data.employmentInfo.monthlyIncome) ?? data.employmentInfo.pageNumber ?? defaultPage}
              confidence={getFieldConfidence(data.employmentInfo.monthlyIncome)}
              onFieldClick={onFieldClick}
            />
          </div>
        </div>
      )}
    </div>
  );
}

// Credit Agreement Fields
function CreditAgreementFields({
  data,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  onFieldClick: _onFieldClick,
}: {
  data: CreditAgreement;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}) {
  const formatCurrency = (val: number | undefined) =>
    val !== undefined ? `$${val.toLocaleString()}` : undefined;
  const formatPercent = (val: number | undefined) =>
    val !== undefined ? `${(val * 100).toFixed(3)}%` : undefined;

  return (
    <div className="space-y-4">
      {/* Agreement Info */}
      {data.agreementInfo && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Agreement Information
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            <FieldRow label="Document Type" value={data.agreementInfo.documentType} />
            <FieldRow label="Amendment Number" value={data.agreementInfo.amendmentNumber} />
            <FieldRow label="Agreement Date" value={data.agreementInfo.agreementDate} />
            <FieldRow label="Effective Date" value={data.agreementInfo.effectiveDate} />
            <FieldRow label="Maturity Date" value={data.agreementInfo.maturityDate} />
          </div>
        </div>
      )}

      {/* Parties */}
      {data.parties && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <User className="w-3.5 h-3.5" />
            Parties
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            <FieldRow label="Borrower" value={data.parties.borrower?.name} />
            {data.parties.coBorrowers && data.parties.coBorrowers.length > 0 && (
              <FieldRow label="Co-Borrower(s)" value={data.parties.coBorrowers.map(cb => typeof cb === 'string' ? cb : cb.name).join(', ')} />
            )}
            <FieldRow label="Administrative Agent" value={data.parties.administrativeAgent} />
            {data.parties.leadArrangers && data.parties.leadArrangers.length > 0 && (
              <FieldRow label="Lead Arrangers" value={data.parties.leadArrangers.join(', ')} />
            )}
            {data.parties.swinglineLender && (
              <FieldRow label="Swingline Lender" value={data.parties.swinglineLender} />
            )}
            {data.parties.lcIssuer && (
              <FieldRow label="L/C Issuer" value={data.parties.lcIssuer} />
            )}
            {data.parties.guarantors && data.parties.guarantors.length > 0 && (
              <FieldRow label="Guarantors" value={data.parties.guarantors.join(', ')} />
            )}
          </div>
        </div>
      )}

      {/* Facility Terms */}
      {data.facilityTerms && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Facility Terms
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            <FieldRow label="Max Revolving Credit" value={formatCurrency(data.facilityTerms.aggregateMaxRevolvingCreditAmount)} />
            <FieldRow label="Elected Revolving Commitment" value={formatCurrency(data.facilityTerms.aggregateElectedRevolvingCreditCommitment)} />
            {data.facilityTerms.lcCommitment && (
              <FieldRow label="LC Commitment" value={formatCurrency(data.facilityTerms.lcCommitment)} />
            )}
            {data.facilityTerms.lcSublimit && (
              <FieldRow label="LC Sublimit" value={formatCurrency(data.facilityTerms.lcSublimit)} />
            )}
            {data.facilityTerms.swinglineSublimit && (
              <FieldRow label="Swingline Sublimit" value={data.facilityTerms.swinglineSublimit} />
            )}
            {data.facilityTerms.termLoanACommitment && (
              <FieldRow label="Term Loan A Commitment" value={formatCurrency(data.facilityTerms.termLoanACommitment)} />
            )}
            {data.facilityTerms.termLoanBCommitment && (
              <FieldRow label="Term Loan B Commitment" value={formatCurrency(data.facilityTerms.termLoanBCommitment)} />
            )}
            {data.facilityTerms.termLoanBondRedemption && (
              <FieldRow label="Term Loan Bond Redemption" value={formatCurrency(data.facilityTerms.termLoanBondRedemption)} />
            )}
            {data.facilityTerms.termCommitment && (
              <FieldRow label="Total Term Commitment" value={formatCurrency(data.facilityTerms.termCommitment)} />
            )}
          </div>
        </div>
      )}

      {/* Facilities */}
      {data.facilities && data.facilities.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <Briefcase className="w-3.5 h-3.5" />
            Facilities
          </h4>
          <div className="space-y-2 pl-1 border-l-2 border-purple-100">
            {data.facilities.map((facility, idx) => (
              <div key={idx} className="bg-gray-50 rounded p-2">
                <FieldRow label="Type" value={facility.facilityType} />
                <FieldRow label="Commitment" value={formatCurrency(facility.commitmentAmount)} />
                <FieldRow label="Maturity" value={facility.maturityDate} />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Applicable Rates / Pricing Grid */}
      {data.applicableRates && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Applicable Rates / Pricing Grid
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            <FieldRow label="Reference Rate" value={data.applicableRates.referenceRate} />
            <FieldRow label="Pricing Basis" value={data.applicableRates.pricingBasis} />
            {data.applicableRates.floor !== undefined && (
              <FieldRow label="Floor Rate" value={formatPercent(data.applicableRates.floor)} />
            )}
          </div>
          {/* Pricing Tiers Table */}
          {data.applicableRates.tiers && data.applicableRates.tiers.length > 0 && (
            <div className="mt-2 overflow-x-auto">
              <table className="w-full text-xs border border-gray-200 rounded">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-2 py-1 text-left text-gray-600 font-medium">Level</th>
                    <th className="px-2 py-1 text-right text-gray-600 font-medium">Term SOFR Spread</th>
                    <th className="px-2 py-1 text-right text-gray-600 font-medium">ABR Spread</th>
                    <th className="px-2 py-1 text-right text-gray-600 font-medium">Unused Fee</th>
                  </tr>
                </thead>
                <tbody>
                  {data.applicableRates.tiers.map((tier, idx) => (
                    <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                      <td className="px-2 py-1 text-gray-900">{tier.level || tier.threshold}</td>
                      <td className="px-2 py-1 text-right text-gray-900">
                        {formatPercent(tier.termBenchmarkRFRSpread || tier.termSOFRSpread)}
                      </td>
                      <td className="px-2 py-1 text-right text-gray-900">{formatPercent(tier.abrSpread)}</td>
                      <td className="px-2 py-1 text-right text-gray-900">{formatPercent(tier.unusedCommitmentFeeRate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Payment Terms */}
      {data.paymentTerms && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Payment Terms
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            {data.paymentTerms.interestPeriodOptions && (
              <FieldRow label="Interest Period Options" value={data.paymentTerms.interestPeriodOptions.join(', ')} />
            )}
            {data.paymentTerms.interestPaymentDates && (
              <FieldRow label="Interest Payment Dates" value={data.paymentTerms.interestPaymentDates.join(', ')} />
            )}
          </div>
        </div>
      )}

      {/* Fees */}
      {data.fees && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Fees
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            {data.fees.commitmentFeeRate !== undefined && (
              <FieldRow label="Commitment Fee Rate" value={formatPercent(data.fees.commitmentFeeRate)} />
            )}
            {data.fees.lcFeeRate !== undefined && (
              <FieldRow label="LC Fee Rate" value={formatPercent(data.fees.lcFeeRate)} />
            )}
            {data.fees.frontingFeeRate !== undefined && (
              <FieldRow label="Fronting Fee Rate" value={formatPercent(data.fees.frontingFeeRate)} />
            )}
            {data.fees.agencyFee !== undefined && (
              <FieldRow label="Agency Fee" value={formatCurrency(data.fees.agencyFee)} />
            )}
          </div>
        </div>
      )}

      {/* Lender Commitments */}
      {data.lenderCommitments && data.lenderCommitments.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <User className="w-3.5 h-3.5" />
            Lender Commitments ({data.lenderCommitments.length} lenders)
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs border border-gray-200 rounded">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-2 py-1 text-left text-gray-600 font-medium">Lender</th>
                  <th className="px-2 py-1 text-right text-gray-600 font-medium">%</th>
                  <th className="px-2 py-1 text-right text-gray-600 font-medium">Revolving</th>
                </tr>
              </thead>
              <tbody>
                {data.lenderCommitments.map((lender, idx) => (
                  <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="px-2 py-1 text-gray-900 truncate max-w-[150px]" title={lender.lenderName}>
                      {lender.lenderName}
                    </td>
                    <td className="px-2 py-1 text-right text-gray-900">
                      {lender.applicablePercentage !== undefined ? `${(lender.applicablePercentage * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="px-2 py-1 text-right text-gray-900">
                      {formatCurrency(lender.revolvingCreditCommitment)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Covenants */}
      {data.covenants && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Covenants
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-purple-100">
            {data.covenants.fixedChargeCoverageRatio && (
              <>
                <FieldRow
                  label="Fixed Charge Coverage Ratio (Min)"
                  value={data.covenants.fixedChargeCoverageRatio.minimum?.toString()}
                />
                {data.covenants.fixedChargeCoverageRatio.testPeriod && (
                  <FieldRow label="Test Period" value={data.covenants.fixedChargeCoverageRatio.testPeriod} />
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Loan Agreement Fields (simple business/personal loans)
function LoanAgreementFields({
  data,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  onFieldClick: _onFieldClick,
}: {
  data: LoanAgreementData;
  onFieldClick?: (pageNumber: number, fieldName: string) => void;
}) {
  const formatCurrency = (val: number | undefined | null) =>
    val != null ? `$${val.toLocaleString()}` : undefined;
  const formatPercent = (val: number | undefined | null) =>
    val != null ? `${(val * 100).toFixed(3)}%` : undefined;

  return (
    <div className="space-y-4">
      {/* Document Info */}
      {data.documentInfo && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Document Information
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            <FieldRow label="Document Type" value={data.documentInfo.documentType} />
            {data.documentInfo.loanNumber && (
              <FieldRow label="Loan Number" value={data.documentInfo.loanNumber} />
            )}
            <FieldRow label="Agreement Date" value={data.documentInfo.agreementDate} />
            <FieldRow label="Effective Date" value={data.documentInfo.effectiveDate} />
            {data.documentInfo.closingDate && (
              <FieldRow label="Closing Date" value={data.documentInfo.closingDate} />
            )}
          </div>
        </div>
      )}

      {/* Loan Terms */}
      {data.loanTerms && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Loan Terms
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            <FieldRow label="Loan Amount" value={formatCurrency(data.loanTerms.loanAmount)} />
            {data.loanTerms.creditLimit && (
              <FieldRow label="Credit Limit" value={formatCurrency(data.loanTerms.creditLimit)} />
            )}
            <FieldRow label="Interest Rate" value={formatPercent(data.loanTerms.interestRate)} />
            {data.loanTerms.annualPercentageRate !== undefined && (
              <FieldRow label="APR" value={formatPercent(data.loanTerms.annualPercentageRate)} />
            )}
            <FieldRow
              label="Rate Type"
              value={data.loanTerms.isFixedRate === true ? 'Fixed' : data.loanTerms.isFixedRate === false ? 'Variable' : undefined}
            />
            <FieldRow label="Maturity Date" value={data.loanTerms.maturityDate} />
            {data.loanTerms.loanTermMonths != null && (
              <FieldRow label="Term (Months)" value={String(data.loanTerms.loanTermMonths)} />
            )}
          </div>
        </div>
      )}

      {/* Interest Details */}
      {data.interestDetails && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Interest Details
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data.interestDetails.rateType && (
              <FieldRow label="Rate Type" value={data.interestDetails.rateType} />
            )}
            {data.interestDetails.indexRate && (
              <FieldRow label="Index Rate" value={data.interestDetails.indexRate} />
            )}
            {data.interestDetails.margin != null && (
              <FieldRow label="Margin/Spread" value={formatPercent(data.interestDetails.margin)} />
            )}
            {data.interestDetails.floor != null && (
              <FieldRow label="Floor Rate" value={formatPercent(data.interestDetails.floor)} />
            )}
            {data.interestDetails.ceiling != null && (
              <FieldRow label="Ceiling Rate" value={formatPercent(data.interestDetails.ceiling)} />
            )}
            {data.interestDetails.defaultRate != null && (
              <FieldRow label="Default Rate" value={formatPercent(data.interestDetails.defaultRate)} />
            )}
            {data.interestDetails.dayCountBasis && (
              <FieldRow label="Day Count Basis" value={data.interestDetails.dayCountBasis} />
            )}
          </div>
        </div>
      )}

      {/* Parties */}
      {data.parties && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <User className="w-3.5 h-3.5" />
            Parties
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data.parties.borrower?.name && (
              <FieldRow label="Borrower" value={data.parties.borrower.name} />
            )}
            {data.parties.borrower?.address && (
              <FieldRow label="Borrower Address" value={data.parties.borrower.address} />
            )}
            {data.parties.lender?.name && (
              <FieldRow label="Lender" value={data.parties.lender.name} />
            )}
            {data.parties.lender?.address && (
              <FieldRow label="Lender Address" value={data.parties.lender.address} />
            )}
            {data.parties.guarantor?.name && (
              <FieldRow label="Guarantor" value={data.parties.guarantor.name} />
            )}
          </div>
        </div>
      )}

      {/* Payment Info */}
      {data.paymentInfo && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Payment Information
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data.paymentInfo.monthlyPayment != null && (
              <FieldRow label="Monthly Payment" value={formatCurrency(data.paymentInfo.monthlyPayment)} />
            )}
            {data.paymentInfo.firstPaymentDate && (
              <FieldRow label="First Payment Date" value={data.paymentInfo.firstPaymentDate} />
            )}
            {data.paymentInfo.paymentDueDay != null && (
              <FieldRow label="Payment Due Day" value={String(data.paymentInfo.paymentDueDay)} />
            )}
            {data.paymentInfo.paymentFrequency && (
              <FieldRow label="Payment Frequency" value={data.paymentInfo.paymentFrequency} />
            )}
            {data.paymentInfo.numberOfPayments != null && (
              <FieldRow label="Number of Payments" value={String(data.paymentInfo.numberOfPayments)} />
            )}
            {data.paymentInfo.balloonPayment != null && (
              <FieldRow label="Balloon Payment" value={formatCurrency(data.paymentInfo.balloonPayment)} />
            )}
          </div>
        </div>
      )}

      {/* Security */}
      {data.security && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <Home className="w-3.5 h-3.5" />
            Security/Collateral
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            <FieldRow
              label="Secured"
              value={data.security.isSecured === true ? 'Yes' : data.security.isSecured === false ? 'No' : undefined}
            />
            {data.security.collateralDescription && (
              <FieldRow label="Collateral" value={data.security.collateralDescription} />
            )}
            {data.security.propertyAddress && (
              <FieldRow label="Property Address" value={data.security.propertyAddress} />
            )}
          </div>
        </div>
      )}

      {/* Fees */}
      {data.fees && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <DollarSign className="w-3.5 h-3.5" />
            Fees
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data.fees.originationFee != null && (
              <FieldRow label="Origination Fee" value={formatCurrency(data.fees.originationFee)} />
            )}
            {data.fees.latePaymentFee != null && (
              <FieldRow label="Late Payment Fee" value={formatCurrency(data.fees.latePaymentFee)} />
            )}
            {data.fees.gracePeriodDays != null && (
              <FieldRow label="Grace Period (Days)" value={String(data.fees.gracePeriodDays)} />
            )}
            {data.fees.closingCosts != null && (
              <FieldRow label="Closing Costs" value={formatCurrency(data.fees.closingCosts)} />
            )}
            {data.fees.annualFee != null && (
              <FieldRow label="Annual Fee" value={formatCurrency(data.fees.annualFee)} />
            )}
          </div>
        </div>
      )}

      {/* Prepayment */}
      {data.prepayment && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Prepayment
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            <FieldRow
              label="Has Penalty"
              value={data.prepayment.hasPenalty === true ? 'Yes' : data.prepayment.hasPenalty === false ? 'No' : undefined}
            />
            {data.prepayment.penaltyTerms && (
              <FieldRow label="Penalty Terms" value={data.prepayment.penaltyTerms} />
            )}
          </div>
        </div>
      )}

      {/* Covenants */}
      {data.covenants && data.covenants.financialCovenants && data.covenants.financialCovenants.length > 0 && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            Financial Covenants
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data.covenants.financialCovenants.map((covenant, idx) => (
              <FieldRow key={idx} label={`Covenant ${idx + 1}`} value={covenant} />
            ))}
            {data.covenants.debtServiceCoverageRatio != null && (
              <FieldRow label="DSCR" value={String(data.covenants.debtServiceCoverageRatio)} />
            )}
            {data.covenants.currentRatio != null && (
              <FieldRow label="Current Ratio" value={String(data.covenants.currentRatio)} />
            )}
          </div>
        </div>
      )}

      {/* Extracted System Codes */}
      {data._extractedCodes && (
        <div>
          <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-2">
            <FileText className="w-3.5 h-3.5" />
            System Codes
          </h4>
          <div className="space-y-1 pl-1 border-l-2 border-amber-100">
            {data._extractedCodes.instrumentType && (
              <FieldRow label="Instrument Type" value={data._extractedCodes.instrumentType} />
            )}
            {data._extractedCodes.billingType && (
              <FieldRow label="Billing Type" value={data._extractedCodes.billingType} />
            )}
            {data._extractedCodes.billingFrequency && (
              <FieldRow label="Billing Frequency" value={data._extractedCodes.billingFrequency} />
            )}
            {data._extractedCodes.interestRateType && (
              <FieldRow label="Interest Rate Type" value={data._extractedCodes.interestRateType} />
            )}
            {data._extractedCodes.rateIndex && (
              <FieldRow label="Rate Index" value={data._extractedCodes.rateIndex} />
            )}
            {data._extractedCodes.rateCalculationMethod && (
              <FieldRow label="Rate Calculation" value={data._extractedCodes.rateCalculationMethod} />
            )}
            {data._extractedCodes.currency && (
              <FieldRow label="Currency" value={data._extractedCodes.currency} />
            )}
            {data._extractedCodes.prepaymentIndicator && (
              <FieldRow label="Prepayment" value={data._extractedCodes.prepaymentIndicator} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
