import { useState } from 'react';
import { ChevronRight, ChevronDown, FileText } from 'lucide-react';
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
}

interface DocumentTreeViewProps {
  tree: PageIndexTree;
  onPageClick?: (pageNumber: number) => void;
  className?: string;
}

function TreeNodeItem({
  node,
  depth = 0,
  onPageClick,
}: {
  node: TreeNode;
  depth?: number;
  onPageClick?: (pageNumber: number) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 2);
  const hasChildren = node.nodes && node.nodes.length > 0;
  const pageRange = node.start_index === node.end_index
    ? `p. ${node.start_index}`
    : `pp. ${node.start_index}-${node.end_index}`;

  return (
    <div className={clsx(depth > 0 && 'ml-4 border-l border-gray-200')}>
      <div
        className={clsx(
          'flex items-start gap-1.5 py-1.5 px-2 rounded-md cursor-pointer transition-colors',
          'hover:bg-blue-50 group'
        )}
        onClick={() => {
          if (hasChildren) setExpanded(!expanded);
          onPageClick?.(node.start_index);
        }}
      >
        {/* Expand/collapse icon */}
        <span className="flex-shrink-0 mt-0.5 w-4 h-4 flex items-center justify-center">
          {hasChildren ? (
            expanded ? (
              <ChevronDown className="w-3.5 h-3.5 text-gray-400" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5 text-gray-400" />
            )
          ) : (
            <FileText className="w-3 h-3 text-gray-300" />
          )}
        </span>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="text-sm font-medium text-gray-800 truncate">
              {node.title}
            </span>
            <span className="text-xs text-gray-400 flex-shrink-0 group-hover:text-blue-500">
              {pageRange}
            </span>
          </div>
          {expanded && node.summary && (
            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
              {node.summary}
            </p>
          )}
        </div>
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {node.nodes!.map((child) => (
            <TreeNodeItem
              key={child.node_id}
              node={child}
              depth={depth + 1}
              onPageClick={onPageClick}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default function DocumentTreeView({
  tree,
  onPageClick,
  className,
}: DocumentTreeViewProps) {
  if (!tree || !tree.structure || tree.structure.length === 0) {
    return (
      <div className={clsx('flex items-center justify-center h-full text-gray-400', className)}>
        <div className="text-center">
          <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No document tree available</p>
          <p className="text-xs mt-1">Tree indexing is not available for this document type</p>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* Document description */}
      {tree.doc_description && (
        <div className="px-4 py-3 bg-blue-50 border-b border-blue-100">
          <p className="text-sm text-blue-800 italic">{tree.doc_description}</p>
          {tree.total_pages && (
            <p className="text-xs text-blue-600 mt-1">
              {tree.total_pages} pages &middot; {_countNodes(tree.structure)} sections
            </p>
          )}
        </div>
      )}

      {/* Tree */}
      <div className="flex-1 overflow-auto px-2 py-2">
        {tree.structure.map((node) => (
          <TreeNodeItem
            key={node.node_id}
            node={node}
            depth={0}
            onPageClick={onPageClick}
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
