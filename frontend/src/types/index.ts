export interface Document {
  documentId: string;
  documentType: 'LOAN_PACKAGE' | 'CREDIT_AGREEMENT' | 'LOAN_AGREEMENT';
  status: ProcessingStatus;
  reviewStatus?: ReviewStatus;
  createdAt: string;
  updatedAt?: string;
  fileName?: string;
  totalPages?: number;
  pdfUrl?: string;
  extractedData?: LoanData | CreditAgreementData;
  data?: LoanData;
  validation?: ValidationResult;
  signatureValidation?: SignatureValidation;
  classification?: DocumentClassification;
  reviewedBy?: string;
  reviewedAt?: string;
  reviewNotes?: string;
  corrections?: Record<string, unknown>;
  version?: number;
  processingCost?: ProcessingCost;
  processingTime?: ProcessingTime;
}

// Processing cost breakdown for a document
export interface ProcessingCost {
  totalCost: number;
  currency: string;
  allCostsReal?: boolean; // True only if ALL cost components are from real measurements
  breakdown: {
    router: {
      model: string;
      inputTokens: number;
      outputTokens: number;
      cost: number;
      isReal?: boolean; // True = from Bedrock API, False = estimated
    };
    textract: {
      pages: number;
      costPerPage: number;
      cost: number;
      isReal?: boolean; // Always true - counted from extractions
    };
    normalizer: {
      model: string;
      inputTokens: number;
      outputTokens: number;
      cost: number;
      isReal?: boolean; // Always true - from Bedrock API in normalizer Lambda
    };
    // Optional AWS infrastructure costs
    stepFunctions?: {
      stateTransitions: number;
      costPerTransition: number;
      cost: number;
      isReal?: boolean; // True - deterministic based on workflow path
    };
    lambda?: {
      invocations: number;
      gbSeconds: number;
      memoryMb: number;
      estimatedDurationMs: number;
      invocationCost: number;
      computeCost: number;
      cost: number;
      isReal?: boolean; // False - duration is estimated
    };
  };
}

// Processing time breakdown for a document
export interface ProcessingTime {
  totalSeconds: number;
  totalSecondsIsReal?: boolean; // True if measured from uploadedAt to completedAt
  startedAt?: string;
  completedAt: string;
  note?: string; // Explains which values are real vs estimated
  breakdown: {
    router: {
      estimatedSeconds: number;
      description: string;
      isEstimated?: boolean; // True - phase breakdown is approximated
    };
    textract: {
      estimatedSeconds: number;
      pages: number;
      description: string;
      isEstimated?: boolean; // True - phase breakdown is approximated
    };
    normalizer: {
      estimatedSeconds: number;
      description: string;
      isEstimated?: boolean; // True - phase breakdown is approximated
    };
  };
}

// Signature validation for all document types
export type SignatureValidationStatus = 'SIGNED' | 'UNSIGNED' | 'PARTIAL';

export interface SignatureValidation {
  hasSignatures: boolean;
  signatureCount: number;
  highConfidenceCount: number;
  lowConfidenceCount: number;
  pagesWithSignatures: number[];
  validationStatus: SignatureValidationStatus;
  signatures: Array<{
    confidence: number;
    meetsThreshold: boolean;
    boundingBox?: {
      left: number;
      top: number;
      width: number;
      height: number;
    };
    sourcePage?: number;
    sourceSection?: string;
  }>;
}

export type ProcessingStatus =
  | 'PENDING'
  | 'CLASSIFIED'
  | 'EXTRACTING'
  | 'EXTRACTED'
  | 'NORMALIZING'
  | 'PROCESSED'
  | 'REPROCESSING'
  | 'FAILED'
  | 'SKIPPED';

export type ReviewStatus = 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';

// Tracks which page each document type was found on
export interface DocumentClassification {
  promissoryNote?: number;
  closingDisclosure?: number;
  form1003?: number;
  otherDocuments?: Array<{ type: string; pageNumber: number }>;
}

// Generic field with value and source page reference
export interface ExtractedField<T = string | number> {
  value: T;
  pageNumber?: number;
  confidence?: number;
  boundingBox?: BoundingBox;
}

export interface BoundingBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

export interface LoanData {
  promissoryNote?: PromissoryNoteData;
  closingDisclosure?: ClosingDisclosureData;
  form1003?: Form1003Data;
  creditAgreement?: CreditAgreement;
  loanAgreement?: LoanAgreementData;
}

export interface PromissoryNoteData {
  pageNumber?: number;
  interestRate?: ExtractedField<number>;
  principalAmount?: ExtractedField<number>;
  borrowerName?: ExtractedField<string>;
  coBorrowerName?: ExtractedField<string>;
  maturityDate?: ExtractedField<string>;
  monthlyPayment?: ExtractedField<number>;
  firstPaymentDate?: ExtractedField<string>;
}

export interface ClosingDisclosureData {
  pageNumber?: number;
  loanAmount?: ExtractedField<number>;
  interestRate?: ExtractedField<number>;
  monthlyPrincipalAndInterest?: ExtractedField<number>;
  estimatedTotalMonthlyPayment?: ExtractedField<number>;
  closingCosts?: ExtractedField<number>;
  cashToClose?: ExtractedField<number>;
  fees?: Array<{ name: string; amount: number; pageNumber?: number }>;
}

export interface Form1003Data {
  pageNumber?: number;
  borrowerInfo?: {
    pageNumber?: number;
    name?: ExtractedField<string>;
    ssn?: ExtractedField<string>;
    dateOfBirth?: ExtractedField<string>;
    phone?: ExtractedField<string>;
    email?: ExtractedField<string>;
  };
  propertyAddress?: {
    pageNumber?: number;
    street?: ExtractedField<string>;
    city?: ExtractedField<string>;
    state?: ExtractedField<string>;
    zipCode?: ExtractedField<string>;
  };
  employmentInfo?: {
    pageNumber?: number;
    employerName?: ExtractedField<string>;
    position?: ExtractedField<string>;
    yearsEmployed?: ExtractedField<number>;
    monthlyIncome?: ExtractedField<number>;
  };
}

// Loan Agreement (simple business/personal loans)
export interface LoanAgreementData {
  documentInfo?: {
    documentType?: string;
    loanNumber?: string;
    agreementDate?: string;
    effectiveDate?: string;
    closingDate?: string;
  };
  loanTerms?: {
    loanAmount?: number;
    creditLimit?: number;
    interestRate?: number;
    annualPercentageRate?: number;
    isFixedRate?: boolean;
    maturityDate?: string;
    loanTermMonths?: number;
  };
  interestDetails?: {
    rateType?: string;
    indexRate?: string;
    margin?: number;
    floor?: number;
    ceiling?: number;
    defaultRate?: number;
    dayCountBasis?: string;
  };
  paymentInfo?: {
    monthlyPayment?: number;
    firstPaymentDate?: string;
    paymentDueDay?: number;
    paymentFrequency?: string;
    numberOfPayments?: number;
    balloonPayment?: number;
  };
  parties?: {
    borrower?: {
      name?: string;
      address?: string;
    };
    guarantor?: {
      name?: string;
      address?: string;
    };
    lender?: {
      name?: string;
      address?: string;
    };
  };
  security?: {
    isSecured?: boolean;
    collateralDescription?: string;
    propertyAddress?: string;
  };
  fees?: {
    originationFee?: number;
    latePaymentFee?: number;
    gracePeriodDays?: number;
    closingCosts?: number;
    annualFee?: number;
  };
  prepayment?: {
    hasPenalty?: boolean;
    penaltyTerms?: string;
  };
  covenants?: {
    financialCovenants?: string[];
    debtServiceCoverageRatio?: number;
    currentRatio?: number;
  };
  repayment?: {
    schedule?: string;
    principalReductions?: string;
    interestOnlyPeriod?: string;
  };
  default?: {
    eventsOfDefault?: string[];
    remedies?: string[];
  };
  _extractedCodes?: {
    instrumentType?: string;
    interestRateType?: string;
    rateIndex?: string;
    rateCalculationMethod?: string;
    billingType?: string;
    billingFrequency?: string;
    prepaymentIndicator?: string;
    currency?: string;
  };
}

export interface ValidationResult {
  isValid: boolean;
  confidence: 'high' | 'medium' | 'low';
  crossReferenceChecks?: Array<{
    field1: string;
    field2: string;
    match: boolean;
    note?: string;
  }>;
  validationNotes?: string[];
  missingRequiredFields?: string[];
}

export interface Metrics {
  statusCounts: Record<string, number>;
  totalDocuments: number;
  recentDocuments: Document[];
}

export interface UploadResponse {
  documentId: string;
  uploadUrl: string;
  fields: Record<string, string>;  // Presigned POST fields
  key: string;
  expiresIn: number;
}

export interface AuditFile {
  key: string;
  lastModified: string;
  size: number;
}

export interface ProcessingStatusResponse {
  documentId: string;
  status: string;
  startDate?: string;
  stopDate?: string;
  executionArn?: string;
}

// Credit Agreement types
export interface CreditAgreementData {
  creditAgreement?: CreditAgreement;
}

export interface CreditAgreement {
  agreementInfo?: {
    documentType?: string;
    agreementDate?: string;
    effectiveDate?: string;
    maturityDate?: string;
    amendmentNumber?: string;
  };
  parties?: {
    borrower?: { name?: string; jurisdiction?: string };
    ultimateHoldings?: { name?: string; jurisdiction?: string };
    coBorrowers?: Array<{ name?: string; jurisdiction?: string }>;
    administrativeAgent?: string;
    leadArrangers?: string[];
    swinglineLender?: string;
    lcIssuer?: string;
    guarantors?: string[];
  };
  paymentTerms?: {
    interestPeriodOptions?: string[];
    interestPaymentDates?: string[];
  };
  facilities?: Array<{
    facilityType?: string;
    facilityName?: string;
    commitmentAmount?: number;
    maturityDate?: string;
  }>;
  facilityTerms?: {
    aggregateMaxRevolvingCreditAmount?: number;
    aggregateElectedRevolvingCreditCommitment?: number;
    lcCommitment?: number;
    lcSublimit?: number;
    swinglineSublimit?: string;
    termLoanACommitment?: number;
    termLoanBCommitment?: number;
    termLoanBondRedemption?: number;
    termCommitment?: number;
  };
  applicableRates?: {
    referenceRate?: string;
    floor?: number;
    pricingBasis?: string;
    tiers?: Array<{
      level?: string;
      threshold?: string;
      termBenchmarkRFRSpread?: number;
      termSOFRSpread?: number;
      applicableMargin?: number;
      abrSpread?: number;
      unusedCommitmentFeeRate?: number;
      lcFeeRate?: number;
    }>;
  };
  fees?: {
    commitmentFeeRate?: number;
    lcFeeRate?: number;
    frontingFeeRate?: number;
    agencyFee?: number;
  };
  covenants?: {
    fixedChargeCoverageRatio?: { minimum?: number; testPeriod?: string };
    otherCovenants?: string[];
  };
  lenderCommitments?: Array<{
    lenderName?: string;
    applicablePercentage?: number;
    termCommitment?: number;
    revolvingCreditCommitment?: number;
    electedRevolvingCreditCommitment?: number;
    maxRevolvingCreditAmount?: number;
  }>;
}

// Review workflow types
export interface ReviewQueueResponse {
  reviewStatus: ReviewStatus;
  documents: Document[];
  count: number;
}

export interface ReviewDocumentResponse {
  document: Document;
  pdfUrl?: string;
  reviewStatus?: ReviewStatus;
  extractedData?: LoanData | CreditAgreementData;
  validation?: ValidationResult;
  corrections?: Record<string, unknown>;
}

export interface ApproveRejectRequest {
  reviewedBy: string;
  notes?: string;
  reprocess?: boolean;
}

export interface CorrectFieldsRequest {
  corrections: Record<string, unknown>;
  correctedBy: string;
  revalidate?: boolean;
}

export interface ReviewActionResponse {
  documentId: string;
  reviewStatus: ReviewStatus;
  reviewedBy?: string;
  reviewedAt?: string;
  message: string;
  error?: string;
}
