import { cn } from "@/lib/utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  hoverable?: boolean;
}

export function Card({ className, hoverable = true, children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "bg-vt-surface rounded-lg p-4 shadow-vt-sm border border-vt-border",
        "transition-all duration-200 ease-smooth",
        hoverable && "hover:shadow-vt-md hover:scale-[1.02]",
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex items-center justify-between mb-3", className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn(
        "font-display text-[1.125rem] font-medium leading-snug text-vt-text-strong",
        className,
      )}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("", className)} {...props}>
      {children}
    </div>
  );
}
