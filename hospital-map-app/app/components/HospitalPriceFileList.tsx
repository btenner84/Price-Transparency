"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { API_CONFIG } from '../config';

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
  price_file_found?: boolean;
}

const HospitalPriceFileList: React.FC = () => {
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  
  const fetchRecentlyUpdatedHospitals = async () => {
    try {
      setLoading(true);
      
      // Fetch only hospitals that have been processed (have a last_search_date)
      // Limit to 20, sorted by most recently searched
      const response = await fetch(`${API_CONFIG.BASE_URL}/api/hospitals?limit=20&sort=last_search_date&order=desc&include_price_files=true`);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch data: ${response.status}`);
      }
      
      const data = await response.json();
      
      // Get hospitals with found status, price_file_found true or with a price_transparency_url
      const hospitalsWithPriceFiles = data.hospitals.filter((h: Hospital) => {
        return (h.price_transparency_url && h.price_transparency_url.trim() !== '') || 
               (h.search_status === "found" && h.price_file_found === true);
      });
      
      // Sort by most recent
      hospitalsWithPriceFiles.sort((a: Hospital, b: Hospital) => {
        if (!a.last_search_date) return 1;
        if (!b.last_search_date) return -1;
        return new Date(b.last_search_date).getTime() - new Date(a.last_search_date).getTime();
      });
      
      // Limit to the most recent 20
      setHospitals(hospitalsWithPriceFiles.slice(0, 20));
      setError(null);
    } catch (err) {
      console.error('Error fetching hospital updates:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };
  
  // Fetch data on component mount and periodically
  useEffect(() => {
    fetchRecentlyUpdatedHospitals();
    
    // Use the configured refresh interval
    const intervalId = setInterval(() => {
      fetchRecentlyUpdatedHospitals();
    }, API_CONFIG.REFRESH_INTERVAL);
    
    return () => clearInterval(intervalId);
  }, []);
  
  // Function to render search status with appropriate styling
  const renderSearchStatus = (status?: string) => {
    if (!status) return null;
    
    let statusClass = "";
    switch (status.toLowerCase()) {
      case "found":
        statusClass = "bg-green-900 text-green-300";
        break;
      case "not_found":
        statusClass = "bg-red-900 text-red-300";
        break;
      case "searching":
        statusClass = "bg-blue-900 text-blue-300 animate-pulse";
        break;
      case "error":
        statusClass = "bg-orange-900 text-orange-300";
        break;
      default:
        statusClass = "bg-gray-800 text-gray-300";
    }
    
    return (
      <span className={`px-2 py-1 rounded text-xs font-mono ${statusClass}`}>
        {status.toUpperCase()}
      </span>
    );
  };
  
  return (
    <div className="w-full my-8 px-4">
      <div className="bg-black border border-blue-400 rounded-md p-4 shadow-xl">
        <h2 className="text-xl font-bold text-blue-300 font-mono mb-4 flex justify-between items-center">
          <span>RECENT HOSPITAL UPDATES</span>
          <Link 
            href="/price-files" 
            className="text-sm bg-blue-900 hover:bg-blue-800 text-blue-200 px-2 py-1 rounded"
          >
            VIEW ALL FILES
          </Link>
        </h2>
        
        {loading && hospitals.length === 0 && (
          <div className="text-center py-4 text-blue-300 font-mono animate-pulse">
            SCANNING FOR PRICE TRANSPARENCY FILES...
          </div>
        )}
        
        {error && (
          <div className="text-center py-4 text-red-300 font-mono">
            ERROR: {error}
          </div>
        )}
        
        <div className="max-h-96 overflow-y-auto">
          <table className="w-full text-left">
            <thead className="border-b border-blue-400">
              <tr className="text-blue-400 font-mono text-sm">
                <th className="p-2">HOSPITAL</th>
                <th className="p-2">LOCATION</th>
                <th className="p-2">STATUS</th>
                <th className="p-2">PRICE FILE</th>
              </tr>
            </thead>
            <tbody>
              {hospitals.map(hospital => (
                <tr key={hospital.id} className="border-b border-blue-900 hover:bg-blue-900/20">
                  <td className="p-2 font-mono text-blue-200">
                    {hospital.NAME}
                  </td>
                  <td className="p-2 font-mono text-blue-300 text-sm">
                    {hospital.CITY}, {hospital.STATE}
                  </td>
                  <td className="p-2">
                    {renderSearchStatus(hospital.search_status)}
                  </td>
                  <td className="p-2">
                    {hospital.price_transparency_url ? (
                      <a 
                        href={hospital.price_transparency_url} 
                        target="_blank" 
                        rel="noopener noreferrer" 
                        className="text-blue-400 hover:text-blue-300 font-mono text-sm underline"
                      >
                        VIEW FILE
                      </a>
                    ) : (
                      <span className="text-gray-500 font-mono text-sm">NO FILE</span>
                    )}
                  </td>
                </tr>
              ))}
              
              {hospitals.length === 0 && !loading && (
                <tr>
                  <td colSpan={4} className="text-center py-4 text-gray-500 font-mono">
                    NO HOSPITAL UPDATES YET
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default HospitalPriceFileList; 