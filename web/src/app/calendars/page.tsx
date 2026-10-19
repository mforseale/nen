"use client";
import RequireAuth from "@/components/require-auth";
import { CalendarWorkspace } from "@/components/calendar-workspace";
import { Shell } from "@/components/ui";

export default function CalendarsPage() {
  return <Shell><RequireAuth><CalendarWorkspace/></RequireAuth></Shell>;
}
