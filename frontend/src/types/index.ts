export interface Document {
  documentId: string;
  documentType: 'LOAN_PACKAGE' | 'CREDIT_AGREEMENT';
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
  breakdown: {
    router: {
      model: string;
      inputTokens: number;
      outputTokens: number;
      cost: number;
    };
    textract: {
      pages: number;
      costPerPage: number;
      cost: number;
    };
    normalizer: {
      model: string;
      inputTokens: number;
      outputTokens: number;
      cost: number;
    };
    // Optional AWS infrastructure costs
    stepFunctions?: {
      stateTransitions: number;
      costPerTransition: number;
      cost: number;
    };
    lambda?: {
      invocations: number;
      gbSeconds: number;
      memoryMb: number;
      estimatedDurationMs: number;
      invocationCost: number;
      computeCost: number;
      cost: number;
    };
  };
}

// Processing time breakdown for a document
export interface ProcessingTime {
  totalSeconds: number;
  startedAt?: string;
  completedAt: string;
  breakdown: {
    router: {
      estimatedSeconds: number;
      description: string;
    };
    textract: {
      estimatedSeconds: number;
      pages: number;
      description: string;
    };
    normalizer: {
      estimatedSeconds: number;
      description: string;
    };
  };
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
