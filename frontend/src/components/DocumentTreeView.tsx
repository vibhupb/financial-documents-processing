import { useState, useCallback, useMemo } from 'react';
import {
  ChevronRight,
  ChevronDown,
  FileText,
  BookOpen,
  Layers,
  Hash,
  Sparkles,
  Loader2,
} from 'lucide-react';
import clsx from 'clsx';

interface TreeNode {
  title: string;
  node_id: string;
  start_index: number;
  end_index: number;
  summary?: string;
  nodes?: TreeNode[];
}

interface PageIndexTree {
  doc_name?: string;
  doc_description?: string;
  structure: TreeNode[];
  total_pages?: number;
  build_duration_seconds?: number;
  verification_accuracy?: number;
}

interface DocumentTreeViewProps {
  tree: PageIndexTree;
  documentId: string;
  apiBaseUrl: string;
  onPageClick?: (pageNumber: number) => void;
  className?: string;
}

const DEPTH_COLORS = [
  { bg: 'bg-primary-50', text: 'text-primary-700', dot: 'bg-primary-400' },
  { bg: 'bg-blue-50', text: 'text-blue-600', dot: 'bg-blue-400' },
  { bg: 'bg-violet-50', text: 'text-violet-600', dot: 'bg-violet-400' },
  { bg: 'bg-gray-50', text: 'text-gray-500', dot: 'bg-gray-400' },
];

function TreeNodeItem({
  node,
  depth = 0,
  onPageClick,
  onSummarize,
  loadingNodeId,
}: {
  node: TreeNode;
  depth?: number;
  onPageClick?: (pageNumber: number) => void;
  onSummarize: (nodeId: string) => void;
  loadingNodeId: string | null;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.nodes && node.nodes.length > 0;
  const pageCount = node.end_index - node.start_index + 1;
  const pageRange =
    node.start_index === node.end_index
      ? `${node.start_index}`
      : `${node.start_index}\u2013${node.end_index}`;
  const colors = DEPTH_COLORS[Math.min(depth, DEPTH_COLORS.length - 1)];
  const isLoading = loadingNodeId === node.node_id;
  const hasSummary = !!node.summary;

  return (
    <div>
      {/* Node header row */}
      <div
        className={clsx(
          'flex items-center gap-2 py-1.5 px-2 rounded-md cursor-pointer transition-all',
          'hover:bg-gray-100 group',
          depth > 0 && 'ml-3'
        )}
        onClick={() => {
          if (hasChildren) setExpanded(!expanded);
          onPageClick?.(node.start_index);
        }}
      >
        <span className="flex-shrink-0 w-5 h-5 flex items-center justify-center">
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
            ) : (
              <ChevronRight className="w-4 h-4 text-gray-400 group-hover:text-gray-600" />
            )
          ) : (
            <span className={clsx('w-1.5 h-1.5 rounded-full', colors.dot)} />
          )}
        </span>

        <span
          className={clsx(
            'flex-1 min-w-0 text-sm truncate',
            depth === 0 ? 'font-semibold text-gray-900' : 'font-medium text-gray-700'
          )}
          title={node.title}
        >
          {node.title}
        </span>

        <span
          className={clsx(
            'flex-shrink-0 text-xs tabular-nums px-1.5 py-0.5 rounded',
            colors.bg, colors.text,
            'opacity-70 group-hover:opacity-100 transition-opacity'
          )}
        >
          {pageCount > 1 ? `${pageRange}` : `p.${pageRange}`}
        </span>
      </div>

      {/* Expanded content: summary card OR summarize button */}
      {expanded && (
        <div className={clsx('pl-7', depth > 0 && 'ml-3')}>
          {hasSummary ? (
            /* Summary card — clearly visible */
            <div className="my-1.5 px-3 py-2 bg-blue-50 border border-blue-100 rounded-md">
              <p className="text-xs text-gray-700 leading-relaxed whitespace-pre-line">
                {node.summary}
              </p>
            </div>
          ) : (
            /* Summarize button — always visible when expanded */
            <div className="my-1">
              {isLoading ? (
                <span className="inline-flex items-center gap-1.5 text-xs text-blue-500 px-2 py-1">
                  <Loader2 className="w-3 h-3 animate-spin" />
                  Generating summary...
                </span>
              ) : (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onSummarize(node.node_id);
                  }}
                  className="inline-flex items-center gap-1.5 text-xs text-blue-600 hover:text-blue-700 px-2 py-1 rounded hover:bg-blue-50 transition-colors"
                >
                  <Sparkles className="w-3 h-3" />
                  Summarize this section
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* Children */}
      {expanded && hasChildren && (
        <div className={clsx(depth > 0 && 'ml-3', 'border-l border-gray-100')}>
          {node.nodes!.map((child) => (
            <TreeNodeItem
              key={child.node_id}
              node={child}
              depth={depth + 1}
              onPageClick={onPageClick}
              onSummarize={onSummarize}
              loadingNodeId={loadingNodeId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocumentTreeView({
  tree,
  documentId,
  apiBaseUrl,
  onPageClick,
  className,
}: DocumentTreeViewProps) {
  const [loadingNodeId, setLoadingNodeId] = useState<string | null>(null);
  const [summaries, setSummaries] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>('');
  const [summarizingAll, setSummarizingAll] = useState(false);

  const stats = useMemo(() => {
    if (!tree?.structure?.length) return null;
    const topLevel = tree.structure.length;
    const total = _countNodes(tree.structure);
    return { topLevel, total };
  }, [tree]);

  // Merge fetched summaries into tree (in-memory)
  const treeWithSummaries = useMemo(() => {
    if (!Object.keys(summaries).length) return tree;
    const merged = JSON.parse(JSON.stringify(tree)) as PageIndexTree;
    _applySummaries(merged.structure, summaries);
    return merged;
  }, [tree, summaries]);

  // Count how many top-level sections have summaries
  const summarizedCount = useMemo(() => {
    return treeWithSummaries.structure.filter(
      (n) => n.summary || summaries[n.node_id]
    ).length;
  }, [treeWithSummaries, summaries]);

  const handleSummarize = useCallback(async (nodeId: string) => {
    if (loadingNodeId) return;
    setLoadingNodeId(nodeId);
    setError('');

    try {
      const resp = await fetch(
        `${apiBaseUrl}/documents/${documentId}/section-summary`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ nodeId }),
        }
      );
      const data = await resp.json();
      if (data.error) {
        setError(data.error);
      } else if (data.summary) {
        setSummaries((prev) => ({ ...prev, [nodeId]: data.summary }));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoadingNodeId(null);
    }
  }, [apiBaseUrl, documentId, loadingNodeId]);

  // Summarize all top-level sections sequentially
  const handleSummarizeAll = useCallback(async () => {
    if (summarizingAll || loadingNodeId) return;
    setSummarizingAll(true);
    setError('');

    for (const node of tree.structure) {
      // Skip if already has summary
      if (node.summary || summaries[node.node_id]) continue;

      setLoadingNodeId(node.node_id);
      try {
        const resp = await fetch(
          `${apiBaseUrl}/documents/${documentId}/section-summary`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nodeId: node.node_id }),
          }
        );
        const data = await resp.json();
        if (data.summary) {
          setSummaries((prev) => ({ ...prev, [node.node_id]: data.summary }));
        }
      } catch {
        // Continue with next section on error
      }
    }
    setLoadingNodeId(null);
    setSummarizingAll(false);
  }, [apiBaseUrl, documentId, loadingNodeId, summarizingAll, tree, summaries]);

  if (!tree || !tree.structure || tree.structure.length === 0) {
    return (
      <div
        className={clsx(
          'flex items-center justify-center h-full text-gray-400',
          className
        )}
      >
        <div className="text-center">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No document tree available</p>
          <p className="text-xs mt-1">
            Tree indexing is not available for this document type
          </p>
        </div>
      </div>
    );
  }

  const allSummarized = summarizedCount >= tree.structure.length;

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Document Overview */}
      <div className="flex-shrink-0 border-b border-gray-200">
        {tree.doc_description && (
          <div className="px-4 pt-4 pb-3">
            <div className="flex items-start gap-2.5">
              <BookOpen className="w-4 h-4 text-primary-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-gray-700 leading-relaxed">
                {tree.doc_description}
              </p>
            </div>
          </div>
        )}

        {/* Stats + Summarize All */}
        {stats && (
          <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50 text-xs text-gray-500">
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {tree.total_pages ?? '?'} pages
              </span>
              <span className="inline-flex items-center gap-1">
                <Layers className="w-3 h-3" />
                {stats.topLevel} sections
              </span>
              <span className="inline-flex items-center gap-1">
                <Hash className="w-3 h-3" />
                {stats.total} nodes
              </span>
              {tree.verification_accuracy != null && (
                <span
                  className={clsx(
                    (tree.verification_accuracy <= 1 ? tree.verification_accuracy * 100 : tree.verification_accuracy) >= 60
                      ? 'text-green-600'
                      : 'text-yellow-600'
                  )}
                >
                  {Math.round(tree.verification_accuracy <= 1 ? tree.verification_accuracy * 100 : tree.verification_accuracy)}% accuracy
                </span>
              )}
            </div>

            {/* Summarize All button */}
            {!allSummarized && (
              <button
                onClick={handleSummarizeAll}
                disabled={summarizingAll || !!loadingNodeId}
                className={clsx(
                  'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium transition-colors',
                  summarizingAll || loadingNodeId
                    ? 'text-gray-400 bg-gray-100 cursor-not-allowed'
                    : 'text-blue-600 bg-blue-50 hover:bg-blue-100'
                )}
              >
                {summarizingAll ? (
                  <>
                    <Loader2 className="w-3 h-3 animate-spin" />
                    Summarizing {summarizedCount}/{stats.topLevel}...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-3 h-3" />
                    Summarize All Sections
                  </>
                )}
              </button>
            )}
            {allSummarized && (
              <span className="text-green-600 text-xs font-medium">
                All sections summarized
              </span>
            )}
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex-shrink-0 px-4 py-2 bg-red-50 text-red-600 text-xs border-b border-red-100">
          {error}
        </div>
      )}

      {/* Tree */}
      <div className="flex-1 overflow-auto px-2 py-2">
        {treeWithSummaries.structure.map((node) => (
          <TreeNodeItem
            key={node.node_id}
            node={node}
            depth={0}
            onPageClick={onPageClick}
            onSummarize={handleSummarize}
            loadingNodeId={loadingNodeId}
          />
        ))}
      </div>
    </div>
  );
}

function _countNodes(nodes: TreeNode[]): number {
  let count = 0;
  for (const node of nodes) {
    count += 1;
    if (node.nodes) count += _countNodes(node.nodes);
  }
  return count;
}

function _applySummaries(
  nodes: TreeNode[],
  summaries: Record<string, string>
): void {
  for (const node of nodes) {
    if (summaries[node.node_id]) {
      node.summary = summaries[node.node_id];
    }
    if (node.nodes) _applySummaries(node.nodes, summaries);
  }
}
