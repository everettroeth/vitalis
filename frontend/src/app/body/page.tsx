import { Card, CardContent } from "@/components/ui/card";

export default function BodyPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Body
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Composition, measurements, and progress
        </p>
      </div>

      {/* Weight Overview */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Current Weight
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <p className="metric-value font-display text-[clamp(1.75rem,3vw,2.5rem)] font-light text-vt-text-strong">
              184.2
              <span className="text-[0.9375rem] text-vt-text-secondary font-sans ml-1">lbs</span>
            </p>
            <p className="text-[0.8125rem] text-vt-text-secondary mt-1">Last logged Feb 22</p>
          </CardContent>
        </Card>
      </section>

      {/* DEXA Summary */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Latest DEXA &middot; Sep 3, 2024
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { label: "Body Fat", value: "22.4%", sub: "Down from 24.1% (2023)" },
            { label: "Lean Mass", value: "148.2 lbs", sub: "+2.1 lbs year over year" },
            { label: "Bone Mineral", value: "7.8 lbs", sub: "Stable" },
          ].map((item) => (
            <Card key={item.label}>
              <CardContent>
                <p className="text-[0.75rem] text-vt-text-secondary uppercase tracking-wider">{item.label}</p>
                <p className="metric-value font-display text-2xl font-light text-vt-text-strong mt-1">{item.value}</p>
                <p className="text-[0.75rem] text-vt-text-secondary mt-1">{item.sub}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      {/* Composition bar */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Composition
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="flex gap-1 h-8 rounded-sm overflow-hidden mb-3">
              <div className="bg-vt-sage w-[77.6%]" title="Lean Mass" />
              <div className="bg-vt-sand w-[22.4%]" title="Fat Mass" />
            </div>
            <div className="flex justify-between text-[0.75rem] text-vt-text-secondary">
              <span>Lean Mass 77.6%</span>
              <span>Fat Mass 22.4%</span>
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Trend placeholder */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Weight Trend
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
