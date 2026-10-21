import type { MarketResearchReport, ResearchEvent, RunDetail, RunSummary } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';
const UNREACHABLE = 'Could not reach the Markey backend. Check that it is running.';

export class ResearchError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...init?.headers },
    });
  } catch {
    throw new ResearchError(UNREACHABLE);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new ResearchError(typeof detail === 'string' ? detail : `The request failed (${response.status}).`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

// Starts researching a topic in the background and returns the run id
export const startResearch = async (query: string): Promise<string> =>
  (await request<{ id: string }>('/research/jobs', { method: 'POST', body: JSON.stringify({ query }) })).id;

export const listReports = () => request<RunSummary[]>('/reports');
export const getReport = (id: string) => request<RunDetail>(`/reports/${encodeURIComponent(id)}`);
export const deleteReport = (id: string) =>
  request<void>(`/reports/${encodeURIComponent(id)}`, { method: 'DELETE' });

// Follows a run from its first event, calling onProgress per stage, and resolves with the finished report.
// Runs continue on the server, so this can be called again after a reload or dropped connection.
export const followResearch = async (
  id: string,
  onProgress: (stage: string, message: string, agent?: string, done?: boolean) => void,
  signal?: AbortSignal,
): Promise<MarketResearchReport> => {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/research/jobs/${encodeURIComponent(id)}/events`, { signal });
  } catch (err) {
    if (signal?.aborted) throw err;
    throw new ResearchError(UNREACHABLE);
  }
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null);
    throw new ResearchError(typeof body?.detail === 'string' ? body.detail : 'This report could not be found.');
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
      if (event.type === 'progress') onProgress(event.stage, event.message, event.agent, event.done);
      else if (event.type === 'report') return event.report;
      else if (event.type === 'error') throw new ResearchError(event.detail);
    }
  }
  throw new ResearchError('The connection to the backend dropped. Reopen this report to keep following it.');
};

export const getErrorMessage = (err: unknown): string =>
  err instanceof ResearchError ? err.message : 'Something went wrong. Please try again.';
