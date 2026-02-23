"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  suffix?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, label, error, hint, suffix, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

    return (
      <div className="space-y-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-[0.8125rem] font-medium leading-[1.4] text-vt-text-primary"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <input
            ref={ref}
            id={inputId}
            className={cn(
              "w-full px-4 py-3 rounded-md",
              "bg-vt-surface border border-vt-sand-light",
              "text-[0.9375rem] leading-[1.6] text-vt-text-strong",
              "placeholder:text-vt-sand-mid",
              "focus:outline-none focus:ring-2 focus:ring-vt-sage/40 focus:border-vt-sage",
              "disabled:opacity-50 disabled:cursor-not-allowed disabled:bg-vt-parchment",
              "transition-all duration-150",
              error && "border-vt-clay ring-2 ring-vt-clay/30",
              suffix && "pr-14",
              className,
            )}
            aria-invalid={!!error}
            aria-describedby={
              error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined
            }
            {...props}
          />
          {suffix && (
            <span className="absolute right-4 top-1/2 -translate-y-1/2 text-[0.8125rem] text-vt-text-secondary">
              {suffix}
            </span>
          )}
        </div>
        {error && (
          <p id={`${inputId}-error`} className="text-[0.75rem] leading-[1.4] text-vt-clay">
            {error}
          </p>
        )}
        {hint && !error && (
          <p id={`${inputId}-hint`} className="text-[0.75rem] leading-[1.4] text-vt-text-secondary">
            {hint}
          </p>
        )}
      </div>
    );
  },
);

Input.displayName = "Input";
