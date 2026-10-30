import React from 'react';
import { GitFork, Sparkles, Layers, Cpu } from 'lucide-react';

export default function Hero() {
  return (
    <section className="pt-12 pb-8 sm:pt-16 sm:pb-12 text-center max-w-4xl mx-auto px-4">
      {/* Pill header */}
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-cyan-950/50 border border-cyan-800/40 text-cyan-300 text-xs font-medium mb-6">
        <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
        <span>Full-Stack Foundation & Integration</span>
      </div>

      {/* Main Title */}
      <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold text-white tracking-tight leading-tight sm:leading-tight">
        AI-Powered GitHub{' '}
        <span className="bg-gradient-to-r from-cyan-400 via-sky-400 to-blue-500 bg-clip-text text-transparent">
          Repository Guide
        </span>
      </h1>

      {/* Subtitle */}
      <p className="mt-4 sm:mt-6 text-base sm:text-lg text-slate-300 max-w-2xl mx-auto leading-relaxed">
        Understand complex codebases with intelligent architecture mapping, semantic symbol search, and contextual code explanations.
      </p>

      {/* Stack feature tags */}
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2.5 text-xs text-slate-400">
        <span className="px-3 py-1 rounded-md bg-slate-900/90 border border-slate-800 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400"></span> FastAPI + Python 3.13
        </span>
        <span className="px-3 py-1 rounded-md bg-slate-900/90 border border-slate-800 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-400"></span> React 19 + Vite
        </span>
        <span className="px-3 py-1 rounded-md bg-slate-900/90 border border-slate-800 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-400"></span> Tailwind CSS v4
        </span>
        <span className="px-3 py-1 rounded-md bg-slate-900/90 border border-slate-800 flex items-center gap-1.5">
          <span className="h-1.5 w-1.5 rounded-full bg-purple-400"></span> Axios Service Layer
        </span>
      </div>
    </section>
  );
}

