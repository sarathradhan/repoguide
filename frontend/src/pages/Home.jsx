import React from 'react';
import Navbar from '../components/Navbar';
import Hero from '../components/Hero';
import ConnectionCard from '../components/ConnectionCard';
import RoadmapCard from '../components/RoadmapCard';
import Footer from '../components/Footer';

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col bg-slate-950 text-slate-100 selection:bg-cyan-500/30 selection:text-cyan-200">
      <Navbar />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-4 sm:py-8 flex flex-col items-center">
        <Hero />
        <ConnectionCard />
        <RoadmapCard />
      </main>

      <Footer />
    </div>
  );
}

