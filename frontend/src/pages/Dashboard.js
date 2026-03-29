import React from 'react';
import useSWR from 'swr';
import {
  Activity,
  Clock,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Users,
  Timer,
  ShieldAlert,
  ArrowUpRight,
} from 'lucide-react';
import { STATUS_COLORS, URGENCY_COLORS } from '../types/hitl';

const API = process.env.REACT_APP_BACKEND_URL;

const fetcher = (url) => fetch(url).then((r) => r.json());

function StatusBar({ health }) {
  const isHealthy = health?.status === 'healthy';
  const dotColor = isHealthy ? 'bg-hitl-approved' : 'bg-hitl-rejected';
  const statusText = isHealthy ? 'Gateway Healthy' : 'Gateway Degraded';

  return (
    <div
      className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 bg-hitl-surface border border-hitl-border px-4 md:px-5 py-3"
      data-testid="status-bar"
    >
      <div className="flex items-center gap-3">
        <span className={`w-2.5 h-2.5 rounded-full ${dotColor} ${isHealthy ? 'animate-pulse' : ''}`} data-testid="health-dot" />
        <span className="text-sm font-medium text-hitl-text-primary" data-testid="health-status-text">{statusText}</span>
        {health?.version && (
          <span className="text-xs font-mono text-hitl-muted">v{health.version}</span>
        )}
      </div>
      <div className="flex items-center gap-4 text-xs text-hitl-secondary flex-wrap">
        {health?.timestamp && (
          <span className="font-mono" data-testid="health-timestamp">
            {new Date(health.timestamp).toLocaleTimeString()}
          </span>
        )}
        {health?.checks && (
          <div className="flex items-center gap-3 flex-wrap">
            {Object.entries(health.checks).map(([key, val]) => (
              <span key={key} className="flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${val.status === 'ok' ? 'bg-hitl-approved' : 'bg-hitl-rejected'}`} />
                <span className="capitalize">{key.replace('_', ' ')}</span>
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color, subtext, testId }) {
  return (
    <div className="stat-card" data-testid={testId}>
      <div className="flex items-start justify-between mb-3">
        <div className={`w-9 h-9 rounded-[4px] flex items-center justify-center ${color}`}>
          <Icon size={18} strokeWidth={1.5} />
        </div>
        <ArrowUpRight size={14} className="text-hitl-muted" />
      </div>
      <div className="font-mono text-2xl font-semibold tracking-tighter text-hitl-text-primary" data-testid={`${testId}-value`}>
        {value}
      </div>
      <div className="text-xs uppercase tracking-[0.15em] text-hitl-muted mt-1">{label}</div>
      {subtext && (
        <div className="text-xs text-hitl-secondary mt-2">{subtext}</div>
      )}
    </div>
  );
}

function ApprovalRateRing({ rate }) {
  const circumference = 2 * Math.PI * 40;
  const offset = circumference - (rate / 100) * circumference;

  return (
    <div className="stat-card flex flex-col sm:flex-row items-center gap-4 sm:gap-5" data-testid="approval-rate-card">
      <div className="relative w-20 h-20 sm:w-24 sm:h-24 flex-shrink-0">
        <svg viewBox="0 0 100 100" className="w-full h-full -rotate-90">
          <circle cx="50" cy="50" r="40" fill="none" className="stroke-hitl-muted/20" strokeWidth="6" />
          <circle
            cx="50" cy="50" r="40" fill="none"
            stroke="#34C759"
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-1000 ease-out"
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="font-mono text-lg font-semibold text-hitl-text-primary" data-testid="approval-rate-value">
            {rate.toFixed(1)}%
          </span>
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-[0.15em] text-hitl-muted mb-1">Approval Rate</div>
        <div className="text-sm text-hitl-secondary">
          Percentage of requests approved by human reviewers
        </div>
      </div>
    </div>
  );
}

function DecisionTimeBar({ avgSeconds, p95Seconds }) {
  const maxBar = Math.max(avgSeconds, p95Seconds, 1);

  return (
    <div className="stat-card" data-testid="decision-time-card">
      <div className="flex items-center gap-2 mb-4">
        <Timer size={16} className="text-hitl-secondary" />
        <span className="text-xs uppercase tracking-[0.15em] text-hitl-muted">Decision Time</span>
      </div>
      <div className="space-y-3">
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-hitl-secondary">Average</span>
            <span className="font-mono text-hitl-text-primary" data-testid="avg-decision-time">{avgSeconds.toFixed(1)}s</span>
          </div>
          <div className="h-2 bg-hitl-muted/20 rounded-[2px] overflow-hidden">
            <div
              className="h-full bg-hitl-active rounded-[2px] transition-all duration-700"
              style={{ width: `${(avgSeconds / maxBar) * 100}%` }}
            />
          </div>
        </div>
        <div>
          <div className="flex justify-between text-xs mb-1">
            <span className="text-hitl-secondary">P95</span>
            <span className="font-mono text-hitl-text-primary" data-testid="p95-decision-time">{p95Seconds.toFixed(1)}s</span>
          </div>
          <div className="h-2 bg-hitl-muted/20 rounded-[2px] overflow-hidden">
            <div
              className="h-full bg-amber-500 rounded-[2px] transition-all duration-700"
              style={{ width: `${(p95Seconds / maxBar) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function UrgencyDistribution({ pending }) {
  const distribution = { CRITICAL: 0, HIGH: 0, NORMAL: 0, LOW: 0 };
  if (pending?.requests) {
    pending.requests.forEach((r) => {
      distribution[r.urgency] = (distribution[r.urgency] || 0) + 1;
    });
  }
  const total = Object.values(distribution).reduce((a, b) => a + b, 0) || 1;

  return (
    <div className="stat-card" data-testid="urgency-distribution-card">
      <div className="flex items-center gap-2 mb-4">
        <ShieldAlert size={16} className="text-hitl-secondary" />
        <span className="text-xs uppercase tracking-[0.15em] text-hitl-muted">Urgency Distribution</span>
      </div>
      {/* Stacked bar */}
      <div className="h-3 flex rounded-[2px] overflow-hidden mb-4" data-testid="urgency-bar">
        {Object.entries(distribution).map(([urgency, count]) => {
          const colors = URGENCY_COLORS[urgency];
          const pct = (count / total) * 100;
          if (pct === 0) return null;
          return (
            <div
              key={urgency}
              className={`${colors?.dot || 'bg-gray-500'} transition-all duration-500`}
              style={{ width: `${pct}%` }}
              title={`${urgency}: ${count}`}
            />
          );
        })}
      </div>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(distribution).map(([urgency, count]) => {
          const colors = URGENCY_COLORS[urgency];
          return (
            <div key={urgency} className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${colors?.dot || 'bg-gray-500'}`} />
              <span className="text-xs text-hitl-secondary">{urgency}</span>
              <span className="font-mono text-xs text-hitl-text-primary ml-auto">{count}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecentActivity({ events }) {
  if (!events?.length) {
    return (
      <div className="stat-card col-span-full" data-testid="recent-activity-card">
        <div className="text-xs uppercase tracking-[0.15em] text-hitl-muted mb-3">Recent Activity</div>
        <div className="text-sm text-hitl-secondary text-center py-6">No recent events</div>
      </div>
    );
  }

  return (
    <div className="stat-card col-span-full" data-testid="recent-activity-card">
      <div className="text-xs uppercase tracking-[0.15em] text-hitl-muted mb-3">Recent Activity</div>
      <div className="space-y-0">
        {events.slice(0, 8).map((ev, i) => {
          const statusColors = STATUS_COLORS[ev.event] || STATUS_COLORS.PENDING;
          return (
            <div
              key={i}
              className="flex items-center gap-3 py-2.5 border-b border-hitl-border last:border-0"
              data-testid={`activity-row-${i}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${statusColors.dot}`} />
              <span className={`badge ${statusColors.bg} ${statusColors.text} ${statusColors.border}`}>
                {ev.event}
              </span>
              <span className="text-xs text-hitl-secondary truncate flex-1">{ev.agent_id}</span>
              <span className="font-mono text-[11px] text-hitl-muted">{ev.instance_id?.slice(0, 8)}...</span>
              <span className="font-mono text-[11px] text-hitl-muted">
                {new Date(ev.timestamp).toLocaleTimeString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data: stats } = useSWR(`${API}/api/stats`, fetcher, { refreshInterval: 5000 });
  const { data: health } = useSWR(`${API}/api/health`, fetcher, { refreshInterval: 30000 });
  const { data: pending } = useSWR(`${API}/api/pending`, fetcher, { refreshInterval: 3000 });
  const { data: audit } = useSWR(`${API}/api/audit?limit=10`, fetcher, { refreshInterval: 10000 });

  return (
    <div className="p-4 md:p-6 space-y-4 md:space-y-6" data-testid="dashboard-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-heading text-xl md:text-2xl font-bold tracking-tight text-hitl-text-primary" data-testid="dashboard-title">
            Dashboard
          </h1>
          <p className="text-xs md:text-sm text-hitl-secondary mt-1">
            Real-time overview of the HITL Gateway
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted hidden sm:inline">Auto-refresh</span>
          <span className="w-2 h-2 rounded-full bg-hitl-approved animate-pulse" />
        </div>
      </div>

      {/* Status Bar */}
      <StatusBar health={health} />

      {/* Stat Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 md:gap-4" data-testid="stat-cards-grid">
        <StatCard
          label="Total Requests"
          value={stats?.total_requests ?? '—'}
          icon={Activity}
          color="bg-hitl-muted/20 text-hitl-text-primary"
          testId="stat-card-total"
        />
        <StatCard
          label="Pending"
          value={stats?.pending ?? '—'}
          icon={Clock}
          color="bg-yellow-500/10 text-yellow-400"
          testId="stat-card-pending"
        />
        <StatCard
          label="Approved"
          value={stats?.approved ?? '—'}
          icon={CheckCircle2}
          color="bg-green-500/10 text-green-400"
          testId="stat-card-approved"
        />
        <StatCard
          label="Rejected"
          value={stats?.rejected ?? '—'}
          icon={XCircle}
          color="bg-red-500/10 text-red-400"
          testId="stat-card-rejected"
        />
        <StatCard
          label="Escalated"
          value={stats?.escalated ?? '—'}
          icon={AlertTriangle}
          color="bg-purple-500/10 text-purple-400"
          testId="stat-card-escalated"
        />
      </div>

      {/* Second Row: Approval Rate + Decision Time + Active Agents + Urgency */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 md:gap-4">
        <ApprovalRateRing rate={stats?.approval_rate ?? 0} />
        <DecisionTimeBar
          avgSeconds={stats?.avg_decision_time_seconds ?? 0}
          p95Seconds={stats?.p95_decision_time_seconds ?? 0}
        />
        <StatCard
          label="Active Agents"
          value={stats?.active_agents ?? '—'}
          icon={Users}
          color="bg-blue-500/10 text-blue-400"
          subtext="Currently connected agent nodes"
          testId="stat-card-agents"
        />
        <UrgencyDistribution pending={pending} />
      </div>

      {/* Recent Activity */}
      <RecentActivity events={audit?.events} />
    </div>
  );
}
