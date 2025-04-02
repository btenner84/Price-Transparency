"use client";

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { HospitalProvider, useHospitalData } from '../../context/HospitalContext';
import Link from 'next/link';
import { API_CONFIG } from '../../config';

// Define the Hospital interface
interface Hospital {
  id: string;
  NAME: string;
  ADDRESS?: string;
  CITY: string;
  STATE: string;
  ZIP?: string;
  TYPE?: string;
  STATUS?: string;
  POPULATION?: number;
  COUNTY?: string;
  OWNER?: string;
  HELIPAD?: boolean;
  health_sys_name: string;
  health_sys_city?: string;
  health_sys_state?: string;
  corp_parent_name?: string;
  price_transparency_url?: string;
  price_file_found?: boolean;
  search_status?: string;
  last_search_date?: string;
}

function StateDetailPageContent() {
  const params = useParams();
  const router = useRouter();
  const { getStateFullName } = useHospitalData();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  
  // Get state code from URL parameters, ensuring it's a string
  const stateCodeParam = params.stateCode;
  const stateCode = typeof stateCodeParam === 'string' ? stateCodeParam.toUpperCase() : null;
  const stateName = stateCode ? getStateFullName(stateCode) : '';

  console.log(`State Detail Page: stateCode from URL = ${stateCode}`);

  // Fetch hospital data for this specific state
  useEffect(() => {
    const fetchStateHospitals = async () => {
      if (!stateCode) {
        setLoading(false);
        return;
      }
      
      try {
        setLoading(true);
        console.log(`Fetching hospitals directly for ${stateCode}...`);
        const response = await fetch(`${API_CONFIG.BASE_URL}/api/hospitals?state=${stateCode}&limit=1000`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch hospitals: ${response.status} ${response.statusText}`);
        }
        
        const data = await response.json();
        if (data.hospitals && Array.isArray(data.hospitals)) {
          setHospitals(data.hospitals);
          console.log(`Loaded ${data.hospitals.length} hospitals for ${stateCode}`);
        } else {
          setHospitals([]);
          console.log(`No hospitals found for ${stateCode}`);
        }
        
        setLoading(false);
      } catch (err) {
        console.error(`Error fetching hospitals for ${stateCode}:`, err);
        setError(`Error loading hospitals: ${err instanceof Error ? err.message : 'Unknown error'}`);
        setLoading(false);
      }
    };
    
    fetchStateHospitals();
  }, [stateCode]);

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-screen">
        <div className="text-2xl mb-4 neon-text animate-pulse">LOADING HOSPITALS</div>
        <div className="w-12 h-12 border-t-2 border-b-2 border-blue-400 rounded-full animate-spin"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link href="/" className="tron-button px-4 py-2 rounded-md inline-block mb-6 transition-all hover:translate-x-2">
          ← BACK TO MAP
        </Link>
        <div className="p-4 rounded-lg border border-red-500 bg-red-900 bg-opacity-20">
          <p className="text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!stateCode) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link href="/" className="tron-button px-4 py-2 rounded-md inline-block mb-6 transition-all hover:translate-x-2">
          ← BACK TO MAP
        </Link>
        <div className="text-center text-xl neon-text">INVALID STATE CODE</div>
      </div>
    );
  }

  if (hospitals.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link href="/" className="tron-button px-4 py-2 rounded-md inline-block mb-6 transition-all hover:translate-x-2">
          ← BACK TO MAP
        </Link>
        <div className="text-center p-6 rounded-lg border border-blue-400 bg-opacity-10 bg-blue-900">
          <p className="text-xl neon-text">NO HOSPITAL DATA FOUND FOR {stateName} ({stateCode})</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto">
      <div className="mb-6">
        <Link href="/" className="px-2 py-1 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 w-fit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          BACK TO MAP
        </Link>
      </div>
      
      <div className="p-6">
        <h1 className="text-4xl font-bold mb-12 text-white">
          HOSPITALS IN <span style={{ color: '#00FFA0' }}>{stateName.toUpperCase()}</span>
        </h1>

        <div className="overflow-y-auto pr-2" style={{ maxHeight: 'calc(100vh - 280px)' }}>
          <table className="w-full" style={{ borderCollapse: 'separate', borderSpacing: '0 8px' }}>
            <thead>
              <tr>
                <th style={{ width: '25%', paddingRight: '20px', paddingBottom: '16px', textAlign: 'left' }}>
                  <span style={{ color: '#00FFA0' }}>FACILITY</span>
                </th>
                <th style={{ width: '20%', textAlign: 'center', paddingBottom: '16px' }}>
                  <span style={{ color: '#00FFA0' }}>LOCATION</span>
                </th>
                <th style={{ width: '20%', paddingBottom: '16px', textAlign: 'center' }}>
                  <span style={{ color: '#00FFA0' }}>HEALTH SYSTEM</span>
                </th>
                <th style={{ width: '15%', paddingBottom: '16px', textAlign: 'center' }}>
                  <span style={{ color: '#00FFA0' }}>TRANSPARENCY</span>
                </th>
                <th style={{ width: '20%', paddingBottom: '16px', textAlign: 'center' }}>
                  <span style={{ color: '#00FFA0' }}>PRICE FILE</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {hospitals.sort((a, b) => a.NAME.localeCompare(b.NAME)).map((hospital, index) => (
                <tr key={hospital.id} className="h-14">
                  <td style={{ width: '25%', paddingRight: '20px', textAlign: 'left' }}>
                    <span style={{ color: '#00AFFF' }}>{hospital.NAME}</span>
                  </td>
                  <td style={{ width: '20%', textAlign: 'center' }}>
                    <span className="text-white">{hospital.CITY}, {hospital.STATE}</span>
                  </td>
                  <td style={{ width: '20%', textAlign: 'center' }}>
                    <span className="text-white">{hospital.health_sys_name || 'Independent'}</span>
                  </td>
                  <td style={{ width: '15%', textAlign: 'center' }}>
                    {formatSearchStatus(hospital.search_status)}
                  </td>
                  <td style={{ width: '20%', textAlign: 'center' }}>
                    {hospital.price_transparency_url ? (
                      <a 
                        href={hospital.price_transparency_url} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="text-blue-400 underline hover:text-blue-300"
                      >
                        VIEW FILE
                      </a>
                    ) : (
                      <span className="text-gray-400">NO FILE</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// Helper function to format search status
function formatSearchStatus(status?: string) {
  if (!status) return <span className="text-gray-400">PENDING</span>;
  
  switch (status) {
    case 'found':
      return <span className="text-green-400">FOUND</span>;
    case 'not_found':
      return <span className="text-red-400">NOT FOUND</span>;
    case 'searching':
      return <span className="text-yellow-400">SEARCHING</span>;
    default:
      return <span className="text-gray-400">{status.toUpperCase()}</span>;
  }
}

export default function StateDetailPage() {
  // Wrap with HospitalProvider to ensure context is available
  return (
    <HospitalProvider>
      <StateDetailPageContent />
    </HospitalProvider>
  );
} 