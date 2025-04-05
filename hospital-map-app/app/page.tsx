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
        <div className="md:col-span-3">
          <div className="bg-black bg-opacity-80 backdrop-blur-sm rounded-lg overflow-hidden shadow-lg border border-blue-400 p-6">
            <USAMap onSelectState={handleSelectState} selectedState={selectedState} />
          </div>
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
