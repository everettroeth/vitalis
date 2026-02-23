import { Card, CardContent } from "@/components/ui/card";
import { StatusBadge } from "@/components/ui/status-badge";
import { HealthStatus } from "@/types";

export default function SleepPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Sleep
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Track and understand your rest
        </p>
      </div>

      {/* Last Night Summary */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Last Night &middot; Feb 22&ndash;23
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="flex items-start justify-between mb-4">
              <div>
                <p className="metric-value font-display text-[clamp(1.75rem,3vw,2.5rem)] font-light text-vt-text-strong">
                  7h 42m
                </p>
                <p className="text-[0.875rem] text-vt-text-secondary">
                  11:18 PM &rarr; 7:00 AM
                </p>
              </div>
              <StatusBadge status={HealthStatus.Thriving} />
            </div>

            {/* Sleep stages placeholder */}
            <div className="flex gap-1 h-6 rounded-sm overflow-hidden mb-4">
              <div className="bg-vt-fern w-[18%]" title="Deep: 1h 24m" />
              <div className="bg-vt-sage w-[24%]" title="REM: 1h 52m" />
              <div className="bg-vt-sand w-[43%]" title="Light: 3h 18m" />
              <div className="bg-vt-sand-light w-[6%]" title="Awake: 28m" />
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "Deep", value: "1h 24m", color: "bg-vt-fern" },
                { label: "REM", value: "1h 52m", color: "bg-vt-sage" },
                { label: "Light", value: "3h 18m", color: "bg-vt-sand" },
                { label: "Awake", value: "28m", color: "bg-vt-sand-light" },
              ].map((stage) => (
                <div key={stage.label} className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${stage.color}`} />
                  <div>
                    <p className="text-[0.75rem] text-vt-text-secondary">{stage.label}</p>
                    <p className="text-[0.875rem] font-medium text-vt-text-strong">{stage.value}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Trend placeholder */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Sleep Quality Trend
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="h-44 flex items-center justify-center text-vt-text-secondary text-[0.875rem]">
              Chart will render here
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Sources */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Sources
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {[
            { source: "Garmin", duration: "7h 42m", score: 82 },
            { source: "Oura", duration: "7h 38m", score: 79 },
          ].map((s) => (
            <Card key={s.source}>
              <CardContent>
                <p className="text-[0.8125rem] font-medium text-vt-text-strong">{s.source}</p>
                <p className="metric-value font-display text-xl font-light text-vt-text-strong mt-1">{s.duration}</p>
                <p className="text-[0.75rem] text-vt-text-secondary mt-1">Score: {s.score}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>
    </div>
  );
}
