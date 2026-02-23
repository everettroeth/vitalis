"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Toggle } from "@/components/ui/toggle";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import { useTheme } from "@/components/layout/theme-provider";

export default function SettingsPage() {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="space-y-8 max-w-2xl">
      <div>
        <h1 className="font-display text-[clamp(1.5rem,2.5vw,2rem)] font-semibold text-vt-text-strong leading-tight">
          Settings
        </h1>
        <p className="text-[0.9375rem] text-vt-text-secondary mt-1">
          Preferences, devices, and account
        </p>
      </div>

      {/* Appearance */}
      <Card hoverable={false}>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Toggle
            checked={theme === "dark"}
            onChange={toggleTheme}
            label="Dark mode"
          />
        </CardContent>
      </Card>

      {/* Units */}
      <Card hoverable={false}>
        <CardHeader>
          <CardTitle>Units</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Select
            label="Unit system"
            options={[
              { value: "imperial", label: "Imperial (lbs, in, \u00b0F)" },
              { value: "metric", label: "Metric (kg, cm, \u00b0C)" },
            ]}
            defaultValue="imperial"
          />
          <Select
            label="Date format"
            options={[
              { value: "MM/DD/YYYY", label: "MM/DD/YYYY" },
              { value: "DD/MM/YYYY", label: "DD/MM/YYYY" },
              { value: "YYYY-MM-DD", label: "YYYY-MM-DD" },
            ]}
            defaultValue="MM/DD/YYYY"
          />
          <Select
            label="Time format"
            options={[
              { value: "12h", label: "12-hour" },
              { value: "24h", label: "24-hour" },
            ]}
            defaultValue="12h"
          />
        </CardContent>
      </Card>

      {/* Connected Devices */}
      <Card hoverable={false}>
        <CardHeader>
          <CardTitle>Connected Devices</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[0.9375rem] font-medium text-vt-text-strong">Garmin</p>
              <p className="text-[0.75rem] text-vt-text-secondary">Last synced 5 min ago</p>
            </div>
            <span className="text-[0.75rem] text-vt-thriving font-medium">Connected</span>
          </div>
          <div className="flex items-center justify-between py-2">
            <div>
              <p className="text-[0.9375rem] font-medium text-vt-text-strong">Oura Ring</p>
              <p className="text-[0.75rem] text-vt-text-secondary">Last synced 12 min ago</p>
            </div>
            <span className="text-[0.75rem] text-vt-thriving font-medium">Connected</span>
          </div>
          <Button variant="secondary" size="sm" className="mt-2">
            Connect new device
          </Button>
        </CardContent>
      </Card>

      {/* Data */}
      <Card hoverable={false}>
        <CardHeader>
          <CardTitle>Data</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Button variant="ghost" size="sm">Export all data</Button>
          <Button variant="destructive" size="sm">Delete account</Button>
        </CardContent>
      </Card>
    </div>
  );
}
