import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Shield, ArrowLeft, Clock, AlertTriangle, Loader2, Zap,
} from 'lucide-react';
import { URGENCY_COLORS } from '../types/hitl';

const API = process.env.REACT_APP_BACKEND_URL;

// ---------------------------------------------------------------------------
// AI Remediation Engine (mock)
// ---------------------------------------------------------------------------
// Enterprise Business Value:
//   One-Click AI Remediation eliminates decision fatigue for reviewers.
//   Instead of a generic Approve/Reject, the LLM drafts 3 contextual
//   remediation strings based on the request's urgency, role, and payload.
//   The reviewer simply clicks the best option — the exact string is POSTed
//   back to the Gateway callback, giving the originating agent a precise,
//   human-approved instruction to execute.
// ---------------------------------------------------------------------------
function generateRemediationOptions(request) {
  const urgency = request?.urgency || 'NORMAL';
  const role = request?.required_role || 'Reviewer';

  // Context-aware remediation drafts based on urgency + role
  const remediationSets = {
    CRITICAL: {
      SecOps_Lead: [
        { label: 'Approve: Isolate Host & Block Lateral Movement', status: 'APPROVED', icon: '🛡️' },
        { label: 'Reject: Confirmed False Positive — Resume Monitoring', status: 'REJECTED', icon: '✅' },
        { label: 'Modify: Quarantine Host, Preserve Forensic Evidence', status: 'APPROVED', icon: '🔬' },
      ],
      default: [
        { label: 'Approve: Execute Immediate Containment', status: 'APPROVED', icon: '🚨' },
        { label: 'Reject: Risk Accepted — No Action Required', status: 'REJECTED', icon: '⏸️' },
        { label: 'Escalate: Route to Senior On-Call Reviewer', status: 'ESCALATED', icon: '📞' },
      ],
    },
    HIGH: {
      SecOps_Lead: [
        { label: 'Approve: Block Outbound Transfer & Alert DLP', status: 'APPROVED', icon: '🔒' },
        { label: 'Reject: False Positive — Whitelist Destination', status: 'REJECTED', icon: '📋' },
        { label: 'Modify: Throttle Transfer, Monitor for 24h', status: 'APPROVED', icon: '⏱️' },
      ],
      Finance_Manager: [
        { label: 'Approve: Authorize Transaction with Dual Sign-Off', status: 'APPROVED', icon: '✅' },
        { label: 'Reject: Insufficient Documentation — Return to Requester', status: 'REJECTED', icon: '📎' },
        { label: 'Modify: Approve Partial Amount, Flag for Audit', status: 'APPROVED', icon: '📊' },
      ],
      default: [
        { label: 'Approve: Proceed with Recommended Action', status: 'APPROVED', icon: '✅' },
        { label: 'Reject: Deny and Log Rationale', status: 'REJECTED', icon: '❌' },
        { label: 'Escalate: Requires Additional Review', status: 'ESCALATED', icon: '⬆️' },
      ],
    },
    NORMAL: {
      Compliance_Officer: [
        { label: 'Approve: Auto-Remediate Non-Compliant Configs', status: 'APPROVED', icon: '🔧' },
        { label: 'Reject: Manual Review Required Before Changes', status: 'REJECTED', icon: '📝' },
        { label: 'Modify: Apply to Staging First, Production After Validation', status: 'APPROVED', icon: '🧪' },
      ],
      default: [
        { label: 'Approve: Execute as Recommended', status: 'APPROVED', icon: '✅' },
        { label: 'Reject: Defer to Next Review Cycle', status: 'REJECTED', icon: '📅' },
        { label: 'Modify: Apply with Additional Constraints', status: 'APPROVED', icon: '⚙️' },
      ],
    },
    LOW: {
      default: [
        { label: 'Approve: Deploy Update to Production', status: 'APPROVED', icon: '🚀' },
        { label: 'Reject: Requires Further Testing', status: 'REJECTED', icon: '🧪' },
        { label: 'Modify: Stage in Canary Deployment First', status: 'APPROVED', icon: '🐦' },
      ],
    },
  };

  const urgencyOptions = remediationSets[urgency] || remediationSets.NORMAL;
  return urgencyOptions[role] || urgencyOptions.default;
}


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
      <Clock size={14} className={isLow ? 'text-red-400' : 'text-hitl-muted'} />
      <div className="flex-1 h-2 bg-white/5 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${isLow ? 'bg-red-500' : 'bg-hitl-active'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`font-mono text-xs ${isLow ? 'text-red-400' : 'text-hitl-muted'}`}>{fmt}</span>
    </div>
  );
}


export default function ReviewRequest() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [request, setRequest] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [deciding, setDeciding] = useState(false);
  const [decided, setDecided] = useState(null);
  const [slaRemaining, setSlaRemaining] = useState(0);

  // Fetch the workflow data
  useEffect(() => {
    async function fetchRequest() {
      try {
        const [workflowRes, pendingRes] = await Promise.all([
          fetch(`${API}/api/workflow/${id}`),
          fetch(`${API}/api/pending`),
        ]);
        const workflow = await workflowRes.json();
        const pending = await pendingRes.json();

        // Try to find in pending requests first (richer data)
        const foundPending = pending?.requests?.find(r => r.instance_id === id);

        if (foundPending) {
          setRequest(foundPending);
          setSlaRemaining(foundPending.sla_remaining_seconds || 0);
        } else if (workflow && !workflow.error) {
          setRequest({
            instance_id: workflow.instance_id,
            agent_id: workflow.agent_id,
            urgency: workflow.urgency,
            required_role: workflow.required_role,
            action_description: workflow.action_description,
            tags: workflow.tags || [],
            context: workflow.context || {},
            sla_remaining_seconds: workflow.sla_remaining_seconds || 0,
            status: workflow.decision?.status || workflow.status,
          });
          setSlaRemaining(workflow.sla_remaining_seconds || 0);

          if (workflow.decision) {
            setDecided(workflow.decision);
          }
        } else {
          setError('Request not found or already resolved');
        }
      } catch (e) {
        setError('Failed to load request. Ensure the backend is running.');
      }
      setLoading(false);
    }
    fetchRequest();
  }, [id]);

  // SLA countdown ticker
  useEffect(() => {
    if (!request || decided) return;
    const interval = setInterval(() => {
      setSlaRemaining(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [request, decided]);

  // Handle AI remediation click — POSTs the exact string back to the callback
  const handleRemediation = async (option) => {
    setDeciding(true);
    try {
      const res = await fetch(`${API}/api/decide/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: option.status,
          reviewer_id: 'admin@hitl-gateway.io',
          reason: option.label,
        }),
      });
      const result = await res.json();
      setDecided({ status: option.status, reason: option.label, result: result.result });
    } catch (e) {
      setError('Failed to submit decision');
    }
    setDeciding(false);
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-hitl-active" />
      </div>
    );
  }

  if (error && !request) {
    return (
      <div className="p-6">
        <button onClick={() => navigate('/pending')} className="flex items-center gap-2 text-sm text-hitl-muted hover:text-hitl-text-primary mb-6 transition-colors">
          <ArrowLeft size={16} /> Back to Inbox
        </button>
        <div className="flex flex-col items-center justify-center py-20 text-hitl-muted">
          <AlertTriangle size={48} strokeWidth={1} />
          <p className="mt-4 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  const urgencyColors = URGENCY_COLORS[request.urgency] || {};
  const remediationOptions = generateRemediationOptions(request);

  return (
    <div className="p-4 md:p-6 max-w-4xl mx-auto space-y-4 md:space-y-6" data-testid="review-page">
      {/* Back nav */}
      <button onClick={() => navigate('/pending')} className="flex items-center gap-2 text-sm text-hitl-muted hover:text-hitl-text-primary transition-colors">
        <ArrowLeft size={16} /> Back to Pending Inbox
      </button>

      {/* Header */}
      <div className="flex items-center gap-4">
        <div className="w-12 h-12 bg-hitl-active/10 border border-hitl-active/20 rounded-xl flex items-center justify-center">
          <Shield size={24} className="text-hitl-active" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold tracking-tight text-hitl-text-primary">
            Review Request
          </h1>
          <p className="text-xs font-mono text-hitl-muted">{id}</p>
        </div>
      </div>

      {/* Request details card */}
      <div className="bg-hitl-surface border border-hitl-border rounded-xl overflow-hidden">
        {/* Urgency banner */}
        <div className={`px-4 md:px-5 py-3 border-b border-hitl-border flex flex-col sm:flex-row sm:items-center justify-between gap-2 ${
          request.urgency === 'CRITICAL' ? 'bg-red-500/10' :
          request.urgency === 'HIGH' ? 'bg-amber-500/10' : 'bg-hitl-surface'
        }`}>
          <div className="flex items-center gap-3">
            <span className={`badge ${urgencyColors.bg} ${urgencyColors.text} ${urgencyColors.border}`}>
              {request.urgency}
            </span>
            <span className="text-xs sm:text-sm text-hitl-text-secondary">requires {request.required_role} approval</span>
          </div>
          <div className="w-full sm:w-48">
            <SLACountdown seconds={slaRemaining} urgency={request.urgency} />
          </div>
        </div>

        {/* Metadata grid */}
        <div className="p-4 md:p-5 space-y-4 md:space-y-5">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Agent</div>
              <div className="text-sm font-mono text-hitl-text-primary">{request.agent_id}</div>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Required Role</div>
              <div className="text-sm text-hitl-text-primary">{request.required_role}</div>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Instance</div>
              <div className="text-sm font-mono text-hitl-text-primary">{id.slice(0, 12)}...</div>
            </div>
            <div>
              <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Status</div>
              <div className="text-sm text-hitl-text-primary">{decided ? decided.status : 'PENDING'}</div>
            </div>
          </div>

          {/* Action description */}
          <div>
            <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Action Description</div>
            <div className="text-sm text-hitl-text-primary bg-hitl-input rounded-lg p-3 border border-hitl-border">
              {request.action_description}
            </div>
          </div>

          {/* Context payload */}
          <div>
            <div className="text-[10px] text-hitl-muted uppercase tracking-wider mb-1">Context Payload</div>
            <pre className="text-xs font-mono text-hitl-secondary bg-hitl-input rounded-lg p-3 border border-hitl-border overflow-x-auto">
              {JSON.stringify(request.context, null, 2)}
            </pre>
          </div>

          {/* Tags */}
          {request.tags?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {request.tags.map(tag => (
                <span key={tag} className="px-2 py-0.5 text-[10px] bg-hitl-active/10 text-hitl-active rounded border border-hitl-active/20">
                  {tag}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* AI Remediation Panel */}
      {!decided ? (
        <div className="bg-hitl-surface border border-hitl-border rounded-xl overflow-hidden">
          <div className="px-4 md:px-5 py-3 border-b border-hitl-border flex items-center gap-2 flex-wrap">
            <Zap size={16} className="text-amber-400" />
            <span className="text-sm font-semibold text-hitl-text-primary">AI-Suggested Remediation Actions</span>
            <span className="sm:ml-auto text-[10px] text-hitl-muted">Powered by LLM Context Analysis</span>
          </div>
          <div className="p-4 md:p-5 space-y-3">
            <p className="text-xs text-hitl-muted mb-4">
              Select one of the AI-generated remediation actions below. The exact action string
              will be sent back to the originating agent as the human-approved instruction.
            </p>
            {remediationOptions.map((option, idx) => (
              <button
                key={idx}
                onClick={() => handleRemediation(option)}
                disabled={deciding}
                className={`w-full text-left px-3 md:px-4 py-4 md:py-3.5 rounded-lg border transition-all flex items-center gap-3 group ${
                  deciding
                    ? 'opacity-50 cursor-not-allowed border-hitl-border bg-hitl-surface'
                    : option.status === 'APPROVED'
                      ? 'border-green-500/30 bg-green-500/5 hover:bg-green-500/10 hover:border-green-500/50'
                      : option.status === 'REJECTED'
                        ? 'border-red-500/30 bg-red-500/5 hover:bg-red-500/10 hover:border-red-500/50'
                        : 'border-amber-500/30 bg-amber-500/5 hover:bg-amber-500/10 hover:border-amber-500/50'
                }`}
                data-testid={`remediation-${idx}`}
              >
                <span className="text-lg flex-shrink-0">{option.icon}</span>
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-hitl-text-primary">{option.label}</span>
                  <div className="text-[10px] text-hitl-muted mt-0.5">
                    Action: {option.status} — Click to submit this decision
                  </div>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded font-medium flex-shrink-0 hidden sm:inline ${
                  option.status === 'APPROVED' ? 'bg-green-500/20 text-green-400' :
                  option.status === 'REJECTED' ? 'bg-red-500/20 text-red-400' :
                  'bg-amber-500/20 text-amber-400'
                }`}>
                  {option.status}
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-hitl-surface border border-hitl-border rounded-xl p-4 md:p-6 text-center">
          <div className={`inline-flex items-center justify-center w-16 h-16 rounded-full mb-4 ${
            decided.status === 'APPROVED' ? 'bg-green-500/20' :
            decided.status === 'REJECTED' ? 'bg-red-500/20' :
            'bg-amber-500/20'
          }`}>
            <span className="text-3xl">
              {decided.status === 'APPROVED' ? '✅' : decided.status === 'REJECTED' ? '❌' : '⚠️'}
            </span>
          </div>
          <h2 className="text-lg font-semibold text-hitl-text-primary mb-1">Decision Submitted</h2>
          <p className="text-sm text-hitl-muted mb-2">Status: <span className="font-mono font-medium">{decided.status}</span></p>
          <p className="text-xs text-hitl-secondary mb-4">{decided.reason}</p>
          {decided.result && (
            <p className="text-xs text-hitl-muted italic">{decided.result}</p>
          )}
          <button
            onClick={() => navigate('/pending')}
            className="mt-6 px-6 py-2 bg-hitl-active hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
          >
            Return to Inbox
          </button>
        </div>
      )}
    </div>
  );
}
