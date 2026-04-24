'use client';

import { ValidationResult } from '@/types';
import { ShieldCheck, ShieldAlert, ShieldX, Info } from 'lucide-react';
import { cn } from '@/lib/utils';

export function ValidationPanel({ result }: { result: ValidationResult }) {
  const { status, score, issues } = result;

  const statusConfig = {
    ok: { icon: ShieldCheck, label: 'Verified', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', stroke: '#10b981' },
    warning: { icon: ShieldAlert, label: 'Needs Review', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20', stroke: '#f59e0b' },
    error: { icon: ShieldX, label: 'Verification Failed', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20', stroke: '#ef4444' },
  }[status] ?? { icon: ShieldCheck, label: 'Unknown', color: 'text-slate-400', bg: 'bg-slate-500/10', border: 'border-slate-500/20', stroke: '#6b7280' };

  const Icon = statusConfig.icon;
  const circumference = 2 * Math.PI * 40;
  const dashOffset = circumference - (score / 100) * circumference;

  // Honest validation claim:
  // We never have Form 26AS uploaded (user only uploads Form 16)
  // so we must NOT claim cross-verification with Form 26AS.
  const description = issues.length === 0
    ? "Document verified for internal consistency. All fields are structurally valid."
    : `Found ${issues.length} internal consistency issue${issues.length > 1 ? 's' : ''} in the document.`;

  return (
    <div className="h-full flex flex-col justify-center p-8 rounded-2xl bg-gradient-to-br from-slate-900/80 to-[#0a0b0f] border border-slate-800/80">

      <div className="flex flex-col md:flex-row items-center gap-8">

        {/* Ring */}
        <div className="relative shrink-0">
          <svg width="100" height="100" className="-rotate-90">
            <circle cx="50" cy="50" r="40" fill="none" stroke="#1e2130" strokeWidth="8" />
            <circle
              cx="50" cy="50" r="40" fill="none"
              stroke={statusConfig.stroke}
              strokeWidth="8"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              className="transition-all duration-1000 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-2xl font-bold text-slate-100">{score}</span>
          </div>
        </div>

        {/* Info */}
        <div className="flex flex-col items-center md:items-start text-center md:text-left gap-2">
          <div className={cn('inline-flex items-center gap-2 px-3 py-1 rounded-full border', statusConfig.bg, statusConfig.border)}>
            <Icon className={cn('w-4 h-4', statusConfig.color)} />
            <span className={cn('text-xs font-bold uppercase tracking-wider', statusConfig.color)}>{statusConfig.label}</span>
          </div>
          <p className="text-sm text-slate-400 mt-2">{description}</p>
          <div className="flex items-center gap-1.5 mt-1">
            <Info className="w-3 h-3 text-slate-600" />
            <span className="text-[10px] text-slate-600">Upload Form 26AS for cross-verification</span>
          </div>
        </div>

      </div>

    </div>
  );
}
