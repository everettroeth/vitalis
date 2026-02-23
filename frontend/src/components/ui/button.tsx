"use client";

import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const variantStyles = {
  primary:
    "bg-vt-fern text-white hover:bg-vt-fern/90 hover:-translate-y-0.5 hover:shadow-vt-md active:translate-y-0 active:shadow-none",
  secondary:
    "border-[1.5px] border-vt-fern text-vt-fern bg-transparent hover:bg-vt-thriving-bg",
  ghost:
    "bg-transparent text-vt-text-primary border border-vt-border hover:bg-vt-surface hover:border-vt-border-strong",
  destructive:
    "bg-vt-concern-bg text-vt-clay border border-vt-concern-border hover:bg-vt-clay hover:text-white",
} as const;

const sizeStyles = {
  sm: "py-2 px-4 text-[0.8125rem] min-h-9",
  md: "py-3 px-6 text-[0.875rem] min-h-11",
  lg: "py-4 px-8 text-[0.9375rem] min-h-[52px]",
  xl: "py-5 px-10 text-base min-h-[60px]",
} as const;

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variantStyles;
  size?: keyof typeof sizeStyles;
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", loading, disabled, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "inline-flex items-center justify-center gap-2 rounded-md font-medium",
          "transition-all duration-150 ease-smooth cursor-pointer",
          "focus:outline-none focus:ring-2 focus:ring-vt-sage/40 focus:ring-offset-2",
          "disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none",
          variantStyles[variant],
          sizeStyles[size],
          loading && "pointer-events-none",
          className,
        )}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin -ml-1 h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {children}
      </button>
    );
  },
);

Button.displayName = "Button";
