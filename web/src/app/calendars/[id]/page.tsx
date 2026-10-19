"use client";
import { Suspense } from "react";
import { useParams } from "next/navigation";
import RequireAuth from "@/components/require-auth";
import { CalendarWorkspace } from "@/components/calendar-workspace";
import { ErrorMessage, Loading, Shell } from "@/components/ui";

function CalendarPageContent() {
  const {id} = useParams<{id:string}>();
  if (!/^\d+$/.test(id) || !Number.isSafeInteger(Number(id)) || Number(id) < 1) return <ErrorMessage error="Календарь не найден"/>;
  return <RequireAuth><CalendarWorkspace calendarId={Number(id)}/></RequireAuth>;
}
export default function CalendarPage() {return <Shell><Suspense fallback={<Loading/>}><CalendarPageContent/></Suspense></Shell>;}
