"use client";
import { Suspense } from "react";
import { useParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/api";
import type { ProfileData } from "@/lib/community";
import { UserProfile } from "@/components/user-profile";
import { ErrorMessage, Loading, Shell } from "@/components/ui";

function ProfileContent() {
  const {username} = useParams<{username:string}>();
  const {user,loading:authLoading} = useAuth();
  const {data,error,loading} = useApi<ProfileData>(authLoading ? null : "/people/"+encodeURIComponent(username)+"?viewer="+(user?.id ?? "guest"));
  return <Shell><ErrorMessage error={error}/>{authLoading || loading ? <Loading/> : data && <UserProfile key={data.user.id+":"+(user?.id ?? "guest")} data={data}/>}</Shell>;
}
export default function ProfilePage() {return <Suspense fallback={<Shell><Loading/></Shell>}><ProfileContent/></Suspense>;}
