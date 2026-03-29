import React, { useState, useEffect } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Inbox,
  ScrollText,
  Play,
  Shield,
  ChevronRight,
  Sun,
  Moon,
  LogOut,
  User,
  Lock,
  X,
  Eye,
  EyeOff,
  Check,
  AlertCircle,
  Menu,
} from 'lucide-react';
import HelpBot from './HelpBot';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, testId: 'sidebar-nav-dashboard' },
  { to: '/demo', label: 'Live Demo', icon: Play, testId: 'sidebar-nav-demo', highlight: true },
  { to: '/pending', label: 'Pending Inbox', icon: Inbox, testId: 'sidebar-nav-pending' },
  { to: '/audit', label: 'Audit Trail', icon: ScrollText, testId: 'sidebar-nav-audit' },
];

function SidebarLink({ to, label, icon: Icon, testId, highlight, onClick }) {
  return (
    <NavLink
      to={to}
      data-testid={testId}
      onClick={onClick}
      className={({ isActive }) =>
        `nav-item ${isActive ? 'active' : ''} ${highlight && !isActive ? 'text-hitl-active' : ''}`
      }
    >
      <Icon size={18} strokeWidth={1.5} />
      <span className="flex-1">{label}</span>
      {highlight && (
        <span className="w-1.5 h-1.5 rounded-full bg-hitl-active animate-pulse" />
      )}
      <ChevronRight size={14} className="opacity-0 group-hover:opacity-50 transition-opacity" />
    </NavLink>
  );
}

/* ── Change Password Modal ────────────────────────────────────────────── */

function ChangePasswordModal({ onClose }) {
  const { changePassword } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNext, setShowNext] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = (e) => {
    e.preventDefault();
    setError('');
    if (next !== confirm) {
      setError('New passwords do not match');
      return;
    }
    const result = changePassword(current, next);
    if (result.success) {
      setSuccess(true);
      setTimeout(onClose, 1500);
    } else {
      setError(result.error);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-hitl-surface border border-hitl-border rounded-xl shadow-2xl w-full max-w-[400px] mx-4">
        <div className="flex items-center justify-between px-5 py-4 border-b border-hitl-border">
          <div className="flex items-center gap-2">
            <Lock size={16} className="text-hitl-active" />
            <span className="text-sm font-semibold text-hitl-text-primary">Change Password</span>
          </div>
          <button onClick={onClose} className="text-hitl-muted hover:text-hitl-text-primary transition-colors">
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="flex items-center gap-2 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
              <AlertCircle size={14} className="text-red-400" />
              <span className="text-xs text-red-400">{error}</span>
            </div>
          )}
          {success && (
            <div className="flex items-center gap-2 px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
              <Check size={14} className="text-green-400" />
              <span className="text-xs text-green-400">Password changed successfully</span>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-hitl-text-secondary mb-1.5">Current Password</label>
            <div className="relative">
              <input
                type={showCurrent ? 'text' : 'password'}
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className="w-full px-3 py-2 pr-9 bg-hitl-input border border-hitl-border rounded-lg text-sm text-hitl-text-primary focus:outline-none focus:border-hitl-active"
                required
              />
              <button type="button" onClick={() => setShowCurrent(!showCurrent)} className="absolute right-3 top-1/2 -translate-y-1/2 text-hitl-muted">
                {showCurrent ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-hitl-text-secondary mb-1.5">New Password</label>
            <div className="relative">
              <input
                type={showNext ? 'text' : 'password'}
                value={next}
                onChange={(e) => setNext(e.target.value)}
                className="w-full px-3 py-2 pr-9 bg-hitl-input border border-hitl-border rounded-lg text-sm text-hitl-text-primary focus:outline-none focus:border-hitl-active"
                required
                minLength={6}
              />
              <button type="button" onClick={() => setShowNext(!showNext)} className="absolute right-3 top-1/2 -translate-y-1/2 text-hitl-muted">
                {showNext ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-hitl-text-secondary mb-1.5">Confirm New Password</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="w-full px-3 py-2 bg-hitl-input border border-hitl-border rounded-lg text-sm text-hitl-text-primary focus:outline-none focus:border-hitl-active"
              required
            />
          </div>

          <div className="flex gap-2 pt-2">
            <button type="button" onClick={onClose} className="flex-1 py-2 text-sm border border-hitl-border rounded-lg text-hitl-text-secondary hover:bg-hitl-surface-hover transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={success} className="flex-1 py-2 text-sm bg-hitl-active text-white rounded-lg hover:bg-blue-500 disabled:opacity-50 transition-colors">
              Update
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

/* ── Layout ────────────────────────────────────────────────────────────── */

export default function Layout() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Close mobile menu on resize to desktop
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) setMobileMenuOpen(false);
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const sidebarContent = (
    <>
      {/* Logo / Brand */}
      <div className="h-16 flex items-center gap-3 px-5 border-b border-hitl-border">
        <div className="w-8 h-8 bg-hitl-active rounded-[4px] flex items-center justify-center">
          <Shield size={18} className="text-white" />
        </div>
        <div>
          <div className="font-heading text-sm font-bold tracking-tight text-hitl-text-primary" data-testid="app-brand">
            HITL GATEWAY
          </div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted">
            Command Center
          </div>
        </div>
        {/* Mobile close button */}
        <button
          onClick={() => setMobileMenuOpen(false)}
          className="md:hidden ml-auto p-1 text-hitl-muted hover:text-hitl-text-primary transition-colors"
        >
          <X size={20} />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 space-y-1 px-2" data-testid="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <SidebarLink key={item.to} {...item} onClick={() => setMobileMenuOpen(false)} />
        ))}
      </nav>

      {/* Azure Badge */}
      <div className="px-5 py-3 border-t border-hitl-border">
        <div className="flex items-center gap-2 mb-2">
          <div className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted">Powered by</div>
        </div>
        <div className="flex flex-wrap gap-1">
          {['Durable Functions', 'Event Grid', 'App Insights'].map(svc => (
            <span key={svc} className="px-2 py-0.5 text-[9px] bg-hitl-active/10 text-hitl-active border border-hitl-active/20 rounded">
              {svc}
            </span>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-hitl-border">
        <div className="text-[10px] uppercase tracking-[0.2em] text-hitl-muted">
          System Status
        </div>
        <div className="mt-2 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-hitl-approved animate-pulse" />
          <span className="text-xs text-hitl-secondary">All systems operational</span>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex h-screen bg-hitl-base overflow-hidden" data-testid="app-layout">
      {/* Desktop Sidebar — hidden on mobile */}
      <aside
        className="hidden md:flex w-[240px] flex-shrink-0 bg-hitl-base border-r border-hitl-border flex-col"
        data-testid="sidebar"
      >
        {sidebarContent}
      </aside>

      {/* Mobile Sidebar Overlay */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)} />
          {/* Drawer */}
          <aside className="absolute left-0 top-0 h-full w-[280px] bg-hitl-base border-r border-hitl-border flex flex-col shadow-2xl animate-slide-in">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar */}
        <header className="h-12 flex-shrink-0 bg-hitl-surface border-b border-hitl-border flex items-center justify-between md:justify-end px-3 md:px-4 gap-2">
          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileMenuOpen(true)}
            className="md:hidden w-8 h-8 flex items-center justify-center rounded-lg text-hitl-muted hover:text-hitl-text-primary hover:bg-hitl-surface-hover transition-colors"
          >
            <Menu size={20} />
          </button>

          {/* Mobile brand */}
          <div className="md:hidden flex items-center gap-2">
            <div className="w-6 h-6 bg-hitl-active rounded-[3px] flex items-center justify-center">
              <Shield size={12} className="text-white" />
            </div>
            <span className="font-heading text-xs font-bold tracking-tight text-hitl-text-primary">HITL</span>
          </div>

          <div className="flex items-center gap-2">
            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="w-8 h-8 flex items-center justify-center rounded-lg text-hitl-muted hover:text-hitl-text-primary hover:bg-hitl-surface-hover transition-colors"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>

            {/* User Menu */}
            <div className="relative">
              <button
                onClick={() => setShowUserMenu(!showUserMenu)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-hitl-surface-hover transition-colors"
              >
                <div className="w-6 h-6 rounded-full bg-hitl-active/20 flex items-center justify-center">
                  <User size={13} className="text-hitl-active" />
                </div>
                <span className="text-xs font-medium text-hitl-text-primary hidden sm:inline">{user?.displayName}</span>
              </button>

              {showUserMenu && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowUserMenu(false)} />
                  <div className="absolute right-0 top-full mt-1 w-52 bg-hitl-surface border border-hitl-border rounded-lg shadow-xl z-50 py-1">
                    <div className="px-3 py-2 border-b border-hitl-border">
                      <div className="text-xs font-medium text-hitl-text-primary">{user?.displayName}</div>
                      <div className="text-[10px] text-hitl-muted">{user?.email}</div>
                      <div className="mt-1">
                        <span className="px-1.5 py-0.5 text-[9px] bg-hitl-active/10 text-hitl-active rounded">
                          {user?.role}
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => { setShowUserMenu(false); setShowChangePassword(true); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-hitl-text-secondary hover:text-hitl-text-primary hover:bg-hitl-surface-hover transition-colors text-left"
                    >
                      <Lock size={13} /> Change Password
                    </button>
                    <button
                      onClick={() => { setShowUserMenu(false); logout(); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors text-left"
                    >
                      <LogOut size={13} /> Sign Out
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto" data-testid="main-content">
          <Outlet />
        </main>
      </div>

      {/* Help Bot */}
      <HelpBot />

      {/* Change Password Modal */}
      {showChangePassword && <ChangePasswordModal onClose={() => setShowChangePassword(false)} />}
    </div>
  );
}
