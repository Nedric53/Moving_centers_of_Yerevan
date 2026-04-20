const EPS = 1e-9;

export function solveArea(market, transport, amenities, history) {
  if (!(market > 0 && market < 2)) {
    return { ok: false, reason: "Market size must be within the supported range." };
  }
  if (!(amenities > 0)) {
    return { ok: false, reason: "Importance of amenities must be positive." };
  }
  if (!(transport >= 0)) {
    return { ok: false, reason: "Transport factor must be zero or positive." };
  }

  const M = 2 - market;
  const theta = transport / amenities;

  function inCity(q, p) {
    return q < p && q >= -1 - 1e-6 && p <= 1 + 1e-6;
  }

  let muB = NaN;
  let pB = NaN;
  let qB = NaN;
  if (theta > EPS) {
    muB = (-M * market) / (4 * theta);
    pB = muB + M / 2;
    qB = muB - M / 2;
  }

  let muC = NaN;
  let pC = NaN;
  let qC = NaN;
  if (theta > EPS) {
    muC = (M * market) / (4 * theta);
    pC = muC + M / 2;
    qC = muC - M / 2;
  }

  let muA = NaN;
  let pA = NaN;
  let qA = NaN;
  const denom = market - 2 * theta;
  if (Math.abs(denom) > EPS) {
    muA = (market * history) / denom;
    pA = muA + M / 2;
    qA = muA - M / 2;
  }

  function scoreCase(kind, q, p, mu) {
    if (!Number.isFinite(q) || !Number.isFinite(p) || !Number.isFinite(mu)) return null;
    let score = 0;

    if (!inCity(q, p)) {
      score += 10 * (Math.max(0, -1 - q) + Math.max(0, p - 1));
    }
    if (kind === "A") {
      score += Math.max(0, q - history) + Math.max(0, history - p);
    } else if (kind === "B") {
      score += Math.max(0, p - history);
    } else if (kind === "C") {
      score += Math.max(0, history - q);
    }

    return score;
  }

  const candidates = [];
  const scoreA = scoreCase("A", qA, pA, muA);
  if (scoreA !== null) {
    candidates.push([scoreA, "Historical center sits inside the commercial area.", qA, pA, muA]);
  }
  const scoreB = scoreCase("B", qB, pB, muB);
  if (scoreB !== null) {
    candidates.push([scoreB, "Historical center is to the east of the commercial area.", qB, pB, muB]);
  }
  const scoreC = scoreCase("C", qC, pC, muC);
  if (scoreC !== null) {
    candidates.push([scoreC, "Historical center is to the west of the commercial area.", qC, pC, muC]);
  }

  if (!candidates.length) {
    return { ok: false, reason: "No valid configuration found for these settings." };
  }

  candidates.sort((left, right) => left[0] - right[0]);
  const best = candidates[0];

  return {
    ok: true,
    market,
    M,
    transport,
    amenities,
    history,
    theta,
    caseText: best[1],
    q: best[2],
    p: best[3],
    mu: best[4]
  };
}

export function posLabel(value) {
  if (!Number.isFinite(value)) return "unknown";
  if (value <= -0.75) return "far west";
  if (value <= -0.35) return "west";
  if (value <= -0.12) return "slightly west of center";
  if (value < 0.12) return "center";
  if (value < 0.35) return "slightly east of center";
  if (value < 0.75) return "east";
  return "far east";
}

export function historyLabel(value) {
  if (!Number.isFinite(value)) return "unknown";
  if (value <= 0.1) return "far west";
  if (value <= 0.3) return "west";
  if (value <= 0.55) return "near center";
  if (value <= 0.8) return "east";
  return "far east";
}

export function strengthLabel(value, min, max, words) {
  if (!Number.isFinite(value)) return "unknown";
  const ratio = (value - min) / (max - min);
  const index = Math.max(0, Math.min(words.length - 1, Math.round(ratio * (words.length - 1))));
  return words[index];
}

export function scanHistory(state, steps = 160) {
  const histories = [];
  const starts = [];
  const ends = [];

  for (let index = 0; index < steps; index += 1) {
    const history = index / (steps - 1);
    const solution = solveArea(state.market, state.transport, state.amenities, history);
    histories.push(history);
    starts.push(solution.ok ? solution.q : null);
    ends.push(solution.ok ? solution.p : null);
  }

  return { histories, starts, ends };
}

export function scanTransport(state, steps = 140) {
  const transports = [];
  const starts = [];
  const ends = [];

  for (let index = 0; index < steps; index += 1) {
    const transport = 1.5 * (index / (steps - 1));
    const solution = solveArea(state.market, transport, state.amenities, state.history);
    transports.push(transport);
    starts.push(solution.ok ? solution.q : null);
    ends.push(solution.ok ? solution.p : null);
  }

  return { transports, starts, ends };
}
