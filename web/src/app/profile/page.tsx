"use client";
import { Suspense, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { profileHref } from "@/lib/profile-navigation";
import RequireAuth from "@/components/require-auth";
import { Loading, Shell } from "@/components/ui";

function MyProfileRedirect() {
  const {user} = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  useEffect(()=>{if(user) router.replace(profileHref(user.username,params.toString(),window.location.hash));},[user,params,router]);
  return <Loading/>;
}
export default function ProfileShortcut() {return <Shell><Suspense fallback={<Loading/>}><RequireAuth><MyProfileRedirect/></RequireAuth></Suspense></Shell>;}
