import numpy as np
import pandas as pd
import statsmodels.api as sm

from .config import SPEED_M_PER_MIN


DEFAULT_FEATURES = [
    "tau_min",
    "dist_to_g_m",
    "herit_density_500m",
    "pop_density_per_km2",
    "log_rent",
    "rent_missing",
]


def tau_minutes(cx, cy, mux, muy, transport_factor: float = 1.0, speed_m_per_min: float = SPEED_M_PER_MIN):
    d = np.sqrt((cx - mux) ** 2 + (cy - muy) ** 2)
    return float(transport_factor) * (d / float(speed_m_per_min))


def _safe_std(series: pd.Series) -> pd.Series:
    return series.replace(0, 1.0)


def fit_business_model(master: pd.DataFrame, features=None) -> dict:
    features = features or list(DEFAULT_FEATURES)
    master = master.copy()

    w = master["M_obs"].fillna(0).to_numpy()
    if float(w.sum()) <= 0:
        raise RuntimeError("M_obs sums to zero, cannot initialize mu.")

    mu0x = float((master["cx"].to_numpy() * w).sum() / w.sum())
    mu0y = float((master["cy"].to_numpy() * w).sum() / w.sum())

    master["tau_min"] = tau_minutes(master["cx"].to_numpy(), master["cy"].to_numpy(), mu0x, mu0y, 1.0)

    est = master[["y_business"] + features].replace([np.inf, -np.inf], np.nan).dropna().copy()
    means = est[features].mean()
    stds = _safe_std(est[features].std())

    def zscore(df_x: pd.DataFrame) -> pd.DataFrame:
        z = df_x.copy()
        for c in df_x.columns:
            z[c] = (z[c] - means[c]) / stds[c]
        return z

    x = sm.add_constant(zscore(est[features]), has_constant="add")
    y = est["y_business"].astype(int)
    logit_model = sm.Logit(y, x).fit(disp=False)

    return {
        "master": master,
        "logit_model": logit_model,
        "features": features,
        "means": means,
        "stds": stds,
        "mu0x": mu0x,
        "mu0y": mu0y,
        "zscore": zscore,
    }


def predict_shares(df, mux, muy, transport_factor, amenity_factor, *, logit_model, features, means, stds):
    tmp = df.copy()
    tmp["tau_min"] = tau_minutes(tmp["cx"].to_numpy(), tmp["cy"].to_numpy(), mux, muy, transport_factor)

    xraw = tmp[features].replace([np.inf, -np.inf], np.nan)
    z = xraw.copy()
    for c in xraw.columns:
        z[c] = (z[c] - means[c]) / stds[c]

    z["dist_to_g_m"] = z["dist_to_g_m"] * amenity_factor
    z["herit_density_500m"] = z["herit_density_500m"] * amenity_factor

    xmat = sm.add_constant(z, has_constant="add")
    p = logit_model.predict(xmat)
    return p.to_numpy()


def solve_mu(
    df,
    transport_factor,
    amenity_factor,
    *,
    logit_model,
    features,
    means,
    stds,
    mu_init,
    max_iters: int = 30,
    tol_m: float = 30.0,
):
    mux, muy = mu_init
    cx = df["cx"].to_numpy()
    cy = df["cy"].to_numpy()

    for _ in range(max_iters):
        s = predict_shares(
            df,
            mux,
            muy,
            transport_factor,
            amenity_factor,
            logit_model=logit_model,
            features=features,
            means=means,
            stds=stds,
        )
        valid = np.isfinite(s)
        s2 = s[valid]
        if s2.sum() <= 1e-9:
            break

        mux_new = float((cx[valid] * s2).sum() / s2.sum())
        muy_new = float((cy[valid] * s2).sum() / s2.sum())
        shift = float(np.sqrt((mux_new - mux) ** 2 + (muy_new - muy) ** 2))
        mux, muy = mux_new, muy_new
        if shift < tol_m:
            break

    s_final = predict_shares(
        df,
        mux,
        muy,
        transport_factor,
        amenity_factor,
        logit_model=logit_model,
        features=features,
        means=means,
        stds=stds,
    )
    return (mux, muy), s_final
