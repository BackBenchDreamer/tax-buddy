'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { TrendingDown, TrendingUp, Banknote, Calculator } from 'lucide-react';

interface TaxSummaryProps {
  result: TaxResult;
}

export function TaxSummary({ result }: TaxSummaryProps) {
  const refund = result.refund_or_payable;
  const isRefund = refund >= 0;

  return (
    <div className="tax-hero-card p-8 md:p-10 flex flex-col items-center text-center">
      
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800/50 border border-slate-700/50 text-xs font-semibold text-slate-300 mb-6">
        <Calculator className="w-3.5 h-3.5 text-amber-400" />
        <span className="capitalize">{result.regime} Regime Tax Summary</span>
      </div>

      <p className="text-sm text-slate-400 uppercase tracking-[0.2em] mb-3">Total Tax {isRefund ? 'Refund' : 'Payable'}</p>
      
      <div className="flex flex-col items-center mb-10">
        <h1 className="text-6xl md:text-8xl font-extrabold text-transparent bg-clip-text bg-gradient-to-br from-amber-200 to-amber-500 tabular-nums tracking-tighter drop-shadow-2xl">
          {formatCurrency(Math.abs(refund))}
        </h1>
        <div className={`mt-4 px-4 py-1.5 rounded-full text-sm font-bold flex items-center gap-2 ${
          isRefund ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-500 border border-amber-500/20'
        }`}>
          {isRefund ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          {isRefund ? 'You are owed a refund' : 'You need to pay this amount'}
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full max-w-4xl">
        {[
          { label: 'Gross Income', value: result.gross_income, color: 'text-slate-200' },
          { label: 'Deductions', value: result.deductions, color: 'text-violet-300' },
          { label: 'Taxable Income', value: result.taxable_income, color: 'text-indigo-300' },
          { label: 'TDS Deducted', value: result.tds_paid, color: 'text-emerald-300' },
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
