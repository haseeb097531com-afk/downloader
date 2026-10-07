'use client';
import React from 'react';

// Mocked for architecture scaffold, ready for React Query or SWR integration later
export const QueryProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <>{children}</>
  );
};
