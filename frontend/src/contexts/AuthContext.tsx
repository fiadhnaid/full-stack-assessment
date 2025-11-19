/**
 * Authentication context for managing user state and tokens.
 * Stores access token in memory (not localStorage) for security.
 */

import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { setAccessToken, refreshToken as apiRefreshToken } from '@/lib/api';

interface User {
  user_id: string;
  tenant_id: string;
  email: string;
}

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (accessToken: string, userData: User) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Try to refresh token on mount (silent re-authentication)
  useEffect(() => {
    const initAuth = async () => {
      try {
        const response = await apiRefreshToken();
        const { access_token, user_id, tenant_id, email } = response.data;

        setAccessToken(access_token);
        setUser({ user_id, tenant_id, email });
      } catch (error) {
        // No valid refresh token, user needs to login
        setAccessToken(null);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = (accessToken: string, userData: User) => {
    setAccessToken(accessToken);
    setUser(userData);
  };

  const logout = () => {
    setAccessToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
