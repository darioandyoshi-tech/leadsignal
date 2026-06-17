import {
  FileText, Landmark, MapPin, Briefcase, Star,
  AlertTriangle, ShieldCheck, Store, TrendingUp, CreditCard,
} from "lucide-react";

export const TYPE_META: Record<
  string,
  { label: string; icon: React.ElementType; accent: "amber" | "emerald" | "rose" | "blue" | "slate" }
> = {
  hiring_spike: { label: "Hiring Spikes", icon: Briefcase, accent: "emerald" },
  negative_review_cluster: { label: "Review Clusters", icon: Star, accent: "rose" },
  permit_filing: { label: "Permit Filings", icon: FileText, accent: "amber" },
  parcel_change: { label: "Parcel Changes", icon: MapPin, accent: "blue" },
  tax_delinquency: { label: "Tax Delinquency", icon: AlertTriangle, accent: "rose" },
  gov_contract_award: { label: "Gov Contracts", icon: ShieldCheck, accent: "emerald" },
  business_license: { label: "Business Licenses", icon: Store, accent: "blue" },
  ucc_filing: { label: "UCC Filings", icon: CreditCard, accent: "slate" },
  new_business_registration: { label: "New Businesses", icon: TrendingUp, accent: "emerald" },
  land_bank_property: { label: "Land Bank Properties", icon: Landmark, accent: "amber" },
};
