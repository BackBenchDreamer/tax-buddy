'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { TrendingDown, TrendingUp, Banknote, Calculator, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';

interface TaxSummaryProps {
  result: TaxResult;
  comparison?: { old: TaxResult; new: TaxResult } | null;
}

export function TaxSummary({ result, comparison }: TaxSummaryProps) {
  const [showSlabs, setShowSlabs] = useState(false);
  const refund = result.refund_or_payable;
  const isRefund = refund >= 0;

  return (
    <div className="tax-hero-card rounded-2xl p-6 flex flex-col gap-6">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-amber-500/30 to-orange-500/20 flex items-center justify-center">
            <Calculator className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h2 className="text-base font-bold text-slate-100 tracking-tight">Tax Summary</h2>
            <p className="text-[11px] text-slate-500 capitalize">{result.regime} regime · FY 2023-24</p>
          </div>
        </div>
      </div>

      {/* Hero number — Total Tax */}
      <div className="text-center py-3">
        <p className="text-[11px] text-slate-500 uppercase tracking-widest mb-2">Total Tax Payable</p>
        <p className="text-4xl md:text-5xl font-extrabold text-amber-400 tabular-nums tracking-tight">
          {formatCurrency(result.total_tax)}
        </p>
        <div className={`inline-flex items-center gap-1.5 mt-3 px-3 py-1 rounded-full text-xs font-semibold ${
          isRefund ? 'bg-emerald-500/10 text-emerald-400' : 'bg-red-500/10 text-red-400'
        }`}>
          {isRefund ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
          {isRefund ? 'Refund' : 'Payable'}: {formatCurrency(Math.abs(refund))}
        </div>
      </div>

      {/* 4 metric cards — bigger */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {[
          { label: 'Gross Income', value: result.gross_income, icon: Banknote, accent: 'indigo' },
          { label: 'Deductions', value: result.deductions, icon: TrendingDown, accent: 'violet' },
          { label: 'Taxable Income', value: result.taxable_income, icon: Calculator, accent: 'sky' },
          { label: 'TDS Paid', value: result.tds_paid, icon: TrendingUp, accent: 'emerald' },
        ].map(({ label, value, icon: Icon, accent }) => (
          <div key={label} className={`rounded-xl border border-${accent}-500/15 bg-${accent}-500/5 p-4`}>
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[10px] text-slate-500 uppercase tracking-widest">{label}</span>
              <Icon className={`w-3.5 h-3.5 text-${accent}-400 opacity-50`} />
            </div>
            <div className={`text-lg font-bold text-${accent}-300`}>{formatCurrency(value)}</div>
          </div>
        ))}
      </div>

      {/* Detail rows */}
      <div className="rounded-xl bg-slate-900/30 border border-slate-800/40 divide-y divide-slate-800/30">
        {[
          { label: 'Tax Before Rebate', value: result.base_tax },
          { label: 'Section 87A Rebate', value: result.rebate },
          { label: 'Surcharge', value: result.surcharge },
          { label: 'Health & Edu Cess (4%)', value: result.cess },
        ].filter(r => r.value != null && r.value !== 0).map(({ label, value }) => (
          <div key={label} className="flex items-center justify-between px-4 py-2.5">
            <span className="text-xs text-slate-500">{label}</span>
            <span className="text-xs font-medium text-slate-300 tabular-nums">{formatCurrency(value)}</span>
          </div>
        ))}
      </div>

      {/* Slab breakdown — collapsible */}
      {result.breakdown && result.breakdown.length > 0 && (
        <div className="rounded-xl bg-slate-900/30 border border-slate-800/40 overflow-hidden">
          <button
            onClick={() => setShowSlabs(!showSlabs)}
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-800/20 transition-colors"
          >
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Slab Breakdown</span>
            {showSlabs ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
          </button>
          {showSlabs && (
            <div className="divide-y divide-slate-800/30 border-t border-slate-800/40">
              {result.breakdown.map((slab, i) => (
                <div key={i} className="flex items-center justify-between px-4 py-2.5">
                  <div>
                    <div className="text-xs font-medium text-slate-300">{slab.range}</div>
                    <div className="text-[10px] text-slate-600">{(slab.rate * 100).toFixed(0)}%</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs font-semibold text-amber-400 tabular-nums">{formatCurrency(slab.tax)}</div>
                    <div className="text-[10px] text-slate-600 tabular-nums">on {formatCurrency(slab.taxable_amount)}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Regime comparison */}
      {comparison && (
        <div className="rounded-xl bg-slate-900/30 border border-slate-800/40 overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-800/40">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Old vs New Regime</span>
          </div>
          <div className="grid grid-cols-2 divide-x divide-slate-800/40">
            {(['old', 'new'] as const).map((r) => {
              const t = comparison[r];
              const better = comparison.new.total_tax < comparison.old.total_tax ? 'new' : 'old';
              return (
                <div key={r} className={`p-4 text-center ${better === r ? 'bg-emerald-500/5' : ''}`}>
                  <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1">{r} regime</div>
                  <div className={`text-lg font-bold tabular-nums ${better === r ? 'text-emerald-400' : 'text-slate-300'}`}>
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
