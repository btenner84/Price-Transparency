"use client";

import React, { createContext, useState, useEffect, useContext, ReactNode } from 'react';
import { API_CONFIG } from '../config';

interface Hospital {
  id: string;
  NAME: string;
  ADDRESS: string;
  CITY: string;
  STATE: string;
  ZIP: string;
  TYPE: string;
  STATUS: string;
  POPULATION: number;
  COUNTY: string;
  OWNER: string;
  HELIPAD: boolean;
  health_sys_name: string;
  health_sys_city: string;
  health_sys_state: string;
  corp_parent_name: string;
  price_transparency_url?: string;
  price_file_found?: boolean;
  search_status?: string;
  last_search_date?: string;
  created_at?: string;
  updated_at?: string;
}

interface HospitalData {
  [stateCode: string]: Hospital[];
}

interface HospitalContextProps {
  hospitalData: HospitalData;
  loading: boolean;
  error: string | null;
  getStateFullName: (stateCode: string) => string;
  refreshData: () => Promise<void>;
}

const HospitalContext = createContext<HospitalContextProps | undefined>(undefined);

// State codes to full names mapping
const stateNames: { [key: string]: string } = {
  AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California',
  CO: 'Colorado', CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia',
  HI: 'Hawaii', ID: 'Idaho', IL: 'Illinois', IN: 'Indiana', IA: 'Iowa',
  KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana', ME: 'Maine', MD: 'Maryland',
  MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi', MO: 'Missouri',
  MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey',
  NM: 'New Mexico', NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio',
  OK: 'Oklahoma', OR: 'Oregon', PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina',
  SD: 'South Dakota', TN: 'Tennessee', TX: 'Texas', UT: 'Utah', VT: 'Vermont',
  VA: 'Virginia', WA: 'Washington', WV: 'West Virginia', WI: 'Wisconsin', WY: 'Wyoming',
  DC: 'District of Columbia', PR: 'Puerto Rico', VI: 'Virgin Islands', GU: 'Guam', MP: 'Northern Mariana Islands'
};

// Commenting out mock data - no longer needed
/*
const mockData: HospitalData = {
  // ... (mock data contents)
};
*/

export const HospitalProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [hospitalData, setHospitalData] = useState<HospitalData>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      console.log("Fetching state list from API...");
      setError(null); // Clear any previous errors
      
      // First get list of states
      const statesResponse = await fetch(`${API_CONFIG.BASE_URL}/api/states`);
      
      if (!statesResponse.ok) {
        throw new Error(`Failed to fetch states: ${statesResponse.status} ${statesResponse.statusText}`);
      }
      
      const statesData = await statesResponse.json();
      // Extract state codes from the response object keys
      const states = Object.keys(statesData);
      console.log(`Found ${states.length} states to fetch data for:`, states);
      
      if (states.length === 0) {
        throw new Error('No states returned from API');
      }
      
      const allHospitalData: HospitalData = {};
      
      // Fetch hospitals for each state
      for (const state of states) {
        try {
          console.log(`Fetching hospitals for ${state}...`);
          const response = await fetch(`${API_CONFIG.BASE_URL}/api/hospitals?state=${state}&limit=1000`);
          
          if (!response.ok) {
            console.error(`Error fetching hospitals for ${state}: ${response.status}`);
            continue;
          }
          
          const data = await response.json();
          if (data.hospitals && Array.isArray(data.hospitals) && data.hospitals.length > 0) {
            allHospitalData[state] = data.hospitals;
            console.log(`Added ${data.hospitals.length} hospitals for ${state}`);
          } else {
            console.log(`No hospitals found for ${state}`);
          }
        } catch (stateErr) {
          console.error(`Error processing state ${state}:`, stateErr);
        }
      }
      
      console.log("All hospital data loaded, states available:", Object.keys(allHospitalData).length);
      
      // Make sure some data was loaded
      if (Object.keys(allHospitalData).length === 0) {
        throw new Error('No hospital data could be loaded for any state');
      }
      
      setHospitalData(allHospitalData);
      setLoading(false);
      setError(null);

    } catch (err) {
      console.error('Error fetching hospital data:', err);
      setError(`Error loading hospital data: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getStateFullName = (stateCode: string): string => {
    return stateNames[stateCode] || stateCode;
  };

  const refreshData = async () => {
    setLoading(true);
    await fetchData();
  };

  return (
    <HospitalContext.Provider
      value={{
        hospitalData,
        loading,
        error,
        getStateFullName,
        refreshData
      }}
    >
      {children}
    </HospitalContext.Provider>
  );
};

export const useHospitalData = (): HospitalContextProps => {
  const context = useContext(HospitalContext);
  if (context === undefined) {
    throw new Error('useHospitalData must be used within a HospitalProvider');
  }
  return context;
}; 