import React from 'react';
import { CheckCircle2, Circle, ArrowRight, Layers, Database, Sparkles, GitBranch } from 'lucide-react';

const milestones = [
  {
    id: 1,
    title: 'Milestone 1: Project Setup & API Bridge',
    description: 'FastAPI backend, React + Vite frontend, Tailwind CSS, Axios health check, environment configuration.',
    status: 'current',
    tag: 'Active Foundation',
  },
  {
    id: 2,
    title: 'Milestone 2: GitHub Repository Ingestion',
    description: 'Repository cloning, file filtering, language detection, and AST/file chunking pipeline.',
    status: 'upcoming',
    tag: 'Next Milestone',
  },
  {
    id: 3,
    title: 'Milestone 3: Embeddings & Vector Store',
    description: 'HuggingFace code embeddings, ChromaDB vector indexing, semantic search store.',
    status: 'upcoming',
    tag: 'Planned',
  },
  {
    id: 4,
    title: 'Milestone 4: RAG Pipeline & Groq Integration',
    description: 'LangChain retrieval pipeline, Groq LLM integration, prompt templates with contextual citations.',
    status: 'upcoming',
    tag: 'Planned',
  },
  {
    id: 5,
    title: 'Milestone 5: Interactive Guide & Dashboard',
    description: 'Interactive chat interface, repository visualizer, dependency graph, and Q&A assistant.',
    status: 'upcoming',
    tag: 'Planned',
  },
];

export default function RoadmapCard() {
  return (
    <div className="w-full max-w-3xl mx-auto mt-10 bg-slate-900/60 backdrop-blur-md border border-slate-800/80 rounded-2xl p-6 sm:p-8">
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2.5 rounded-xl bg-slate-800 text-sky-400 border border-slate-700/60">
          <Layers className="h-5 w-5" />
        </div>
        <div>
          <h3 className="text-base font-semibold text-white">Project Roadmap & Architecture</h3>
          <p className="text-xs text-slate-400">Step-by-step phased development plan</p>
        </div>
      </div>

      <div className="space-y-3">
        {milestones.map((m) => {
          const isCurrent = m.status === 'current';
          return (
            <div
              key={m.id}
              className={`p-4 rounded-xl border transition-all text-left ${
                isCurrent
                  ? 'bg-gradient-to-r from-cyan-950/40 to-blue-950/30 border-cyan-500/40 shadow-lg shadow-cyan-950/20'
                  : 'bg-slate-950/40 border-slate-800/60 opacity-75 hover:opacity-90'
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  {isCurrent ? (
                    <CheckCircle2 className="h-5 w-5 text-cyan-400 shrink-0 mt-0.5" />
                  ) : (
                    <Circle className="h-5 w-5 text-slate-600 shrink-0 mt-0.5" />
                  )}
                  <div>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-sm font-semibold ${isCurrent ? 'text-white' : 'text-slate-300'}`}>
                        {m.title}
                      </span>
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${
                          isCurrent
                            ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                            : 'bg-slate-800 text-slate-400'
                        }`}
                      >
                        {m.tag}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 mt-1 leading-relaxed">{m.description}</p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

