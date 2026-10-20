import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";
import "./planner.css";
import "./pact-seal.css";
import "./profile.css";
import "./readability.css";
import "./profile-compact.css";
import "./home-directions.css";
import "./feed-layout.css";
import "./post-experience.css";
import "./profile-experience.css";
import "./responsive-shell.css";
import "./home-media-refinements.css";

export const metadata: Metadata = {
  title: "Nen — пакты и самоконтроль",
  description: "Собственные и совместные пакты, отслеживание прогресса, заметки и личные календари.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="ru"><body><AuthProvider>{children}</AuthProvider></body></html>;
}
