'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { useState } from 'react';
import { ChevronDown, ChevronUp, BookOpen } from 'lucide-react';

export function TaxExplanation({ result }: { result: TaxResult }) {
  const [open, setOpen] = useState(false);

  // Preview equation: total = base_tax - rebate + surcharge + cess
  const previewParts: string[] = [];
  if (result.base_tax > 0) previewParts.push(`${formatCurrency(result.base_tax)} tax`);
  if (result.rebate > 0) previewParts.push(`−${formatCurrency(result.rebate)} rebate`);
  if (result.surcharge > 0) previewParts.push(`+${formatCurrency(result.surcharge)} surcharge`);
  if (result.cess > 0) previewParts.push(`+${formatCurrency(result.cess)} cess`);
  const previewEquation = `${formatCurrency(result.total_tax)} = ${previewParts.join(' ')}`;

  return (
    <div className="rounded-2xl bg-gradient-to-br from-slate-900/80 to-[#0a0b0f] border border-slate-800/80 overflow-hidden">

      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-6 hover:bg-slate-800/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-sky-500/10 flex items-center justify-center">
            <BookOpen className="w-4 h-4 text-sky-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-bold text-slate-200">Explain Your Tax</h3>
            {/* Show preview equation when collapsed */}
            <p className="text-xs text-slate-500 mt-1 font-mono tabular-nums">
              {previewEquation}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {!open && (
            <span className="text-xs text-sky-400 font-semibold hidden sm:inline">See full breakdown</span>
          )}
          <div className="shrink-0 p-2 rounded-full bg-slate-800/50">
            {open ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
          </div>
        </div>
      </button>

      {open && (
        <div className="p-6 pt-0 border-t border-slate-800/40">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-6">

            {/* Left: Slab Breakdown */}
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">Slab Breakdown</h4>
              <div className="flex flex-col gap-3">
                {result.breakdown?.map((slab, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800/50">
                    <div>
                      <div className="text-sm font-medium text-slate-200">{slab.range}</div>
                      <div className="text-xs text-slate-500">at {(slab.rate * 100).toFixed(0)}%</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-semibold text-amber-400 tabular-nums">{formatCurrency(slab.tax)}</div>
                      <div className="text-[10px] text-slate-600">on {formatCurrency(slab.taxable_amount)}</div>
                    </div>
                  </div>
                ))}
                <div className="flex justify-between items-center px-3 py-2 mt-2 border-t border-slate-800/60">
                  <span className="text-xs text-slate-400">Tax Before Rebate</span>
                  <span className="text-sm font-bold text-slate-200 tabular-nums">{formatCurrency(result.base_tax)}</span>
                </div>
              </div>
            </div>

            {/* Right: Adjustments */}
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-4">Adjustments & Cess</h4>
              <div className="flex flex-col gap-3">

                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800/50">
                  <div>
                    <div className="text-sm text-slate-300">Section 87A Rebate</div>
                    <div className="text-[10px] text-slate-600">For taxable income ≤ ₹5L (old) or ₹12L (new)</div>
                  </div>
                  <div className="text-sm font-semibold text-emerald-400 tabular-nums">−{formatCurrency(result.rebate)}</div>
                </div>

                {result.surcharge > 0 && (
                  <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800/50">
                    <div>
                      <div className="text-sm text-slate-300">Surcharge</div>
                      <div className="text-[10px] text-slate-600">10% on tax for income &gt; ₹50L</div>
                    </div>
                    <div className="text-sm font-semibold text-amber-400 tabular-nums">+{formatCurrency(result.surcharge)}</div>
                  </div>
                )}

                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-900/50 border border-slate-800/50">
                  <div>
                    <div className="text-sm text-slate-300">Health & Edu Cess</div>
                    <div className="text-[10px] text-slate-600">4% on (tax + surcharge)</div>
                  </div>
                  <div className="text-sm font-semibold text-amber-400 tabular-nums">+{formatCurrency(result.cess)}</div>
                </div>

                <div className="flex justify-between items-center px-3 py-2 mt-2 border-t border-slate-800/60">
                  <span className="text-xs text-slate-400">Total Tax Payable</span>
                  <span className="text-sm font-bold text-amber-500 tabular-nums">{formatCurrency(result.total_tax)}</span>
                </div>
              </div>
            </div>

          </div>
        </div>
      )}

    </div>
  );
}
