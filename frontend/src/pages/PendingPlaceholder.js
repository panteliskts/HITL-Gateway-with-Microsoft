import React from 'react';
import { Inbox } from 'lucide-react';

export default function PendingPlaceholder() {
  return (
    <div className="p-6 space-y-6" data-testid="pending-page">
      <h1 className="font-heading text-2xl font-bold tracking-tight text-white">Pending Inbox</h1>
      <div className="flex flex-col items-center justify-center py-20 text-hitl-muted">
        <Inbox size={48} strokeWidth={1} />
        <p className="mt-4 text-sm">Pending approvals will appear here</p>
        <p className="text-xs text-hitl-muted mt-1">Coming in the next iteration</p>
      </div>
    </div>
  );
}
