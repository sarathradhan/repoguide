import React, { useState, useEffect } from 'react';
import { 
  Activity, 
  CheckCircle2, 
  XCircle, 
  RefreshCw, 
  Clock, 
  Server, 
  ShieldAlert, 
  Code2, 
  ChevronDown, 
  ChevronUp,
  Copy,
  Check
} from 'lucide-react';
import { checkBackendHealth } from '../services/api';

export default function ConnectionCard() {
  const [status, setStatus] = useState('idle'); // 'idle' | 'loading' | 'connected' | 'failed'
  const [healthData, setHealthData] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [latency, setLatency] = useState(null);
  const [lastTestedAt, setLastTestedAt] = useState(null);
  const [showRawJson, setShowRawJson] = useState(false);
  const [copied, setCopied] = useState(false);

  const testConnection = async () => {
    setStatus('loading');
    setErrorMessage('');
    
    const result = await checkBackendHealth();
    setLastTestedAt(new Date().toLocaleTimeString());
    setLatency(result.latencyMs);

    if (result.success) {
      setStatus('connected');
      setHealthData(result.data);
    } else {
      setStatus('failed');
      setHealthData(null);
      setErrorMessage(result.error || 'Connection failed');
    }
  };

  // Perform an initial health check on component mount
  useEffect(() => {
    testConnection();
  }, []);

  const handleCopyJson = () => {
    if (!healthData) return;
    navigator.clipboard.writeText(JSON.stringify(healthData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 sm:p-8 shadow-2xl shadow-black/40">
      {/* Header with status badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-800/80">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-slate-800 text-cyan-400 border border-slate-700/60">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-white tracking-tight">Backend Integration Status</h2>
            <p className="text-xs text-slate-400">Verifying live communication with FastAPI backend</p>
          </div>
        </div>

        {/* Dynamic Status Indicator */}
        <div className="flex items-center">
          {status === 'loading' && (
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-950/60 border border-amber-600/40 text-amber-300 text-xs font-medium animate-pulse">
              <RefreshCw className="h-3.5 w-3.5 animate-spin text-amber-400" />
              Testing Connection...
            </span>
          )}

          {status === 'connected' && (
            <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-950/70 border border-emerald-500/40 text-emerald-300 text-xs font-semibold shadow-lg shadow-emerald-950/40">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              Connected
            </span>
          )}

          {status === 'failed' && (
            <span className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-rose-950/70 border border-rose-500/40 text-rose-300 text-xs font-semibold">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500"></span>
              Connection Failed
            </span>
          )}

          {status === 'idle' && (
            <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 text-slate-400 text-xs font-medium">
              Ready to test
            </span>
          )}
        </div>
      </div>

      {/* Main Body Metrics / Details */}
      <div className="py-6">
        {status === 'connected' && healthData && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Service</span>
              <span className="text-sm font-semibold text-white truncate block">{healthData.service}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Version</span>
              <span className="text-sm font-semibold text-cyan-400 block">{healthData.version}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Environment</span>
              <span className="text-sm font-semibold text-emerald-400 capitalize block">{healthData.environment}</span>
            </div>
            <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
              <span className="text-[11px] font-medium text-slate-400 block mb-1">Roundtrip Latency</span>
              <span className="text-sm font-semibold text-sky-300 block">{latency !== null ? `${latency} ms` : '—'}</span>
            </div>
          </div>
        )}

        {status === 'failed' && (
          <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-800/50 mb-6 flex items-start gap-3 text-left">
            <ShieldAlert className="h-5 w-5 text-rose-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-rose-300">Connection Error</p>
              <p className="text-xs text-rose-400/90 mt-1">{errorMessage}</p>
              <div className="mt-3 pt-3 border-t border-rose-900/40 text-[11px] text-slate-400 space-y-1">
                <p className="font-mono text-slate-300">Troubleshooting checklist:</p>
                <p>1. Ensure backend is running: <code className="text-rose-300 bg-black/40 px-1 py-0.5 rounded">uvicorn app.main:app --reload</code></p>
                <p>2. Verify backend port: <code className="text-rose-300 bg-black/40 px-1 py-0.5 rounded">http://localhost:8000/api/health</code></p>
                <p>3. Check CORS origins in <code className="text-rose-300 bg-black/40 px-1 py-0.5 rounded">backend/.env</code></p>
              </div>
            </div>
          </div>
        )}

        {/* Action button & target info */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2">
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <span className="font-mono bg-slate-950 px-2 py-1 rounded text-cyan-400 border border-slate-800">
              GET /api/health
            </span>
            {lastTestedAt && (
              <span className="flex items-center gap-1 text-slate-400">
                <Clock className="h-3 w-3" /> Tested at {lastTestedAt}
              </span>
            )}
          </div>

          <button
            onClick={testConnection}
            disabled={status === 'loading'}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 active:scale-[0.98] text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${status === 'loading' ? 'animate-spin' : ''}`} />
            <span>Test Connection</span>
          </button>
        </div>

        {/* Collapsible raw JSON response inspector */}
        {healthData && (
          <div className="mt-6 pt-4 border-t border-slate-800/60">
            <button
              onClick={() => setShowRawJson(!showRawJson)}
              className="w-full flex items-center justify-between text-xs text-slate-400 hover:text-slate-200 transition-colors py-1 cursor-pointer"
            >
              <span className="flex items-center gap-1.5 font-mono">
                <Code2 className="h-3.5 w-3.5 text-cyan-400" />
                Raw Backend Response
              </span>
              {showRawJson ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>

            {showRawJson && (
              <div className="mt-2 relative rounded-xl bg-slate-950 p-4 border border-slate-800/90 text-left font-mono text-xs">
                <button
                  onClick={handleCopyJson}
                  className="absolute top-3 right-3 p-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors cursor-pointer"
                  title="Copy JSON"
                >
                  {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                </button>
                <pre className="text-cyan-300/90 overflow-x-auto whitespace-pre leading-relaxed pr-8">
                  {JSON.stringify(healthData, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

