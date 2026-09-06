import type {Change} from "./types";

type Kind = "equal" | "removed" | "added" | "omission";
export type DeltaPart = {text:string; kind:Kind};
type Operation = {old:string; new:string; equal:boolean};
const CONTEXT = 64, CHANGE = 120;
const chars = (value:string, count:number, end=false) => {
  const points=Array.from(value);
  return (end ? points.slice(-count) : points.slice(0,count)).join("");
};

export function materialDelta(change?: Change) {
  const oldText=change?.old?.text || "", newText=change?.new?.text || "";
  const fallback = () => ({old:[{kind:"equal" as Kind,text:chars(oldText,248)}],
    new:[{kind:"equal" as Kind,text:chars(newText,248)}], fragments:0, focused:false,
    limited:Array.from(oldText).length>248 || Array.from(newText).length>248});
  if(!change) return fallback();
  const before=change.old_parts, after=change.new_parts;
  if(!Array.isArray(before) || !Array.isArray(after)
    || before.some(part=>!part || typeof part.text!=="string" || !["equal","removed"].includes(part.kind))
    || after.some(part=>!part || typeof part.text!=="string" || !["equal","added"].includes(part.kind))
    || before.map(part=>part.text).join("")!==oldText || after.map(part=>part.text).join("")!==newText) return fallback();
  const operations: Operation[]=[];
  let i=0,j=0;
  while(i<before.length || j<after.length){
    let old="", current="";
    while(i<before.length && before[i].kind!=="equal") old+=before[i++].text;
    while(j<after.length && after[j].kind!=="equal") current+=after[j++].text;
    if(old || current) {operations.push({old,new:current,equal:false}); continue;}
    if(i>=before.length || j>=after.length || before[i].text!==after[j].text) return fallback();
    operations.push({old:before[i++].text,new:after[j++].text,equal:true});
  }
  const index=operations.findIndex(part=>!part.equal);
  if(index<0) return fallback();
  const fragments=operations.filter(part=>!part.equal).length;
  let limited=index>1 || index+2<operations.length;
  function side(key:"old"|"new"):DeltaPart[]{
    const result:DeltaPart[]=[];
    const omit=()=>{limited=true; result.push({kind:"omission",text:"…"});};
    const prefix=operations[index-1]?.[key] || "";
    if(index>1 || Array.from(prefix).length>CONTEXT) omit();
    if(prefix) result.push({kind:"equal",text:chars(prefix,CONTEXT,true)});
    const value=operations[index][key];
    if(value) result.push({kind:key==='old'?'removed':'added',text:chars(value,CHANGE)});
    if(Array.from(value).length>CHANGE) omit();
    const suffix=operations[index+1]?.[key] || "";
    if(suffix) result.push({kind:"equal",text:chars(suffix,CONTEXT)});
    if(index+2<operations.length || Array.from(suffix).length>CONTEXT) omit();
    return result;
  }
  const old=side('old'), current=side('new');
  return {old,new:current,fragments,focused:true,limited};
}
