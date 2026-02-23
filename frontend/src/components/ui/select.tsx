"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";
import { CaretDown } from "@phosphor-icons/react";

export interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: { value: string; label: string }[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, label, error, hint, options, placeholder, id, ...props }, ref) => {
    const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="text-[0.8125rem] font-medium leading-[1.4] text-vt-text-primary"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              "w-full px-4 py-3 pr-10 rounded-md appearance-none",
              "bg-vt-surface border border-vt-sand-light",
              "text-[0.9375rem] leading-[1.6] text-vt-text-strong",
              "focus:outline-none focus:ring-2 focus:ring-vt-sage/40 focus:border-vt-sage",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-vt-parchment",
              "transition-all duration-150",
              error && "border-vt-clay ring-2 ring-vt-clay/30",
              className,
            )}
            aria-invalid={!!error}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <CaretDown
            className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-vt-text-secondary pointer-events-none"
            weight="bold"
          />
        </div>
        {error && (
          <p className="text-[0.75rem] leading-[1.4] text-vt-clay">{error}</p>
        )}
        {hint && !error && (
          <p className="text-[0.75rem] leading-[1.4] text-vt-text-secondary">{hint}</p>
        )}
      </div>
    );
  },
);

Select.displayName = "Select";
