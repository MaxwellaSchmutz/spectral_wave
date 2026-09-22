// The time grid of a result, reproduced exactly as NumPy builds it.
//
// Python computes psi on np.linspace(t_min, t_max, n_t); the bridge returns
// only (t_min, t_max, n_t). For labelling rows we need the same doubles, so
// this follows numpy.linspace (endpoint=True, scalar bounds) operation for
// operation: y = arange(n) * step + start, step = (stop - start) / (n - 1),
// and the last sample is set to stop. It is axis bookkeeping, not physics.
export function linspace(start: number, stop: number, num: number): Float64Array {
  const out = new Float64Array(num);
  if (num === 1) {
    out[0] = start;
    return out;
  }
  const div = num - 1;
  const delta = stop - start;
  const step = delta / div;
  for (let i = 0; i < num; i++) {
    out[i] = step === 0 ? (i / div) * delta + start : i * step + start;
  }
  out[num - 1] = stop;
  return out;
}
