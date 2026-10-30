import React from 'react';
import { Terminal, ExternalLink, ShieldCheck, GitBranch } from 'lucide-react';

export default function Navbar() {
  const apiDocsUrl = `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/docs`;

  return (
    <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 border border-cyan-400/30">
            <Terminal className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-lg text-white tracking-tight">RepoGuide AI</span>
              <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-cyan-950/80 text-cyan-400 border border-cyan-800/60">
                v0.1.0
              </span>
            </div>
            <p className="text-xs text-slate-400 hidden sm:block">Repository Understanding Assistant</p>
          </div>
        </div>

        {/* Right side navigation & status badges */}
        <div className="flex items-center gap-3 sm:gap-4">
          <div className="hidden md:flex items-center gap-2 px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-xs text-slate-300">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span>Milestone 1 Active</span>
          </div>

          <a
            href={apiDocsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white border border-slate-800 hover:border-slate-700 transition-all duration-150"
            title="Open FastAPI Swagger Interactive Documentation"
          >
            <span>Swagger Docs</span>
            <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
          </a>
        </div>
      </div>
    </header>
  );
}

