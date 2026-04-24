'use client';

import { useState } from 'react';
import { Entity, ExtractedData } from '@/types';
import { formatCurrency, cn } from '@/lib/utils';
import { User, Wallet, Receipt, ChevronDown, ShieldCheck } from 'lucide-react';

interface ExtractedDataTableProps {
  entities: Entity[];
}

const PERSONAL_FIELDS: Array<{ key: keyof ExtractedData; label: string }> = [
  { key: 'PAN', label: 'PAN' },
  { key: 'TAN', label: 'TAN (Employer)' },
  { key: 'AssessmentYear', label: 'Assessment Year' },
  { key: 'EmployerName', label: 'Employer' },
  { key: 'EmployeeName', label: 'Employee' },
];

const INCOME_FIELDS: Array<{ key: keyof ExtractedData; label: string; isCurrency: boolean }> = [
  { key: 'GrossSalary', label: 'Gross Salary', isCurrency: true },
  { key: 'TaxableIncome', label: 'Taxable Income', isCurrency: true },
  { key: 'TDS', label: 'TDS Deducted', isCurrency: true },
];

const DEDUCTION_FIELDS: Array<{ key: keyof ExtractedData; label: string }> = [
  { key: 'Section80C', label: 'Section 80C' },
  { key: 'Section80D', label: 'Section 80D' },
];

export function ExtractedDataTable({ entities }: ExtractedDataTableProps) {
  const map: Record<string, string> = {};
  const confMap: Record<string, number> = {};
  
  entities.forEach((e) => { 
    map[e.label] = e.value; 
    confMap[e.label] = e.confidence;
  });

  const get = (key: string) => map[key];
  const getConf = (key: string) => confMap[key];
  const getNum = (key: string) => {
    const v = map[key];
    return v != null ? parseFloat(v) : undefined;
  };

  return (
    <div className="flex flex-col gap-3">
      <AccordionSection
        icon={<User className="w-4 h-4 text-violet-400" />}
        title="Personal Info"
        defaultOpen={false}
        count={PERSONAL_FIELDS.filter(f => get(String(f.key))).length}
      >
        {PERSONAL_FIELDS.map(({ key, label }) => (
          <Row key={String(key)} label={label} value={get(String(key))} conf={getConf(String(key))} mono={['PAN','TAN'].includes(String(key))} />
        ))}
      </AccordionSection>

      <AccordionSection
        icon={<Wallet className="w-4 h-4 text-indigo-400" />}
        title="Income Details"
        defaultOpen={true}
        count={INCOME_FIELDS.filter(f => getNum(String(f.key)) != null).length}
      >
        {INCOME_FIELDS.map(({ key, label, isCurrency }) => {
          const val = getNum(String(key));
          return (
            <Row
              key={String(key)}
              label={label}
              value={isCurrency && val != null ? formatCurrency(val) : val?.toString()}
              conf={getConf(String(key))}
            />
          );
        })}
      </AccordionSection>

      <AccordionSection
        icon={<Receipt className="w-4 h-4 text-emerald-400" />}
        title="Deductions"
        defaultOpen={false}
        count={DEDUCTION_FIELDS.filter(f => getNum(String(f.key)) != null).length}
      >
        {DEDUCTION_FIELDS.map(({ key, label }) => {
          const val = getNum(String(key));
          return <Row key={String(key)} label={label} value={val != null ? formatCurrency(val) : undefined} conf={getConf(String(key))} />;
        })}
      </AccordionSection>
    </div>
  );
}

function AccordionSection({ icon, title, children, defaultOpen = false, count }: { icon: React.ReactNode; title: string; children: React.ReactNode; defaultOpen?: boolean; count: number }) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="rounded-xl bg-slate-900/30 border border-slate-800/50 overflow-hidden transition-colors hover:border-slate-700/50">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-6 py-4"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-slate-800/50">{icon}</div>
          <span className="text-sm font-semibold text-slate-200">{title}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-800 text-slate-400">{count} fields</span>
        </div>
        <ChevronDown className={cn('w-4 h-4 text-slate-500 transition-transform duration-200', open && 'rotate-180')} />
      </button>
      <div className={cn('transition-all duration-300 ease-in-out overflow-hidden', open ? 'max-h-[500px] opacity-100' : 'max-h-0 opacity-0')}>
        <div className="divide-y divide-slate-800/30 px-6 pb-2">{children}</div>
      </div>
    </div>
  );
}

function Row({ label, value, conf, mono = false }: { label: string; value?: string; conf?: number; mono?: boolean }) {
  // Confidence color coding:
  //   > 0.9  → green  (high confidence)
  //   0.7-0.9 → yellow (medium)
  //   < 0.7  → red    (low)
  const confColor = !conf ? '' :
    conf > 0.9 ? 'text-emerald-500 bg-emerald-500/10 border-emerald-500/20' :
    conf > 0.7 ? 'text-amber-400 bg-amber-500/10 border-amber-500/20' :
    'text-red-400 bg-red-500/10 border-red-500/20';

  return (
    <div className="flex items-center justify-between py-3 group">
      <div className="flex items-center gap-2">
        <span className="text-xs text-slate-400 group-hover:text-slate-300 transition-colors">{label}</span>
      </div>
      <div className="flex items-center gap-3 text-right">
        <span className={cn('text-sm font-medium', !value ? 'text-slate-600 italic' : mono ? 'font-mono text-slate-200 tracking-wider' : 'text-slate-100')}>
          {value ?? 'Not detected'}
        </span>
        {value && conf != null && (
          <div
            className={cn('flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded border cursor-help', confColor)}
            title="Confidence based on OCR + extraction pipeline"
          >
            <ShieldCheck className="w-3 h-3" /> {(conf * 100).toFixed(0)}%
          </div>
        )}
      </div>
    </div>
  );
}
