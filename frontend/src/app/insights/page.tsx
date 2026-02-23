import { Card, CardContent } from "@/components/ui/card";

export default function InsightsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Insights
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Cross-domain correlations and AI-generated patterns
        </p>
      </div>

      {/* Health Fingerprint placeholder */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Health Fingerprint
        </h2>
        <Card hoverable={false}>
          <CardContent>
            <div className="h-56 flex items-center justify-center text-vt-text-secondary text-[0.875rem]">
              Radar chart will render here
            </div>
          </CardContent>
        </Card>
      </section>

      {/* Correlations */}
      <section>
        <h2 className="text-[0.6875rem] font-semibold tracking-[0.08em] uppercase text-vt-text-secondary mb-4">
          Cross-Domain Correlations
        </h2>
        <div className="space-y-4">
          <Card hoverable={false} className="bg-vt-thriving-bg/50 border-vt-thriving-border">
            <CardContent>
              <div className="flex items-start gap-3">
                <span className="text-vt-sage text-lg">&#10022;</span>
                <div>
                  <p className="text-[0.875rem] font-medium text-vt-text-strong mb-1">Strong correlation</p>
                  <p className="text-[0.9375rem] text-vt-text-primary leading-relaxed">
                    On nights you log stress &gt;3, your HRV drops 18% the following morning.
                    23 data points.
                  </p>
                  <p className="text-[0.75rem] text-vt-text-secondary mt-1">p=0.003, high confidence</p>
                </div>
              </div>
            </CardContent>
          </Card>
          <Card hoverable={false} className="bg-vt-watch-bg/50 border-vt-watch-border">
            <CardContent>
              <div className="flex items-start gap-3">
                <span className="text-vt-watch text-lg">&#10022;</span>
                <div>
                  <p className="text-[0.875rem] font-medium text-vt-text-strong mb-1">Trend detected</p>
                  <p className="text-[0.9375rem] text-vt-text-primary leading-relaxed">
                    Your Ferritin has trended down 15% over the last 4 panels.
                    Consider discussing with your doctor.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
