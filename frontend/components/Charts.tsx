'use client';

import { TaxResult } from '@/types';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';
import { formatCurrency } from '@/lib/utils';
import { BarChart2, PieChart as PieIcon } from 'lucide-react';

interface ChartsProps {
  tax: TaxResult;
}

const COLORS = ['#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd', '#ddd6fe'];

export function Charts({ tax }: ChartsProps) {
  const barData = [
    { name: 'Gross Income', value: tax.gross_income, fill: '#6366f1' },
    { name: 'Deductions', value: tax.deductions, fill: '#8b5cf6' },
    { name: 'Taxable', value: tax.taxable_income, fill: '#a78bfa' },
    { name: 'Total Tax', value: tax.total_tax, fill: '#f59e0b' },
  ];

  const pieData = (tax.breakdown ?? [])
    .filter((s) => s.tax > 0)
    .map((s) => ({ name: s.range, value: s.tax }));

  const customTooltip = ({ active, payload }: { active?: boolean; payload?: { value: number; name: string }[] }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className="bg-[#1a1d27] border border-slate-700 rounded-xl px-3 py-2 shadow-2xl">
        <p className="text-xs text-slate-400 mb-0.5">{payload[0].name}</p>
        <p className="text-sm font-semibold text-slate-100">{formatCurrency(payload[0].value)}</p>
      </div>
    );
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      
      {/* Bar Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/30 border border-slate-800/50">
        <div className="flex items-center gap-2 mb-6">
          <BarChart2 className="w-4 h-4 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">Income Breakdown</h3>
        </div>
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={barData} barCategoryGap="25%">
            <CartesianGrid vertical={false} stroke="#1e2130" />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} />
            <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} axisLine={false} tickLine={false} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
            <Tooltip content={customTooltip as never} cursor={{ fill: 'rgba(99,102,241,0.06)' }} />
            <Bar dataKey="value" radius={[4, 4, 0, 0]}>
              {barData.map((entry, i) => <Cell key={i} fill={entry.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Donut Chart */}
      <div className="p-6 rounded-2xl bg-slate-900/30 border border-slate-800/50">
        <div className="flex items-center gap-2 mb-6">
          <PieIcon className="w-4 h-4 text-violet-400" />
          <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-widest">Slab Distribution</h3>
        </div>
        {pieData.length > 0 ? (
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={pieData} cx="50%" cy="50%" innerRadius={60} outerRadius={90} paddingAngle={2} dataKey="value" stroke="none">
                {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Legend iconType="circle" iconSize={8} formatter={(value) => <span style={{ fontSize: 11, color: '#9ca3af' }}>{value}</span>} />
              <Tooltip content={customTooltip as never} />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[240px] flex items-center justify-center">
            <p className="text-sm text-slate-600">No slab data available</p>
          </div>
        )}
      </div>

    </div>
  );
}
