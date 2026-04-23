'use client';

import { useState } from 'react';
import { toast } from 'sonner';
import { FileUpload } from '@/components/FileUpload';
import { ExtractedDataTable } from '@/components/ExtractedDataTable';
import { ValidationPanel } from '@/components/ValidationPanel';
import { TaxSummary } from '@/components/TaxSummary';
import { Charts } from '@/components/Charts';
import { processDocument, computeTax, APIError } from '@/lib/api';
import { ProcessResponse, TaxResult } from '@/types';
import { Zap, Activity, ArrowLeftRight } from 'lucide-react';

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [regimeNew, setRegimeNew] = useState<TaxResult | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [comparingRegimes, setComparingRegimes] = useState(false);

  const handleProcess = async (file: File) => {
    setLoading(true);
    setResult(null);
    setRegimeNew(null);
    setShowComparison(false);
    try {
      const data = await processDocument(file);
      setResult(data);
      toast.success('Document processed successfully!', {
        description: `${data.entities.length} fields extracted · Trust score: ${data.validation.score}/100`,
      });
    } catch (err) {
      const msg = err instanceof APIError
        ? `[${err.stage}] ${err.message}`
        : 'Unexpected error. Is the backend running?';
      toast.error('Processing failed', { description: msg });
    } finally {
      setLoading(false);
    }
  };

  const handleCompareRegimes = async () => {
    if (!result?.tax) return;
    setComparingRegimes(true);
    try {
      const entityMap: Record<string, string | number> = {};
      result.entities.forEach(e => { entityMap[e.label] = e.value; });
      const gross = parseFloat(String(entityMap['GrossSalary'] ?? 0));
      const taxable = parseFloat(String(entityMap['TaxableIncome'] ?? 0));
      const tds = parseFloat(String(entityMap['TDS'] ?? 0));
      const newTax = await computeTax({ GrossSalary: gross, Deductions: gross - taxable, TDS: tds }, 'new');
      setRegimeNew(newTax);
      setShowComparison(true);
      toast.success('Regime comparison ready');
    } catch {
      toast.error('Could not compute new regime tax');
    } finally {
      setComparingRegimes(false);
    }
  };

  const comparison = showComparison && result?.tax && regimeNew
    ? { old: result.tax, new: regimeNew }
    : null;

  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top Nav ─────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-slate-800/60 bg-[#0a0b0f]/80 backdrop-blur-xl">
        <div className="max-w-screen-2xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-xl bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-bold text-slate-100 tracking-tight">Tax Buddy</span>
              <span className="text-slate-600 text-xs ml-2 hidden sm:inline">AI Filing Assistant</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {result && (
              <button
                onClick={handleCompareRegimes}
                disabled={comparingRegimes}
                className="flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-slate-100 border border-slate-700 hover:border-slate-600 transition-all"
              >
                <ArrowLeftRight className="w-3.5 h-3.5" />
                {comparingRegimes ? 'Comparing…' : 'Compare Regimes'}
              </button>
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-slate-500 hidden sm:inline">API Connected</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────────── */}
      {!result && !loading && (
        <div className="text-center py-16 px-6">
          <div className="inline-flex items-center gap-2 text-xs text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 rounded-full px-3 py-1 mb-6">
            <Activity className="w-3 h-3" />
            <span>Powered by OCR · NER · AI Tax Engine</span>
          </div>
          <h1 className="text-4xl md:text-5xl font-bold text-slate-100 mb-4 leading-tight">
            Instant Tax Analysis<br />
            <span className="gradient-text">From Your Form 16</span>
          </h1>
          <p className="text-slate-500 max-w-xl mx-auto text-base">
            Upload your Form 16 PDF and get extracted entities, validation against Form 26AS,
            and full tax computation in seconds.
          </p>
        </div>
      )}

      {/* ── Main Layout ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 md:px-6 pb-10">
        {!result ? (
          /* Upload-focused layout */
          <div className="max-w-md mx-auto">
            <FileUpload onProcess={handleProcess} isLoading={loading} />
          </div>
        ) : (
          /* Results dashboard */
          <div className="flex flex-col gap-5">
            {/* Upload strip */}
            <div className="max-w-sm">
              <FileUpload onProcess={handleProcess} isLoading={loading} />
            </div>

            {/* 3-column grid */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <ExtractedDataTable entities={result.entities} />
              <ValidationPanel result={result.validation} />
              {result.tax ? (
                <TaxSummary result={result.tax} comparison={comparison} />
              ) : (
                <div className="glow-card p-8 flex items-center justify-center">
                  <p className="text-slate-600 text-sm">Tax result unavailable</p>
                </div>
              )}
            </div>

            {/* Charts row */}
            {result.tax && <Charts tax={result.tax} />}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/40 py-4 text-center text-xs text-slate-700">
        Tax Buddy · AI-powered Indian Income Tax Analysis · For informational purposes only
      </footer>
    </div>
  );
}
