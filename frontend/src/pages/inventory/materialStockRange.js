export const MATERIAL_STOCK_RANGE_ERROR = 'El stock mínimo no puede ser mayor que el stock máximo.';

export function getMaterialStockRangeError(minimum, maximum) {
  const values = [minimum, maximum].map((value) => String(value ?? '').trim() || '0');
  if (values.some((value) => !/^(?:\d+(?:\.\d*)?|\.\d+)$/.test(value))) {
    return 'El stock mínimo y máximo deben ser números mayores o iguales a cero.';
  }
  // Compare decimal strings so four-decimal limits do not lose precision in Number.
  const parts = values.map((value) => {
    const [integer, fraction = ''] = value.split('.');
    return [(integer || '0').replace(/^0+(?=\d)/, ''), fraction];
  });
  const [[minInteger, minFraction], [maxInteger, maxFraction]] = parts;
  const scale = Math.max(minFraction.length, maxFraction.length);
  const exceeds = minInteger.length !== maxInteger.length
    ? minInteger.length > maxInteger.length
    : minInteger !== maxInteger
      ? minInteger > maxInteger
      : minFraction.padEnd(scale, '0') > maxFraction.padEnd(scale, '0');
  return exceeds ? MATERIAL_STOCK_RANGE_ERROR : '';
}
