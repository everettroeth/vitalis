"use client";

import { cn } from "@/lib/utils";
import { HealthStatus, type MetricSnapshot } from "@/types";
import { StatusBadge } from "./status-badge";
import { Card } from "./card";
import { TrendUp, TrendDown, Minus } from "@phosphor-icons/react";

const trendIcons = {
  up: TrendUp,
  down: TrendDown,
  flat: Minus,
} as const;

const trendColors: Record<HealthStatus, Record<"up" | "down" | "flat", string>> = {
  [HealthStatus.Thriving]: { up: "text-vt-thriving", down: "text-vt-thriving", flat: "text-vt-text-secondary" },
  [HealthStatus.Watch]: { up: "text-vt-watch", down: "text-vt-watch", flat: "text-vt-text-secondary" },
  [HealthStatus.Concern]: { up: "text-vt-concern", down: "text-vt-concern", flat: "text-vt-text-secondary" },
  [HealthStatus.Unknown]: { up: "text-vt-text-secondary", down: "text-vt-text-secondary", flat: "text-vt-text-secondary" },
};

export interface MetricCardProps {
  metric: MetricSnapshot;
  className?: string;
}

export function MetricCard({ metric, className }: MetricCardProps) {
  const TrendIcon = trendIcons[metric.trend];

  return (
    <Card className={cn("", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <StatusBadge status={metric.status} showDot className="px-0 py-0 bg-transparent text-[0.6875rem] tracking-[0.08em] uppercase" />
        </div>
        <TrendIcon
          className={cn("w-4 h-4", trendColors[metric.status][metric.trend])}
          weight="bold"
        />
      </div>

      {/* Metric Value */}
      <div className="mb-2">
        <span className="metric-value font-display text-[clamp(1.75rem,3vw,2.5rem)] font-light text-vt-text-strong">
          {metric.value}
        </span>
        <span className="font-sans text-[0.9375rem] text-vt-text-secondary ml-1">
          {metric.unit}
        </span>
      </div>

      {/* Sparkline placeholder */}
      {metric.sparklineData && metric.sparklineData.length > 0 && (
        <div className="h-8 mb-2 flex items-end gap-[2px]">
          {metric.sparklineData.map((val, i) => {
            const max = Math.max(...metric.sparklineData!);
            const pct = max > 0 ? (val / max) * 100 : 0;
            return (
              <div
                key={i}
                className="flex-1 rounded-t-[1px] bg-vt-sage/40"
                style={{ height: `${Math.max(pct, 8)}%` }}
              />
            );
          })}
        </div>
      )}

      {/* Delta */}
      <p className="text-[0.75rem] leading-[1.4] text-vt-text-secondary">
        {metric.delta}
      </p>

      {/* Label */}
      <p className="text-[0.6875rem] tracking-[0.08em] uppercase text-vt-text-secondary mt-1">
        {metric.label}
      </p>
    </Card>
  );
}
