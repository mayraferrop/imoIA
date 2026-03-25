export interface Property {
  id: string;
  source: string;
  municipality: string;
  parish?: string;
  address?: string;
  property_type?: string;
  typology?: string;
  area_m2?: number;
  asking_price?: number;
  price_per_m2?: number;
  deal_grade?: string;
  confidence?: number;
  opportunity_type?: string;
  description?: string;
  url?: string;
  status?: string;
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
  strategy: string;
  status: string;
  current_state: string;
  asking_price?: number;
  offered_price?: number;
  estimated_arv?: number;
  created_at: string;
  property?: Property;
}

export interface KanbanData {
  columns: Record<string, { deals: Deal[]; count: number; total_value: number }>;
  total_deals: number;
}

export interface FinancialSimulation {
  go_no_go: string;
  total_investment: number;
  estimated_profit: number;
  roi_simple: number;
  moic: number;
  cash_flow?: any[];
}

export interface HealthResponse {
  status: string;
  service: string;
}
