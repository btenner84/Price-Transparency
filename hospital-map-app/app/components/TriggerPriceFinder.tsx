"use client";

import React, { useState } from 'react';
import { useTransparency } from '../context/TransparencyContext';

interface TriggerPriceFinderProps {
  className?: string;
}

const TriggerPriceFinder: React.FC<TriggerPriceFinderProps> = ({ className = '' }) => {
  const { runPriceFinder, priceFinderRunning, lastPriceFinderResult, refreshStats } = useTransparency();
  const [batchSize, setBatchSize] = useState<number>(1);
  const [state, setState] = useState<string>('');

  const handleRunPriceFinder = async () => {
    // Run the price finder
    const result = await runPriceFinder(batchSize, state.trim() || undefined);
    
    // Force an immediate refresh of the statistics after completion
    if (result) {
      await refreshStats();
    }
  };

  return (
    <div className={`bg-black border border-blue-400 rounded-md p-4 shadow-xl ${className}`}>
      <h2 className="text-xl font-bold text-blue-300 font-mono mb-4">
        PRICE FINDER CONTROL
      </h2>
      
      <div className="mb-4">
        <label className="block text-blue-300 font-mono text-sm mb-2">
          BATCH SIZE
        </label>
        <input
          type="number"
          min="1"
          max="10"
          value={batchSize}
          onChange={(e) => setBatchSize(Math.max(1, Math.min(10, parseInt(e.target.value) || 1)))}
          className="bg-blue-900/30 border border-blue-500 text-blue-100 font-mono p-2 rounded w-full"
        />
      </div>
      
      <div className="mb-4">
        <label className="block text-blue-300 font-mono text-sm mb-2">
          STATE (OPTIONAL)
        </label>
        <input
          type="text"
          placeholder="e.g. CA, TX"
          value={state}
          onChange={(e) => setState(e.target.value)}
          className="bg-blue-900/30 border border-blue-500 text-blue-100 font-mono p-2 rounded w-full"
        />
      </div>
      
      <button
        onClick={handleRunPriceFinder}
        disabled={priceFinderRunning}
        className={`w-full p-3 rounded font-mono text-center ${
          priceFinderRunning
            ? 'bg-gray-700 text-gray-400 cursor-not-allowed'
            : 'bg-blue-700 text-blue-100 hover:bg-blue-600 animate-pulse'
        }`}
      >
        {priceFinderRunning ? 'PROCESSING...' : 'RUN PRICE FINDER'}
      </button>
      
      {lastPriceFinderResult && (
        <div className="mt-4 p-3 border border-blue-500 rounded bg-blue-900/20">
          <h3 className="text-blue-300 font-mono text-sm mb-2">LAST RUN RESULTS:</h3>
          <div className="grid grid-cols-2 gap-2 text-xs font-mono">
            <div className="text-blue-400">HOSPITALS:</div>
            <div className="text-blue-200">{lastPriceFinderResult.hospitals_processed}</div>
            
            <div className="text-blue-400">FILES FOUND:</div>
            <div className="text-blue-200">{lastPriceFinderResult.files_found}</div>
            
            <div className="text-blue-400">VALIDATED:</div>
            <div className="text-blue-200">{lastPriceFinderResult.files_validated}</div>
            
            <div className="text-blue-400">ERRORS:</div>
            <div className="text-blue-200">{lastPriceFinderResult.errors}</div>
            
            <div className="text-blue-400">DURATION:</div>
            <div className="text-blue-200">
              {lastPriceFinderResult.end_time && lastPriceFinderResult.start_time
                ? Math.round((new Date(lastPriceFinderResult.end_time).getTime() - 
                    new Date(lastPriceFinderResult.start_time).getTime()) / 1000)
                : 'N/A'} sec
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TriggerPriceFinder; 