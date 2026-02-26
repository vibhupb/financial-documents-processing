import type { Document } from '../types';

/**
 * Tracks placeholder documents between upload and DynamoDB record creation.
 * UploadBar adds placeholders on success; WorkQueue merges them into the list
 * and resolves them once real data arrives from the server.
 */
const pending = new Map<string, Document>();

export const optimisticUploads = {
  add(doc: Document) {
    pending.set(doc.documentId, doc);
    // Auto-expire after 60s in case trigger Lambda silently fails
    setTimeout(() => pending.delete(doc.documentId), 60_000);
  },

  resolve(serverIds: string[]) {
    for (const id of serverIds) pending.delete(id);
  },

  getPending(): Document[] {
    return [...pending.values()];
  },

  hasPending(): boolean {
    return pending.size > 0;
  },
};
