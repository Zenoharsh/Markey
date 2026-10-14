import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { Source } from '../types';
import { hostname } from '../lib/format';

const CARD_HALF_WIDTH = 150;

// One numbered marker. Its hover card is drawn above everything else and kept inside the window,
// so it is never clipped by a scrolling table or covered by neighbouring text.
const Cite: React.FC<{ source: Source }> = ({ source }) => {
  const ref = useRef<HTMLAnchorElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number; below: boolean } | null>(null);

  const show = () => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const below = rect.top < 110;
    const x = Math.min(Math.max(rect.left + rect.width / 2, CARD_HALF_WIDTH + 8), window.innerWidth - CARD_HALF_WIDTH - 8);
    setPos({ x, y: below ? rect.bottom + 8 : rect.top - 8, below });
  };
  const hide = () => setPos(null);

  useEffect(() => {
    if (!pos) return;
    window.addEventListener('scroll', hide, true);
    return () => window.removeEventListener('scroll', hide, true);
  }, [pos]);

  return (
    <span className="cite">
      <a
        ref={ref}
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`Source ${source.id}: ${source.title}`}
        onPointerEnter={show}
        onPointerLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        {source.id}
      </a>
      {pos &&
        createPortal(
          <span
            className="cite-card"
            role="tooltip"
            style={{ left: pos.x, top: pos.y, transform: pos.below ? 'translateX(-50%)' : 'translate(-50%, -100%)' }}
          >
            {source.title}
            <span>{hostname(source.url)}</span>
          </span>,
          document.body,
        )}
    </span>
  );
};

export const Citations: React.FC<{ ids: number[]; sources: Source[] }> = ({ ids, sources }) => (
  <>
    {ids.map(id => {
      const source = sources.find(s => s.id === id);
      return source ? <Cite key={id} source={source} /> : null;
    })}
  </>
);
