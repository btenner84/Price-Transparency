"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { HospitalProvider, useHospitalData } from './context/HospitalContext';
import { TransparencyProvider } from './context/TransparencyContext';
import Header from './components/Header';
import USAMap from './components/USAMap';
import HealthSystemList from './components/HealthSystemList';

function MainApp() {
  const router = useRouter();
  const { loading, error } = useHospitalData();
  const [selectedState, setSelectedState] = useState<string | null>(null);

  const handleSelectState = (stateCode: string) => {
    console.log('Map clicked state:', stateCode);
    setSelectedState(stateCode);
    router.push(`/state/${stateCode}`);
  };

  if (loading) {
    return (
      <div className="flex flex-col justify-center items-center h-screen">
        <div className="text-2xl mb-4 neon-text animate-pulse">LOADING HOSPITAL DATA</div>
        <div className="w-12 h-12 border-t-2 border-b-2 border-blue-400 rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto max-w-7xl px-4 py-8 pb-16">
      <Header />
      
      {error && (
        <div className="p-4 rounded-lg mb-6 border border-red-500 bg-red-900 bg-opacity-20">
          <p className="text-red-300">{error}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <div className="md:col-span-2">
          <h1 className="text-4xl font-bold text-center mb-2 neon-text tracking-wider">
            
          </h1>
          
          <div className="bg-black bg-opacity-80 backdrop-blur-sm rounded-lg overflow-hidden shadow-lg border border-blue-400 p-6">
            <USAMap onSelectState={handleSelectState} selectedState={selectedState} />
          </div>
        </div>
        
        <div className="md:col-span-1 flex flex-col justify-center items-center">
          <Link href="/price-files">
            <div className="bg-black bg-opacity-80 border border-blue-400 shadow-[0_0_8px_rgba(66,153,225,0.4)] hover:shadow-[0_0_15px_rgba(66,153,225,0.7)] transition-all duration-300 rounded-lg p-4 text-center hover:bg-blue-900 hover:bg-opacity-20 cursor-pointer w-full max-w-xs">
              <div className="flex items-center justify-between">
                <div className="text-left">
                  <h2 className="text-xl font-bold neon-text tracking-wide">PRICE FILES</h2>
                  <p className="text-blue-300 text-sm mt-1 font-mono">Hospital Transparency Data</p>
                </div>
                <div className="text-blue-400 flex-shrink-0">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" 
                       fill="none" viewBox="0 0 24 24" stroke="currentColor"
                       style={{ maxWidth: '24px', maxHeight: '24px' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </div>
            </div>
          </Link>
        </div>
      </div>
      
      <div className="w-full mt-20 mb-12">
        <div className="border-t border-blue-400 pt-16">
          <HealthSystemList />
        </div>
      </div>
    </div>
  );
}

export default function Home() {
  return (
    <HospitalProvider>
      <TransparencyProvider>
        <MainApp />
      </TransparencyProvider>
    </HospitalProvider>
  );
}
