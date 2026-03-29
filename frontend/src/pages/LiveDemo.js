import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Zap, Play, RotateCcw, Shield, Brain, Radio, Clock, Users,
  Send, CheckCircle2, XCircle, AlertTriangle, ArrowRight, Bot,
} from 'lucide-react';
import { URGENCY_COLORS } from '../types/hitl';

const API = process.env.REACT_APP_BACKEND_URL;

const STAGE_ICONS = {
  agent_analysis: Brain,
  threat_detection: Shield,
  gateway_ingress: Radio,
  orchestrator: Clock,
  notification: Send,
  human_review: Users,
  agent_callback: Zap,
};

const STAGE_COLORS = {
  idle: 'border-hitl-border bg-hitl-muted/10 text-hitl-muted',
  active: 'border-blue-500 bg-blue-500/10 text-blue-400 ring-2 ring-blue-500/30',
  completed: 'border-green-500 bg-green-500/10 text-green-400',
  waiting: 'border-amber-500 bg-amber-500/10 text-amber-400 ring-2 ring-amber-500/30 animate-pulse',
};

const CONNECTOR_COLORS = {
  idle: 'bg-hitl-muted/20',
  completed: 'bg-green-500',
  active: 'bg-blue-500 animate-pulse',
};

function StageNode({ stage, index, total }) {
  const Icon = STAGE_ICONS[stage.id] || Zap;
  const colorClass = STAGE_COLORS[stage.status] || STAGE_COLORS.idle;
  const isLast = index === total - 1;
  const connectorStatus = stage.status === 'completed' ? 'completed' : stage.status === 'active' || stage.status === 'waiting' ? 'active' : 'idle';

  return (
    <div className="flex items-center" data-testid={`stage-${stage.id}`}>
      <div className="flex flex-col items-center gap-2 min-w-[100px]">
        <div className={`w-14 h-14 rounded-lg border-2 flex items-center justify-center transition-all duration-500 ${colorClass}`}>
          {stage.status === 'completed' ? (
            <CheckCircle2 size={22} />
          ) : stage.status === 'waiting' ? (
            <Clock size={22} />
          ) : (
            <Icon size={22} />
          )}
        </div>
        <div className="text-center">
          <div className="text-[11px] font-medium text-hitl-text-primary leading-tight max-w-[100px]">{stage.label}</div>
          <div className="text-[9px] text-hitl-muted mt-0.5 font-mono">{stage.azure_service}</div>
        </div>
      </div>
      {!isLast && (
        <div className="flex items-center mx-1 -mt-6">
          <div className={`h-[3px] w-8 rounded-full transition-all duration-500 ${CONNECTOR_COLORS[connectorStatus]}`} />
          <ArrowRight size={12} className={`-ml-1 transition-all duration-500 ${stage.status === 'completed' ? 'text-green-500' : 'text-hitl-muted/40'}`} />
        </div>
      )}
    </div>
  );
}

function EventLog({ events }) {
  const bottomRef = useRef(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events.length]);

  const typeColors = {
    info: 'text-blue-400',
    warning: 'text-amber-400',
    success: 'text-green-400',
    error: 'text-red-400',
  };

  return (
    <div className="bg-hitl-base border border-hitl-border rounded-lg overflow-hidden" data-testid="event-log">
      <div className="px-4 py-2 border-b border-hitl-border flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        <span className="text-xs font-mono text-hitl-muted uppercase tracking-wider">Live Event Stream</span>
      </div>
      <div className="h-[240px] overflow-y-auto p-3 font-mono text-xs space-y-1 scrollbar-thin">
        {events.length === 0 && (
          <div className="text-hitl-muted text-center py-8">Trigger a scenario to see live events...</div>
        )}
        {events.map((ev, i) => (
          <div key={i} className="flex gap-2 py-0.5">
            <span className="text-hitl-muted flex-shrink-0">
              {new Date(ev.timestamp).toLocaleTimeString('en-US', { hour12: false })}
            </span>
            <span className={`flex-shrink-0 w-[140px] ${typeColors[ev.type] || 'text-hitl-text-primary'}`}>
              [{ev.stage_label}]
            </span>
            <span className="text-hitl-secondary">{ev.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

function ScenarioCard({ name, scenario, onTrigger, disabled }) {
  const urgencyColors = URGENCY_COLORS[scenario.urgency] || {};
  const slaLabel = scenario.sla_seconds >= 3600
    ? `${Math.round(scenario.sla_seconds / 3600)}h`
    : `${Math.round(scenario.sla_seconds / 60)}m`;

  return (
    <button
      onClick={() => onTrigger(name)}
      disabled={disabled}
      className={`text-left p-4 border rounded-lg transition-all duration-200 ${
        disabled
          ? 'border-hitl-border bg-hitl-muted/5 opacity-50 cursor-not-allowed'
          : 'border-hitl-border bg-hitl-surface hover:border-hitl-text-primary/30 hover:-translate-y-[1px] cursor-pointer'
      }`}
      data-testid={`scenario-${name}`}
    >
      <div className="flex items-center justify-between mb-2">
        <span className={`badge ${urgencyColors.bg} ${urgencyColors.text} ${urgencyColors.border}`}>
          {scenario.urgency}
        </span>
        <span className="text-[10px] font-mono text-hitl-muted">SLA {slaLabel}</span>
      </div>
      <div className="text-sm font-medium text-hitl-text-primary mb-1">
        {name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
      </div>
      <div className="text-xs text-hitl-secondary line-clamp-2">{scenario.description}</div>
      <div className="flex items-center gap-2 mt-2">
        <Bot size={12} className="text-hitl-muted" />
        <span className="text-[10px] font-mono text-hitl-muted">{scenario.agent_id}</span>
      </div>
    </button>
  );
}

function DecisionPanel({ workflow, onDecide }) {
  const [reason, setReason] = useState('');

  if (!workflow || workflow.status !== 'waiting_for_human') return null;

  return (
    <div className="border-2 border-amber-500/50 bg-amber-500/5 rounded-lg p-5 animate-in" data-testid="decision-panel">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
          <Users size={20} className="text-amber-400" />
        </div>
        <div>
          <div className="text-sm font-semibold text-hitl-text-primary">Human Decision Required</div>
          <div className="text-xs text-hitl-secondary">
            Review the action and approve or reject. Role: {workflow.required_role}
          </div>
        </div>
      </div>

      <div className="bg-hitl-input rounded-lg p-3 mb-4 font-mono text-xs border border-hitl-border">
        <div className="text-hitl-muted mb-1">Action:</div>
        <div className="text-hitl-text-primary">{workflow.action_description}</div>
        <div className="text-hitl-muted mt-2 mb-1">Context:</div>
        <pre className="text-hitl-secondary overflow-x-auto">{JSON.stringify(workflow.context, null, 2)}</pre>
      </div>

      <input
        type="text"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Enter review reason..."
        className="w-full bg-hitl-input border border-hitl-border rounded-lg px-3 py-2 text-sm text-hitl-text-primary placeholder:text-hitl-muted mb-3 focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30"
        data-testid="decision-reason-input"
      />

      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={() => onDecide('APPROVED', reason || 'Reviewed and approved')}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-green-600 hover:bg-green-500 text-white rounded-lg text-sm font-medium transition-colors"
          data-testid="approve-btn"
        >
          <CheckCircle2 size={16} /> Approve
        </button>
        <button
          onClick={() => onDecide('REJECTED', reason || 'Reviewed and rejected')}
          className="flex-1 flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-sm font-medium transition-colors"
          data-testid="reject-btn"
        >
          <XCircle size={16} /> Reject
        </button>
        <button
          onClick={() => onDecide('ESCALATED', reason || 'Escalating to senior reviewer')}
          className="flex-1 sm:flex-none flex items-center justify-center gap-2 px-4 py-3 sm:py-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-medium transition-colors"
          data-testid="escalate-btn"
        >
          <AlertTriangle size={16} /> Escalate
        </button>
      </div>
    </div>
  );
}

export default function LiveDemo() {
  const [scenarios, setScenarios] = useState({});
  const [activeWorkflow, setActiveWorkflow] = useState(null);
  const [events, setEvents] = useState([]);
  const [isRunning, setIsRunning] = useState(false);
  const pollRef = useRef(null);

  // Load scenarios on mount
  useEffect(() => {
    fetch(`${API}/api/scenarios`).then(r => r.json()).then(setScenarios).catch(() => {});
  }, []);

  // Poll active workflow
  useEffect(() => {
    if (!activeWorkflow?.instance_id) return;
    const poll = setInterval(async () => {
      try {
        const res = await fetch(`${API}/api/workflow/${activeWorkflow.instance_id}`);
        const wf = await res.json();
        setActiveWorkflow(wf);
        setEvents(wf.events || []);
        if (wf.status === 'completed') {
          setIsRunning(false);
        }
      } catch (e) { /* ignore */ }
    }, 500);
    pollRef.current = poll;
    return () => clearInterval(poll);
  }, [activeWorkflow?.instance_id]);

  const handleTrigger = useCallback(async (scenarioName) => {
    setIsRunning(true);
    setEvents([]);
    try {
      const res = await fetch(`${API}/api/trigger/${scenarioName}`, { method: 'POST' });
      const data = await res.json();
      // Immediately fetch the workflow
      const wfRes = await fetch(`${API}/api/workflow/${data.instance_id}`);
      const wf = await wfRes.json();
      setActiveWorkflow(wf);
    } catch (e) {
      setIsRunning(false);
    }
  }, []);

  const handleDecide = useCallback(async (status, reason) => {
    if (!activeWorkflow) return;
    try {
      await fetch(`${API}/api/decide/${activeWorkflow.instance_id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status,
          reviewer_id: 'jane.doe@contoso.com',
          reason,
        }),
      });
    } catch (e) { /* poll will pick up changes */ }
  }, [activeWorkflow]);

  const handleReset = useCallback(async () => {
    setActiveWorkflow(null);
    setEvents([]);
    setIsRunning(false);
    if (pollRef.current) clearInterval(pollRef.current);
    await fetch(`${API}/api/reset`, { method: 'POST' }).catch(() => {});
  }, []);

  return (
    <div className="p-4 md:p-6 space-y-4 md:space-y-6" data-testid="live-demo-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl md:text-2xl font-bold tracking-tight text-hitl-text-primary flex items-center gap-2 md:gap-3">
            <Play size={20} className="text-hitl-active md:w-6 md:h-6" />
            Live Demo
          </h1>
          <p className="text-xs md:text-sm text-hitl-secondary mt-1">
            Trigger a scenario and watch the Azure Durable Functions orchestration in real-time
          </p>
        </div>
        <button
          onClick={handleReset}
          className="flex items-center gap-2 px-3 py-2 text-xs text-hitl-secondary border border-hitl-border rounded-lg hover:border-hitl-text-primary/30 transition-colors"
          data-testid="reset-btn"
        >
          <RotateCcw size={14} /> Reset
        </button>
      </div>

      {/* Azure Architecture Flow */}
      {activeWorkflow && (
        <div className="bg-hitl-surface border border-hitl-border rounded-lg p-4 md:p-6" data-testid="flow-visualizer">
          <div className="flex items-center gap-2 mb-5">
            <div className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted">Azure Durable Functions Pipeline</div>
            {activeWorkflow.status === 'completed' ? (
              <span className="badge bg-green-500/10 text-green-400 border-green-500/20">Complete</span>
            ) : activeWorkflow.status === 'waiting_for_human' ? (
              <span className="badge bg-amber-500/10 text-amber-400 border-amber-500/20 animate-pulse">Awaiting Decision</span>
            ) : (
              <span className="badge bg-blue-500/10 text-blue-400 border-blue-500/20 animate-pulse">Processing</span>
            )}
          </div>
          <div className="flex items-start justify-start md:justify-center overflow-x-auto pb-2 -mx-2 px-2">
            {activeWorkflow.stages?.map((stage, i) => (
              <StageNode key={stage.id} stage={stage} index={i} total={activeWorkflow.stages.length} />
            ))}
          </div>
        </div>
      )}

      {/* Decision Panel */}
      <DecisionPanel workflow={activeWorkflow} onDecide={handleDecide} />

      {/* Scenarios Grid */}
      <div>
        <div className="text-xs uppercase tracking-[0.15em] text-hitl-muted mb-3">
          {isRunning ? 'Scenario Running...' : 'Select a Threat Scenario'}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3">
          {Object.entries(scenarios).map(([name, scenario]) => (
            <ScenarioCard
              key={name}
              name={name}
              scenario={scenario}
              onTrigger={handleTrigger}
              disabled={isRunning}
            />
          ))}
        </div>
      </div>

      {/* Event Log */}
      <EventLog events={events} />
    </div>
  );
}
