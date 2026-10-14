import React from 'react';
import { motion } from 'framer-motion';
import { Plus } from 'lucide-react';
import type { CitedText, MarketResearchReport, Source } from '../types';
import { Citations } from './Citations';
import { CompetitorTable } from './CompetitorTable';
import { SourcesList } from './SourcesList';
import { StrengthChart } from './StrengthChart';
import { formatDate, formatDuration } from '../lib/format';

interface ReportViewProps {
  report: MarketResearchReport;
  createdAt?: string;
  durationSeconds?: number | null;
  onNew: () => void;
}

const CitedList: React.FC<{ items: CitedText[]; sources: Source[]; empty: string }> = ({ items, sources, empty }) =>
  items.length ? (
    <ol className="cited-list">
      {items.map((item, i) => (
        <li key={i}>
          <span>
            {item.text}
            <Citations ids={item.source_ids} sources={sources} />
          </span>
        </li>
      ))}
    </ol>
  ) : (
    <p className="empty-note">{empty}</p>
  );

const reveal = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] as const } },
};

export const ReportView: React.FC<ReportViewProps> = ({ report, createdAt, durationSeconds, onNew }) => {
  const meta = [
    createdAt && formatDate(createdAt),
    `${report.sources.length} sources`,
    `${report.competitors.length} competitors`,
    durationSeconds && `researched in ${formatDuration(durationSeconds)}`,
  ].filter(Boolean);

  return (
    <motion.article initial="hidden" animate="visible" transition={{ staggerChildren: 0.06 }}>
      <motion.header className="report-header" variants={reveal}>
        <div>
          <div className="eyebrow">Market report</div>
          <h1>{report.industry_name}</h1>
          <div className="meta">{meta.join(' · ')}</div>
        </div>
        <button className="button button-secondary" onClick={onNew}>
          <Plus size={16} aria-hidden="true" /> New research
        </button>
      </motion.header>

      <div className="report-grid">
        <motion.section className="panel glass span-2" variants={reveal}>
          <h2>Executive summary</h2>
          <p className="panel-sub">What the sources say, in brief</p>
          <p className="summary-text">
            {report.executive_summary}
            <Citations ids={report.executive_summary_source_ids} sources={report.sources} />
          </p>
        </motion.section>

        <motion.section className="panel glass" variants={reveal}>
          <h2>Key trends</h2>
          <p className="panel-sub">Shifts shaping the market</p>
          <CitedList items={report.key_trends} sources={report.sources} empty="No trend was backed by the sources." />
        </motion.section>

        <motion.section className="panel glass" variants={reveal}>
          <h2>Whitespace opportunities</h2>
          <p className="panel-sub">Needs the current players leave open</p>
          <CitedList
            items={report.whitespace_opportunities}
            sources={report.sources}
            empty="No opportunity was backed by the sources."
          />
        </motion.section>

        <motion.section className="panel glass span-2" variants={reveal}>
          <h2>Competitive landscape</h2>
          {report.competitors.length ? (
            <>
              <p className="panel-sub">Market strength, 0 to 10, as estimated by the model from the cited sources</p>
              <StrengthChart competitors={report.competitors} />
              <div style={{ height: 24 }} />
              <CompetitorTable competitors={report.competitors} sources={report.sources} />
            </>
          ) : (
            <p className="empty-note" style={{ marginTop: 8 }}>No competitor was backed by the sources.</p>
          )}
        </motion.section>

        <motion.section className="panel glass span-2" variants={reveal}>
          <h2>Sources</h2>
          <p className="panel-sub">Every numbered marker in this report links to one of these pages</p>
          <SourcesList sources={report.sources} />
        </motion.section>
      </div>
    </motion.article>
  );
};
