import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

// Master credentials (enterprise pre-provisioned)
const MASTER_USER = {
  username: 'admin',
  password: 'password123',
  displayName: 'Admin',
  email: 'admin@hitl-gateway.io',
  role: 'SecOps_Lead',
};

// Mock JWT (simulates real token structure)
function createMockToken(user) {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const payload = btoa(JSON.stringify({
    sub: user.username,
    name: user.displayName,
    email: user.email,
    role: user.role,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 86400, // 24h
  }));
  const signature = btoa('mock-signature');
  return `${header}.${payload}.${signature}`;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const stored = localStorage.getItem('hitl_auth');
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        // Check token expiry
        const payload = JSON.parse(atob(parsed.token.split('.')[1]));
        if (payload.exp * 1000 > Date.now()) {
          setUser(parsed);
        } else {
          localStorage.removeItem('hitl_auth');
        }
      } catch {
        localStorage.removeItem('hitl_auth');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback((username, password) => {
    if (username === MASTER_USER.username && password === MASTER_USER.password) {
      const token = createMockToken(MASTER_USER);
      const session = {
        username: MASTER_USER.username,
        displayName: MASTER_USER.displayName,
        email: MASTER_USER.email,
        role: MASTER_USER.role,
        token,
      };
      localStorage.setItem('hitl_auth', JSON.stringify(session));
      setUser(session);
      return { success: true };
    }
    return { success: false, error: 'Invalid credentials' };
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('hitl_auth');
    setUser(null);
  }, []);

  const changePassword = useCallback((currentPassword, newPassword) => {
    if (currentPassword !== MASTER_USER.password) {
      return { success: false, error: 'Current password is incorrect' };
    }
    if (newPassword.length < 6) {
      return { success: false, error: 'New password must be at least 6 characters' };
    }
    // In a real app this would call the backend
    MASTER_USER.password = newPassword;
    return { success: true };
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, changePassword }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
