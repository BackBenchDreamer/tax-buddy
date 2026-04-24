'use client';

import { useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { FileUpload } from '@/components/FileUpload';
import { ProcessingSteps, StepKey } from '@/components/ProcessingSteps';
import { ExtractedDataTable } from '@/components/ExtractedDataTable';
import { ValidationPanel } from '@/components/ValidationPanel';
import { TaxSummary } from '@/components/TaxSummary';
import { Charts } from '@/components/Charts';
import { processDocument, computeTax, APIError } from '@/lib/api';
import { ProcessResponse, TaxResult } from '@/types';
import { Zap, Activity, ArrowLeftRight } from 'lucide-react';

type AppState = 'idle' | 'processing' | 'results';

export default function Home() {
  // ── Core state ─────────────────────────────────────────────────────────
  const [appState, setAppState] = useState<AppState>('idle');
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [regimeNew, setRegimeNew] = useState<TaxResult | null>(null);
  const [showComparison, setShowComparison] = useState(false);
  const [comparingRegimes, setComparingRegimes] = useState(false);

  // ── Processing orchestration ───────────────────────────────────────────
  const [apiResolved, setApiResolved] = useState(false);
  const [processingError, setProcessingError] = useState<{ stage: StepKey; message: string } | null>(null);
  const currentFileRef = useRef<File | null>(null);
  const [currentFileName, setCurrentFileName] = useState<string>('');

  const handleProcess = useCallback(async (file: File) => {
    // Reset all state for new run
    currentFileRef.current = file;
    setCurrentFileName(file.name);
    setResult(null);
    setRegimeNew(null);
    setShowComparison(false);
    setApiResolved(false);
    setProcessingError(null);
    setAppState('processing');

    try {
      const data = await processDocument(file);
      setResult(data);
      setApiResolved(true);
      // onComplete callback in ProcessingSteps will transition to 'results'
    } catch (err) {
      const stage: StepKey = (err instanceof APIError && err.stage === 'process') ? 'ocr' : 'ocr';
      const msg = err instanceof APIError
        ? err.message
        : 'Unexpected error. Is the backend running?';

      setProcessingError({ stage, message: msg });
      setApiResolved(true);
      toast.error('Processing failed', { description: msg });
    }
  }, []);

  const handleProcessingComplete = useCallback(() => {
    setAppState('results');
    if (result) {
      toast.success('Document processed successfully!', {
        description: `${result.entities.length} fields extracted · Trust score: ${result.validation.score}/100`,
      });
    }
  }, [result]);

  const handleRetry = useCallback(() => {
    if (currentFileRef.current) {
      handleProcess(currentFileRef.current);
    }
  }, [handleProcess]);

  // ── Regime comparison ──────────────────────────────────────────────────
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

  // ── Render ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen flex flex-col">
      {/* ── Top Nav ──────────────────────────────────────────────────────── */}
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
            {appState === 'results' && result && (
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

      {/* ── Hero (only when idle) ────────────────────────────────────────── */}
      {appState === 'idle' && (
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

      {/* ── Main Content ─────────────────────────────────────────────────── */}
      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 md:px-6 pb-10">
        {appState === 'idle' && (
          /* Upload-focused layout */
          <div className="max-w-md mx-auto">
            <FileUpload onProcess={handleProcess} isLoading={false} />
          </div>
        )}

        {appState === 'processing' && (
          /* Processing panel — replaces upload card */
          <div className="max-w-md mx-auto">
            <ProcessingSteps
              isProcessing={true}
              apiResolved={apiResolved}
              error={processingError}
              onComplete={handleProcessingComplete}
              onRetry={handleRetry}
              fileName={currentFileName}
            />
          </div>
        )}

        {appState === 'results' && result && (
          /* Results dashboard — hierarchical layout */
          <div className="flex flex-col gap-8">
            {/* Compact upload strip */}
            <div className="max-w-sm">
              <FileUpload onProcess={handleProcess} isLoading={false} />
            </div>

            {/* ── TOP ROW: Tax Summary (primary) + Validation (support) ── */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-1 h-5 rounded-full bg-gradient-to-b from-amber-400 to-amber-600" />
                <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Results</h2>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="lg:col-span-2">
                  {result.tax ? (
                    <TaxSummary result={result.tax} comparison={comparison} />
                  ) : (
                    <div className="glow-card p-8 flex items-center justify-center">
                      <p className="text-slate-600 text-sm">Tax result unavailable</p>
                    </div>
                  )}
                </div>
                <div className="lg:col-span-1">
                  <ValidationPanel result={result.validation} />
                </div>
              </div>
            </section>

            {/* ── MIDDLE ROW: Extracted Data (secondary) ── */}
            <section>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-1 h-5 rounded-full bg-gradient-to-b from-violet-400 to-violet-600" />
                <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Document Details</h2>
              </div>
              <ExtractedDataTable entities={result.entities} />
            </section>

            {/* ── BOTTOM ROW: Charts ── */}
            {result.tax && (
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1 h-5 rounded-full bg-gradient-to-b from-indigo-400 to-indigo-600" />
                  <h2 className="text-sm font-bold text-slate-300 uppercase tracking-widest">Analytics</h2>
                </div>
                <Charts tax={result.tax} />
              </section>
            )}
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
