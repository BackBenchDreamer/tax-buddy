'use client';

import { useEffect, useState } from 'react';
import { Check, Loader2, Circle, AlertCircle, Scan, Brain, ShieldCheck, Calculator, RotateCcw } from 'lucide-react';
import { cn } from '@/lib/utils';

// ── Types ──────────────────────────────────────────────────────────────────

export type StepKey = 'ocr' | 'ner' | 'validation' | 'tax';
export type StepStatus = 'pending' | 'active' | 'completed' | 'error';

export interface PipelineStep {
  key: StepKey;
  label: string;
  description: string;
  icon: React.ElementType;
}

const STEPS: PipelineStep[] = [
  { key: 'ocr',        label: 'Running OCR',          description: 'Scanning pages and extracting text…',   icon: Scan },
  { key: 'ner',        label: 'Extracting Entities',   description: 'Identifying PAN, TAN, salary fields…', icon: Brain },
  { key: 'validation', label: 'Validating Data',       description: 'Cross-checking Form 16 vs 26AS…',      icon: ShieldCheck },
  { key: 'tax',        label: 'Computing Tax',         description: 'Calculating slabs, rebate & cess…',     icon: Calculator },
];

// Simulated step durations (ms) — gives a sense of progress before API resolves
const STEP_DURATIONS: Record<StepKey, number> = {
  ocr: 1400,
  ner: 1200,
  validation: 1000,
  tax: 800,
};

// ── Component ──────────────────────────────────────────────────────────────

interface ProcessingStepsProps {
  /** true while the API call is in flight */
  isProcessing: boolean;
  /** optional: backend can push the current stage */
  apiStage?: StepKey | null;
  /** fired when all steps visually complete (after API resolved) */
  onComplete?: () => void;
  /** if an error occurs during processing */
  error?: { stage: StepKey; message: string } | null;
  /** callback to retry after error */
  onRetry?: () => void;
  /** true once the API call has resolved (success or error) */
  apiResolved: boolean;
  /** file name being processed */
  fileName?: string;
}

export function ProcessingSteps({
  isProcessing,
  apiStage,
  onComplete,
  error,
  onRetry,
  apiResolved,
  fileName,
}: ProcessingStepsProps) {
  const [currentStepIdx, setCurrentStepIdx] = useState(-1);
  const [stepStatuses, setStepStatuses] = useState<Record<StepKey, StepStatus>>({
    ocr: 'pending',
    ner: 'pending',
    validation: 'pending',
    tax: 'pending',
  });

  // ── Simulated progression timer ────────────────────────────────────────
  useEffect(() => {
    if (!isProcessing) return;

    // Reset everything on new processing run
    setCurrentStepIdx(0);
    setStepStatuses({
      ocr: 'active',
      ner: 'pending',
      validation: 'pending',
      tax: 'pending',
    });

    let idx = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];

    const advance = () => {
      if (idx >= STEPS.length - 1) return; // stop at last step — wait for API
      const currentKey = STEPS[idx].key;
      const delay = STEP_DURATIONS[currentKey];

      const timer = setTimeout(() => {
        idx += 1;
        const nextKey = STEPS[idx].key;
        setCurrentStepIdx(idx);
        setStepStatuses((prev) => ({
          ...prev,
          [currentKey]: 'completed',
          [nextKey]: 'active',
        }));
        advance();
      }, delay);

      timers.push(timer);
    };

    advance();

    return () => timers.forEach(clearTimeout);
  }, [isProcessing]);

  // ── Sync with API stage (optional backend hint) ────────────────────────
  useEffect(() => {
    if (!apiStage) return;
    const targetIdx = STEPS.findIndex((s) => s.key === apiStage);
    if (targetIdx <= currentStepIdx) return; // don't go backwards

    // Fast-forward to the API-reported stage
    setCurrentStepIdx(targetIdx);
    setStepStatuses((prev) => {
      const next = { ...prev };
      STEPS.forEach((step, i) => {
        if (i < targetIdx) next[step.key] = 'completed';
        else if (i === targetIdx) next[step.key] = 'active';
        // leave future steps as-is
      });
      return next;
    });
  }, [apiStage, currentStepIdx]);

  // ── API resolved → mark remaining as completed ────────────────────────
  useEffect(() => {
    if (!apiResolved) return;

    if (error) {
      // Mark error step
      setStepStatuses((prev) => ({ ...prev, [error.stage]: 'error' }));
      return;
    }

    // Success: fast-forward remaining steps with staggered animation
    const unfinished = STEPS.filter((s) => stepStatuses[s.key] !== 'completed');

    unfinished.forEach((step, i) => {
      setTimeout(() => {
        setStepStatuses((prev) => ({ ...prev, [step.key]: 'completed' }));
        // Fire onComplete after last step
        if (i === unfinished.length - 1) {
          setTimeout(() => onComplete?.(), 400);
        }
      }, i * 200);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiResolved, error]);

  // ── Elapsed timer ─────────────────────────────────────────────────────
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!isProcessing) { setElapsed(0); return; }
    const interval = setInterval(() => setElapsed((e) => e + 100), 100);
    return () => clearInterval(interval);
  }, [isProcessing]);

  const completedCount = STEPS.filter((s) => stepStatuses[s.key] === 'completed').length;
  const progress = (completedCount / STEPS.length) * 100;

  // ── Render ─────────────────────────────────────────────────────────────

  return (
    <div className="glow-card p-6 flex flex-col gap-5 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <div className="w-7 h-7 rounded-lg bg-indigo-500/20 flex items-center justify-center pulse-ring">
              <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
            </div>
            <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Processing</h2>
          </div>
          {fileName && (
            <p className="text-xs text-slate-500 ml-9 truncate max-w-[240px]">{fileName}</p>
          )}
        </div>
        <span className="text-xs text-slate-600 tabular-nums font-mono">
          {(elapsed / 1000).toFixed(1)}s
        </span>
      </div>

      {/* Progress bar */}
      <div className="relative h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
        <div
          className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-indigo-500 to-violet-500 transition-all duration-500 ease-out"
          style={{ width: `${error ? progress : Math.max(progress, 8)}%` }}
        />
        {!error && isProcessing && (
          <div className="absolute inset-0 progress-shimmer" />
        )}
      </div>

      {/* Steps */}
      <div className="flex flex-col gap-1">
        {STEPS.map((step, i) => {
          const status = stepStatuses[step.key];
          const Icon = step.icon;
          return (
            <div
              key={step.key}
              className={cn(
                'flex items-start gap-3.5 rounded-xl px-3.5 py-3 transition-all duration-300',
                status === 'active' && 'bg-indigo-500/8 border border-indigo-500/15',
                status === 'completed' && 'opacity-70',
                status === 'error' && 'bg-red-500/8 border border-red-500/15',
                status === 'pending' && 'opacity-40',
              )}
            >
              {/* Step indicator */}
              <div className="mt-0.5 flex-shrink-0">
                <StepIcon status={status} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon className={cn(
                      'w-3.5 h-3.5',
                      status === 'active' && 'text-indigo-400',
                      status === 'completed' && 'text-emerald-400',
                      status === 'error' && 'text-red-400',
                      status === 'pending' && 'text-slate-600',
                    )} />
                    <span className={cn(
                      'text-sm font-medium',
                      status === 'active' && 'text-slate-100',
                      status === 'completed' && 'text-slate-300',
                      status === 'error' && 'text-red-300',
                      status === 'pending' && 'text-slate-500',
                    )}>
                      {step.label}
                    </span>
                  </div>
                  <StatusLabel status={status} />
                </div>

                {/* Microcopy */}
                {(status === 'active' || status === 'error') && (
                  <p className={cn(
                    'text-xs mt-1 ml-5.5 transition-all duration-300 step-microcopy',
                    status === 'active' && 'text-slate-500',
                    status === 'error' && 'text-red-400/70',
                  )}>
                    {status === 'error' ? error?.message : step.description}
                  </p>
                )}
              </div>

              {/* Connector line */}
              {i < STEPS.length - 1 && (
                <div className="absolute left-[29px] mt-[30px] w-px h-[18px]" />
              )}
            </div>
          );
        })}
      </div>

      {/* Error retry */}
      {error && onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center justify-center gap-2 w-full h-10 rounded-xl bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 text-red-400 text-sm font-medium transition-all duration-200 hover:-translate-y-0.5"
        >
          <RotateCcw className="w-3.5 h-3.5" />
          Retry Processing
        </button>
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────────

function StepIcon({ status }: { status: StepStatus }) {
  if (status === 'completed') {
    return (
      <div className="w-5 h-5 rounded-full bg-emerald-500/20 flex items-center justify-center step-check-enter">
        <Check className="w-3 h-3 text-emerald-400" strokeWidth={3} />
      </div>
    );
  }

  if (status === 'active') {
    return (
      <div className="w-5 h-5 rounded-full bg-indigo-500/20 flex items-center justify-center relative">
        <div className="w-2 h-2 rounded-full bg-indigo-400 step-active-dot" />
        <div className="absolute inset-0 rounded-full border border-indigo-400/30 step-active-ring" />
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="w-5 h-5 rounded-full bg-red-500/20 flex items-center justify-center">
        <AlertCircle className="w-3 h-3 text-red-400" />
      </div>
    );
  }

  // pending
  return (
    <div className="w-5 h-5 rounded-full border border-slate-700 flex items-center justify-center">
      <Circle className="w-2 h-2 text-slate-700" />
    </div>
  );
}

function StatusLabel({ status }: { status: StepStatus }) {
  if (status === 'completed') {
    return <span className="text-[10px] text-emerald-400 font-semibold uppercase tracking-wider">Done</span>;
  }
  if (status === 'active') {
    return <span className="text-[10px] text-indigo-400 font-semibold uppercase tracking-wider animate-pulse">Running</span>;
  }
  if (status === 'error') {
    return <span className="text-[10px] text-red-400 font-semibold uppercase tracking-wider">Failed</span>;
  }
  return <span className="text-[10px] text-slate-700 uppercase tracking-wider">Queued</span>;
}
