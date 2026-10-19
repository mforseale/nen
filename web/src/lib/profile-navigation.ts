/** One address for both the owner and visitors; /profile only resolves "me". */
export function profileHref(username?: string | null, search = "", hash = "") {
  const path = username ? "/people/"+encodeURIComponent(username) : "/profile";
  return path+(search ? "?"+search.replace(/^\?/,"") : "")+(hash ? "#"+hash.replace(/^#/,"") : "");
}
