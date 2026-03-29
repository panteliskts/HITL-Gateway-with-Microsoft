import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, Eye, EyeOff, AlertCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTheme } from '../context/ThemeContext';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const { theme } = useTheme();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    // Simulate network delay
    await new Promise(r => setTimeout(r, 600));

    const result = login(username, password);
    if (result.success) {
      navigate('/dashboard', { replace: true });
    } else {
      setError(result.error);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-hitl-base p-4">
      {/* Background grid */}
      <div className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(${theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'} 1px, transparent 1px), linear-gradient(90deg, ${theme === 'dark' ? 'rgba(255,255,255,0.1)' : 'rgba(0,0,0,0.1)'} 1px, transparent 1px)`,
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative w-full max-w-[400px]">
        {/* Brand header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-hitl-active rounded-xl mb-4">
            <Shield size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold text-hitl-text-primary font-heading tracking-tight">
            HITL GATEWAY
          </h1>
          <p className="text-sm text-hitl-muted mt-1">
            Enterprise AI Governance Platform
          </p>
        </div>

        {/* Login card */}
        <div className="bg-hitl-surface border border-hitl-border rounded-xl p-8 shadow-xl">
          <h2 className="text-lg font-semibold text-hitl-text-primary mb-1">
            Sign in
          </h2>
          <p className="text-xs text-hitl-muted mb-6">
            Access the HITL Command Center
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="flex items-center gap-2 px-3 py-2.5 bg-red-500/10 border border-red-500/20 rounded-lg">
                <AlertCircle size={14} className="text-red-400 flex-shrink-0" />
                <span className="text-xs text-red-400">{error}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-hitl-text-secondary mb-1.5">
                Username
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter your username"
                autoComplete="username"
                className="w-full px-3 py-2.5 bg-hitl-input border border-hitl-border rounded-lg text-sm text-hitl-text-primary placeholder:text-hitl-muted focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30 transition-colors"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-hitl-text-secondary mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  autoComplete="current-password"
                  className="w-full px-3 py-2.5 pr-10 bg-hitl-input border border-hitl-border rounded-lg text-sm text-hitl-text-primary placeholder:text-hitl-muted focus:outline-none focus:border-hitl-active focus:ring-1 focus:ring-hitl-active/30 transition-colors"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-hitl-muted hover:text-hitl-text-secondary transition-colors"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-hitl-active hover:bg-blue-500 disabled:bg-hitl-active/50 text-white text-sm font-medium rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                'Sign In'
              )}
            </button>
          </form>

          <div className="mt-6 pt-4 border-t border-hitl-border">
            <p className="text-[10px] text-hitl-muted text-center">
              This is an enterprise internal tool. Credentials are pre-provisioned by your IT administrator.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 text-center">
          <div className="flex items-center justify-center gap-2 text-[10px] text-hitl-muted">
            <span>Powered by</span>
            {['Azure Durable Functions', 'Microsoft Teams'].map(svc => (
              <span key={svc} className="px-1.5 py-0.5 bg-hitl-active/10 text-hitl-active border border-hitl-active/20 rounded text-[9px]">
                {svc}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
