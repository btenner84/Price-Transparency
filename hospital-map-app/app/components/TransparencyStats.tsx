"use client";

import React from 'react';
import { useTransparency } from '../context/TransparencyContext';

const TransparencyStats: React.FC = () => {
  const { stats, loading, priceFinderRunning } = useTransparency();
  
  return (
    <div className="w-full my-2 px-4">
      <div className="bg-black border-4 border-blue-400 rounded-md p-4 shadow-xl">
        <h1 className="text-3xl font-bold text-blue-300 font-mono neon-text text-center mb-4">
          HOSPITAL PRICE TRANSPARENCY
        </h1>
        
        {/* Single percentage display - only validated */}
        <div className="flex justify-center mb-4">
          <div className="text-center">
            <span className="block text-4xl font-bold font-mono text-blue-200 neon-text-blue">
              {stats.percent_validated.toFixed(1)}%
            </span>
            <span className="text-sm font-mono text-blue-300 opacity-80">VALIDATED</span>
          </div>
        </div>
        
        {/* Sleek progress bar */}
        <div className="progress-bar-container h-12 border-4 mb-8">
          {/* Found files bar */}
          <div 
            className="progress-bar-found"
            style={{ width: `${stats.percent_found}%` }}
          ></div>
          
          {/* Validated files bar */}
          <div 
            className="progress-bar-validated"
            style={{ width: `${stats.percent_validated}%` }}
          >
            {/* Glow effect */}
            <div className="absolute right-0 top-0 h-full w-4 bg-gradient-to-r from-transparent to-blue-400 opacity-80"></div>
          </div>
          
          {/* Animated scan line - only show when actively searching */}
          {priceFinderRunning && (
            <div className="absolute inset-0 bg-gradient-to-r from-transparent via-blue-300 to-transparent opacity-30 animate-scan"></div>
          )}
        </div>
        
        {/* Status line */}
        <div className="flex flex-col items-center">
          <div className="font-mono text-sm text-blue-400 opacity-80">
            {priceFinderRunning ? (
              <span className="animate-pulse">SEARCHING FOR PRICE FILES...</span>
            ) : loading ? (
              <span className="animate-pulse">SCANNING {stats.total_hospitals.toLocaleString()} HOSPITALS...</span>
            ) : (
              <span>MONITORING {stats.total_hospitals.toLocaleString()} HOSPITALS</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default TransparencyStats; 