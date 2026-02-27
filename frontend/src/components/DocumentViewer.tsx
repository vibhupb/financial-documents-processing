import { useState, useCallback } from 'react';
import { PanelLeftClose, PanelRightClose, Columns } from 'lucide-react';
import clsx from 'clsx';
import PDFViewer from './PDFViewer';
import ExtractedValuesPanel from './ExtractedValuesPanel';
import DataViewTabs, { type DataViewTab } from './DataViewTabs';
import DocumentTreeView from './DocumentTreeView';
import DocumentQA from './DocumentQA';
import RawJsonView from './RawJsonView';
import ExtractionTrigger from './ExtractionTrigger';
import ProcessingMetricsPanel from './ProcessingMetricsPanel';
import type { Document, LoanData } from '../types';

interface DocumentViewerProps {
  document: Document;
  pdfUrl: string;
  className?: string;
  reviewBar?: React.ReactNode;
}

type PanelLayout = 'split' | 'pdf-only' | 'data-only';

export default function DocumentViewer({
  document,
  pdfUrl,
  className,
  reviewBar,
}: DocumentViewerProps) {
  const [layout, setLayout] = useState<PanelLayout>('split');
  const [highlightedPage, setHighlightedPage] = useState<number | undefined>();
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [totalPages, setTotalPages] = useState<number>(0);

  // Determine default tab based on available data
  const hasTree = !!(document.pageIndexTree?.structure?.length);
  const hasExtractedData = !!(document.extractedData || document.data);
  const defaultTab: DataViewTab = hasExtractedData ? 'extracted' : hasTree ? 'summary' : 'extracted';
  const [activeTab, setActiveTab] = useState<DataViewTab>(defaultTab);

  // API base URL from env
  const apiBaseUrl = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL || '';

  // Handle field click from extracted values panel
  const handleFieldClick = useCallback((pageNumber: number, fieldName: string) => {
    console.log(`Navigating to page ${pageNumber} for field: ${fieldName}`);
    setHighlightedPage(pageNumber);

    // If in data-only view, switch to split view to show the PDF
    if (layout === 'data-only') {
      setLayout('split');
    }
  }, [layout]);

  // Handle page click from tree view or Q&A
  const handlePageClick = useCallback((pageNumber: number) => {
    setHighlightedPage(pageNumber);
    if (layout === 'data-only') {
      setLayout('split');
    }
  }, [layout]);

  // Handle page change from PDF viewer
  const handlePageChange = useCallback((page: number) => {
    setCurrentPage(page);
    if (highlightedPage && page !== highlightedPage) {
      setHighlightedPage(undefined);
    }
  }, [highlightedPage]);

  // Handle document load
  const handleDocumentLoad = useCallback((numPages: number) => {
    setTotalPages(numPages);
  }, []);

  // Determine what JSON to show in Raw JSON tab
  const rawJsonData = document.extractedData || document.data || document.pageIndexTree || null;

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Layout Toggle Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
        <div className="flex items-center gap-4">
          <h2 className="text-sm font-medium text-gray-700">
            {document.fileName || 'Document'}
            {totalPages > 0 && (
              <span className="text-gray-400 font-normal ml-2">
                ({totalPages} pages)
              </span>
            )}
          </h2>
        </div>

        <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
          <button
            onClick={() => setLayout('pdf-only')}
            className={clsx(
              'p-1.5 rounded transition-colors',
              layout === 'pdf-only'
                ? 'bg-white shadow text-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            )}
            title="PDF only"
          >
            <PanelRightClose className="w-4 h-4" />
          </button>
          <button
            onClick={() => setLayout('split')}
            className={clsx(
              'p-1.5 rounded transition-colors',
              layout === 'split'
                ? 'bg-white shadow text-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            )}
            title="Split view"
          >
            <Columns className="w-4 h-4" />
          </button>
          <button
            onClick={() => setLayout('data-only')}
            className={clsx(
              'p-1.5 rounded transition-colors',
              layout === 'data-only'
                ? 'bg-white shadow text-primary-600'
                : 'text-gray-500 hover:text-gray-700'
            )}
            title="Data only"
          >
            <PanelLeftClose className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* PDF Viewer (Left Panel) */}
        {(layout === 'split' || layout === 'pdf-only') && (
          <div
            className={clsx(
              'border-r border-gray-200 transition-all duration-300',
              layout === 'split' ? 'w-1/2' : 'w-full'
            )}
          >
            <PDFViewer
              url={pdfUrl}
              initialPage={1}
              highlightedPage={highlightedPage}
              onPageChange={handlePageChange}
              onDocumentLoad={handleDocumentLoad}
              className="h-full"
            />
          </div>
        )}

        {/* Right Panel: Tabs + Content */}
        {(layout === 'split' || layout === 'data-only') && (
          <div
            className={clsx(
              'flex flex-col transition-all duration-300 overflow-hidden',
              layout === 'split' ? 'w-1/2' : 'w-full'
            )}
          >
            {/* View Tabs */}
            <DataViewTabs
              activeTab={activeTab}
              onTabChange={setActiveTab}
              hasTree={hasTree}
              hasExtractedData={hasExtractedData}
            />

            {/* Tab Content */}
            <div className="flex-1 overflow-auto">
              {activeTab === 'summary' && (
                <div className="flex flex-col h-full">
                  <div className="flex-1 overflow-auto">
                    <DocumentTreeView
                      tree={document.pageIndexTree!}
                      onPageClick={handlePageClick}
                    />
                  </div>
                  {/* Q&A at bottom of summary tab */}
                  {hasTree && (
                    <DocumentQA
                      documentId={document.documentId}
                      apiBaseUrl={apiBaseUrl}
                      onPageClick={handlePageClick}
                    />
                  )}
                </div>
              )}

              {activeTab === 'extracted' && (
                hasExtractedData ? (
                  <ExtractedValuesPanel
                    data={(document.extractedData as LoanData) || document.data || null}
                    validation={document.validation}
                    signatureValidation={document.signatureValidation}
                    classification={document.classification}
                    processingCost={undefined}
                    processingTime={undefined}
                    onFieldClick={handleFieldClick}
                    className="h-full"
                  />
                ) : (
                  <ExtractionTrigger
                    documentId={document.documentId}
                    apiBaseUrl={apiBaseUrl}
                    onExtractionStarted={() => window.location.reload()}
                  />
                )
              )}

              {activeTab === 'json' && (
                <RawJsonView
                  data={rawJsonData}
                  label={document.extractedData ? 'Extracted Data' : 'PageIndex Tree'}
                />
              )}
            </div>

            {/* Processing Metrics — always visible, collapsed by default */}
            <ProcessingMetricsPanel
              processingCost={document.processingCost}
              processingTime={document.processingTime}
              defaultCollapsed
            />
          </div>
        )}
      </div>

      {/* Status Bar */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-t border-gray-200 text-xs text-gray-500">
        <div className="flex items-center gap-4">
          <span>
            Current Page: <strong className="text-gray-700">{currentPage}</strong> / {totalPages}
          </span>
          {highlightedPage && (
            <span className="text-primary-600">
              Highlighting page {highlightedPage}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <span>
            Status: <strong className="text-gray-700">{document.status}</strong>
          </span>
          {document.validation && (
            <span>
              Validation:{' '}
              <strong
                className={
                  document.validation.isValid ? 'text-green-600' : 'text-yellow-600'
                }
              >
                {document.validation.isValid ? 'Valid' : 'Review Required'}
              </strong>
            </span>
          )}
          {document.processingCost && (
            <span>
              Cost:{' '}
              <strong className="text-green-600">
                ${document.processingCost.totalCost.toFixed(4)}
              </strong>
            </span>
          )}
        </div>
      </div>

      {/* Review Bar (sticky footer) */}
      {reviewBar && (
        <div className="sticky bottom-0 z-10 flex-shrink-0">
          {reviewBar}
        </div>
      )}
    </div>
  );
}
