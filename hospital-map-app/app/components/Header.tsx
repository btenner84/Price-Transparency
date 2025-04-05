"use client";

import React from 'react';
import Link from 'next/link';
import TransparencyStats from './TransparencyStats';

const Header: React.FC = () => {
  return (
    <header className="py-2 mb-2">
      {/* App Logo/Title */}
      <div className="container mx-auto px-4">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold text-blue-300 neon-text">HOSPITAL PRICE TRANSPARENCY</h1>
          <Link 
            href="/price-files" 
            className="cyberpunk-button"
          >
            <span className="flex items-center gap-1">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              PRICE FILES
            </span>
          </Link>
        </div>
        <TransparencyStats />
      </div>
    </header>
  );
};

export default Header; 