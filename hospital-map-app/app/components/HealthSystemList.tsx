"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { API_CONFIG, UI_CONFIG } from '../config';

interface Hospital {
  id: string;
  NAME: string;
  CITY: string;
  STATE: string;
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

const HealthSystemList: React.FC = () => {
  const [healthSystems, setHealthSystems] = useState<HealthSystem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHealthSystems = async () => {
      try {
        setLoading(true);
        console.log("Fetching health systems from API...");
        
        // Limit to top 100 health systems by size
        const response = await fetch(`${API_CONFIG.BASE_URL}/api/health-systems?limit=100`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch data: ${response.status}`);
        }
        
        const data = await response.json();
        console.log(`Loaded ${data.health_systems.length} health systems from API`);
        setHealthSystems(data.health_systems);
      } catch (err) {
        console.error('Error fetching health systems:', err);
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };

    fetchHealthSystems();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center items-center p-12">
        <div className="animate-pulse text-blue-400">Loading health system data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-900 bg-opacity-20 border border-red-500 rounded-lg">
        <p className="text-red-300">Error loading health system data: {error}</p>
        <p className="mt-4 text-sm">
          Make sure the backend server is running at {API_CONFIG.BASE_URL}
        </p>
      </div>
    );
  }

  // Inspect a sample system to debug the field names
  if (healthSystems.length > 0) {
    console.log("Sample health system data:", healthSystems[0]);
  }

  return (
    <div className="grid gap-4 p-4 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
      {healthSystems.map((system) => {
        // Use corporate parent name if available, otherwise use system name
        const displayName = system.corp_parent_name && system.corp_parent_name.trim() !== '' 
          ? system.corp_parent_name 
          : system.name;
          
        return (
          <div key={system.id} className="border border-blue-400 p-4 rounded-lg bg-black bg-opacity-30">
            <h2 className="text-xl font-bold mb-2 text-blue-300">{displayName}</h2>
            <div className="flex justify-between text-sm mb-3">
              <span>{system.hospital_count} Hospitals</span>
              {system.state && <span>{system.state}</span>}
            </div>
            <Link 
              href={`/system/${encodeURIComponent(system.name)}`} 
              className="mt-3 block text-center py-1 bg-blue-900 hover:bg-blue-800 rounded text-sm">
              View Hospitals
            </Link>
          </div>
        );
      })}
    </div>
  );
};

export default HealthSystemList; 