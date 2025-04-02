"use client";

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { API_CONFIG } from '../../config';

interface Hospital {
  id: string;
  NAME: string;
  CITY: string;
  STATE: string;
  ADDRESS?: string;
  health_sys_name: string;
  health_sys_id?: string;
  corp_parent_name?: string;
  price_transparency_url?: string;
  search_status?: string;
}

interface HealthSystem {
  id: string;
  name: string;
  city?: string;
  state?: string;
  corp_parent_name?: string;
  hospital_count: number;
}

function SystemDetailPage() {
  const params = useParams();
  const [hospitals, setHospitals] = useState<Hospital[]>([]);
  const [healthSystem, setHealthSystem] = useState<HealthSystem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Get system name from URL parameters and decode it
  const systemName = params.systemName ? decodeURIComponent(params.systemName as string) : null;

  useEffect(() => {
    const fetchSystemData = async () => {
      if (!systemName) return;
      
      try {
        setLoading(true);
        console.log(`Fetching hospitals for system: ${systemName}`);
        
        // First, fetch the system details
        const systemResponse = await fetch(`${API_CONFIG.BASE_URL}/api/health-systems`);
        if (!systemResponse.ok) {
          throw new Error(`Failed to fetch health systems: ${systemResponse.status}`);
        }
        
        const systemData = await systemResponse.json();
        const system = systemData.health_systems.find(
          (s: HealthSystem) => s.name === systemName
        );
        
        if (system) {
          setHealthSystem(system);
          console.log(`Found health system: ${system.name}`);
        }
        
        // Then fetch all hospitals for this system
        const hospitalResponse = await fetch(
          `${API_CONFIG.BASE_URL}/api/hospitals?system_name=${encodeURIComponent(systemName)}&limit=1000`
        );
        
        if (!hospitalResponse.ok) {
          throw new Error(`Failed to fetch hospitals: ${hospitalResponse.status}`);
        }
        
        const hospitalData = await hospitalResponse.json();
        console.log(`Found ${hospitalData.hospitals.length} hospitals in system: ${systemName}`);
        setHospitals(hospitalData.hospitals);
      } catch (err) {
        console.error('Error fetching data:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchSystemData();
  }, [systemName]);

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
        <Link href="/" className="px-2 py-1 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 w-fit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          BACK TO LIST
        </Link>
        <div className="p-4 rounded-lg border border-red-500 bg-red-900 bg-opacity-20">
          <p className="text-red-300">{error}</p>
        </div>
      </div>
    );
  }

  if (!systemName) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link href="/" className="px-2 py-1 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 w-fit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          BACK TO LIST
        </Link>
        <div className="text-center text-xl neon-text">INVALID SYSTEM NAME</div>
      </div>
    );
  }

  if (hospitals.length === 0) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Link href="/" className="px-2 py-1 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 w-fit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          BACK TO LIST
        </Link>
        <div className="text-center p-6 border border-blue-400 rounded-lg bg-blue-900 bg-opacity-10">
          <p className="text-xl">No hospitals found for system: {systemName}</p>
        </div>
      </div>
    );
  }

  // Sort hospitals by state, then city, then name
  const sortedHospitals = [...hospitals].sort((a, b) => {
    const stateCompare = a.STATE.localeCompare(b.STATE);
    if (stateCompare !== 0) return stateCompare;
    const cityCompare = a.CITY.localeCompare(b.CITY);
    if (cityCompare !== 0) return cityCompare;
    return a.NAME.localeCompare(b.NAME);
  });

  const stateCount = new Set(sortedHospitals.map(h => h.STATE)).size;
  
  // Use corporate parent name if available
  const displayName = healthSystem?.corp_parent_name && healthSystem.corp_parent_name.trim() !== '' 
    ? healthSystem.corp_parent_name.toUpperCase() 
    : systemName.toUpperCase();

  return (
    <div className="container mx-auto">
      <div className="mb-6">
        <Link href="/" className="px-2 py-1 border border-blue-400 hover:bg-blue-900 hover:bg-opacity-20 flex items-center gap-2 w-fit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 16 16">
            <path fillRule="evenodd" d="M11.354 1.646a.5.5 0 0 1 0 .708L5.707 8l5.647 5.646a.5.5 0 0 1-.708.708l-6-6a.5.5 0 0 1 0-.708l6-6a.5.5 0 0 1 .708 0z"/>
          </svg>
          BACK TO LIST
        </Link>
      </div>
      
      <div className="p-6">
        <h1 className="text-4xl font-bold mb-4 text-white">
          <span className="text-blue-300">{displayName}</span>
        </h1>
        <div className="mb-12 text-blue-400">
          {sortedHospitals.length} FACILITIES ACROSS {stateCount} STATES
        </div>

        <div className="overflow-y-auto pr-2" style={{ maxHeight: 'calc(100vh - 280px)' }}>
          <table className="w-full" style={{ borderCollapse: 'separate', borderSpacing: '0 8px' }}>
            <thead>
              <tr>
                <th style={{ width: '45%', paddingBottom: '16px', textAlign: 'left' }}>
                  <span className="text-blue-300">FACILITY</span>
                </th>
                <th style={{ width: '30%', paddingBottom: '16px', textAlign: 'center' }}>
                  <span className="text-blue-300">LOCATION</span>
                </th>
                <th style={{ width: '25%', paddingBottom: '16px', textAlign: 'center' }}>
                  <span className="text-blue-300">STATE</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedHospitals.map((hospital) => (
                <tr key={hospital.id} className="h-14">
                  <td style={{ width: '45%', textAlign: 'left' }}>
                    <span className="text-blue-400">
                      {hospital.NAME}
                      {hospital.price_transparency_url && (
                        <span className="ml-2 px-1 py-0.5 bg-green-800 text-green-200 text-xs rounded">
                          FILE
                        </span>
                      )}
                    </span>
                  </td>
                  <td style={{ width: '30%', textAlign: 'center' }}>
                    <span className="text-white">{hospital.CITY}</span>
                  </td>
                  <td style={{ width: '25%', textAlign: 'center' }}>
                    <Link 
                      href={`/state/${hospital.STATE}`}
                      className="text-white hover:text-blue-300 transition-colors"
                    >
                      {hospital.STATE}
                    </Link>
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

export default SystemDetailPage; 