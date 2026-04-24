'use client';

import { TaxResult } from '@/types';
import { formatCurrency } from '@/lib/utils';
import { ArrowRight, Check } from 'lucide-react';

export function RegimeComparison({ comparison }: { comparison: { old: TaxResult; new: TaxResult } | null }) {
  if (!comparison) {
    return (
      <div className="h-full flex items-center justify-center p-8 rounded-2xl bg-slate-900/30 border border-slate-800/50">
        <p className="text-sm text-slate-500">Regime comparison not available</p>
      </div>
    );
  }

  const { old: oldT, new: newT } = comparison;
  const newIsBetter = newT.total_tax < oldT.total_tax;
  const oldIsBetter = oldT.total_tax < newT.total_tax;
  const difference = Math.abs(oldT.total_tax - newT.total_tax);

  return (
    <div className="h-full flex flex-col justify-center p-8 rounded-2xl bg-gradient-to-br from-slate-900/80 to-[#0a0b0f] border border-slate-800/80">
      
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Regime Comparison</h3>
        {difference > 0 && (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            Saves {formatCurrency(difference)}
          </span>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        
        {/* Old Regime */}
        <div className={`relative p-4 rounded-xl border transition-all ${
          oldIsBetter ? 'bg-emerald-500/5 border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.05)]' : 'bg-slate-900/40 border-slate-800/60 opacity-60'
        }`}>
          {oldIsBetter && (
            <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full bg-emerald-500 text-[#0a0b0f] text-[9px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Check className="w-3 h-3" /> Recommended
            </div>
          )}
          <p className="text-[10px] text-slate-500 uppercase tracking-widest text-center mb-2">Old Regime</p>
          <p className={`text-xl font-bold tabular-nums text-center ${oldIsBetter ? 'text-emerald-400' : 'text-slate-300'}`}>
            {formatCurrency(oldT.total_tax)}
          </p>
        </div>

        {/* New Regime */}
        <div className={`relative p-4 rounded-xl border transition-all ${
          newIsBetter ? 'bg-emerald-500/5 border-emerald-500/30 shadow-[0_0_20px_rgba(16,185,129,0.05)]' : 'bg-slate-900/40 border-slate-800/60 opacity-60'
        }`}>
          {newIsBetter && (
            <div className="absolute -top-2.5 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded-full bg-emerald-500 text-[#0a0b0f] text-[9px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Check className="w-3 h-3" /> Recommended
            </div>
          )}
          <p className="text-[10px] text-slate-500 uppercase tracking-widest text-center mb-2">New Regime</p>
          <p className={`text-xl font-bold tabular-nums text-center ${newIsBetter ? 'text-emerald-400' : 'text-slate-300'}`}>
            {formatCurrency(newT.total_tax)}
          </p>
        </div>

      </div>

    </div>
  );
}
