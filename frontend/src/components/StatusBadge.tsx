import React from 'react';
import { AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import type { RunStatus } from '../types';

const LABELS: Record<RunStatus, string> = { done: 'Ready', running: 'Researching', failed: 'Failed' };

export const StatusBadge: React.FC<{ status: RunStatus }> = ({ status }) => (
  <span className={`status status-${status}`}>
    {status === 'done' && <CheckCircle2 size={13} aria-hidden="true" />}
    {status === 'failed' && <AlertCircle size={13} aria-hidden="true" />}
    {status === 'running' && <Loader2 size={13} className="spin" aria-hidden="true" />}
    {LABELS[status]}
  </span>
);
