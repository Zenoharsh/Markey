import { useState } from 'react';
import { motion } from 'framer-motion';
import { SearchBar } from './components/SearchBar';
import { Card } from './components/Card';
import { CompetitorChart } from './components/CompetitorChart';
import { SkeletonLoader } from './components/SkeletonLoader';
import { fetchResearch } from './api/client';
import type { MarketResearchReport } from './types';

function App() {
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<MarketResearchReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (query: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchResearch(query);
      setReport(data);
    } catch (err: any) {
      setError(err.message || 'An error occurred during research. Please ensure the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const itemVariant = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: { opacity: 1, scale: 1 }
  };

  return (
    <div style={{ height: '100vh', width: '100vw', display: 'flex', flexDirection: 'column', backgroundColor: 'var(--bg-color)', overflow: 'hidden' }}>
      
      {/* Skeletons or Bento Grid */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '24px', paddingBottom: '150px' }}>
        
        {!loading && !report && (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center' }}>
            <h1 style={{ fontSize: '4rem', marginBottom: '16px', color: '#2d3748' }}>Market Analyst AI</h1>
            <p style={{ color: '#718096', fontSize: '1.2rem', fontWeight: 500 }}>Generic industry analysis powered by RAG</p>
          </div>
        )}

        {loading && <SkeletonLoader />}

        {!loading && report && (
          <motion.div 
            initial="hidden"
            animate="visible"
            transition={{ staggerChildren: 0.1 }}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 1fr',
              gap: '24px'
            }}
          >
            {/* Top Left: Header */}
            <motion.div variants={itemVariant} style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '0 24px' }}>
               <h2 style={{ fontSize: '3rem', color: '#2d3748', lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: '16px' }}>
                  {report.industry_name} <br/> Industry
               </h2>
               <p style={{ color: '#718096', fontSize: '1.1rem' }}>Generated Analysis Report</p>
            </motion.div>

            {/* Top Right: Chart */}
            <motion.div variants={itemVariant} style={{ minHeight: '340px' }}>
               <CompetitorChart competitors={report.competitors} />
            </motion.div>

            {/* Middle Left: Summary */}
            <motion.div variants={itemVariant} style={{ minHeight: 0 }}>
               <Card style={{ margin: 0, padding: '24px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ fontSize: '1.2rem', marginBottom: '12px', color: '#4a5568' }}>Executive Summary</h3>
                  <div style={{ flex: 1, paddingRight: '8px' }}>
                    <p style={{ lineHeight: '1.6', fontSize: '0.95rem', marginBottom: '16px', color: '#4a5568' }}>{report.executive_summary}</p>
                    <h4 style={{ fontSize: '1rem', marginBottom: '8px', color: '#4a5568' }}>Key Trends</h4>
                    <ul style={{ paddingLeft: '20px', lineHeight: '1.6', color: '#4a5568', fontSize: '0.9rem' }}>
                      {report.key_trends.map((trend, i) => <li key={i} style={{ marginBottom: '4px' }}>{trend}</li>)}
                    </ul>
                  </div>
               </Card>
            </motion.div>

            {/* Middle Right: Whitespace */}
            <motion.div variants={itemVariant} style={{ minHeight: 0 }}>
               <Card style={{ margin: 0, padding: '24px', display: 'flex', flexDirection: 'column' }}>
                  <h3 style={{ fontSize: '1.2rem', marginBottom: '12px', color: '#4a5568' }}>Whitespace Opportunities</h3>
                  <div style={{ flexGrow: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-evenly', paddingRight: '8px' }}>
                    <ul style={{ paddingLeft: '20px', lineHeight: '1.6', color: '#4a5568', fontSize: '0.95rem' }}>
                      {report.whitespace_opportunities.map((opp, i) => <li key={i} style={{ marginBottom: '8px' }}>{opp}</li>)}
                    </ul>
                  </div>
               </Card>
            </motion.div>

            {/* Bottom: Competitors Row */}
            <motion.div variants={itemVariant} style={{ gridColumn: 'span 2', minHeight: 0, display: 'flex', flexDirection: 'column' }}>
               <div style={{ flex: 1, display: 'grid', gridTemplateColumns: `repeat(${Math.max(report.competitors.length, 1)}, 1fr)`, gap: '24px', minHeight: 0 }}>
                  {report.competitors.map((comp, i) => (
                    <Card key={i} style={{ margin: 0, padding: '20px', display: 'flex', flexDirection: 'column' }}>
                      <h4 style={{ fontSize: '1.2rem', marginBottom: '12px', color: '#2d3748', borderBottom: '1px solid rgba(163, 177, 198, 0.3)', paddingBottom: '8px' }}>{comp.name}</h4>
                      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', color: '#4a5568', fontSize: '0.9rem', paddingRight: '4px' }}>
                        
                        <div style={{ paddingBottom: '12px', marginBottom: '12px', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
                           <strong style={{ color: '#3b82f6', display: 'block', marginBottom: '4px', fontSize: '0.95rem' }}>Pricing Model</strong>
                           <span style={{ lineHeight: '1.5' }}>{comp.pricing_model}</span>
                        </div>
                        
                        <div style={{ paddingBottom: '12px', marginBottom: '12px', borderBottom: '1px solid rgba(0,0,0,0.05)' }}>
                           <strong style={{ color: '#f59e0b', display: 'block', marginBottom: '4px', fontSize: '0.95rem' }}>Target Audience</strong>
                           <span style={{ lineHeight: '1.5' }}>{comp.target_audience}</span>
                        </div>
                        
                        <div style={{ paddingBottom: '4px' }}>
                           <strong style={{ color: '#8b5cf6', display: 'block', marginBottom: '4px', fontSize: '0.95rem' }}>Value Proposition</strong>
                           <span style={{ lineHeight: '1.5' }}>{comp.core_value_proposition}</span>
                        </div>

                      </div>
                    </Card>
                  ))}
               </div>
            </motion.div>
            
          </motion.div>
        )}
      </div>

      {/* Fixed Bottom Search Bar */}
      <div style={{ padding: '24px', zIndex: 10 }}>
        <div style={{ maxWidth: '800px', margin: '0 auto' }}>
          <SearchBar onSearch={handleSearch} isLoading={loading} />
          {error && <p style={{ color: '#e53e3e', marginTop: '12px', textAlign: 'center', fontWeight: 500, fontSize: '0.9rem' }}>{error}</p>}
        </div>
      </div>

    </div>
  );
}

export default App;
