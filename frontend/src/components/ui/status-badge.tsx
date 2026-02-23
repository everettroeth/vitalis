import { cn } from "@/lib/utils";
import { HealthStatus } from "@/types";

const statusConfig: Record<
  HealthStatus,
  { bg: string; text: string; dot: string; label: string }
> = {
  [HealthStatus.Thriving]: {
    bg: "bg-vt-thriving-bg",
    text: "text-vt-thriving",
    dot: "bg-vt-thriving",
    label: "Thriving",
  },
  [HealthStatus.Watch]: {
    bg: "bg-vt-watch-bg",
    text: "text-vt-watch",
    dot: "bg-vt-watch",
    label: "Watch",
  },
  [HealthStatus.Concern]: {
    bg: "bg-vt-concern-bg",
    text: "text-vt-concern",
    dot: "bg-vt-clay",
    label: "Concern",
  },
  [HealthStatus.Unknown]: {
    bg: "bg-vt-unknown-bg",
    text: "text-vt-text-secondary",
    dot: "bg-vt-unknown",
    label: "Unknown",
  },
};

export interface StatusBadgeProps {
  status: HealthStatus;
  className?: string;
  showDot?: boolean;
}

export function StatusBadge({ status, className, showDot = true }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-pill",
        "text-[0.75rem] font-medium leading-[1.4]",
        config.bg,
        config.text,
        className,
      )}
    >
      {showDot && <span className={cn("w-1.5 h-1.5 rounded-full", config.dot)} />}
      {config.label}
    </span>
  );
}
