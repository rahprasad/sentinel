// Pretty labels + icons for the canonical field names emitted by the walker.
// Keep keys aligned with `_CANONICAL_LABEL` in apps/sandbox/src/form_filler.py.

export interface HarvestedFieldPresentation {
  icon: string;
  label: string;
  severity: "high" | "medium" | "low";
}

const TABLE: Record<string, HarvestedFieldPresentation> = {
  card_number: { icon: "💳", label: "Card number", severity: "high" },
  cvv: { icon: "🔐", label: "CVV", severity: "high" },
  card_expiration: { icon: "📅", label: "Card expiration", severity: "medium" },
  ssn: { icon: "🆔", label: "SSN", severity: "high" },
  date_of_birth: { icon: "🎂", label: "Date of birth", severity: "medium" },
  email: { icon: "📧", label: "Email", severity: "low" },
  phone: { icon: "📱", label: "Phone", severity: "low" },
  address: { icon: "📍", label: "Address", severity: "medium" },
  zip: { icon: "📮", label: "ZIP", severity: "low" },
  name: { icon: "👤", label: "Name", severity: "low" },
  password: { icon: "🔒", label: "Password", severity: "high" },
  crypto_seed: { icon: "🗝️", label: "Wallet seed", severity: "high" },
};

export function describeField(key: string): HarvestedFieldPresentation {
  return (
    TABLE[key] ?? {
      icon: "📝",
      label: key.replace(/_/g, " "),
      severity: "low",
    }
  );
}
