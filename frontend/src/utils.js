export const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

export function fmtMoney(value = 0) {
  return `S$${Number(value || 0).toLocaleString("en-SG", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function fmtMoneyShort(value = 0) {
  const num = Number(value || 0);
  return num >= 1000 ? `S$${(num / 1000).toFixed(num % 1000 ? 1 : 0)}k` : fmtMoney(num);
}

export function fmtDate(value) {
  if (!value) return "N/A";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

export function monthIndex(name) {
  return MONTHS.indexOf(name);
}

export function daysUntilMonth(monthName) {
  const index = monthIndex(monthName);
  if (index < 0) return 999;
  const now = new Date();
  let due = new Date(now.getFullYear(), index, 14);
  if (due < now) due = new Date(now.getFullYear() + 1, index, 14);
  return Math.ceil((due - now) / 86400000);
}

export function feeTone(card) {
  if (card.status === "cancelled") return "muted";
  const days = daysUntilMonth(card.feeMonth);
  if (days <= 30) return "rose";
  if (days <= 60) return "amber";
  return "teal";
}

export function bonusProgress(card) {
  const bonus = card.bonus || {};
  const minSpend = Number(bonus.minSpend || 0);
  const currentSpend = Number(bonus.currentSpend || 0);
  const percent = minSpend > 0 ? Math.min(100, Math.round((currentSpend / minSpend) * 100)) : 0;
  const days = bonus.deadline ? Math.ceil((new Date(bonus.deadline) - new Date()) / 86400000) : null;
  return { percent, days, remaining: Math.max(0, minSpend - currentSpend) };
}

export function isBonusActive(card) {
  const status = card.bonus?.status;
  return card.bonus?.deadline && ["Not Started", "In Progress"].includes(status);
}

export function bankColor(bank = "") {
  const palette = {
    DBS: ["#8f1d22", "#421114"],
    POSB: ["#2f6fbd", "#17406f"],
    UOB: ["#1e3a8a", "#0f172a"],
    OCBC: ["#b91c1c", "#450a0a"],
    Citi: ["#2563eb", "#111827"],
    HSBC: ["#dc2626", "#111827"],
    "Standard Chartered": ["#0f766e", "#064e3b"],
    "American Express": ["#2563eb", "#0f172a"],
    CIMB: ["#991b1b", "#3f0d0d"],
    Trust: ["#0d9488", "#134e4a"],
  };
  const key = Object.keys(palette).find((item) => bank.includes(item));
  return palette[key] || ["#44403c", "#18181b"];
}

export function emptyCard() {
  return {
    bank: "",
    name: "",
    annualFee: 0,
    expiry: "",
    feeMonth: "",
    imageFilename: "default.png",
    sortOrder: 99,
    notes: "",
    tags: [],
    last4: "",
    dates: {},
    bonus: {
      offer: "",
      minSpend: 0,
      currentSpend: 0,
      deadline: "",
      status: "Not Started",
    },
    feeHistory: {
      waivedCount: 0,
      paidCount: 0,
      lastActionYear: 0,
      lastAction: "",
    },
  };
}
