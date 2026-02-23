import { MetricCard } from "@/components/ui/metric-card";
import { Card, CardContent } from "@/components/ui/card";
import { HealthStatus, type MetricSnapshot } from "@/types";

const sampleMetrics: MetricSnapshot[] = [
  {
    label: "Sleep",
    value: "7h 42m",
    unit: "",
    status: HealthStatus.Thriving,
    trend: "up",
    delta: "22 min more than avg",
    sparklineData: [65, 72, 58, 80, 75, 88, 82],
  },
  {
    label: "HRV",
    value: "44",
    unit: "ms",
    status: HealthStatus.Thriving,
    trend: "up",
    delta: "Up 12% this month",
    sparklineData: [32, 38, 35, 40, 42, 39, 44],
  },
  {
    label: "Steps",
    value: "8,420",
    unit: "",
    status: HealthStatus.Thriving,
    trend: "up",
    delta: "1,200 above goal",
    sparklineData: [6200, 7800, 5400, 8100, 9200, 7600, 8420],
  },
  {
    label: "Resting HR",
    value: "58",
    unit: "bpm",
    status: HealthStatus.Thriving,
    trend: "down",
    delta: "3 below last week",
    sparklineData: [62, 60, 61, 59, 60, 58, 58],
  },
  {
    label: "Body Battery",
    value: "72",
    unit: "%",
    status: HealthStatus.Watch,
    trend: "flat",
    delta: "Same as yesterday",
    sparklineData: [85, 70, 75, 68, 72, 74, 72],
  },
  {
    label: "Stress",
    value: "28",
    unit: "",
    status: HealthStatus.Thriving,
    trend: "down",
    delta: "Lower than avg",
    sparklineData: [45, 38, 42, 35, 30, 32, 28],
  },
];

export default function DashboardPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Good morning, Ev
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Feb 23, 2026 &middot; Day 419
        </p>
      </div>

      {/* Daily Summary */}
      <Card hoverable={false} className="border-l-4 border-l-vt-sage">
        <CardContent>
          <p className="text-[0.9375rem] text-vt-text-primary leading-relaxed">
            Overall feeling strong. Your sleep was restorative and HRV is trending up.
            Steps are well above your daily goal.
          </p>
        </CardContent>
      </Card>

      {/* Today&rsquo;s Snapshot */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary">
            Today&apos;s Snapshot
          </h2>
          <button className="text-[0.8125rem] text-vt-sage hover:text-vt-fern transition-colors">
            View all
          </button>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {sampleMetrics.map((metric) => (
            <MetricCard key={metric.label} metric={metric} />
          ))}
        </div>
      </section>

      {/* Watchlist */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Watchlist
        </h2>
        <Card className="border-l-4 border-l-vt-watch" hoverable={false}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span className="w-2 h-2 rounded-full bg-vt-watch" />
              <div>
                <p className="text-[0.9375rem] font-medium text-vt-text-strong">Ferritin</p>
                <p className="text-[0.8125rem] text-vt-text-secondary">22 ng/mL &middot; Optimal: 40&ndash;80</p>
              </div>
            </div>
            <span className="text-[0.75rem] text-vt-watch font-medium">Watch</span>
          </div>
        </Card>
      </section>

      {/* Recent Insight */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Recent Insight
        </h2>
        <Card hoverable={false} className="bg-vt-thriving-bg/50 border-vt-thriving-border">
          <div className="flex items-start gap-3">
            <span className="text-vt-sage text-lg">&#10022;</span>
            <div>
              <p className="text-[0.9375rem] text-vt-text-primary leading-relaxed">
                On nights you log stress &gt;3, your HRV drops 18% the next morning.
                23 data points. High confidence.
              </p>
              <button className="text-[0.8125rem] text-vt-sage hover:text-vt-fern font-medium mt-2 transition-colors">
                Explore &rarr;
              </button>
            </div>
          </div>
        </Card>
      </section>
    </div>
  );
}
