import React, { useEffect, useState } from 'react';
import { Check, Loader2 } from 'lucide-react';
import { formatDuration } from '../lib/format';

const STEPS = [
  { stage: 'searching', label: 'Searching the web' },
  { stage: 'reading', label: 'Reading sources' },
  { stage: 'analyzing', label: 'Finding the relevant evidence' },
  { stage: 'writing', label: 'Writing the report' },
];

interface ProgressStepsProps {
  topic: string;
  stage: string | null;
  message: string | null;
  startedAt: number;
}

export const ProgressSteps: React.FC<ProgressStepsProps> = ({ topic, stage, message, startedAt }) => {
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
              <span className="step-icon" aria-hidden="true">
                {state === 'done' && <Check size={15} strokeWidth={3} />}
                {state === 'active' && <Loader2 size={20} className="spin" />}
                {state === 'todo' && <span style={{ fontSize: 12, fontWeight: 600 }}>{i + 1}</span>}
              </span>
              <div>
                <div className="step-label">{step.label}</div>
                {state === 'active' && message && <div className="step-detail">{message}</div>}
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
