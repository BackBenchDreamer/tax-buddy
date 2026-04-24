'use client';

import { useState, useCallback, useRef } from 'react';
import { toast } from 'sonner';
import { FileUpload } from '@/components/FileUpload';
import { ProcessingSteps, StepKey } from '@/components/ProcessingSteps';
import { ExtractedDataTable } from '@/components/ExtractedDataTable';
import { ValidationPanel } from '@/components/ValidationPanel';
import { TaxSummary } from '@/components/TaxSummary';
import { RegimeComparison } from '@/components/RegimeComparison';
import { TaxExplanation } from '@/components/TaxExplanation';
import { Charts } from '@/components/Charts';
import { processDocument, computeTax, downloadTaxReport, APIError } from '@/lib/api';
import { ProcessResponse, TaxResult } from '@/types';
import { Zap, FileText, Download } from 'lucide-react';

type AppState = 'idle' | 'processing' | 'results';

export default function Home() {
  const [appState, setAppState] = useState<AppState>('idle');
  const [result, setResult] = useState<ProcessResponse | null>(null);
  const [regimeNew, setRegimeNew] = useState<TaxResult | null>(null);
  const [apiResolved, setApiResolved] = useState(false);
  const [processingError, setProcessingError] = useState<{ stage: StepKey; message: string } | null>(null);
  
  const currentFileRef = useRef<File | null>(null);
  const [currentFileName, setCurrentFileName] = useState<string>('');

  const handleProcess = useCallback(async (file: File) => {
    currentFileRef.current = file;
    setCurrentFileName(file.name);
    setResult(null);
    setRegimeNew(null);
    setApiResolved(false);
    setProcessingError(null);
    setAppState('processing');

    try {
      const data = await processDocument(file);
      setResult(data);
      
      // Auto-compute new regime if old is present
      if (data.tax) {
        try {
          const entityMap: Record<string, string | number> = {};
          data.entities.forEach(e => { entityMap[e.label] = e.value; });
          const gross = parseFloat(String(entityMap['GrossSalary'] ?? 0));
          const taxable = parseFloat(String(entityMap['TaxableIncome'] ?? 0));
          const tds = parseFloat(String(entityMap['TDS'] ?? 0));
          
          if (gross > 0) {
            const newTax = await computeTax({ GrossSalary: gross, Deductions: gross - taxable, TDS: tds }, 'new');
            setRegimeNew(newTax);
          }
        } catch (e) {
          console.error("Failed to auto-compute new regime", e);
        }
      }

      setApiResolved(true);
    } catch (err) {
      const stage: StepKey = (err instanceof APIError && err.stage === 'process') ? 'ocr' : 'ocr';
      const msg = err instanceof APIError ? err.message : 'Unexpected error. Is the backend running?';
      setProcessingError({ stage, message: msg });
      setApiResolved(true);
      toast.error('Processing failed', { description: msg });
    }
  }, []);

  const handleProcessingComplete = useCallback(() => {
    setAppState('results');
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (result) {
      toast.success('Analysis Complete', {
        description: `Verified ${result.entities.length} fields. Score: ${result.validation.score}/100`,
      });
    }
  }, [result]);

  const handleRetry = useCallback(() => {
    if (currentFileRef.current) {
      handleProcess(currentFileRef.current);
    } else {
      setAppState('idle');
    }
  }, [handleProcess]);

  const comparison = result?.tax && regimeNew ? { old: result.tax, new: regimeNew } : null;

  return (
    <div className="min-h-screen flex flex-col bg-[#0a0b0f] text-slate-100 font-sans selection:bg-indigo-500/30">
      
      {/* ── TOP NAV ───────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-50 border-b border-slate-800/60 bg-[#0a0b0f]/80 backdrop-blur-xl">
        <div className="max-w-screen-xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => setAppState('idle')}>
            <div className="w-8 h-8 rounded-xl bg-indigo-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <Zap className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-bold text-slate-100 tracking-tight">Tax Buddy</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {appState === 'results' && (
              <>
                {result?.tax && (
                  <button
                    onClick={() => {
                      if (!result) return;
                      downloadTaxReport({
                        entities: result.entities,
                        validation: result.validation,
                        tax: result.tax as unknown as Record<string, unknown>,
                      }).catch(() => toast.error('Report generation failed'));
                    }}
                    className="text-xs font-semibold px-4 py-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-400 transition-colors flex items-center gap-2"
                  >
                    <Download className="w-3.5 h-3.5" />
                    Download Report
                  </button>
                )}
                <button
                  onClick={() => setAppState('idle')}
                  className="text-xs font-semibold px-4 py-2 rounded-lg bg-slate-800/50 hover:bg-slate-700/50 border border-slate-700/50 transition-colors"
                >
                  Upload another document
                </button>
              </>
            )}
            <div className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="text-xs text-slate-500 hidden sm:inline">AI Engine Active</span>
            </div>
          </div>
        </div>
      </header>

      {/* ── MAIN CONTENT ─────────────────────────────────────────────────── */}
      <main className="flex-1 w-full flex flex-col">
        
        {/* PHASE 1: UPLOAD */}
        {appState === 'idle' && (
          <div className="flex-1 flex items-center justify-center p-6 animate-in fade-in duration-700">
            <div className="max-w-2xl w-full text-center">
              <h1 className="text-4xl md:text-5xl font-extrabold tracking-tight mb-4 text-slate-100">
                Upload your <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-violet-400">Form 16</span>
              </h1>
              <p className="text-slate-400 text-lg mb-10 max-w-lg mx-auto">
                AI-powered tax analysis in seconds. We extract, validate, and compute everything for you.
              </p>
              <div className="p-1 rounded-3xl bg-gradient-to-b from-slate-800/60 to-slate-900/40 border border-slate-800/80 shadow-2xl">
                <div className="bg-[#0f111a] rounded-[22px] p-6">
                  <FileUpload onProcess={handleProcess} isLoading={false} />
                </div>
              </div>
            </div>
          </div>
        )}

        {/* PHASE 2: PROCESSING */}
        {appState === 'processing' && (
          <div className="flex-1 flex items-center justify-center p-6 bg-[#0a0b0f]/80 backdrop-blur-sm animate-in fade-in duration-500">
            <div className="max-w-md w-full">
              <ProcessingSteps
                isProcessing={true}
                apiResolved={apiResolved}
                error={processingError}
                onComplete={handleProcessingComplete}
                onRetry={handleRetry}
                fileName={currentFileName}
              />
            </div>
          </div>
        )}

        {/* PHASE 3: RESULTS */}
        {appState === 'results' && result && (
          <div className="max-w-screen-xl mx-auto w-full px-6 py-10 flex flex-col gap-10 animate-in slide-in-from-bottom-8 fade-in duration-700">
            
            {/* ROW 1: HERO TAX SUMMARY */}
            <section className="animate-in slide-in-from-bottom-4 fade-in duration-700 delay-100 fill-mode-both">
              {result.tax ? (() => {
                // Determine recommended regime: show whichever has lower total_tax
                const oldTax = result.tax;
                const newTax = regimeNew;
                const hasComparison = oldTax && newTax;
                
                let heroResult = oldTax;
                let recommendedRegime: string | undefined;
                let savings: number | undefined;
                
                if (hasComparison && newTax) {
                  if (newTax.total_tax < oldTax.total_tax) {
                    heroResult = newTax;
                    recommendedRegime = 'new';
                    savings = oldTax.total_tax - newTax.total_tax;
                  } else if (oldTax.total_tax < newTax.total_tax) {
                    heroResult = oldTax;
                    recommendedRegime = 'old';
                    savings = newTax.total_tax - oldTax.total_tax;
                  }
                }
                
                return (
                  <TaxSummary
                    result={heroResult}
                    recommended={hasComparison ? heroResult : null}
                    recommendedRegime={recommendedRegime}
                    savings={savings}
                  />
                );
              })() : (
                <div className="p-8 rounded-2xl bg-slate-900/50 border border-slate-800 text-center text-slate-500">
                  Tax computation not available.
                </div>
              )}
            </section>

            {/* ROW 2: VALIDATION & REGIME */}
            <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 animate-in slide-in-from-bottom-4 fade-in duration-700 delay-200 fill-mode-both">
              <ValidationPanel result={result.validation} />
              <RegimeComparison comparison={comparison} />
            </section>

            {/* ROW 3: EXPLAIN YOUR TAX */}
            {result.tax && (
              <section className="animate-in slide-in-from-bottom-4 fade-in duration-700 delay-300 fill-mode-both">
                <TaxExplanation result={result.tax} />
              </section>
            )}

            {/* ROW 4: DOCUMENT DETAILS */}
            <section className="animate-in slide-in-from-bottom-4 fade-in duration-700 delay-400 fill-mode-both">
              <div className="flex items-center gap-2 mb-4">
                <FileText className="w-4 h-4 text-slate-400" />
                <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">Document Details</h3>
              </div>
              <ExtractedDataTable entities={result.entities} />
            </section>

            {/* ROW 5: CHARTS */}
            {result.tax && (
              <section className="animate-in slide-in-from-bottom-4 fade-in duration-700 delay-500 fill-mode-both">
                <div className="flex items-center gap-2 mb-4">
                  <div className="w-1 h-5 rounded-full bg-gradient-to-b from-indigo-400 to-indigo-600" />
                  <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-widest">Analytics</h3>
                </div>
                <Charts tax={result.tax} />
              </section>
            )}

          </div>
        )}

      </main>
    </div>
  );
}
