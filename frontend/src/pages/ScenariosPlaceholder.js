import React from 'react';
import { Zap } from 'lucide-react';

export default function ScenariosPlaceholder() {
  return (
    <div className="p-6 space-y-6" data-testid="scenarios-page">
      <h1 className="font-heading text-2xl font-bold tracking-tight text-white">Scenarios</h1>
      <div className="flex flex-col items-center justify-center py-20 text-hitl-muted">
        <Zap size={48} strokeWidth={1} />
        <p className="mt-4 text-sm">Test scenario triggers will appear here</p>
        <p className="text-xs text-hitl-muted mt-1">Coming in the next iteration</p>
      </div>
    </div>
  );
}
