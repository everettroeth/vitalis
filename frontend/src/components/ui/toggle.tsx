"use client";

import { cn } from "@/lib/utils";

export interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
  disabled?: boolean;
  className?: string;
}

export function Toggle({ checked, onChange, label, disabled, className }: ToggleProps) {
  return (
    <label
      className={cn(
        "inline-flex items-center gap-3 cursor-pointer select-none",
        disabled && "opacity-50 cursor-not-allowed",
        className,
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          "relative w-11 h-6 rounded-pill transition-colors duration-150 ease-smooth",
          "focus:outline-none focus:ring-2 focus:ring-vt-sage/40 focus:ring-offset-2",
          checked ? "bg-vt-sage" : "bg-vt-sand-light",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow-vt-sm",
            "transition-transform duration-250 ease-spring",
            checked && "translate-x-5",
          )}
        />
      </button>
      {label && (
        <span className="text-[0.9375rem] text-vt-text-primary">{label}</span>
      )}
    </label>
  );
}
