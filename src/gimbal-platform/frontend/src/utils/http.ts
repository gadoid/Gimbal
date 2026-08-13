/**
 * utils/http.ts — re-export shim for the shared axios instance.
 *
 * The V3 scenario-composer modules import from ``@/utils/http`` (named
 * export ``http``); the canonical instance lives at ``@/api/http`` and
 * uses default export.  This shim bridges the two naming styles so
 * ``@/utils/http`` resolves to the same singleton without duplicating
 * any request/response interceptor logic.
 */
import http from '@/api/http'

export { http }
export default http
