import React from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { Card } from './Card';
import type { CompetitorData } from '../types';

interface CompetitorChartProps {
  competitors: CompetitorData[];
}

export const CompetitorChart: React.FC<CompetitorChartProps> = ({ competitors }) => {
  return (
    <Card style={{ margin: 0, height: '100%', padding: '24px', display: 'flex', flexDirection: 'column' }}>
      <h3 style={{ marginBottom: '16px', color: '#4a5568', fontSize: '1.2rem' }}>Market Strength Scores</h3>
      <div style={{ flexGrow: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={competitors} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#a3b1c6" opacity={0.4} />
            <XAxis
              dataKey="name"
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#4a5568', fontSize: 12, fontWeight: 500 }}
              dy={10}
            />
            <YAxis
              domain={[0, 10]}
              axisLine={false}
              tickLine={false}
              tick={{ fill: '#4a5568', fontSize: 12 }}
              dx={-10}
            />
            <Tooltip
              cursor={{ fill: 'rgba(163, 177, 198, 0.15)' }}
              contentStyle={{
                borderRadius: '12px',
                border: 'none',
                boxShadow: '6px 6px 12px #a3b1c6, -6px -6px 12px #ffffff',
                backgroundColor: '#e0e5ec',
                color: '#4a5568'
              }}
            />
            <Bar dataKey="market_strength_score" fill="#10b981" radius={[6, 6, 0, 0]} barSize={36} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
};
