"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  House,
  Moon,
  Person,
  Drop,
  Barbell,
  GearSix,
  Leaf,
  Sparkle,
} from "@phosphor-icons/react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ElementType;
  section?: string;
}

const navItems: NavItem[] = [
  { label: "Home", href: "/", icon: House },
  { label: "Sleep", href: "/sleep", icon: Moon, section: "HEALTH DATA" },
  { label: "Activity", href: "/activity", icon: Person },
  { label: "Body", href: "/body", icon: Barbell },
  { label: "Blood Work", href: "/blood", icon: Drop },
  { label: "Longevity", href: "/longevity", icon: Leaf },
  { label: "Insights", href: "/insights", icon: Sparkle, section: "INTELLIGENCE" },
  { label: "Settings", href: "/settings", icon: GearSix, section: "SETTINGS" },
];

export function Sidebar() {
  const pathname = usePathname();
  let currentSection = "";

  return (
    <aside className="hidden lg:flex flex-col w-[280px] h-screen fixed left-0 top-0 bg-vt-parchment border-r border-vt-border overflow-y-auto">
      {/* Logo */}
      <div className="px-5 pt-6 pb-4">
        <Link href="/" className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-md bg-vt-sage flex items-center justify-center">
            <Leaf className="w-5 h-5 text-white" weight="bold" />
          </div>
          <span className="font-display text-xl font-semibold tracking-wide text-vt-text-strong">
            Vitalis
          </span>
        </Link>
      </div>

      {/* Profile */}
      <div className="px-3 pb-3 border-b border-vt-border mx-2 mb-2">
        <div className="flex items-center gap-3 px-3 py-2 rounded-sm hover:bg-vt-sand-light/50 transition-colors cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-vt-sage flex items-center justify-center text-white text-[0.75rem] font-semibold">
            EV
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[0.875rem] font-medium text-vt-text-strong truncate">Ev Varden</p>
            <p className="text-[0.6875rem] text-vt-text-secondary">Pro plan</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const showSection = item.section && item.section !== currentSection;
          if (item.section) currentSection = item.section;
          const Icon = item.icon;

          return (
            <div key={item.href}>
              {showSection && (
                <p className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary px-3 pt-5 pb-1">
                  {item.section}
                </p>
              )}
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-2.5 px-3 py-2.5 rounded-sm",
                  "text-[0.9375rem] transition-all duration-150 ease-smooth",
                  "min-h-11",
                  isActive
                    ? "bg-vt-thriving-bg text-vt-fern font-medium"
                    : "text-vt-text-primary hover:bg-vt-sand-light hover:text-vt-text-strong",
                )}
              >
                <Icon size={20} weight={isActive ? "fill" : "regular"} />
                {item.label}
              </Link>
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
