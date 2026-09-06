// A short-lived, same-tab reading marker. No document text or AI output is stored.
const KEY = "helvetic.registry-position.v1";
const TTL = 30 * 60 * 1000;
type Storage = Pick<globalThis.Storage, "getItem" | "setItem" | "removeItem">;
export type RegistryPosition = {version:1; scope:string; route:string; row:string; target:string; savedAt:number};
export function registryScope(user?:string, organization?:string, development=false) {
  return user && organization ? JSON.stringify([user,organization]) : development ? "anonymous-development" : null;
}
function localPath(value:unknown, registry=false):value is string {
  if(typeof value!=="string" || value.length>4096 || /[\\\r\n]/.test(value) || !value.startsWith("/") || value.startsWith("//")) return false;
  try {
    const url=new URL(value,"https://local.invalid");
    return url.origin==="https://local.invalid" && (registry ? ["/registry","/discover"].includes(url.pathname) : /^\/(?:corpus-evidence|evidence|laws|compare)\/[^/]+$/.test(url.pathname));
  } catch { return false; }
}
export function readRegistryPosition(storage:Storage, scope:string|null, now=Date.now()):RegistryPosition|null {
  if(!scope) return null;
  try {
    const raw=storage.getItem(KEY);
    if(!raw || raw.length>10000) return null;
    const value=JSON.parse(raw);
    if(!value || value.version!==1 || value.scope!==scope || !localPath(value.route,true) || !localPath(value.target)
      || typeof value.row!=="string" || !value.row || value.row.length>256
      || !Number.isFinite(value.savedAt) || value.savedAt>now || now-value.savedAt>=TTL) return null;
    return {version:1,scope,route:value.route,row:value.row,target:value.target,savedAt:value.savedAt};
  } catch { return null; }
}
export function saveRegistryPosition(storage:Storage, scope:string|null, route:string,row:string,target:string,now=Date.now()) {
  if(!scope) return;
  const value={version:1,scope,route,row,target,savedAt:now};
  // Apply the same structural rules to writes as restored data.
  if(!readRegistryPosition({getItem:()=>JSON.stringify(value),setItem:()=>{},removeItem:()=>{}},scope,now)) return;
  try {storage.setItem(KEY,JSON.stringify(value));} catch { /* Browser storage is optional. Native Back still works. */ }
}
export function clearRegistryPosition(storage:Storage, scope:string|null) {
  if(!readRegistryPosition(storage,scope)) return;
  try {storage.removeItem(KEY);} catch { /* No persisted-data dependency. */ }
}
