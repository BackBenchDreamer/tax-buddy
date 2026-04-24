'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { TrendingDown, TrendingUp, Calculator, CheckCircle2, Sparkles } from 'lucide-react';

interface TaxSummaryProps {
  result: TaxResult;
  recommended?: TaxResult | null;
  recommendedRegime?: string;
  savings?: number;
}

/**
 * Determine the correct tax status based on total_tax vs TDS.
 *
 * total_tax > TDS → "Amount Payable" (red)
 * total_tax < TDS → "Refund Due"     (green)
 * total_tax = TDS → "No Tax Due"     (neutral green)
 */
function getTaxStatus(result: TaxResult) {
  const diff = result.tds_paid - result.total_tax; // positive = refund

  if (diff > 0) {
    return {
      kind: 'refund' as const,
      label: 'Refund Due',
      heroLabel: 'Your Refund Amount',
      summary: 'You are eligible for a refund',
      amount: diff,
      color: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10 border-emerald-500/20',
      gradientFrom: 'from-emerald-300',
      gradientTo: 'to-emerald-500',
      icon: TrendingUp,
    };
  }

  if (diff < 0) {
    return {
      kind: 'payable' as const,
      label: 'Additional Tax Due',
      heroLabel: 'Amount Payable',
      summary: 'Additional tax payment required',
      amount: Math.abs(diff),
      color: 'text-red-400',
      bgColor: 'bg-red-500/10 border-red-500/20',
      gradientFrom: 'from-amber-300',
      gradientTo: 'to-red-500',
      icon: TrendingDown,
    };
  }

  return {
    kind: 'settled' as const,
    label: 'Fully Settled',
    heroLabel: 'No Additional Tax',
    summary: 'Your taxes are fully settled',
    amount: 0,
    color: 'text-emerald-400',
    bgColor: 'bg-emerald-500/10 border-emerald-500/20',
    gradientFrom: 'from-emerald-300',
    gradientTo: 'to-emerald-500',
    icon: CheckCircle2,
  };
}

export function TaxSummary({ result, recommended, recommendedRegime, savings }: TaxSummaryProps) {
  const status = getTaxStatus(result);
  const StatusIcon = status.icon;

  return (
    <div className="tax-hero-card p-8 md:p-10 flex flex-col items-center text-center">

      {/* Top badge row */}
      <div className="flex items-center gap-3 mb-6">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/50 border border-slate-700/50 text-xs font-semibold text-slate-300">
          <Calculator className="w-3.5 h-3.5 text-amber-400" />
          <span className="capitalize">{result.regime} Regime</span>
        </div>
        {recommendedRegime && (
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-xs font-bold text-indigo-400">
            <Sparkles className="w-3 h-3" />
            Recommended
          </div>
        )}
      </div>

      {/* Hero number */}
      <p className="text-sm text-slate-400 uppercase tracking-[0.2em] mb-3">{status.heroLabel}</p>

      <div className="flex flex-col items-center mb-4">
        {status.kind === 'settled' ? (
          <div className="flex flex-col items-center gap-3">
            <CheckCircle2 className="w-16 h-16 text-emerald-400" />
            <h1 className="text-4xl font-extrabold text-emerald-400">{formatCurrency(result.total_tax)}</h1>
            <p className="text-sm text-slate-400">Total tax = TDS deducted</p>
          </div>
        ) : (
          <h1 className={`text-6xl md:text-8xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br ${status.gradientFrom} ${status.gradientTo} tabular-nums tracking-tighter drop-shadow-2xl`}>
            {formatCurrency(status.amount)}
          </h1>
        )}
      </div>

      {/* Status badge */}
      <div className={`px-4 py-1.5 rounded-full text-sm font-bold flex items-center gap-2 border ${status.bgColor}`}>
        <StatusIcon className={`w-4 h-4 ${status.color}`} />
        <span className={status.color}>{status.label}</span>
      </div>

      {/* Summary line */}
      <p className="text-sm text-slate-400 mt-3">{status.summary}</p>

      {/* Savings callout */}
      {savings != null && savings > 0 && recommendedRegime && (
        <div className="mt-4 px-4 py-2 rounded-xl bg-indigo-500/5 border border-indigo-500/15 text-xs text-indigo-400">
          💡 Switching to <span className="font-bold capitalize">{recommendedRegime} Regime</span> saves {formatCurrency(savings)}
        </div>
      )}

      {/* 4 metric cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-4xl mt-8">
        {[
          { label: 'Gross Income', value: result.gross_income, color: 'text-slate-200' },
          { label: 'Deductions', value: result.deductions, color: 'text-slate-300' },
          { label: 'Taxable Income', value: result.taxable_income, color: 'text-slate-200' },
          { label: 'TDS Deducted', value: result.tds_paid, color: 'text-slate-300' },
        ].map(({ label, value, color }) => (
          <div key={label} className="flex flex-col items-center p-4 rounded-2xl bg-slate-900/40 border border-slate-800/50">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest mb-1.5">{label}</span>
            <span className={`text-xl font-bold tabular-nums ${color}`}>{formatCurrency(value)}</span>
          </div>
        ))}
      </div>

    </div>
  );
}
