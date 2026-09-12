// api.ts — REST endpoint types and request handler (TypeScript test file)

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

export interface Route {
  method: HttpMethod;
  path: string;
  handler: (req: Request, res: Response) => Promise<void>;
  requiresAuth?: boolean;
}

export interface Request {
  method: HttpMethod;
  path: string;
  params: Record<string, string>;
  body: unknown;
  headers: Record<string, string>;
  userId?: string;  // populated after auth middleware
}

export interface Response {
  statusCode: number;
  body: unknown;
  headers: Record<string, string>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Router
// ─────────────────────────────────────────────────────────────────────────────

export class Router {
  private routes: Route[] = [];

  register(route: Route): void {
    this.routes.push(route);
    console.log(`[Router] Registered ${route.method} ${route.path}`);
  }

  async dispatch(req: Request): Promise<Response> {
    const matched = this.routes.find(
      (r) => r.method === req.method && r.path === req.path,
    );

    if (!matched) {
      return { statusCode: 404, body: { error: 'Not found' }, headers: {} };
    }

    const res: Response = { statusCode: 200, body: null, headers: {} };

    try {
      await matched.handler(req, res);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Internal server error';
      res.statusCode = 500;
      res.body = { error: message };
    }

    return res;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Built-in handlers
// ─────────────────────────────────────────────────────────────────────────────

export async function healthHandler(req: Request, res: Response): Promise<void> {
  res.statusCode = 200;
  res.body = { status: 'ok', timestamp: new Date().toISOString() };
}

export async function echoHandler(req: Request, res: Response): Promise<void> {
  res.statusCode = 200;
  res.body = { echo: req.body };
}

// ─────────────────────────────────────────────────────────────────────────────
// Middleware
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Strips "Bearer " prefix and returns the raw token, or null if missing.
 */
export function extractBearerToken(req: Request): string | null {
  const auth = req.headers['authorization'] ?? '';
  if (!auth.startsWith('Bearer ')) return null;
  return auth.slice(7).trim() || null;
}

/**
 * Apply a list of middleware functions sequentially.
 * Each middleware can mutate req/res or throw to abort the chain.
 */
export async function applyMiddleware(
  req: Request,
  res: Response,
  middlewares: Array<(req: Request, res: Response) => Promise<void>>,
): Promise<void> {
  for (const mw of middlewares) {
    await mw(req, res);
  }
}
