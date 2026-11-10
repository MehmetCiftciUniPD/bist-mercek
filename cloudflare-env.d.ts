declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
    BUCKET?: R2Bucket;
    // Yapay zekâ analizi (isteğe bağlı). Bkz. lib/analysis.ts.
    AI_API_KEY?: string;
    OPENROUTER_API_KEY?: string;
    AI_BASE_URL?: string;
    AI_MODEL?: string;
  }
}
