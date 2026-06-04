import React, { type ReactNode } from 'react';

interface CardProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({ children, className = '', style }) => {
  return (
    <div
      className={`neu-flat ${className}`}
      style={{ padding: '32px', margin: '24px 0', height: '100%', display: 'flex', flexDirection: 'column', ...style }}
    >
      {children}
    </div>
  );
};
