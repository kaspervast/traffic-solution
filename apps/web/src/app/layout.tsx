import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/lib/query-provider";
import { Nav } from "@/components/ui/Nav";

export const metadata: Metadata = {
  title: "Rajkot AI Traffic Command Center (1 km Pilot)",
  description: "SUMO-integrated traffic intelligence platform for a 1 km pilot zone in Rajkot, Gujarat.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <div className="flex min-h-screen flex-col">
            <Nav />
            <main className="flex-1">{children}</main>
          </div>
        </QueryProvider>
      </body>
    </html>
  );
}
