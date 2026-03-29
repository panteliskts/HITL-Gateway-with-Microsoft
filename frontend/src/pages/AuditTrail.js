import React, { useState, useMemo } from 'react';
import useSWR from 'swr';
import {
  ScrollText, CheckCircle2, XCircle, AlertTriangle, Clock, Zap, Radio,
  Download, Filter, X, ChevronDown,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const fetcher = (url) => fetch(url).then((r) => r.json());

const EVENT_CONFIG = {
  TRIGGERED: { icon: Zap, color: 'text-blue-400', dot: 'bg-blue-400', label: 'Triggered' },
  PENDING: { icon: Clock, color: 'text-yellow-400', dot: 'bg-yellow-400', label: 'Pending' },
  APPROVED: { icon: CheckCircle2, color: 'text-green-400', dot: 'bg-green-400', label: 'Approved' },
  REJECTED: { icon: XCircle, color: 'text-red-400', dot: 'bg-red-400', label: 'Rejected' },
  ESCALATED: { icon: AlertTriangle, color: 'text-purple-400', dot: 'bg-purple-400', label: 'Escalated' },
  COMPLETE: { icon: Radio, color: 'text-green-400', dot: 'bg-green-400', label: 'Complete' },
};

const URGENCY_OPTIONS = ['ALL', 'CRITICAL', 'HIGH', 'NORMAL', 'LOW'];
const EVENT_OPTIONS = ['ALL', 'TRIGGERED', 'PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', 'COMPLETE'];
const TIME_OPTIONS = [
  { label: 'All Time', value: 'all' },
  { label: 'Last 5 min', value: '5m' },
  { label: 'Last 15 min', value: '15m' },
  { label: 'Last 1 hour', value: '1h' },
  { label: 'Last 24 hours', value: '24h' },
];

function FilterDropdown({ label, options, value, onChange, icon: Icon }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(!open)}
        className={`flex items-center gap-2 px-3 py-1.5 text-xs border rounded-lg transition-colors ${
          value !== 'ALL' && value !== 'all'
            ? 'bg-hitl-active/10 border-hitl-active/30 text-hitl-active'
            : 'bg-hitl-surface border-hitl-border text-hitl-secondary hover:border-hitl-text-primary/30'
        }`}
      >
        {Icon && <Icon size={12} />}
        <span>{label}: {typeof value === 'object' ? value.label : value}</span>
        <ChevronDown size={12} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute top-full mt-1 left-0 z-50 bg-hitl-surface border border-hitl-border rounded-lg shadow-xl py-1 min-w-[140px]">
            {options.map((opt) => {
              const optValue = typeof opt === 'object' ? opt.value : opt;
              const optLabel = typeof opt === 'object' ? opt.label : opt;
              const isActive = (typeof value === 'object' ? value.value : value) === optValue;
              return (
                <button
                  key={optValue}
                  onClick={() => { onChange(opt); setOpen(false); }}
                  className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                    isActive ? 'bg-hitl-active/10 text-hitl-active' : 'text-hitl-secondary hover:bg-hitl-muted/10 hover:text-hitl-text-primary'
                  }`}
                >
                  {optLabel}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

function StatsBar({ events }) {
  const counts = useMemo(() => {
    const c = { TRIGGERED: 0, PENDING: 0, APPROVED: 0, REJECTED: 0, ESCALATED: 0, COMPLETE: 0 };
    events.forEach((ev) => { if (c[ev.event] !== undefined) c[ev.event]++; });
    return c;
  }, [events]);

  const total = events.length;
  const approvalRate = total > 0
    ? ((counts.APPROVED / Math.max(1, counts.APPROVED + counts.REJECTED + counts.ESCALATED)) * 100).toFixed(1)
    : '0.0';

  return (
    <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-2 md:gap-3">
      {[
        { label: 'Total', count: total, color: 'text-hitl-text-primary' },
        { label: 'Triggered', count: counts.TRIGGERED, color: 'text-blue-400' },
        { label: 'Pending', count: counts.PENDING, color: 'text-yellow-400' },
        { label: 'Approved', count: counts.APPROVED, color: 'text-green-400' },
        { label: 'Rejected', count: counts.REJECTED, color: 'text-red-400' },
        { label: 'Escalated', count: counts.ESCALATED, color: 'text-purple-400' },
        { label: 'Approval Rate', count: `${approvalRate}%`, color: 'text-hitl-active' },
      ].map(({ label, count, color }) => (
        <div key={label} className="bg-hitl-surface border border-hitl-border rounded-lg px-3 py-2 text-center">
          <div className={`font-mono text-lg font-semibold ${color}`}>{count}</div>
          <div className="text-[10px] uppercase tracking-wider text-hitl-muted">{label}</div>
        </div>
      ))}
    </div>
  );
}

function TimelineEvent({ event, isLast }) {
  const config = EVENT_CONFIG[event.event] || EVENT_CONFIG.PENDING;
  const Icon = config.icon;

  return (
    <div className="flex gap-4" data-testid={`audit-event-${event.instance_id?.slice(0, 8)}`}>
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div className={`w-8 h-8 rounded-full border-2 flex items-center justify-center flex-shrink-0 ${
          event.event === 'APPROVED' ? 'border-green-500 bg-green-500/10' :
          event.event === 'REJECTED' ? 'border-red-500 bg-red-500/10' :
          event.event === 'ESCALATED' ? 'border-purple-500 bg-purple-500/10' :
          event.event === 'COMPLETE' ? 'border-green-500 bg-green-500/10' :
          'border-hitl-border bg-hitl-muted/10'
        }`}>
          <Icon size={14} className={config.color} />
        </div>
        {!isLast && <div className="w-[2px] flex-1 bg-hitl-border min-h-[20px]" />}
      </div>

      {/* Content */}
      <div className="pb-5 flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 flex-wrap">
          <span className={`text-xs font-semibold ${config.color}`}>{config.label}</span>
          <span className="text-[10px] font-mono text-hitl-muted">
            {new Date(event.timestamp).toLocaleString()}
          </span>
          {event.required_role && event.required_role !== 'N/A' && (
            <span className="px-1.5 py-0.5 text-[9px] bg-hitl-active/10 text-hitl-secondary rounded border border-hitl-border">
              {event.required_role}
            </span>
          )}
        </div>
        <div className="text-sm text-hitl-text-primary mb-1">{event.detail}</div>
        <div className="flex items-center gap-3 text-xs text-hitl-secondary flex-wrap">
          <span className="font-mono">{event.instance_id?.slice(0, 12)}...</span>
          <span>{event.agent_id}</span>
          {event.reviewer_id && <span>by {event.reviewer_id}</span>}
          <span className={`badge ${
            event.urgency === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
            event.urgency === 'HIGH' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
            event.urgency === 'NORMAL' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
            'bg-gray-500/10 text-gray-400 border-gray-500/20'
          }`}>{event.urgency}</span>
        </div>
      </div>
    </div>
  );
}

export default function AuditTrail() {
  const { data } = useSWR(`${API}/api/audit?limit=200`, fetcher, { refreshInterval: 2000 });
  const allEvents = useMemo(() => data?.events || [], [data]);

  const [urgencyFilter, setUrgencyFilter] = useState('ALL');
  const [eventFilter, setEventFilter] = useState('ALL');
  const [timeFilter, setTimeFilter] = useState(TIME_OPTIONS[0]);
  const [roleSearch, setRoleSearch] = useState('');

  // Derive unique roles from events
  const uniqueRoles = useMemo(() => {
    const roles = new Set();
    allEvents.forEach((ev) => {
      if (ev.required_role && ev.required_role !== 'N/A') roles.add(ev.required_role);
    });
    return Array.from(roles).sort();
  }, [allEvents]);

  // Apply filters
  const filteredEvents = useMemo(() => {
    let events = allEvents;

    if (urgencyFilter !== 'ALL') {
      events = events.filter((e) => e.urgency === urgencyFilter);
    }
    if (eventFilter !== 'ALL') {
      events = events.filter((e) => e.event === eventFilter);
    }
    if (roleSearch) {
      events = events.filter((e) =>
        (e.required_role || '').toLowerCase().includes(roleSearch.toLowerCase())
      );
    }
    if (timeFilter.value !== 'all') {
      const ms = { '5m': 5 * 60000, '15m': 15 * 60000, '1h': 3600000, '24h': 86400000 }[timeFilter.value];
      const cutoff = new Date(Date.now() - ms).toISOString();
      events = events.filter((e) => e.timestamp >= cutoff);
    }

    return events;
  }, [allEvents, urgencyFilter, eventFilter, timeFilter, roleSearch]);

  const activeFilterCount = [
    urgencyFilter !== 'ALL',
    eventFilter !== 'ALL',
    timeFilter.value !== 'all',
    roleSearch !== '',
  ].filter(Boolean).length;

  const handleDownloadCSV = () => {
    const params = new URLSearchParams();
    if (urgencyFilter !== 'ALL') params.set('urgency', urgencyFilter);
    if (eventFilter !== 'ALL') params.set('event', eventFilter);
    if (roleSearch) params.set('role', roleSearch);
    if (timeFilter.value !== 'all') {
      const ms = { '5m': 5 * 60000, '15m': 15 * 60000, '1h': 3600000, '24h': 86400000 }[timeFilter.value];
      params.set('since', new Date(Date.now() - ms).toISOString());
    }
    const qs = params.toString();
    window.open(`${API}/api/audit/csv${qs ? `?${qs}` : ''}`, '_blank');
  };

  const clearFilters = () => {
    setUrgencyFilter('ALL');
    setEventFilter('ALL');
    setTimeFilter(TIME_OPTIONS[0]);
    setRoleSearch('');
  };

  return (
    <div className="p-4 md:p-6 space-y-4 md:space-y-5" data-testid="audit-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h1 className="font-heading text-xl md:text-2xl font-bold tracking-tight text-hitl-text-primary flex items-center gap-2 md:gap-3">
            <ScrollText size={20} className="text-hitl-secondary md:w-6 md:h-6" />
            Audit Trail
          </h1>
          <p className="text-xs md:text-sm text-hitl-secondary mt-1">
            Complete compliance log of all HITL decisions and state transitions
          </p>
        </div>
        <button
          onClick={handleDownloadCSV}
          className="flex items-center justify-center gap-2 px-4 py-2 bg-hitl-active hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors w-full sm:w-auto"
          data-testid="download-csv-btn"
        >
          <Download size={16} />
          Export CSV
        </button>
      </div>

      {/* Stats Overview */}
      <StatsBar events={filteredEvents} />

      {/* Filters Bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <div className="flex items-center gap-1.5 text-hitl-muted mr-1">
          <Filter size={14} />
          <span className="text-[10px] uppercase tracking-wider hidden sm:inline">Filters</span>
        </div>

        <FilterDropdown
          label="Urgency"
          options={URGENCY_OPTIONS}
          value={urgencyFilter}
          onChange={setUrgencyFilter}
        />
        <FilterDropdown
          label="Event"
          options={EVENT_OPTIONS}
          value={eventFilter}
          onChange={setEventFilter}
        />
        <FilterDropdown
          label="Time"
          options={TIME_OPTIONS}
          value={timeFilter}
          onChange={setTimeFilter}
          icon={Clock}
        />

        {/* Role search */}
        <div className="relative">
          <input
            type="text"
            value={roleSearch}
            onChange={(e) => setRoleSearch(e.target.value)}
            placeholder="Filter by role..."
            className="bg-hitl-surface border border-hitl-border rounded-lg px-3 py-1.5 text-xs text-hitl-text-primary placeholder:text-hitl-muted focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30 w-[120px] sm:w-[150px]"
            list="role-suggestions"
          />
          {uniqueRoles.length > 0 && (
            <datalist id="role-suggestions">
              {uniqueRoles.map((r) => <option key={r} value={r} />)}
            </datalist>
          )}
        </div>

        {activeFilterCount > 0 && (
          <button
            onClick={clearFilters}
            className="flex items-center gap-1 px-2 py-1.5 text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            <X size={12} /> Clear ({activeFilterCount})
          </button>
        )}

        <div className="sm:ml-auto text-xs text-hitl-muted">
          {filteredEvents.length} of {allEvents.length} events
        </div>
      </div>

      {/* Timeline */}
      {filteredEvents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-hitl-muted">
          <ScrollText size={48} strokeWidth={1} />
          <p className="mt-4 text-sm">
            {allEvents.length === 0 ? 'No audit events yet' : 'No events match the current filters'}
          </p>
          <p className="text-xs text-hitl-muted mt-1">
            {allEvents.length === 0
              ? 'Trigger a scenario from the Live Demo to see the audit trail'
              : 'Try adjusting or clearing the filters'}
          </p>
        </div>
      ) : (
        <div className="bg-hitl-surface border border-hitl-border rounded-lg p-3 md:p-5">
          <div className="flex items-center gap-2 mb-5">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            <span className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted">
              {filteredEvents.length} events {activeFilterCount > 0 ? '(filtered)' : 'recorded'}
            </span>
          </div>
          <div>
            {filteredEvents.map((event, i) => (
              <TimelineEvent key={`${event.instance_id}-${event.event}-${i}`} event={event} isLast={i === filteredEvents.length - 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
