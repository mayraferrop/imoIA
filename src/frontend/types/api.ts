export interface Property {
  id: string;
  source: string;
  district?: string;
  municipality: string;
  parish?: string;
  address?: string;
  property_type?: string;
  typology?: string;
  gross_area_m2?: number;
  net_area_m2?: number;
  bedrooms?: number;
  bathrooms?: number;
  condition?: string;
  asking_price?: number;
  currency?: string;
  status?: string;
  contact_name?: string;
  contact_phone?: string;
  contact_email?: string;
  notes?: string;
  tags?: string[];
  is_off_market?: boolean;
  created_at: string;
}

export interface PropertiesResponse {
  total: number;
  limit: number;
  offset: number;
  items: Property[];
}

export interface Deal {
  id: string;
  property_id: string;
  investment_strategy: string;
  status: string;
  title?: string;
  purchase_price?: number;
  target_sale_price?: number;
  monthly_rent?: number;
  renovation_budget?: number;
  contact_name?: string;
  contact_phone?: string;
  notes?: string;
  created_at: string;
  property?: Property;
}

export interface KanbanData {
  columns: Record<string, { deals: Deal[]; count: number; total_value: number }>;
  total_deals: number;
}

export interface FinancialSimulation {
  go_nogo: string;
  total_investment: number;
  net_profit: number;
  roi_pct: number;
  roi_simple_pct: number;
  moic: number;
  cash_flow?: any[];
}

export interface HealthResponse {
  status: string;
  service: string;
}
