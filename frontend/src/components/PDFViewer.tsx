import { useState, useRef, useEffect, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCw,
  Download,
  Maximize2,
  Minimize2,
  ExternalLink,
  Image as ImageIcon,
  File,
} from 'lucide-react';
import clsx from 'clsx';

// Configure PDF.js worker - use unpkg with .js extension (not .mjs)
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.js`;

// Supported file types
type FileType = 'pdf' | 'image' | 'unknown';

// Detect file type from URL or filename
function detectFileType(url: string, fileName?: string): FileType {
  const source = fileName || url;
  const lowerSource = source.toLowerCase();
  const urlPath = lowerSource.split('?')[0];

  // PDF
  if (urlPath.endsWith('.pdf') || lowerSource.includes('content-type=application/pdf')) {
    return 'pdf';
  }

  // Images
  if (
    urlPath.endsWith('.jpg') ||
    urlPath.endsWith('.jpeg') ||
    urlPath.endsWith('.png') ||
    urlPath.endsWith('.gif') ||
    urlPath.endsWith('.webp') ||
    urlPath.endsWith('.tiff') ||
    urlPath.endsWith('.bmp') ||
    lowerSource.includes('content-type=image/')
  ) {
    return 'image';
  }

  // Default to PDF for financial documents (most common case)
  if (!urlPath.includes('.') || urlPath.endsWith('/')) {
    return 'pdf';
  }

  return 'unknown';
}

interface PDFViewerProps {
  url: string;
  fileName?: string;
  className?: string;
  initialPage?: number;
  highlightedPage?: number;
  onPageChange?: (pageNumber: number) => void;
  onDocumentLoad?: (numPages: number) => void;
}

export default function PDFViewer({
  url,
  fileName,
  className,
  initialPage = 1,
  highlightedPage,
  onPageChange,
  onDocumentLoad,
}: PDFViewerProps) {
  const [numPages, setNumPages] = useState<number>(0);
  const [currentPage, setCurrentPage] = useState<number>(initialPage);
  const [scale, setScale] = useState<number>(1.0);
  const [rotation, setRotation] = useState<number>(0);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Image-specific state
  const [imageError, setImageError] = useState<boolean>(false);
  const [imageLoading, setImageLoading] = useState<boolean>(true);

  const containerRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Detect file type
  const fileType = detectFileType(url, fileName);

  // Handle document load
  const onDocumentLoadSuccess = useCallback(
    ({ numPages }: { numPages: number }) => {
      setNumPages(numPages);
      setError(null);
      onDocumentLoad?.(numPages);
    },
    [onDocumentLoad]
  );

  const [retryCount, setRetryCount] = useState<number>(0);

  const onDocumentLoadError = useCallback((error: Error) => {
    console.error('PDF load error:', error);
    setError(`Failed to load PDF: ${error.message || 'Unknown error'}`);
  }, []);

  const retryLoad = useCallback(() => {
    setError(null);
    setRetryCount(c => c + 1);
  }, []);

  // Navigation functions
  const goToPage = useCallback(
    (page: number) => {
      const targetPage = Math.max(1, Math.min(page, numPages));
      setCurrentPage(targetPage);
      onPageChange?.(targetPage);

      // Scroll to the page
      const pageElement = pageRefs.current.get(targetPage);
      if (pageElement) {
        pageElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    },
    [numPages, onPageChange]
  );

  const nextPage = useCallback(() => goToPage(currentPage + 1), [currentPage, goToPage]);
  const prevPage = useCallback(() => goToPage(currentPage - 1), [currentPage, goToPage]);

  // Zoom functions
  const zoomIn = useCallback(() => setScale((s) => Math.min(s + 0.25, 3)), []);
  const zoomOut = useCallback(() => setScale((s) => Math.max(s - 0.25, 0.5)), []);
  const resetZoom = useCallback(() => setScale(1), []);

  // Rotation
  const rotate = useCallback(() => setRotation((r) => (r + 90) % 360), []);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!isFullscreen) {
      containerRef.current?.requestFullscreen?.();
    } else {
      document.exitFullscreen?.();
    }
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // Listen for fullscreen changes
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
  }, []);

  // Scroll to highlighted page when it changes
  useEffect(() => {
    if (highlightedPage && highlightedPage !== currentPage) {
      goToPage(highlightedPage);
    }
  }, [highlightedPage, currentPage, goToPage]);

  // Handle keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'PageDown') {
        nextPage();
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        prevPage();
      } else if (e.key === '+' || e.key === '=') {
        zoomIn();
      } else if (e.key === '-') {
        zoomOut();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [nextPage, prevPage, zoomIn, zoomOut]);

  // Track visible page during scroll
  const handleScroll = useCallback(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;
    const containerRect = container.getBoundingClientRect();
    const containerCenter = containerRect.top + containerRect.height / 2;

    let closestPage = currentPage;
    let closestDistance = Infinity;

    pageRefs.current.forEach((element, pageNum) => {
      const rect = element.getBoundingClientRect();
      const pageCenter = rect.top + rect.height / 2;
      const distance = Math.abs(pageCenter - containerCenter);

      if (distance < closestDistance) {
        closestDistance = distance;
        closestPage = pageNum;
      }
    });

    if (closestPage !== currentPage) {
      setCurrentPage(closestPage);
      onPageChange?.(closestPage);
    }
  }, [currentPage, onPageChange]);

  // Image Viewer
  if (fileType === 'image' && !imageError) {
    return (
      <div
        ref={containerRef}
        className={clsx(
          'flex flex-col h-full bg-gray-100 rounded-lg overflow-hidden',
          isFullscreen && 'fixed inset-0 z-50',
          className
        )}
      >
        {/* Image Toolbar */}
        <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <ImageIcon className="w-4 h-4" />
            <span>Image Preview</span>
          </div>
          <div className="flex items-center gap-1">
            <button
              onClick={zoomOut}
              disabled={scale <= 0.25}
              className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"
              title="Zoom out"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <button
              onClick={resetZoom}
              className="px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded"
            >
              {Math.round(scale * 100)}%
            </button>
            <button
              onClick={zoomIn}
              disabled={scale >= 3}
              className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"
              title="Zoom in"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <div className="w-px h-5 bg-gray-200 mx-2" />
            <a
              href={url}
              download={fileName}
              className="p-1.5 rounded hover:bg-gray-100"
              title="Download"
            >
              <Download className="w-4 h-4" />
            </a>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-1.5 rounded hover:bg-gray-100"
              title="Open in new tab"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Image Content */}
        <div className="flex-1 overflow-auto p-4 flex items-center justify-center relative">
          {imageLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
            </div>
          )}
          <img
            src={url}
            alt={fileName || 'Document preview'}
            onLoad={() => {
              setImageLoading(false);
              onDocumentLoad?.(1);
            }}
            onError={() => {
              setImageLoading(false);
              setImageError(true);
            }}
            className="max-w-full shadow-lg rounded-lg transition-transform"
            style={{ transform: `scale(${scale})`, transformOrigin: 'center' }}
          />
        </div>
      </div>
    );
  }

  // Fallback for unknown/unsupported types or image error
  if (fileType === 'unknown' || imageError) {
    return (
      <div
        ref={containerRef}
        className={clsx(
          'flex flex-col h-full bg-gray-100 rounded-lg overflow-hidden',
          className
        )}
      >
        <div className="flex-1 flex items-center justify-center p-8">
          <div className="text-center">
            {imageError ? (
              <ImageIcon className="w-16 h-16 text-red-400 mx-auto" />
            ) : (
              <File className="w-16 h-16 text-gray-400 mx-auto" />
            )}
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              {imageError ? 'Failed to load image' : 'Preview not available'}
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              {imageError
                ? 'The image could not be loaded. Try opening it in a new tab.'
                : 'This file type cannot be previewed in the browser.'}
            </p>
            {fileName && (
              <p className="mt-1 text-xs text-gray-400">{fileName}</p>
            )}
            <div className="mt-6 flex flex-col gap-2 items-center">
              <a
                href={url}
                download={fileName}
                className="inline-flex items-center px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-700"
              >
                <Download className="w-4 h-4 mr-2" />
                Download File
              </a>
              <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded hover:bg-gray-50"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Open in New Tab
              </a>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // PDF Viewer (default)
  return (
    <div
      ref={containerRef}
      className={clsx(
        'flex flex-col h-full bg-gray-100 rounded-lg overflow-hidden',
        isFullscreen && 'fixed inset-0 z-50',
        className
      )}
    >
      {/* Toolbar */}
      <div className="flex items-center justify-between px-4 py-2 bg-white border-b border-gray-200">
        {/* Page navigation */}
        <div className="flex items-center gap-2">
          <button
            onClick={prevPage}
            disabled={currentPage <= 1}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Previous page"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
          <span className="text-sm text-gray-600 min-w-[80px] text-center">
            Page {currentPage} / {numPages || '...'}
          </span>
          <button
            onClick={nextPage}
            disabled={currentPage >= numPages}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed"
            title="Next page"
          >
            <ChevronRight className="w-5 h-5" />
          </button>
        </div>

        {/* Zoom and tools */}
        <div className="flex items-center gap-1">
          <button
            onClick={zoomOut}
            disabled={scale <= 0.5}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            onClick={resetZoom}
            className="px-2 py-1 text-xs font-medium text-gray-600 hover:bg-gray-100 rounded"
          >
            {Math.round(scale * 100)}%
          </button>
          <button
            onClick={zoomIn}
            disabled={scale >= 3}
            className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-50"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <div className="w-px h-5 bg-gray-200 mx-2" />
          <button
            onClick={rotate}
            className="p-1.5 rounded hover:bg-gray-100"
            title="Rotate"
          >
            <RotateCw className="w-4 h-4" />
          </button>
          <button
            onClick={toggleFullscreen}
            className="p-1.5 rounded hover:bg-gray-100"
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4" />
            ) : (
              <Maximize2 className="w-4 h-4" />
            )}
          </button>
          <a
            href={url}
            download
            className="p-1.5 rounded hover:bg-gray-100"
            title="Download"
          >
            <Download className="w-4 h-4" />
          </a>
        </div>
      </div>

      {/* PDF Content */}
      <div
        className="flex-1 overflow-auto p-4"
        onScroll={handleScroll}
      >
        {error ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <p className="text-red-500 font-medium">{error}</p>
              <p className="text-sm text-gray-500 mt-2">
                The PDF viewer may have trouble loading some documents.
              </p>
              <div className="mt-4 flex flex-col gap-2 items-center">
                <button
                  onClick={retryLoad}
                  className="px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded hover:bg-indigo-700"
                >
                  Try Again
                </button>
                <a
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="px-4 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded hover:bg-gray-50"
                >
                  Open PDF in New Tab
                </a>
              </div>
            </div>
          </div>
        ) : (
          <Document
            key={`${url}-${retryCount}`}
            file={url}
            onLoadSuccess={onDocumentLoadSuccess}
            onLoadError={onDocumentLoadError}
            loading={
              <div className="flex items-center justify-center h-64">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
              </div>
            }
            className="flex flex-col items-center gap-4"
          >
            {Array.from({ length: numPages }, (_, index) => {
              const pageNum = index + 1;
              return (
                <div
                  key={pageNum}
                  ref={(el) => {
                    if (el) pageRefs.current.set(pageNum, el);
                  }}
                  className={clsx(
                    'relative shadow-lg rounded-lg overflow-hidden',
                    highlightedPage === pageNum && 'ring-4 ring-primary-500 ring-offset-2'
                  )}
                >
                  {/* Page number indicator */}
                  <div className="absolute top-2 left-2 px-2 py-1 bg-black/50 text-white text-xs rounded z-10">
                    Page {pageNum}
                  </div>
                  <Page
                    pageNumber={pageNum}
                    scale={scale}
                    rotate={rotation}
                    loading={
                      <div className="w-[612px] h-[792px] bg-white flex items-center justify-center">
                        <div className="animate-pulse text-gray-400">Loading page...</div>
                      </div>
                    }
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                    className="bg-white"
                  />
                </div>
              );
            })}
          </Document>
        )}
      </div>

      {/* Page thumbnails (bottom strip) */}
      {numPages > 0 && (
        <div className="flex items-center gap-2 p-2 bg-white border-t border-gray-200 overflow-x-auto">
          {Array.from({ length: numPages }, (_, index) => {
            const pageNum = index + 1;
            return (
              <button
                key={pageNum}
                onClick={() => goToPage(pageNum)}
                className={clsx(
                  'flex-shrink-0 w-12 h-16 rounded border-2 transition-all',
                  currentPage === pageNum
                    ? 'border-primary-500 shadow-md'
                    : 'border-gray-200 hover:border-gray-300',
                  highlightedPage === pageNum && 'ring-2 ring-yellow-400'
                )}
              >
                <Document file={url} loading="">
                  <Page
                    pageNumber={pageNum}
                    scale={0.1}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                  />
                </Document>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
