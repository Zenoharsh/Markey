import React from 'react';
import { motion, type Variants } from 'framer-motion';

export const SkeletonLoader: React.FC = () => {
  const pulseVariant: Variants = {
    animate: {
      opacity: [0.5, 1, 0.5],
      transition: { duration: 1.5, repeat: Infinity, ease: "easeInOut" }
    }
  };

  const blockStyle = (height: string, width: string = '100%') => ({
    height, width, borderRadius: '8px', backgroundColor: 'rgba(163, 177, 198, 0.2)'
  });

  return (
    <motion.div 
      variants={pulseVariant} 
      animate="animate" 
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: '24px'
      }}
    >
      {/* Top Left: Header */}
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '16px', padding: '0 24px' }}>
        <div className="neu-pressed" style={blockStyle('48px', '80%')} />
        <div className="neu-pressed" style={blockStyle('48px', '60%')} />
      </div>

      {/* Top Right: Chart */}
      <div className="neu-flat" style={{ minHeight: '340px', borderRadius: '16px', padding: '24px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-around' }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} className="neu-pressed" style={{ width: '15%', height: `${Math.random() * 50 + 30}%`, borderRadius: '8px 8px 0 0' }} />
        ))}
      </div>

      {/* Middle Left: Summary */}
      <div className="neu-flat" style={{ borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="neu-pressed" style={blockStyle('24px', '50%')} />
        <div className="neu-pressed" style={blockStyle('16px')} />
        <div className="neu-pressed" style={blockStyle('16px')} />
        <div className="neu-pressed" style={blockStyle('16px', '80%')} />
      </div>

      {/* Middle Right: Whitespace */}
      <div className="neu-flat" style={{ borderRadius: '16px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div className="neu-pressed" style={blockStyle('24px', '50%')} />
        <div className="neu-pressed" style={blockStyle('16px', '90%')} />
        <div className="neu-pressed" style={blockStyle('16px', '75%')} />
      </div>

      {/* Bottom: Competitors */}
      <div style={{ gridColumn: 'span 2', display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '24px' }}>
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="neu-flat" style={{ borderRadius: '16px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="neu-pressed" style={blockStyle('24px', '70%')} />
            <div className="neu-pressed" style={blockStyle('12px', '40%')} />
            <div className="neu-pressed" style={blockStyle('32px', '100%')} />
            <div className="neu-pressed" style={blockStyle('12px', '40%')} />
            <div className="neu-pressed" style={blockStyle('32px', '100%')} />
          </div>
        ))}
      </div>
    </motion.div>
  );
};
