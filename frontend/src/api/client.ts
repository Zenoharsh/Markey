import axios from 'axios';
import type { MarketResearchReport } from '../types';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchResearch = async (query: string): Promise<MarketResearchReport> => {
  const response = await apiClient.post<MarketResearchReport>('/research', { query });
  return response.data;
};
