import React, { useState, useEffect, memo } from 'react';
import { ComposableMap, Geographies, Geography } from 'react-simple-maps';

// Map topojson data URL
const geoUrl = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json';

interface USAMapProps {
  onSelectState: (stateCode: string) => void;
  selectedState: string | null;
}

// Define the properties we expect to get from topojson
interface GeoProperties {
  name: string;
  id: string;
}

// Map of state names to state codes
const stateNameToCode: { [key: string]: string } = {
  'Alabama': 'AL', 'Alaska': 'AK', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
  'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA',
  'Hawaii': 'HI', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA',
  'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD',
  'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO',
  'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
  'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH',
  'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
  'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
  'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
  'District of Columbia': 'DC', 'Puerto Rico': 'PR'
};

const USAMap: React.FC<USAMapProps> = ({ onSelectState, selectedState }) => {
  const [mapData, setMapData] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    // Fetch the map data
    fetch(geoUrl)
      .then(response => response.json())
      .then(data => {
        setMapData(data);
        setLoading(false);
      })
      .catch(error => {
        console.error('Error loading map data:', error);
        setLoading(false);
      });
  }, []);

  const handleStateClick = (geo: { properties: GeoProperties }) => {
    const stateName = geo.properties.name;
    const stateCode = stateNameToCode[stateName];
    console.log('Clicked state:', stateName, '→', stateCode);
    
    if (stateCode) {
      onSelectState(stateCode);
    } else {
      console.warn('No state code found for:', stateName);
    }
  };

  if (loading || !mapData) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-2xl font-bold">Loading Map Data...</div>
      </div>
    );
  }

  return (
    <div className="w-full rounded-lg p-4 bg-gray-800 bg-opacity-30 border border-gray-700">
      <ComposableMap
        projection="geoAlbersUsa"
        projectionConfig={{ scale: 1000 }}
        className="w-full h-auto"
      >
        <Geographies geography={mapData}>
          {({ geographies }) => 
            geographies.map(geo => {
              const stateName = geo.properties.name;
              const stateCode = stateNameToCode[stateName];
              const isSelected = selectedState === stateCode;
              
              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  onClick={() => handleStateClick(geo)}
                  className={`map-state ${isSelected ? 'active' : ''}`}
                  style={{
                    default: { outline: 'none' },
                    hover: { outline: 'none' },
                    pressed: { outline: 'none' },
                  }}
                />
              );
            })
          }
        </Geographies>
      </ComposableMap>
    </div>
  );
};

export default memo(USAMap); 