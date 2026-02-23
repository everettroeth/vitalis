import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

/** Merge Tailwind classes with clsx. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** Format a date string to a human-readable format. */
export function formatDate(
  dateStr: string,
  options?: Intl.DateTimeFormatOptions,
): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    ...options,
  });
}

/** Format a number with locale-aware separators. */
export function formatNumber(value: number, decimals = 0): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

/** Format a duration in minutes to a human-readable string. */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  if (hours === 0) return `${mins}m`;
  if (mins === 0) return `${hours}h`;
  return `${hours}h ${mins}m`;
}

/** Get the current theme from the document. */
export function getTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return (document.documentElement.getAttribute("data-theme") as "light" | "dark") ?? "light";
}

/** Toggle between light and dark themes. */
export function toggleTheme(): "light" | "dark" {
  const current = getTheme();
  const next = current === "light" ? "dark" : "light";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("vitalis-theme", next);
  return next;
}

/** Initialize theme from localStorage or system preference. */
export function initTheme(): void {
  if (typeof window === "undefined") return;
  const stored = localStorage.getItem("vitalis-theme") as "light" | "dark" | null;
  if (stored) {
    document.documentElement.setAttribute("data-theme", stored);
    return;
  }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.setAttribute("data-theme", prefersDark ? "dark" : "light");
}
