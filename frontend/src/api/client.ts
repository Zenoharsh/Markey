import axios from 'axios';
import type { MarketResearchReport, ResearchEvent } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const fetchResearch = async (query: string): Promise<MarketResearchReport> => {
  const response = await apiClient.post<MarketResearchReport>('/research', { query });
  return response.data;
};

export class ResearchError extends Error {}

// Runs a research job, calling onProgress for each stage, and resolves with the finished report
export const streamResearch = async (
  query: string,
  onProgress: (message: string) => void,
): Promise<MarketResearchReport> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/research/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
  } catch {
    throw new ResearchError('Could not reach the backend. Please ensure it is running.');
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ResearchError(typeof detail === 'string' ? detail : 'The research request was rejected.');
  }

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += value;
    // Server-sent events are separated by a blank line
    const events = buffer.split('\n\n');
    buffer = events.pop() ?? '';
    for (const raw of events) {
      if (!raw.startsWith('data: ')) continue;
      const event = JSON.parse(raw.slice('data: '.length)) as ResearchEvent;
      if (event.type === 'progress') onProgress(event.message);
      else if (event.type === 'report') return event.report;
      else throw new ResearchError(event.detail);
    }
  }
  throw new ResearchError('The connection closed before the report was finished.');
};

// Prefers the backend's explanation (e.g. "The model declined to answer this query.")
export const getErrorMessage = (err: unknown): string => {
  if (err instanceof ResearchError) return err.message;
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === 'string') return detail;
    if (!err.response) return 'Could not reach the backend. Please ensure it is running.';
  }
  return 'An error occurred during research. Please try again.';
};
