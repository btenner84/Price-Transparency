"use client";

import React from 'react';
import TransparencyStats from './TransparencyStats';

const Header: React.FC = () => {
  return (
    <header className="py-2 mb-2">
      {/* App Logo/Title */}
      <div className="container mx-auto px-4">
        <h1 className="text-3xl font-bold text-blue-300 neon-text"></h1>
        <TransparencyStats />
      </div>
    </header>
  );
};

export default Header; 