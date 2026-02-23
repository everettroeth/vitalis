import type { Metadata, Viewport } from "next";
import { Quicksand, Inter } from "next/font/google";
import { ThemeProvider } from "@/components/layout/theme-provider";
import { AppShell } from "@/components/layout/app-shell";
import "./globals.css";

const quicksand = Quicksand({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Vitalis — Every signal, one home",
  description: "Personal health intelligence platform. Your body has been talking. Now you can listen.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Vitalis",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#FAFAF5" },
    { media: "(prefers-color-scheme: dark)", color: "#1A1714" },
  ],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${quicksand.variable} ${inter.variable} antialiased`}>
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
