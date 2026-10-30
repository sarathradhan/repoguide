import React from 'react';
import { Terminal, Code2, Sparkles } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="mt-16 border-t border-slate-900 bg-slate-950/80 py-8 text-center text-xs text-slate-400">
      <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-slate-400">
          <Terminal className="h-4 w-4 text-cyan-400" />
          <span className="font-semibold text-slate-300">RepoGuide AI</span>
          <span>•</span>
          <span>Milestone 1 Complete</span>
        </div>

        <p className="text-slate-400">
          Modular fullstack architecture ready for Milestone 2 ingestion pipeline.
        </p>

        <div className="flex items-center gap-4 text-slate-400">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 transition-colors"
          >
            API Docs
          </a>
          <span>•</span>
          <a
            href="http://localhost:8000/api/health"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 transition-colors"
          >
            Health JSON
          </a>
        </div>
      </div>
    </footer>
  );
}
