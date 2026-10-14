import React from 'react';
import { motion } from 'framer-motion';
import { FileDown, Plus } from 'lucide-react';
import type { CitedText, MarketResearchReport, Source } from '../types';
import { Citations } from './Citations';
import { CompetitorTable } from './CompetitorTable';
import { ForcesPanel } from './ForcesPanel';
import { KeyFigures } from './KeyFigures';
import { ShareChart } from './ShareChart';
import { SourcesList } from './SourcesList';
import { formatDate, formatDuration } from '../lib/format';

interface ReportViewProps {
  report: MarketResearchReport;
  createdAt?: string;
  durationSeconds?: number | null;
  onNew: () => void;
}

const CitedList: React.FC<{ items: CitedText[]; sources: Source[] }> = ({ items, sources }) =>
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
    <p className="empty-note">The sources didn't cover this.</p>
  );

const reveal = {
  hidden: { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.25, 0.1, 0.25, 1] as const } },
};

const Panel: React.FC<{ id?: string; title: string; sub?: string; wide?: boolean; children: React.ReactNode }> = ({
  id, title, sub, wide, children,
}) => (
  <motion.section id={id} className={`panel glass${wide ? ' span-all' : ''}`} variants={reveal}>
    <h2>{title}</h2>
    {sub && <p className="panel-sub">{sub}</p>}
    {children}
  </motion.section>
);

export const ReportView: React.FC<ReportViewProps> = ({ report, createdAt, durationSeconds, onNew }) => {
  const s = report.sources;
  const shares = report.competitors.filter(c => c.market_share_percent !== null).length;
  const meta = [
    createdAt && formatDate(createdAt),
    `${s.length} sources`,
    `${report.competitors.length} companies`,
    durationSeconds && `researched in ${formatDuration(durationSeconds)}`,
  ].filter(Boolean);

  const sections = [
    { id: 'summary', label: 'Summary' },
    { id: 'market', label: 'Market' },
    { id: 'dynamics', label: 'Dynamics' },
    { id: 'customers', label: 'Customers' },
    { id: 'competition', label: 'Competition' },
    { id: 'strategy', label: 'Strategy' },
    { id: 'sources', label: 'Sources' },
  ];
  // Scrolls without touching the address, which identifies the report
  const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <motion.article initial="hidden" animate="visible" transition={{ staggerChildren: 0.05 }}>
      <motion.header className="report-header" variants={reveal}>
        <div>
          <div className="eyebrow">Market research brief</div>
          <h1>{report.industry_name}</h1>
          <div className="meta">{meta.join(' · ')}</div>
        </div>
        <div className="header-actions">
          <button className="button button-secondary" onClick={() => window.print()}>
            <FileDown size={16} aria-hidden="true" /> Export PDF
          </button>
          <button className="button button-secondary" onClick={onNew}>
            <Plus size={16} aria-hidden="true" /> New research
          </button>
        </div>
      </motion.header>

      <motion.nav className="section-nav" variants={reveal} aria-label="Report sections">
        {sections.map(section => (
          <button key={section.id} className="chip" onClick={() => jump(section.id)}>
            {section.label}
          </button>
        ))}
      </motion.nav>

      <div className="report-grid">
        <Panel id="summary" title="Executive summary" wide>
          <p className="summary-text">
            {report.executive_summary}
            <Citations ids={report.executive_summary_source_ids} sources={s} />
          </p>
        </Panel>

        <Panel id="market" title="Market size and growth" sub="Every number here appears word for word in the source it cites" wide>
          {report.key_figures.length ? (
            <KeyFigures figures={report.key_figures} sources={s} />
          ) : (
            <p className="empty-note">The sources gave no figures for the size or growth of this market.</p>
          )}
        </Panel>

        <div id="dynamics" className="span-all grid-3">
          <Panel title="Key trends" sub="Shifts shaping the market">
            <CitedList items={report.key_trends} sources={s} />
          </Panel>
          <Panel title="Growth drivers" sub="What pushes demand up">
            <CitedList items={report.growth_drivers} sources={s} />
          </Panel>
          <Panel title="Challenges" sub="Restraints, risks and barriers">
            <CitedList items={report.challenges} sources={s} />
          </Panel>
        </div>

        <Panel id="customers" title="Customer segments" sub="Who buys, and what they need">
          <CitedList items={report.customer_segments} sources={s} />
        </Panel>
        <Panel title="Whitespace opportunities" sub="Needs the current players leave open">
          <CitedList items={report.whitespace_opportunities} sources={s} />
        </Panel>

        <Panel id="competition" title="Competitive landscape" sub="Companies named in the sources, with what the sources say about them" wide>
          {report.competitors.length ? (
            <>
              {shares >= 2 && (
                <>
                  <h3 className="sub-heading">Market share</h3>
                  <ShareChart competitors={report.competitors} />
                  <div style={{ height: 24 }} />
                </>
              )}
              <CompetitorTable competitors={report.competitors} sources={s} />
            </>
          ) : (
            <p className="empty-note">No company was backed by the sources.</p>
          )}
        </Panel>

        {report.competitive_forces.length > 0 && (
          <Panel title="Industry forces" sub="Porter's five forces, rated from the evidence" wide>
            <ForcesPanel forces={report.competitive_forces} sources={s} />
          </Panel>
        )}

        <Panel id="strategy" title="Recommendations" sub="Moves the evidence supports">
          <CitedList items={report.recommendations} sources={s} />
        </Panel>
        <Panel title="Gaps and method" sub="What this brief can't tell you, and how it was made">
          {report.data_gaps.length > 0 && (
            <ul className="gaps">
              {report.data_gaps.map((gap, i) => <li key={i}>{gap}</li>)}
            </ul>
          )}
          <p className="method">
            Markey read {s.length} web sources{createdAt ? ` on ${formatDate(createdAt)}` : ''} and links every statement to
            the ones it came from.
            {report.removed_statements + report.removed_figures > 0 &&
              ` It removed ${report.removed_statements} statement${report.removed_statements === 1 ? '' : 's'} without a source and ${report.removed_figures} number${report.removed_figures === 1 ? '' : 's'} that didn't appear in the cited text.`}{' '}
            Treat it as a starting point and check key numbers before relying on them.
          </p>
        </Panel>

        <Panel id="sources" title="Sources" sub="Every numbered marker in this brief links to one of these pages" wide>
          <SourcesList sources={s} />
        </Panel>
      </div>
    </motion.article>
  );
};
