import axios from 'axios';
import type { MarketResearchReport } from '../types';

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchResearch = async (query: string): Promise<MarketResearchReport> => {
  const response = await apiClient.post<MarketResearchReport>('/research', { query });
  return response.data;
};

// Prefers the backend's explanation (e.g. "The model declined to answer this query.")
export const getErrorMessage = (err: unknown): string => {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (!err.response) return 'Could not reach the backend. Please ensure it is running.';
  }
  return 'An error occurred during research. Please try again.';
};
