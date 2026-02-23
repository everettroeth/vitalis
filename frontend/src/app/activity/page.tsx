import { Card, CardContent } from "@/components/ui/card";
import { MetricCard } from "@/components/ui/metric-card";
import { HealthStatus, type MetricSnapshot } from "@/types";

const activityMetrics: MetricSnapshot[] = [
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
    label: "Active Minutes",
    value: "64",
    unit: "min",
    status: HealthStatus.Thriving,
    trend: "up",
    delta: "14 above avg",
    sparklineData: [45, 52, 38, 60, 55, 48, 64],
  },
  {
    label: "Calories Burned",
    value: "2,340",
    unit: "kcal",
    status: HealthStatus.Thriving,
    trend: "flat",
    delta: "On target",
    sparklineData: [2200, 2100, 2350, 2280, 2400, 2300, 2340],
  },
  {
    label: "VO2 Max",
    value: "46",
    unit: "mL/kg",
    status: HealthStatus.Thriving,
    trend: "up",
    delta: "Up 2 this quarter",
    sparklineData: [43, 43, 44, 44, 45, 45, 46],
  },
];

export default function ActivityPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Activity
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Movement, training, and recovery
        </p>
      </div>

      {/* Metrics grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {activityMetrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </div>

      {/* Recent Workouts */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Recent Workouts
        </h2>
        <div className="space-y-3">
          {[
            { type: "Running", duration: "42 min", distance: "5.2 km", date: "Today" },
            { type: "Strength", duration: "55 min", distance: "", date: "Yesterday" },
            { type: "Cycling", duration: "1h 15m", distance: "28 km", date: "Feb 20" },
          ].map((workout) => (
            <Card key={`${workout.type}-${workout.date}`}>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[0.9375rem] font-medium text-vt-text-strong">{workout.type}</p>
                    <p className="text-[0.8125rem] text-vt-text-secondary">
                      {workout.duration}{workout.distance && ` · ${workout.distance}`}
                    </p>
                  </div>
                  <span className="text-[0.75rem] text-vt-text-secondary">{workout.date}</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Trend placeholder */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Activity Trend
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="h-44 flex items-center justify-center text-vt-text-secondary text-[0.875rem]">
              Chart will render here
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
