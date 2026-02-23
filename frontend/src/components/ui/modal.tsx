"use client";

import { useEffect, useCallback, useRef } from "react";
import { cn } from "@/lib/utils";
import { X } from "@phosphor-icons/react";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function Modal({ open, onClose, title, children, className }: ModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-[rgba(30,26,22,0.4)] backdrop-blur-[4px] animate-fade-in" />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={cn(
          "relative bg-vt-surface-elevated rounded-xl shadow-vt-float",
          "p-8 w-[min(560px,calc(100vw-32px))] max-h-[80vh] overflow-y-auto",
          "animate-modal-in",
          /* Mobile: slide up from bottom */
          "max-md:fixed max-md:bottom-0 max-md:left-0 max-md:right-0 max-md:w-full",
          "max-md:rounded-b-none max-md:rounded-t-xl max-md:max-h-[90vh]",
          "max-md:pb-[calc(2rem+env(safe-area-inset-bottom))]",
          className,
        )}
      >
        {/* Mobile drag handle */}
        <div className="md:hidden flex justify-center mb-4">
          <div className="w-8 h-1 rounded-pill bg-vt-sand-mid" />
        </div>

        {/* Header */}
        {title && (
          <div className="flex items-center justify-between mb-6">
            <h2 className="font-display text-[1.25rem] font-semibold text-vt-text-strong">
              {title}
            </h2>
            <button
              onClick={onClose}
              className="p-2 rounded-sm text-vt-text-secondary hover:bg-vt-surface hover:text-vt-text-strong transition-colors duration-150 min-w-11 min-h-11 flex items-center justify-center"
              aria-label="Close"
            >
              <X size={20} />
            </button>
          </div>
        )}

        {children}
      </div>
    </div>
  );
}
