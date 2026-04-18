// Money formatting. All API amounts are integer cents. The UI presents them
// as dollars with 2 decimals and optional thousands separators.

export function formatCents(cents: number, opts: { sign?: boolean } = {}): string {
  const negative = cents < 0;
  const absCents = Math.abs(cents);
  const whole = Math.floor(absCents / 100);
  const frac = absCents % 100;
  const wholeFmt = whole.toLocaleString("en-US");
  const body = `${wholeFmt}.${String(frac).padStart(2, "0")}`;
  if (negative) return `(${body})`;
  return opts.sign ? `+${body}` : body;
}

export function parseDollars(input: string): number {
  // Accept "$1,234.56", "-30", "(45.00)", "12.3", etc.
  const cleaned = input.trim().replace(/[$,]/g, "");
  const negParen = /^\((.+)\)$/.exec(cleaned);
  const value = negParen ? -parseFloat(negParen[1]) : parseFloat(cleaned);
  if (Number.isNaN(value)) {
    throw new Error(`not a number: ${input}`);
  }
  return Math.round(value * 100);
}
