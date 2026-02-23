import { Card, CardContent } from "@/components/ui/card";

export default function LongevityPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Longevity
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Biological age, epigenetics, and aging pace
        </p>
      </div>

      <Card hoverable={false}>
        <CardContent>
          <div className="py-12 text-center">
            <p className="text-vt-text-secondary text-[0.9375rem]">
              Upload your epigenetics results to see biological age data here.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
