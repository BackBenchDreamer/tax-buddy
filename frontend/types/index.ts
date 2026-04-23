// Type definitions for the AI Tax Filing API

export interface Entity {
  label: string;
  value: string;
  confidence: number;
}

export interface ExtractedData {
  PAN?: string;
  TAN?: string;
  AssessmentYear?: string;
  EmployerName?: string;
  EmployeeName?: string;
  GrossSalary?: number;
  TaxableIncome?: number;
  TDS?: number;
  Section80C?: number;
  Section80D?: number;
  [key: string]: string | number | undefined;
}

export interface ValidationIssue {
  type: string;
  severity: string;
  field?: string;
  message: string;
}

export interface ValidationResult {
  status: 'ok' | 'warning' | 'error';
  score: number;
  issues: ValidationIssue[];
}

export interface SlabBreakdown {
  slab: string;
  rate: number;
  taxable_in_slab: number;
  tax_in_slab: number;
}

export interface TaxResult {
  regime: string;
  gross_income: number;
  deductions: number;
  taxable_income: number;
  tax_before_rebate: number;
  rebate: number;
  surcharge: number;
  cess: number;
  total_tax: number;
  tds_paid: number;
  refund_or_payable: number;
  slab_breakdown?: SlabBreakdown[];
}

export interface ProcessResponse {
  file_id: string;
  text: string;
  entities: Entity[];
  validation: ValidationResult;
  tax: TaxResult | null;
}

export interface RegimeComparison {
  old: TaxResult;
  new: TaxResult;
}
