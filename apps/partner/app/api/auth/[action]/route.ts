import { handlePortalAuthGet, handlePortalAuthPost } from "@breero/portal/server";

import { portalRuntime } from "../../../../portal.config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = { params: Promise<{ action: string }> };

export async function GET(request: Request, context: RouteContext) {
  const { action } = await context.params;
  return handlePortalAuthGet(request, action, portalRuntime);
}

export async function POST(request: Request, context: RouteContext) {
  const { action } = await context.params;
  return handlePortalAuthPost(request, action, portalRuntime);
}
