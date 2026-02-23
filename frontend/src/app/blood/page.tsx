import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { HealthStatus } from "@/types";

const markers = [
  { category: "METABOLIC", items: [
    { name: "Glucose", value: "94 mg/dL", status: HealthStatus.Thriving },
    { name: "HbA1c", value: "5.1%", status: HealthStatus.Thriving },
    { name: "Insulin", value: "6.2 \u00b5U/mL", status: HealthStatus.Thriving },
  ]},
  { category: "THYROID", items: [
    { name: "TSH", value: "1.8 mIU/L", status: HealthStatus.Thriving },
    { name: "Free T3", value: "3.2 pg/mL", status: HealthStatus.Watch },
    { name: "Free T4", value: "1.1 ng/dL", status: HealthStatus.Thriving },
  ]},
  { category: "IRON PANEL", items: [
    { name: "Ferritin", value: "22 ng/mL", status: HealthStatus.Concern },
    { name: "Serum Iron", value: "88 \u00b5g/dL", status: HealthStatus.Thriving },
  ]},
  { category: "VITAMINS", items: [
    { name: "Vitamin D", value: "18 ng/mL", status: HealthStatus.Concern },
    { name: "B12", value: "680 pg/mL", status: HealthStatus.Thriving },
  ]},
];

export default function BloodPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Blood Work
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Lab panels, markers, and trends
        </p>
      </div>

      {/* Latest Panel Header */}
      <section>
        <p className="text-[0.8125rem] text-vt-text-secondary mb-1">Latest Panel &middot; Oct 15, 2024</p>
        <p className="text-[0.75rem] text-vt-text-secondary">Quest Diagnostics</p>
      </section>

      {/* Status Overview */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Status Overview
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-vt-thriving" />
                <span className="text-[0.875rem] text-vt-text-primary">Thriving: 18</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-vt-watch" />
                <span className="text-[0.875rem] text-vt-text-primary">Watch: 4</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-vt-clay" />
                <span className="text-[0.875rem] text-vt-text-primary">Concern: 2</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Marker Categories */}
      {markers.map((cat) => (
        <section key={cat.category}>
          <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
            {cat.category}
          </h2>
          <Card hoverable={false}>
            <CardContent>
              <div className="divide-y divide-vt-border">
                {cat.items.map((marker) => (
                  <div key={marker.name} className="flex items-center justify-between py-3 first:pt-0 last:pb-0">
                    <div>
                      <p className="text-[0.9375rem] text-vt-text-strong">{marker.name}</p>
                      <p className="text-[0.8125rem] text-vt-text-secondary">{marker.value}</p>
                    </div>
                    <StatusBadge status={marker.status} />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </section>
      ))}
    </div>
  );
}
