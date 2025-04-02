import React from 'react';

interface Hospital {
  NAME: string;
  ADDRESS: string;
  CITY: string;
  STATE: string;
  ZIP: number;
  TYPE: string;
  STATUS: string;
  POPULATION: number;
  COUNTY: string;
  OWNER: string;
  HELIPAD: string;
  health_sys_name: string;
  health_sys_city: string;
  health_sys_state: string;
  corp_parent_name: string;
  price_transparency_url?: string;
  price_file_found?: boolean;
  search_status?: string;
  last_search_date?: string;
}

interface HospitalListProps {
  hospitals: Hospital[];
  stateName: string;
}

const HospitalList: React.FC<HospitalListProps> = ({ hospitals, stateName }) => {
  const sortedHospitals = [...hospitals].sort((a, b) => a.NAME.localeCompare(b.NAME));

  const renderStatus = (status: string, beds?: number) => {
    if (beds) {
      return <span style={{ color: '#00AFFF' }}>{beds} BEDS{status === 'OPEN' ? 'OPEN' : 'CLOSED'}</span>;
    }
    return <span style={{ color: '#00FFA0' }}>{status}</span>;
  };

  const formatSearchStatus = (status?: string) => {
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
  };

  return (
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
            {sortedHospitals.map((hospital, index) => (
              <tr key={index} className="h-14">
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
  );
};

export default HospitalList; 