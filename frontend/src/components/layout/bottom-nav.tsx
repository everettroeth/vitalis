"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  House,
  Moon,
  Person,
  Drop,
  Sparkle,
} from "@phosphor-icons/react";

interface BottomNavItem {
  label: string;
  href: string;
  icon: React.ElementType;
}

const navItems: BottomNavItem[] = [
  { label: "Home", href: "/", icon: House },
  { label: "Sleep", href: "/sleep", icon: Moon },
  { label: "Body", href: "/body", icon: Person },
  { label: "Blood", href: "/blood", icon: Drop },
  { label: "Insights", href: "/insights", icon: Sparkle },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      className={cn(
        "lg:hidden fixed bottom-0 left-0 right-0 z-40",
        "h-[calc(64px+env(safe-area-inset-bottom))]",
        "pb-[env(safe-area-inset-bottom)]",
        "bg-vt-parchment/92 backdrop-blur-[12px]",
        "border-t border-vt-border",
        "flex items-start pt-2",
      )}
    >
      {navItems.map((item) => {
        const isActive = pathname === item.href;
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex-1 flex flex-col items-center gap-1 py-1 relative",
              "min-h-11 min-w-11",
              "transition-colors duration-150 ease-smooth",
              isActive ? "text-vt-fern" : "text-vt-text-secondary",
            )}
          >
            {isActive && (
              <span className="absolute -top-[1px] w-6 h-0.5 rounded-b-sm bg-vt-sage" />
            )}
            <Icon size={22} weight={isActive ? "fill" : "regular"} />
            <span
              className={cn(
                "text-[0.625rem] leading-none",
                isActive && "font-medium",
              )}
            >
              {item.label}
            </span>
          </Link>
        );
      })}
    </nav>
  );
}
