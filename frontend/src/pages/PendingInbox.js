import React, { useState } from 'react';
import useSWR from 'swr';
import {
  Inbox, CheckCircle2, XCircle, AlertTriangle, Clock, Shield, Eye, X,
} from 'lucide-react';
import { URGENCY_COLORS } from '../types/hitl';

const API = process.env.REACT_APP_BACKEND_URL;
const fetcher = (url) => fetch(url).then((r) => r.json());

function SLACountdown({ seconds, urgency }) {
  const total = { CRITICAL: 300, HIGH: 900, NORMAL: 3600, LOW: 86400 }[urgency] || 300;
  const pct = Math.min(100, (seconds / total) * 100);
  const isLow = seconds < total * 0.2;

  const fmt = seconds >= 3600
    ? `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
    : seconds >= 60
      ? `${Math.floor(seconds / 60)}m ${seconds % 60}s`
      : `${seconds}s`;

  return (
    <div className="flex items-center gap-2">
      <Clock size={12} className={isLow ? 'text-red-400' : 'text-hitl-muted'} />
      <div className="flex-1 h-1.5 bg-hitl-muted/20 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${isLow ? 'bg-red-500' : 'bg-hitl-active'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono text-[11px] ${isLow ? 'text-red-400' : 'text-hitl-muted'}`}>{fmt}</span>
    </div>
  );
}

function ReviewModal({ request, onClose, onDecide }) {
  const [reason, setReason] = useState('');
  const [deciding, setDeciding] = useState(false);
  const urgencyColors = URGENCY_COLORS[request.urgency] || {};

  const handleDecide = async (status) => {
    setDeciding(true);
    try {
      await fetch(`${API}/api/decide/${request.instance_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status,
          reviewer_id: 'jane.doe@contoso.com',
          reason: reason || `Reviewed and ${status.toLowerCase()}`,
        }),
      });
      onClose();
    } catch (e) {
      setDeciding(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4" data-testid="review-modal">
      <div className="bg-hitl-surface border border-hitl-border rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-hitl-border">
          <div className="flex items-center gap-3">
            <Shield size={20} className="text-hitl-active" />
            <div>
              <div className="text-sm font-semibold text-hitl-text-primary">Review Request</div>
              <div className="text-xs font-mono text-hitl-muted">{request.instance_id.slice(0, 12)}...</div>
            </div>
          </div>
          <button onClick={onClose} className="p-1 text-hitl-muted hover:text-hitl-text-primary transition-colors">
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4">
          {/* Meta */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider">Agent</div>
              <div className="text-sm font-mono text-hitl-text-primary">{request.agent_id}</div>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider">Urgency</div>
              <span className={`badge ${urgencyColors.bg} ${urgencyColors.text} ${urgencyColors.border}`}>
                {request.urgency}
              </span>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider">Role</div>
              <div className="text-sm text-hitl-text-primary">{request.required_role}</div>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider">SLA</div>
              <SLACountdown seconds={request.sla_remaining_seconds} urgency={request.urgency} />
            </div>
          </div>

          {/* Description */}
          <div>
            <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Action Description</div>
            <div className="text-sm text-hitl-text-primary bg-hitl-input rounded-lg p-3 border border-hitl-border">{request.action_description}</div>
          </div>

          {/* Context */}
          <div>
            <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Context Payload</div>
            <pre className="text-xs font-mono text-hitl-secondary bg-hitl-input rounded-lg p-3 border border-hitl-border overflow-x-auto">
              {JSON.stringify(request.context, null, 2)}
            </pre>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-1">
            {request.tags?.map((tag) => (
              <span key={tag} className="px-2 py-0.5 text-[10px] bg-hitl-active/10 text-hitl-secondary rounded border border-hitl-border">
                {tag}
              </span>
            ))}
          </div>

          {/* Decision */}
          <div className="border-t border-hitl-border pt-4">
            <input
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Enter review reason..."
              className="w-full bg-hitl-input border border-hitl-border rounded-lg px-3 py-2 text-sm text-hitl-text-primary placeholder:text-hitl-muted mb-3 focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30"
              data-testid="modal-reason-input"
            />
            <div className="flex flex-col sm:flex-row gap-3">
              <button
                onClick={() => handleDecide('APPROVED')}
                disabled={deciding}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <CheckCircle2 size={16} /> Approve
              </button>
              <button
                onClick={() => handleDecide('REJECTED')}
                disabled={deciding}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <XCircle size={16} /> Reject
              </button>
              <button
                onClick={() => handleDecide('ESCALATED')}
                disabled={deciding}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                <AlertTriangle size={16} /> Escalate
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function PendingInbox() {
  const { data } = useSWR(`${API}/api/pending`, fetcher, { refreshInterval: 1000 });
  const [reviewing, setReviewing] = useState(null);

  const requests = data?.requests || [];

  return (
    <div className="p-4 md:p-6 space-y-4 md:space-y-6" data-testid="pending-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl md:text-2xl font-bold tracking-tight text-hitl-text-primary flex items-center gap-2 md:gap-3">
            <Inbox size={20} className="text-amber-400 md:w-6 md:h-6" />
            Pending Inbox
          </h1>
          <p className="text-xs md:text-sm text-hitl-secondary mt-1">
            {requests.length} request{requests.length !== 1 ? 's' : ''} awaiting human review
          </p>
        </div>
      </div>

      {requests.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-hitl-muted">
          <Inbox size={48} strokeWidth={1} />
          <p className="mt-4 text-sm">No pending requests</p>
          <p className="text-xs text-hitl-muted mt-1">Trigger a scenario from the Live Demo to see requests here</p>
        </div>
      ) : (
        <div className="space-y-3">
          {requests.map((req) => {
            const urgencyColors = URGENCY_COLORS[req.urgency] || {};
            return (
              <div
                key={req.instance_id}
                className={`bg-hitl-surface border rounded-lg p-3 md:p-4 transition-all hover:border-white/30 ${
                  req.urgency === 'CRITICAL' ? 'border-red-500/30' : 'border-hitl-border'
                }`}
                data-testid={`pending-card-${req.instance_id.slice(0, 8)}`}
              >
                <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                      <span className={`badge ${urgencyColors.bg} ${urgencyColors.text} ${urgencyColors.border}`}>
                        {req.urgency}
                      </span>
                      <span className="text-xs font-mono text-hitl-muted">{req.instance_id.slice(0, 12)}...</span>
                    </div>
                    <div className="text-sm text-hitl-text-primary mb-1">{req.action_description}</div>
                    <div className="flex items-center gap-3 md:gap-4 text-xs text-hitl-secondary flex-wrap">
                      <span>Agent: <span className="font-mono">{req.agent_id}</span></span>
                      <span>Role: {req.required_role}</span>
                    </div>
                    <div className="mt-2 max-w-md">
                      <SLACountdown seconds={req.sla_remaining_seconds} urgency={req.urgency} />
                    </div>
                  </div>
                  <button
                    onClick={() => setReviewing(req)}
                    className="flex items-center justify-center gap-2 px-4 py-2.5 sm:py-2 bg-hitl-active hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors w-full sm:w-auto flex-shrink-0"
                  >
                    <Eye size={14} /> Review
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {reviewing && (
        <ReviewModal
          request={reviewing}
          onClose={() => setReviewing(null)}
          onDecide={() => setReviewing(null)}
        />
      )}
    </div>
  );
}
