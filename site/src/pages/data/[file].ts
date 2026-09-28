import { searchIndexFile, searchIndexRaw } from "../../lib/data";

export function getStaticPaths() {
  return [{ params: { file: searchIndexFile() } }];
}

export function GET() {
  return new Response(searchIndexRaw(), { headers: { "Content-Type": "application/json" } });
}
