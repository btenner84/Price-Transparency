"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { API_CONFIG } from '../config';
import Header from '../components/Header';

interface HospitalPriceFile {
  id: string;
  hospital_id: string;
  file_url: string;
  file_type: string;
  found_date: string;
  validated: boolean;
  validation_date?: string;
}

interface Hospital {
  id: string;
  NAME: string;
  CITY: string;
  STATE: string;
  health_sys_name: string;
  price_transparency_url?: string;
  search_status?: string;
  last_search_date?: string;
  price_files?: HospitalPriceFile[];
  price_file_found?: boolean;
}

export default function PriceFilesPage() {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  const fetchHospitalsWithPriceFiles = async () => {
    try {
      setLoading(true);
      
      // Get ALL hospitals first - we'll filter them client-side
      const response = await fetch(
        `${API_CONFIG.BASE_URL}/api/hospitals?limit=1000&include_price_files=true`
      );
      
      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.status}`);
      }
      
      const data = await response.json();
      console.log("Got hospital data:", data.hospitals.length, "hospitals");
      
      // Filter to only show hospitals with price_file_found = true or
      // that have an actual price_transparency_url
      const hospitalsWithFiles = data.hospitals.filter((hospital: Hospital) => {
        return hospital.price_file_found === true || 
              (hospital.price_transparency_url && hospital.price_transparency_url.trim() !== '');
      });
      
      console.log("Filtered to", hospitalsWithFiles.length, "hospitals with price files");
      setHospitals(hospitalsWithFiles);
      setError(null);
    } catch (err) {
      console.error('Error fetching hospital price files:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };
  
  useEffect(() => {
    fetchHospitalsWithPriceFiles();
    
    // Refresh data periodically
    const intervalId = setInterval(() => {
      fetchHospitalsWithPriceFiles();
    }, API_CONFIG.REFRESH_INTERVAL);
    
    return () => clearInterval(intervalId);
  }, []);

  return (
    <div className="min-h-screen bg-gray-900">
      <div className="container mx-auto px-4 py-8">
        <Header />
        
        <div className="mb-6 flex items-center">
          <Link href="/" className="px-3 py-2 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 mr-4">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
              <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
            </svg>
            BACK TO MAP
          </Link>
          <h1 className="text-2xl font-bold neon-text">HOSPITAL PRICE TRANSPARENCY FILES</h1>
        </div>

        <div className="relative bg-black bg-opacity-80 border border-blue-400 rounded-lg p-6 mb-6 shadow-lg">
          {loading && (
            <div className="flex justify-center items-center py-16">
              <div className="text-xl neon-text animate-pulse mr-4">LOADING PRICE FILES</div>
              <div className="w-6 h-6 border-t-2 border-b-2 border-blue-400 rounded-full animate-spin"></div>
            </div>
          )}
          
          {error && (
            <div className="p-4 rounded-lg border border-red-500 bg-red-900 bg-opacity-20">
              <p className="text-red-300">{error}</p>
            </div>
          )}
          
          {!loading && hospitals.length === 0 && (
            <div className="text-center py-16 text-gray-500 font-mono">
              NO PRICE FILES FOUND YET
            </div>
          )}
          
          {!loading && hospitals.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead className="border-b border-blue-400">
                  <tr className="text-blue-400 font-mono text-sm">
                    <th className="p-3 text-left">HOSPITAL</th>
                    <th className="p-3 text-left">LOCATION</th>
                    <th className="p-3 text-left">HEALTH SYSTEM</th>
                    <th className="p-3 text-left">FILE TYPE</th>
                    <th className="p-3 text-left">VALIDATION</th>
                    <th className="p-3 text-center">ACTIONS</th>
                  </tr>
                </thead>
                <tbody>
                  {hospitals.map(hospital => (
                    <tr 
                      key={hospital.id} 
                      className="border-b border-blue-900 hover:bg-blue-900/20"
                    >
                      <td className="p-3 font-mono text-blue-200">
                        {hospital.NAME}
                      </td>
                      <td className="p-3 font-mono text-blue-300 text-sm">
                        {hospital.CITY}, {hospital.STATE}
                      </td>
                      <td className="p-3 font-mono text-blue-300 text-sm">
                        {hospital.health_sys_name || "Independent"}
                      </td>
                      <td className="p-3 font-mono text-blue-300 text-sm uppercase">
                        {hospital.price_files?.[0]?.file_type || 
                         (hospital.price_transparency_url?.split('.').pop()?.toLowerCase() || "Unknown")}
                      </td>
                      <td className="p-3 font-mono text-sm">
                        {hospital.price_files?.find(file => file.validated) ? (
                          <span className="px-2 py-1 bg-green-900 text-green-300 rounded">VALIDATED</span>
                        ) : (
                          <span className="px-2 py-1 bg-orange-900 text-orange-300 rounded">UNVERIFIED</span>
                        )}
                      </td>
                      <td className="p-3 text-center">
                        {hospital.price_transparency_url && (
                          <a 
                            href={hospital.price_transparency_url} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            className="inline-block px-3 py-1 bg-blue-800 hover:bg-blue-700 text-blue-100 rounded text-sm"
                          >
                            VIEW FILE
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        
        <div className="text-center text-gray-500 text-sm">
          <p>Data updates automatically. Showing {hospitals.length} hospitals with price transparency information.</p>
        </div>
      </div>
    </div>
  );
} 