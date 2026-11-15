"""BTC price forecast: 4 hours (240 min) ahead.
Input: 1-minute US dollar closes of the 72 hours before a checkpoint.
Output: one number per case at /output/<id>.out
Score: MAE in cents over 12 cases. Baseline = persistence (checkpoint close).
"""
import json, os, sys

CASE = "/input/{}.in".format(sys.argv[1]) if len(sys.argv) > 1 else "/input/{}.in".format(os.environ.get("CASE_ID", ""))
if CASE == "/input/.in" or CASE.strip() == "/input/":
    # fallback: read case id from stdin/env
    pass

def read_cases(path):
    """Read JSON lines: each line = one minute bar {\"t\": ts, \"p\": price}."""
    out = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                bar = json.loads(line)
                out.append((bar["t"], bar["p"]))
            except Exception:
                continue
    return out

def forecast(prices, lookback=1440):
    """Predict price 240 minutes after the last observed close.
    Uses EMA with trend extrapolation.
    """
    if len(prices) == 0:
        return None
    if len(prices) == 1:
        return prices[-1]

    n = min(lookback, len(prices))
    window = prices[-n:]

    # EMA with alpha tuned for 4h drift
    alpha = 0.15
    ema = window[0]
    for p in window[1:]:
        ema = alpha * p + (1 - alpha) * ema

    # trend: linear regression slope over last 2h (120 min)
    m = 120
    seg = window[-m:] if len(window) >= m else window
    x0 = len(seg) - 1
    sx = sum(x0 - i for i in range(len(seg)))
    sy = sum(seg)
    sxx = sum((x0 - i) ** 2 for i in range(len(seg)))
    sxy = sum((x0 - i) * v for i, v in enumerate(seg))
    slope = (len(seg) * sxy - sx * sy) / (len(seg) * sxx - sx * sx) if (len(seg) * sxx - sx * sx) != 0 else 0.0

    # predict: EMA + trend * 240, but dampen trend to avoid overreaction
    trend_damped = slope * 240 * 0.6
    pred = ema + trend_damped

    # fallback: persistence if something weird
    if pred is None or not isinstance(pred, (int, float)):
        pred = prices[-1]

    return pred

def main():
    path = CASE if os.path.exists(CASE) else "/input/{}.in".format(os.environ.get("CASE_ID", "0"))
    if not os.path.exists(path):
        # try to discover case id
        candidates = []
        for d in ["/input", "./input"]:
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".in"):
                        candidates.append(os.path.join(d, f))
        if candidates:
            path = candidates[0]
        else:
            sys.stderr.write("no input found\n")
            sys.exit(1)

    bars = read_cases(path)
    prices = [float(b) for _, b in bars]
    pred = forecast(prices)
    pred = round(pred, 2)

    os.makedirs("/output", exist_ok=True)
    with open("/output/{}.out".format(os.path.basename(path).replace(".in", "")), "w") as f:
        f.write("{}\n".format(pred))

if __name__ == "__main__":
    main()
