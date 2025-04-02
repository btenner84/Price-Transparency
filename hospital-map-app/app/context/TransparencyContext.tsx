"use client";

import React, { createContext, useContext, useState, useEffect } from 'react';
import { API_CONFIG } from '../config';

type TransparencyStats = {
  total_hospitals: number;
  found_files: number;
  validated_files: number;
  percent_found: number;
  percent_validated: number;
  last_updated: string | null;
};

const initialStats: TransparencyStats = {
  total_hospitals: 0,
  found_files: 0,
  validated_files: 0,
  percent_found: 0,
  percent_validated: 0,
  last_updated: null
};

type PriceFinderResult = {
  hospitals_processed: number;
  files_found: number;
  files_validated: number;
  errors: number;
  start_time: string;
  end_time: string | null;
};

type TransparencyContextType = {
  stats: TransparencyStats;
  loading: boolean;
  error: string | null;
  refreshStats: () => Promise<void>;
  runPriceFinder: (batch_size?: number, state?: string) => Promise<PriceFinderResult | null>;
  priceFinderRunning: boolean;
  lastPriceFinderResult: PriceFinderResult | null;
};

const TransparencyContext = createContext<TransparencyContextType | undefined>(undefined);

export const TransparencyProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [stats, setStats] = useState<TransparencyStats>(initialStats);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState<number>(0);
  const [priceFinderRunning, setPriceFinderRunning] = useState<boolean>(false);
  const [lastPriceFinderResult, setLastPriceFinderResult] = useState<PriceFinderResult | null>(null);

  const fetchStats = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log("Fetching transparency stats from API...");
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/statistics/transparency`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      
      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.status}`);
      }
      
      const data = await response.json();
      console.log("Received transparency stats:", data);
      setStats(data);
      setRetryCount(0); // Reset retry count on success
    } catch (err) {
      console.error('Error fetching transparency stats:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      
      // Increment retry count
      setRetryCount(prev => prev + 1);
    } finally {
      setLoading(false);
    }
  };

  // Function to manually trigger the price finder
  const runPriceFinder = async (batch_size: number = 10, state?: string): Promise<PriceFinderResult | null> => {
    try {
      setPriceFinderRunning(true);
      
      const url = new URL(`${API_CONFIG.BASE_URL}/api/run-price-finder`);
      url.searchParams.append('batch_size', batch_size.toString());
      if (state) {
        url.searchParams.append('state', state);
      }
      
      console.log(`Running price finder with batch size ${batch_size}${state ? ` for state ${state}` : ''}...`);
      
      const response = await fetch(url.toString(), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        signal: AbortSignal.timeout(60000) // 60 second timeout for longer operations
      });
      
      if (!response.ok) {
        throw new Error(`Failed to run price finder: ${response.status}`);
      }
      
      const result: PriceFinderResult = await response.json();
      console.log("Price finder completed:", result);
      
      // Store the result for display
      setLastPriceFinderResult(result);
      
      // Immediately refresh stats after a run
      await fetchStats();
      
      return result;
    } catch (err) {
      console.error('Error running price finder:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
      return null;
    } finally {
      setPriceFinderRunning(false);
    }
  };

  // Initial fetch with retry logic
  useEffect(() => {
    fetchStats();
    
    // Set up polling for updates - more frequent if a price finder run is in progress
    const intervalId = setInterval(() => {
      fetchStats();
    }, priceFinderRunning ? API_CONFIG.PRICE_FINDER_ACTIVE_REFRESH : API_CONFIG.REFRESH_INTERVAL);
    
    return () => clearInterval(intervalId);
  }, [priceFinderRunning]);

  // Additional effect to handle retries with exponential backoff
  useEffect(() => {
    if (retryCount > 0 && retryCount <= 5) {
      const backoffTime = Math.min(1000 * Math.pow(2, retryCount), 30000); // Max 30 second backoff
      console.log(`Retrying in ${backoffTime/1000} seconds (attempt ${retryCount})...`);
      
      const retryTimeout = setTimeout(() => {
        fetchStats();
      }, backoffTime);
      
      return () => clearTimeout(retryTimeout);
    }
  }, [retryCount]);

  return (
    <TransparencyContext.Provider 
      value={{ 
        stats, 
        loading, 
        error, 
        refreshStats: fetchStats,
        runPriceFinder,
        priceFinderRunning,
        lastPriceFinderResult
      }}
    >
      {children}
    </TransparencyContext.Provider>
  );
};

export const useTransparency = (): TransparencyContextType => {
  const context = useContext(TransparencyContext);
  
  if (context === undefined) {
    throw new Error('useTransparency must be used within a TransparencyProvider');
  }
  
  return context;
}; 