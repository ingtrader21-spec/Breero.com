const TRACE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/;

export function safeTraceId(value: string | null | undefined): string | undefined {
  return value && TRACE_ID_PATTERN.test(value) ? value : undefined;
}
