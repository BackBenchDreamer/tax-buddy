'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { TrendingDown, TrendingUp, Banknote, Calculator } from 'lucide-react';

interface TaxSummaryProps {
  result: TaxResult;
  comparison?: { old: TaxResult; new: TaxResult } | null;
}

export function TaxSummary({ result, comparison }: TaxSummaryProps) {
  const refund = result.refund_or_payable;
  const isRefund = refund >= 0;

  const cards = [
    { label: 'Gross Income', value: result.gross_income, icon: Banknote, color: 'indigo' },
    { label: 'Taxable Income', value: result.taxable_income, icon: Calculator, color: 'violet' },
    { label: 'Total Tax', value: result.total_tax, icon: TrendingDown, color: 'amber' },
    { label: isRefund ? 'Refund' : 'Tax Due', value: Math.abs(refund), icon: TrendingUp, color: isRefund ? 'emerald' : 'red' },
  ] as const;

  const colorMap = {
    indigo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    violet: 'text-violet-400 bg-violet-500/10 border-violet-500/20',
    amber:  'text-amber-400 bg-amber-500/10 border-amber-500/20',
    emerald:'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    red:    'text-red-400 bg-red-500/10 border-red-500/20',
  };

  return (
    <div className="glow-card p-5 flex flex-col gap-5 h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-amber-500/20 flex items-center justify-center">
            <Calculator className="w-4 h-4 text-amber-400" />
          </div>
          <h2 className="text-sm font-semibold text-slate-200 tracking-wide uppercase">Tax Summary</h2>
        </div>
        <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded-full capitalize">
          {result.regime} regime
        </span>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 gap-2.5">
        {cards.map(({ label, value, icon: Icon, color }) => (
          <div key={label} className={`rounded-xl border p-3.5 ${colorMap[color]}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-widest opacity-70">{label}</span>
              <Icon className="w-3.5 h-3.5 opacity-60" />
            </div>
            <div className="text-base font-bold">{formatCurrency(value)}</div>
          </div>
        ))}
      </div>

      {/* Slab Table */}
      {result.slab_breakdown && result.slab_breakdown.length > 0 && (
        <div className="rounded-xl bg-slate-900/40 border border-slate-800/60 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-800/60 bg-slate-800/30">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Slab Breakdown</span>
          </div>
          <div className="divide-y divide-slate-800/40">
            {result.slab_breakdown.map((slab, i) => (
              <div key={i} className="flex items-center justify-between px-4 py-2.5">
                <div>
                  <div className="text-xs font-medium text-slate-300">{slab.slab}</div>
                  <div className="text-[10px] text-slate-600">{(slab.rate * 100).toFixed(0)}% rate</div>
                </div>
                <div className="text-right">
                  <div className="text-xs font-semibold text-amber-400">{formatCurrency(slab.tax_in_slab)}</div>
                  <div className="text-[10px] text-slate-600">{formatCurrency(slab.taxable_in_slab)}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between px-4 py-3 bg-amber-500/5 border-t border-amber-500/20">
            <span className="text-xs font-semibold text-amber-400 uppercase tracking-wider">Total Tax (incl. cess)</span>
            <span className="text-sm font-bold text-amber-400">{formatCurrency(result.total_tax)}</span>
          </div>
        </div>
      )}

      {/* Tax detail rows */}
      <div className="rounded-xl bg-slate-900/40 border border-slate-800/60 divide-y divide-slate-800/40">
        {[
          { label: 'Deductions', value: result.deductions },
          { label: 'Tax Before Rebate', value: result.tax_before_rebate },
          { label: 'Section 87A Rebate', value: result.rebate },
          { label: 'Health & Edu Cess (4%)', value: result.cess },
          { label: 'TDS Already Paid', value: result.tds_paid },
        ].filter(r => r.value).map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between px-4 py-2.5">
            <span className="text-xs text-slate-500">{label}</span>
            <span className="text-xs font-medium text-slate-300">{formatCurrency(value)}</span>
          </div>
        ))}
      </div>

      {/* Regime comparison */}
      {comparison && (
        <div className="rounded-xl bg-slate-900/40 border border-slate-800/60 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-800/60 bg-slate-800/30 flex items-center gap-2">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Old vs New Regime</span>
          </div>
          <div className="grid grid-cols-2 divide-x divide-slate-800/60">
            {(['old', 'new'] as const).map((r) => {
              const t = comparison[r];
              const better = comparison.new.total_tax < comparison.old.total_tax ? 'new' : 'old';
              return (
                <div key={r} className={`p-4 text-center ${better === r ? 'bg-emerald-500/5' : ''}`}>
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">{r} regime</div>
                  <div className={`text-base font-bold ${better === r ? 'text-emerald-400' : 'text-slate-300'}`}>
                    {formatCurrency(t.total_tax)}
                  </div>
                  {better === r && (
                    <div className="text-[10px] text-emerald-500 mt-1 font-medium">✓ Better</div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
