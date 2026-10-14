import React from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Trash2, X } from 'lucide-react';
import type { RunSummary } from '../types';
import { StatusBadge } from './StatusBadge';
import { relativeTime } from '../lib/format';

interface HistoryDrawerProps {
  open: boolean;
  runs: RunSummary[];
  activeId: string | null;
  onClose: () => void;
  onOpen: (id: string) => void;
  onDelete: (run: RunSummary) => void;
}

export const HistoryDrawer: React.FC<HistoryDrawerProps> = ({ open, runs, activeId, onClose, onOpen, onDelete }) => (
  <AnimatePresence>
    {open && (
      <>
        <motion.div className="scrim" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
        <motion.aside
          className="drawer glass"
          role="dialog"
          aria-label="Report history"
          initial={{ x: -24, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: -24, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 420, damping: 36 }}
          onKeyDown={e => e.key === 'Escape' && onClose()}
        >
          <div className="drawer-head">
            <h2>History</h2>
            <button className="icon-button" onClick={onClose} aria-label="Close history" autoFocus>
              <X size={18} />
            </button>
          </div>
          {runs.length === 0 ? (
            <p className="empty-note" style={{ padding: '0 18px' }}>Reports you run will appear here.</p>
          ) : (
            <ul className="drawer-list">
              {runs.map(run => (
                <li key={run.id} className={`history-item${run.id === activeId ? ' active' : ''}`}>
                  <button className="history-open" onClick={() => onOpen(run.id)}>
                    <strong>{run.industry_name ?? run.topic}</strong>
                    <span className="history-meta">
                      <StatusBadge status={run.status} />
                      <span className="meta">{relativeTime(run.created_at)}</span>
                    </span>
                  </button>
                  <button
                    className="icon-button history-delete"
                    onClick={() => onDelete(run)}
                    aria-label={`Delete ${run.topic}`}
                  >
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </motion.aside>
      </>
    )}
  </AnimatePresence>
);
