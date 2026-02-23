"use client";

import { Sidebar } from "./sidebar";
import { BottomNav } from "./bottom-nav";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-vt-bg">
      <Sidebar />
      <BottomNav />

      {/* Main content area */}
      <main className="lg:ml-[280px] pb-[calc(80px+env(safe-area-inset-bottom))] lg:pb-0">
        <div className="px-4 md:px-6 lg:px-8 py-6 max-w-7xl mx-auto">
          <div className="animate-page-enter">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
