/**
 * API client with authentication handling.
 * Automatically attaches access token and handles refresh on 401.
 */

import axios from 'axios';

// Create axios instance
const api = axios.create({
  baseURL: 'http://localhost:8000',
  withCredentials: true, // Required for cookies
});

// Token storage (in memory for security)
let accessToken: string | null = null;

export const setAccessToken = (token: string | null) => {
  accessToken = token;
};

export const getAccessToken = () => accessToken;

// Request interceptor - attach access token
api.interceptors.request.use(
  (config) => {
    if (accessToken) {
      config.headers.Authorization = `Bearer ${accessToken}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor - handle 401 errors
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // Don't retry for auth endpoints (prevents infinite loop)
    const isAuthEndpoint = originalRequest.url?.includes('/auth/');

    // If 401 and not already retrying and not an auth endpoint, try to refresh token
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
      originalRequest._retry = true;

      try {
        // Try to refresh the token
        const response = await axios.post(
          'http://localhost:8000/auth/refresh',
          {},
          { withCredentials: true }
        );

        const newToken = response.data.access_token;
        setAccessToken(newToken);

        // Retry original request with new token
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, user needs to login again
        setAccessToken(null);
        // Only redirect if not already on login page
        if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
          window.location.href = '/login';
        }
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;

// ============================================
// API Functions
// ============================================

// Auth
export const getTenants = () => api.get('/auth/tenants');
export const register = (data: { email: string; password: string; tenant_id: string }) =>
  api.post('/auth/register', data);
export const login = (data: { email: string; password: string }) =>
  api.post('/auth/login', data);
export const refreshToken = () =>
  api.post('/auth/refresh');
export const logout = () =>
  api.post('/auth/logout');

// Datasets
export const listDatasets = () => api.get('/datasets');
export const uploadDataset = (file: File) => {
  const formData = new FormData();
  formData.append('file', file);
  return api.post('/datasets', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
export const getDataset = (id: string) => api.get(`/datasets/${id}`);
export const aggregateDataset = (
  id: string,
  data: { group_by: string; metrics: string[] }
) => api.post(`/datasets/${id}/aggregate`, data);
export const deleteDataset = (id: string) => api.delete(`/datasets/${id}`);
