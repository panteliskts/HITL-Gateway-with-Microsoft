/**
 * HITL Gateway — Types, Constants & Color Maps
 * ==============================================
 * All data models, enumerations, SLA mappings, and visual constants
 * for the Human-in-the-Loop Gateway Dashboard.
 */

// ---------------------------------------------------------------------------
// Enumerations
// ---------------------------------------------------------------------------

export const UrgencyLevel = Object.freeze({
  CRITICAL: 'CRITICAL',
  HIGH: 'HIGH',
  NORMAL: 'NORMAL',
  LOW: 'LOW',
});

export const HITLStatus = Object.freeze({
  PENDING: 'PENDING',
  APPROVED: 'APPROVED',
  REJECTED: 'REJECTED',
  ESCALATED: 'ESCALATED',
});

export const ApprovalPolicy = Object.freeze({
  ANY: 'ANY',
  ALL: 'ALL',
  MAJORITY: 'MAJORITY',
});

// ---------------------------------------------------------------------------
// SLA Timeout Map (seconds) — drives client-side countdown timers
// ---------------------------------------------------------------------------

export const SLA_TIMEOUT_SECONDS = Object.freeze({
  [UrgencyLevel.CRITICAL]: 300,     // 5 minutes
  [UrgencyLevel.HIGH]: 900,         // 15 minutes
  [UrgencyLevel.NORMAL]: 3600,      // 60 minutes
  [UrgencyLevel.LOW]: 86400,        // 24 hours
});

// ---------------------------------------------------------------------------
// Role → Channel Mapping (display only)
// ---------------------------------------------------------------------------

export const ROLE_CHANNEL_MAP = Object.freeze({
  Finance_Manager: '#finance-approvals',
  SecOps_Lead: '#secops-alerts',
  Compliance_Officer: '#compliance-reviews',
  Risk_Manager: '#risk-management',
});

export const DEFAULT_CHANNEL = '#hitl-general';

// ---------------------------------------------------------------------------
// Urgency Color Scheme
// ---------------------------------------------------------------------------

export const URGENCY_COLORS = Object.freeze({
  [UrgencyLevel.CRITICAL]: { bg: 'bg-red-500/10', text: 'text-red-500', border: 'border-red-500/20', dot: 'bg-red-500' },
  [UrgencyLevel.HIGH]: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20', dot: 'bg-amber-400' },
  [UrgencyLevel.NORMAL]: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', dot: 'bg-blue-400' },
  [UrgencyLevel.LOW]: { bg: 'bg-gray-500/10', text: 'text-gray-400', border: 'border-gray-500/20', dot: 'bg-gray-400' },
});

// ---------------------------------------------------------------------------
// Status Color Scheme
// ---------------------------------------------------------------------------

export const STATUS_COLORS = Object.freeze({
  [HITLStatus.PENDING]: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/20', dot: 'bg-yellow-400' },
  [HITLStatus.APPROVED]: { bg: 'bg-green-500/10', text: 'text-green-400', border: 'border-green-500/20', dot: 'bg-green-400' },
  [HITLStatus.REJECTED]: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20', dot: 'bg-red-400' },
  [HITLStatus.ESCALATED]: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20', dot: 'bg-purple-400' },
});

// ---------------------------------------------------------------------------
// Urgency sort order (for sorting pending requests)
// ---------------------------------------------------------------------------

export const URGENCY_SORT_ORDER = Object.freeze({
  [UrgencyLevel.CRITICAL]: 0,
  [UrgencyLevel.HIGH]: 1,
  [UrgencyLevel.NORMAL]: 2,
  [UrgencyLevel.LOW]: 3,
});
