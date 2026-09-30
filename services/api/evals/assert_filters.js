module.exports = (output, context) => {
  try {
    const parsed = typeof output === 'string' ? JSON.parse(output) : output;
    const actual = parsed.filters;
    const expected = context.vars.expected_filters;
    if (!actual || !expected) return false;
    return ['phase', 'zone', 'trigger', 'team', 'competition', 'outcome'].every((key) => JSON.stringify(actual[key] ?? null) === JSON.stringify(expected[key] ?? null));
  } catch (_) {
    return false;
  }
};
