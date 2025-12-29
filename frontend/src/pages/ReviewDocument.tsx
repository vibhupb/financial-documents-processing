import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import type { Document, ReviewDocumentResponse, ValidationResult } from '../types';
import PDFViewer from '../components/PDFViewer';
import StatusBadge from '../components/StatusBadge';
import ProcessingMetricsPanel from '../components/ProcessingMetricsPanel';

export default function ReviewDocument() {
  const { documentId } = useParams<{ documentId: string }>();
  const navigate = useNavigate();

  const [document, setDocument] = useState<Document | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [reviewerName, setReviewerName] = useState('');
  const [notes, setNotes] = useState('');
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [showRawJson, setShowRawJson] = useState(false);

  useEffect(() => {
    if (documentId) {
      loadDocument();
    }
  }, [documentId]);

  async function loadDocument() {
    try {
      setLoading(true);
      setError(null);

      const result: ReviewDocumentResponse = await api.getDocumentForReview(documentId!);
      setDocument(result.document);
      setPdfUrl(result.pdfUrl || null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document');
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove() {
    if (!documentId || !reviewerName.trim()) {
      setError('Please enter your name to approve');
      return;
    }

    try {
      setActionLoading(true);
      setError(null);

      await api.approveDocument(documentId, {
        reviewedBy: reviewerName.trim(),
        notes: notes.trim() || undefined,
      });

      navigate('/review', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve document');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReject() {
    if (!documentId || !reviewerName.trim() || !notes.trim()) {
      setError('Please enter your name and rejection reason');
      return;
    }

    try {
      setActionLoading(true);
      setError(null);

      await api.rejectDocument(documentId, {
        reviewedBy: reviewerName.trim(),
        notes: notes.trim(),
        reprocess: false,
      });

      setShowRejectModal(false);
      navigate('/review', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reject document');
    } finally {
      setActionLoading(false);
    }
  }

  async function handleReprocess() {
    if (!documentId) return;

    try {
      setActionLoading(true);
      setError(null);

      await api.reprocessDocument(documentId);
      navigate('/review', { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reprocess document');
    } finally {
      setActionLoading(false);
    }
  }

  function renderValidation(validation: ValidationResult | undefined) {
    if (!validation) return null;

    return (
      <div className="bg-white shadow rounded-lg p-4 mb-4">
        <h3 className="text-lg font-medium text-gray-900 mb-3">Validation</h3>
        <div className="space-y-2">
          <div className="flex items-center">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                validation.isValid
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {validation.isValid ? 'Valid' : 'Invalid'}
            </span>
            <span
              className={`ml-2 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                validation.confidence === 'high'
                  ? 'bg-green-100 text-green-800'
                  : validation.confidence === 'medium'
                  ? 'bg-yellow-100 text-yellow-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {validation.confidence} confidence
            </span>
          </div>

          {validation.validationNotes && validation.validationNotes.length > 0 && (
            <div className="mt-2">
              <p className="text-sm font-medium text-gray-700">Notes:</p>
              <ul className="list-disc list-inside text-sm text-gray-600">
                {validation.validationNotes.map((note, idx) => (
                  <li key={idx}>{note}</li>
                ))}
              </ul>
            </div>
          )}

          {validation.missingRequiredFields &&
            validation.missingRequiredFields.length > 0 && (
              <div className="mt-2">
                <p className="text-sm font-medium text-red-700">Missing Fields:</p>
                <ul className="list-disc list-inside text-sm text-red-600">
                  {validation.missingRequiredFields.map((field, idx) => (
                    <li key={idx}>{field}</li>
                  ))}
                </ul>
              </div>
            )}
        </div>
      </div>
    );
  }

  function formatCurrency(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'N/A';
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  }

  function formatPercent(value: number | null | undefined): string {
    if (value === null || value === undefined) return 'N/A';
    return `${(value * 100).toFixed(2)}%`;
  }

  // Helper to check if an object has any non-null, non-empty values
  function hasNonNullValues(obj: Record<string, unknown> | null | undefined): boolean {
    if (!obj) return false;
    return Object.values(obj).some(v => {
      if (v === null || v === undefined) return false;
      if (typeof v === 'object' && !Array.isArray(v)) {
        return hasNonNullValues(v as Record<string, unknown>);
      }
      if (Array.isArray(v)) return v.length > 0;
      if (typeof v === 'string') return v.trim().length > 0;
      return true;
    });
  }

  function renderCreditAgreementData(ca: Record<string, unknown>) {
    const agreementInfo = ca.agreementInfo as Record<string, unknown> | undefined;
    const parties = ca.parties as Record<string, unknown> | undefined;
    const facilityTerms = ca.facilityTerms as Record<string, unknown> | undefined;
    const facilities = ca.facilities as Array<Record<string, unknown>> | undefined;
    const applicableRates = ca.applicableRates as Record<string, unknown> | undefined;
    const fees = ca.fees as Record<string, unknown> | undefined;
    const lenderCommitments = ca.lenderCommitments as Array<Record<string, unknown>> | undefined;
    const covenants = ca.covenants as Record<string, unknown> | undefined;
    const paymentTerms = ca.paymentTerms as Record<string, unknown> | undefined;

    return (
      <div className="space-y-4">
        {/* Agreement Information */}
        {hasNonNullValues(agreementInfo) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Agreement Information
            </h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {agreementInfo!.documentType != null && (
                <>
                  <dt className="text-gray-500">Document Type</dt>
                  <dd className="font-medium text-gray-900">{String(agreementInfo!.documentType)}</dd>
                </>
              )}
              {agreementInfo!.amendmentNumber != null && (
                <>
                  <dt className="text-gray-500">Amendment #</dt>
                  <dd className="font-medium text-gray-900">{String(agreementInfo!.amendmentNumber)}</dd>
                </>
              )}
              {agreementInfo!.agreementDate != null && (
                <>
                  <dt className="text-gray-500">Agreement Date</dt>
                  <dd className="font-medium text-gray-900">{String(agreementInfo!.agreementDate)}</dd>
                </>
              )}
              {agreementInfo!.effectiveDate != null && (
                <>
                  <dt className="text-gray-500">Effective Date</dt>
                  <dd className="font-medium text-gray-900">{String(agreementInfo!.effectiveDate)}</dd>
                </>
              )}
              {agreementInfo!.maturityDate != null && (
                <>
                  <dt className="text-gray-500">Maturity Date</dt>
                  <dd className="font-medium text-gray-900">{String(agreementInfo!.maturityDate)}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        {/* Parties */}
        {hasNonNullValues(parties) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Parties
            </h4>
            <dl className="grid grid-cols-1 gap-y-1 text-xs">
              {(parties!.borrower as Record<string, unknown>)?.name != null && (
                <>
                  <dt className="text-gray-500">Borrower</dt>
                  <dd className="font-medium text-gray-900">{String((parties!.borrower as Record<string, unknown>).name)}</dd>
                </>
              )}
              {parties!.administrativeAgent != null && (
                <>
                  <dt className="text-gray-500 mt-1">Administrative Agent</dt>
                  <dd className="font-medium text-gray-900">{String(parties!.administrativeAgent)}</dd>
                </>
              )}
              {Array.isArray(parties!.leadArrangers) && parties!.leadArrangers.length > 0 && (
                <>
                  <dt className="text-gray-500 mt-1">Lead Arrangers</dt>
                  <dd className="font-medium text-gray-900">{(parties!.leadArrangers as string[]).join(', ')}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        {/* Facility Terms */}
        {hasNonNullValues(facilityTerms) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Facility Terms
            </h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {facilityTerms!.aggregateMaxRevolvingCreditAmount != null && (
                <>
                  <dt className="text-gray-500">Max Revolving Credit</dt>
                  <dd className="font-medium text-green-700">{formatCurrency(facilityTerms!.aggregateMaxRevolvingCreditAmount as number)}</dd>
                </>
              )}
              {facilityTerms!.aggregateElectedRevolvingCreditCommitment != null && (
                <>
                  <dt className="text-gray-500">Elected Commitment</dt>
                  <dd className="font-medium text-green-700">{formatCurrency(facilityTerms!.aggregateElectedRevolvingCreditCommitment as number)}</dd>
                </>
              )}
              {facilityTerms!.lcCommitment != null && (
                <>
                  <dt className="text-gray-500">LC Commitment</dt>
                  <dd className="font-medium text-gray-900">{formatCurrency(facilityTerms!.lcCommitment as number)}</dd>
                </>
              )}
              {facilityTerms!.swinglineSublimit != null && (
                <>
                  <dt className="text-gray-500">Swingline Sublimit</dt>
                  <dd className="font-medium text-gray-900">{typeof facilityTerms!.swinglineSublimit === 'number' ? formatCurrency(facilityTerms!.swinglineSublimit) : String(facilityTerms!.swinglineSublimit)}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        {/* Facilities */}
        {facilities && facilities.length > 0 && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Facilities
            </h4>
            <div className="space-y-2">
              {facilities.map((facility, idx) => (
                <div key={idx} className="bg-gray-50 rounded p-2">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                    {facility.facilityType != null && (
                      <>
                        <dt className="text-gray-500">Type</dt>
                        <dd className="font-medium text-gray-900">{String(facility.facilityType)}</dd>
                      </>
                    )}
                    {facility.commitmentAmount != null && (
                      <>
                        <dt className="text-gray-500">Commitment</dt>
                        <dd className="font-medium text-green-700">{formatCurrency(facility.commitmentAmount as number)}</dd>
                      </>
                    )}
                    {facility.maturityDate != null && (
                      <>
                        <dt className="text-gray-500">Maturity</dt>
                        <dd className="font-medium text-gray-900">{String(facility.maturityDate)}</dd>
                      </>
                    )}
                  </dl>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Applicable Rates */}
        {hasNonNullValues(applicableRates) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Applicable Rates / Pricing Grid
            </h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-2">
              {applicableRates!.referenceRate != null && (
                <>
                  <dt className="text-gray-500">Reference Rate</dt>
                  <dd className="font-medium text-gray-900">{String(applicableRates!.referenceRate)}</dd>
                </>
              )}
              {applicableRates!.pricingBasis != null && (
                <>
                  <dt className="text-gray-500">Pricing Basis</dt>
                  <dd className="font-medium text-gray-900">{String(applicableRates!.pricingBasis)}</dd>
                </>
              )}
              {applicableRates!.floor !== null && applicableRates!.floor !== undefined && (
                <>
                  <dt className="text-gray-500">Floor</dt>
                  <dd className="font-medium text-gray-900">{formatPercent(applicableRates!.floor as number)}</dd>
                </>
              )}
            </dl>
            {/* Pricing Tiers Table */}
            {Array.isArray(applicableRates!.tiers) && (applicableRates!.tiers as Array<Record<string, unknown>>).length > 0 && (
              <div className="overflow-x-auto mt-2">
                <table className="min-w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50">
                      <th className="text-left text-gray-500 py-1 px-2">Level</th>
                      <th className="text-right text-gray-500 py-1 px-2">Term SOFR Spread</th>
                      <th className="text-right text-gray-500 py-1 px-2">ABR Spread</th>
                      <th className="text-right text-gray-500 py-1 px-2">Unused Fee</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(applicableRates!.tiers as Array<Record<string, unknown>>).map((tier, idx) => (
                      <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="py-1 px-2 text-gray-900">{tier.level != null ? String(tier.level) : (tier.threshold != null ? String(tier.threshold) : '—')}</td>
                        <td className="py-1 px-2 text-right text-gray-900">
                          {tier.termBenchmarkRFRSpread != null ? formatPercent(tier.termBenchmarkRFRSpread as number) : (tier.termSOFRSpread != null ? formatPercent(tier.termSOFRSpread as number) : '—')}
                        </td>
                        <td className="py-1 px-2 text-right text-gray-900">{tier.abrSpread != null ? formatPercent(tier.abrSpread as number) : '—'}</td>
                        <td className="py-1 px-2 text-right text-gray-900">{tier.unusedCommitmentFeeRate != null ? formatPercent(tier.unusedCommitmentFeeRate as number) : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Payment Terms */}
        {hasNonNullValues(paymentTerms) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Payment Terms
            </h4>
            <dl className="grid grid-cols-1 gap-y-1 text-xs">
              {Array.isArray(paymentTerms!.interestPeriodOptions) && (paymentTerms!.interestPeriodOptions as string[]).length > 0 && (
                <>
                  <dt className="text-gray-500">Interest Period Options</dt>
                  <dd className="font-medium text-gray-900">{(paymentTerms!.interestPeriodOptions as string[]).join(', ')}</dd>
                </>
              )}
              {Array.isArray(paymentTerms!.interestPaymentDates) && (paymentTerms!.interestPaymentDates as string[]).length > 0 && (
                <>
                  <dt className="text-gray-500 mt-1">Interest Payment Dates</dt>
                  <dd className="font-medium text-gray-900">{(paymentTerms!.interestPaymentDates as string[]).join(', ')}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        {/* Fees */}
        {hasNonNullValues(fees) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Fees
            </h4>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
              {fees!.commitmentFeeRate != null && (
                <>
                  <dt className="text-gray-500">Commitment Fee</dt>
                  <dd className="font-medium text-gray-900">{formatPercent(fees!.commitmentFeeRate as number)}</dd>
                </>
              )}
              {fees!.lcFeeRate != null && (
                <>
                  <dt className="text-gray-500">LC Fee</dt>
                  <dd className="font-medium text-gray-900">{formatPercent(fees!.lcFeeRate as number)}</dd>
                </>
              )}
              {fees!.frontingFeeRate != null && (
                <>
                  <dt className="text-gray-500">Fronting Fee</dt>
                  <dd className="font-medium text-gray-900">{formatPercent(fees!.frontingFeeRate as number)}</dd>
                </>
              )}
            </dl>
          </div>
        )}

        {/* Lender Commitments */}
        {lenderCommitments && lenderCommitments.length > 0 && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Lender Commitments ({lenderCommitments.length} lenders)
            </h4>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left text-gray-500 py-1 pr-2">Lender</th>
                    <th className="text-right text-gray-500 py-1 px-2">%</th>
                    <th className="text-right text-gray-500 py-1 pl-2">Commitment</th>
                  </tr>
                </thead>
                <tbody>
                  {lenderCommitments.map((lender, idx) => (
                    <tr key={idx} className="border-b border-gray-100">
                      <td className="py-1 pr-2 font-medium text-gray-900">{lender.lenderName != null ? String(lender.lenderName) : '—'}</td>
                      <td className="py-1 px-2 text-right text-gray-700">{lender.applicablePercentage != null ? formatPercent(lender.applicablePercentage as number) : '—'}</td>
                      <td className="py-1 pl-2 text-right text-green-700">{lender.revolvingCreditCommitment != null ? formatCurrency(lender.revolvingCreditCommitment as number) : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Covenants */}
        {hasNonNullValues(covenants) && (
          <div className="border border-gray-200 rounded-lg p-3">
            <h4 className="text-sm font-semibold text-indigo-700 mb-2 border-b border-gray-100 pb-1">
              Financial Covenants
            </h4>
            <dl className="grid grid-cols-1 gap-y-1 text-xs">
              {(covenants!.fixedChargeCoverageRatio as Record<string, unknown>)?.minimum != null && (
                <>
                  <dt className="text-gray-500">Fixed Charge Coverage Ratio</dt>
                  <dd className="font-medium text-gray-900">
                    Min: {String((covenants!.fixedChargeCoverageRatio as Record<string, unknown>).minimum)}
                    {(covenants!.fixedChargeCoverageRatio as Record<string, unknown>).testPeriod != null &&
                      ` (${String((covenants!.fixedChargeCoverageRatio as Record<string, unknown>).testPeriod)})`}
                  </dd>
                </>
              )}
              {Array.isArray(covenants!.otherCovenants) && covenants!.otherCovenants.length > 0 && (
                <>
                  <dt className="text-gray-500 mt-1">Other Covenants</dt>
                  <dd className="font-medium text-gray-900">{(covenants!.otherCovenants as string[]).join(', ')}</dd>
                </>
              )}
            </dl>
          </div>
        )}
      </div>
    );
  }

  function renderExtractedData(data: Record<string, unknown> | undefined) {
    if (!data) return null;

    // Check if this is Credit Agreement data
    const creditAgreement = data.creditAgreement as Record<string, unknown> | undefined;
    const hasFormattedView = !!creditAgreement;

    return (
      <div className="bg-white shadow rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-lg font-medium text-gray-900">Extracted Data</h3>
          {hasFormattedView && (
            <div className="flex rounded-md shadow-sm">
              <button
                onClick={() => setShowRawJson(false)}
                className={`px-3 py-1 text-sm font-medium rounded-l-md border ${
                  !showRawJson
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Formatted
              </button>
              <button
                onClick={() => setShowRawJson(true)}
                className={`px-3 py-1 text-sm font-medium rounded-r-md border-t border-r border-b ${
                  showRawJson
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                }`}
              >
                Raw JSON
              </button>
            </div>
          )}
        </div>
        <div className="max-h-[500px] overflow-y-auto">
          {showRawJson || !hasFormattedView ? (
            <pre className="text-xs text-gray-700 whitespace-pre-wrap bg-gray-50 p-3 rounded">
              {JSON.stringify(data, null, 2)}
            </pre>
          ) : (
            renderCreditAgreementData(creditAgreement!)
          )}
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  if (error && !document) {
    return (
      <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
        {error}
      </div>
    );
  }

  if (!document) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Document not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => navigate('/review')}
              className="text-gray-500 hover:text-gray-700"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
            </button>
            <h1 className="text-2xl font-semibold text-gray-900">
              Review Document
            </h1>
          </div>
          <p className="mt-1 text-sm text-gray-500">
            Document ID: {document.documentId}
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <StatusBadge status={document.status} />
          {document.reviewStatus && (
            <span
              className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                document.reviewStatus === 'APPROVED'
                  ? 'bg-green-100 text-green-800'
                  : document.reviewStatus === 'REJECTED'
                  ? 'bg-red-100 text-red-800'
                  : 'bg-yellow-100 text-yellow-800'
              }`}
            >
              {document.reviewStatus.replace('_', ' ')}
            </span>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Main content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Viewer */}
        <div className="bg-white shadow rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            <h2 className="text-lg font-medium text-gray-900">Document</h2>
          </div>
          <div className="h-[600px]">
            {pdfUrl ? (
              <PDFViewer url={pdfUrl} fileName={document.fileName} />
            ) : (
              <div className="flex items-center justify-center h-full text-gray-500">
                Document not available
              </div>
            )}
          </div>
        </div>

        {/* Extracted Data & Actions */}
        <div className="space-y-4">
          {/* Document Info */}
          <div className="bg-white shadow rounded-lg p-4">
            <h3 className="text-lg font-medium text-gray-900 mb-3">
              Document Information
            </h3>
            <dl className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <dt className="text-gray-500">Type</dt>
                <dd className="font-medium text-gray-900">
                  {document.documentType === 'CREDIT_AGREEMENT'
                    ? 'Credit Agreement'
                    : 'Loan Package'}
                </dd>
              </div>
              <div>
                <dt className="text-gray-500">Status</dt>
                <dd className="font-medium text-gray-900">{document.status}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Created</dt>
                <dd className="font-medium text-gray-900">
                  {new Date(document.createdAt).toLocaleDateString()}
                </dd>
              </div>
              {document.totalPages && (
                <div>
                  <dt className="text-gray-500">Pages</dt>
                  <dd className="font-medium text-gray-900">{document.totalPages}</dd>
                </div>
              )}
            </dl>
          </div>

          {/* Validation */}
          {renderValidation(document.validation)}

          {/* Extracted Data */}
          {renderExtractedData(document.extractedData as Record<string, unknown>)}

          {/* Processing Metrics (Cost & Time) */}
          <ProcessingMetricsPanel
            processingCost={document.processingCost}
            processingTime={document.processingTime}
          />

          {/* Review Actions */}
          {document.reviewStatus === 'PENDING_REVIEW' && (
            <div className="bg-white shadow rounded-lg p-4">
              <h3 className="text-lg font-medium text-gray-900 mb-3">
                Review Actions
              </h3>

              <div className="space-y-4">
                <div>
                  <label
                    htmlFor="reviewerName"
                    className="block text-sm font-medium text-gray-700"
                  >
                    Your Name
                  </label>
                  <input
                    type="text"
                    id="reviewerName"
                    value={reviewerName}
                    onChange={(e) => setReviewerName(e.target.value)}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                    placeholder="Enter your name"
                  />
                </div>

                <div>
                  <label
                    htmlFor="notes"
                    className="block text-sm font-medium text-gray-700"
                  >
                    Notes (required for rejection)
                  </label>
                  <textarea
                    id="notes"
                    rows={3}
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                    placeholder="Add any notes..."
                  />
                </div>

                <div className="flex space-x-3">
                  <button
                    onClick={handleApprove}
                    disabled={actionLoading || !reviewerName.trim()}
                    className="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {actionLoading ? 'Processing...' : 'Approve'}
                  </button>
                  <button
                    onClick={() => setShowRejectModal(true)}
                    disabled={actionLoading}
                    className="flex-1 inline-flex justify-center items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Reject
                  </button>
                  <button
                    onClick={handleReprocess}
                    disabled={actionLoading}
                    className="inline-flex justify-center items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md shadow-sm text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Reprocess
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Previous Review Info */}
          {document.reviewedBy && (
            <div className="bg-gray-50 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-2">
                Previous Review
              </h3>
              <p className="text-sm text-gray-600">
                Reviewed by <strong>{document.reviewedBy}</strong>
                {document.reviewedAt && (
                  <span>
                    {' '}
                    on {new Date(document.reviewedAt).toLocaleDateString()}
                  </span>
                )}
              </p>
              {document.reviewNotes && (
                <p className="mt-2 text-sm text-gray-600 italic">
                  "{document.reviewNotes}"
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-medium text-gray-900 mb-4">
              Reject Document
            </h3>
            <p className="text-sm text-gray-500 mb-4">
              Please provide a reason for rejection. This will be recorded in the
              audit trail.
            </p>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Your Name
                </label>
                <input
                  type="text"
                  value={reviewerName}
                  onChange={(e) => setReviewerName(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">
                  Rejection Reason *
                </label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm py-2 px-3 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                  placeholder="Explain why this document is being rejected..."
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end space-x-3">
              <button
                onClick={() => setShowRejectModal(false)}
                className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleReject}
                disabled={actionLoading || !reviewerName.trim() || !notes.trim()}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {actionLoading ? 'Rejecting...' : 'Reject Document'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
