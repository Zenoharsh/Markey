import React, { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import type { AgentStatus } from '../types';
import { formatDuration } from '../lib/format';

const STEPS = [
  { stage: 'scoping', label: 'Defining the market' },
  { stage: 'researching', label: 'Four analysts researching in parallel' },
  { stage: 'writing', label: 'Writing the summary and recommendations' },
];

const AGENTS = [
  { key: 'sizing', label: 'Market sizing' },
  { key: 'competition', label: 'Competitive landscape' },
  { key: 'demand', label: 'Customers and demand' },
  { key: 'trends', label: 'Trends and risks' },
];

interface ProgressStepsProps {
  topic: string;
  stage: string | null;
  message: string | null;
  agents: Record<string, AgentStatus>;
  startedAt: number;
}

const StepIcon: React.FC<{ state: 'done' | 'active' | 'todo'; number?: number; size?: number }> = ({ state, number, size = 20 }) => (
  <span className="step-icon" aria-hidden="true">
    {state === 'done' && <Check size={size - 5} strokeWidth={3} />}
    {state === 'active' && <Loader2 size={size} className="spin" />}
    {state === 'todo' && number !== undefined && <span style={{ fontSize: 12, fontWeight: 600 }}>{number}</span>}
  </span>
);

export const ProgressSteps: React.FC<ProgressStepsProps> = ({ topic, stage, message, agents, startedAt }) => {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const current = Math.max(0, STEPS.findIndex(s => s.stage === stage));

  return (
    <section className="progress-card glass" aria-live="polite">
      <div className="eyebrow">Researching</div>
      <h2>{topic}</h2>
      <ol className="steps">
        {STEPS.map((step, i) => {
          const state = i < current ? 'done' : i === current ? 'active' : 'todo';
          return (
            <li key={step.stage} className={`step step-${state}`}>
              <StepIcon state={state} number={i + 1} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="step-label">{step.label}</div>
                {state === 'active' && message && step.stage !== 'researching' && (
                  <div className="step-detail">{message}</div>
                )}
                {step.stage === 'researching' && state !== 'todo' && (
                  <ul className="agents">
                    {AGENTS.map(agent => {
                      const status = agents[agent.key];
                      const agentState = status?.done || state === 'done' ? 'done' : 'active';
                      return (
                        <li key={agent.key} className={`agent step-${agentState}`}>
                          <StepIcon state={agentState} size={16} />
                          <span className="agent-name">{agent.label}</span>
                          <span className="agent-status">{status?.message ?? 'Starting'}</span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <div className="progress-foot">
        <span>You can close this page. The report keeps going and appears in History.</span>
        <span style={{ fontVariantNumeric: 'tabular-nums', flex: 'none' }}>{formatDuration((now - startedAt) / 1000)}</span>
      </div>
    </section>
  );
};
