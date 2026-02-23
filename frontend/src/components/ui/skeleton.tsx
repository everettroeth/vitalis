import { cn } from "@/lib/utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Width class — e.g. "w-24", "w-full" */
  width?: string;
  /** Height class — e.g. "h-4", "h-8" */
  height?: string;
}

export function Skeleton({ className, width, height, ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "rounded-sm animate-shimmer",
        "bg-gradient-to-r from-vt-sand-light via-vt-parchment to-vt-sand-light",
        "bg-[length:200%_100%]",
        width ?? "w-full",
        height ?? "h-4",
        className,
      )}
      {...props}
    />
  );
}

export function SkeletonMetricCard({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "bg-vt-surface rounded-lg p-4 shadow-vt-sm border border-vt-border space-y-3",
        className,
      )}
    >
      <div className="flex items-center justify-between">
        <Skeleton width="w-24" height="h-3" />
        <Skeleton width="w-4" height="h-4" className="rounded-full" />
      </div>
      <Skeleton width="w-20" height="h-8" />
      <Skeleton height="h-8" />
      <Skeleton width="w-32" height="h-3" />
    </div>
  );
}
