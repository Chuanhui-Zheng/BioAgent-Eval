from __future__ import annotations
import csv
import io
import math
import numpy as np
from scipy.stats import hypergeom


def benjamini_hochberg(values: list[float]) -> list[float]:
    p = np.asarray(values, dtype=float)
    if not len(p):
        return []
    order = np.argsort(p)
    adjusted = np.minimum.accumulate(
        (p[order] * len(p) / np.arange(1, len(p) + 1))[::-1]
    )[::-1]
    result = np.empty(len(p))
    result[order] = np.minimum(adjusted, 1)
    return result.tolist()


def parse_gmt(text: str) -> dict[str, set[str]]:
    terms: dict[str, set[str]] = {}
    for line in text.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 3 or not fields[0].strip():
            raise ValueError(
                "GMT requires term, description and at least one gene, separated by tabs."
            )
        name = fields[0].strip()
        if name in terms:
            raise ValueError(f"Duplicate gene set: {name}")
        genes = {g.strip().upper() for g in fields[2:] if g.strip()}
        if genes:
            terms[name] = genes
    if not terms:
        raise ValueError("The gene-set library is empty.")
    return terms


def enrichment(
    selected: list[str],
    background: list[str],
    terms: dict[str, set[str]],
    threshold: float = 0.05,
) -> dict:
    universe = {g.strip().upper() for g in background if g.strip()}
    query = {g.strip().upper() for g in selected if g.strip()}
    if not universe or not query:
        raise ValueError("Selected genes and background must be nonempty.")
    if not query <= universe:
        raise ValueError("All selected genes must occur in the measured background.")
    rows = []
    for term, genes in terms.items():
        available = genes & universe
        if not available:
            continue
        overlap = sorted(query & available)
        p = float(
            hypergeom.sf(len(overlap) - 1, len(universe), len(available), len(query))
        )
        rows.append(
            {
                "term": term,
                "p_value": p,
                "overlap": overlap,
                "overlap_count": len(overlap),
                "term_size": len(available),
                "selected_size": len(query),
                "background_size": len(universe),
                "fold_enrichment": len(overlap)
                * len(universe)
                / (len(query) * len(available)),
            }
        )
    for row, q in zip(rows, benjamini_hochberg([row["p_value"] for row in rows])):
        row["q_value"] = q
    rows.sort(key=lambda r: (r["q_value"], r["p_value"], r["term"]))
    return {
        "method": "one-sided hypergeometric overrepresentation; Benjamini-Hochberg across all testable terms",
        "tested_terms": len(rows),
        "background_size": len(universe),
        "selected_size": len(query),
        "results": [r for r in rows if r["overlap_count"] > 0][:500],
        "significant_count": sum(r["q_value"] <= threshold for r in rows),
        "threshold": threshold,
    }


def parse_matrix(text: str) -> tuple[list[str], list[str], np.ndarray]:
    reader = csv.reader(io.StringIO(text.lstrip("\ufeff")))
    try:
        header = next(reader)
    except StopIteration:
        raise ValueError("Matrix CSV is empty.")
    columns = [s.strip() for s in header[1:]]
    if not columns or any(not c for c in columns) or len(set(columns)) != len(columns):
        raise ValueError("Matrix column labels must be nonempty and unique.")
    labels = []
    values = []
    seen = set()
    for line, row in enumerate(reader, 2):
        if not row or all(not x.strip() for x in row):
            continue
        if len(row) != len(header):
            raise ValueError(f"Matrix row {line} has the wrong number of columns.")
        label = row[0].strip()
        if not label or label in seen:
            raise ValueError(f"Duplicate or empty row label at row {line}.")
        try:
            numeric = [float(x) for x in row[1:]]
        except ValueError:
            raise ValueError(f"Matrix row {line} contains missing or nonnumeric cells.")
        if not all(math.isfinite(x) for x in numeric):
            raise ValueError(f"Matrix row {line} contains nonfinite values.")
        labels.append(label)
        seen.add(label)
        values.append(numeric)
        if len(values) * len(columns) > 250000:
            raise ValueError("Matrix exceeds 250,000 cells; reduce the input size.")
    if not labels:
        raise ValueError("Matrix has no data rows.")
    return labels, columns, np.asarray(values, dtype=float)


def factorize(
    x: np.ndarray, components: int, iterations: int = 500, seed: int = 46
) -> tuple[np.ndarray, np.ndarray, dict]:
    if np.any(x < 0):
        raise ValueError(
            "NMF requires nonnegative values. Use a nonnegative evidence-strength matrix; signed effects belong in associations.csv."
        )
    if not np.any(x > 0):
        raise ValueError("NMF requires at least one positive value.")
    if not 1 <= components <= min(x.shape):
        raise ValueError(
            "Component count must be between 1 and the smaller matrix dimension."
        )
    rng = np.random.default_rng(seed)
    scale = float(np.max(x))
    scaled = x / scale
    w = rng.uniform(0.1, 1, (x.shape[0], components))
    h = rng.uniform(0.1, 1, (components, x.shape[1]))
    baseline = float(np.linalg.norm(scaled))
    previous = math.inf
    converged = False
    history = []
    for i in range(iterations):
        h *= (w.T @ scaled) / np.maximum(w.T @ w @ h, 1e-12)
        w *= (scaled @ h.T) / np.maximum(w @ h @ h.T, 1e-12)
        if i % 10 == 0 or i == iterations - 1:
            error = float(np.linalg.norm(scaled - w @ h))
            history.append({"iteration": i + 1, "relative_error": error / baseline})
            if math.isfinite(previous) and abs(previous - error) <= 1e-6 * max(
                previous, 1e-12
            ):
                converged = True
                break
            previous = error
    # Unit-sum W columns make component weights comparable within this run.
    norms = np.maximum(w.sum(axis=0), 1e-12)
    w /= norms
    h *= norms[:, None] * scale
    return (
        w,
        h,
        {
            "method": "NMF multiplicative updates, Frobenius objective (not Bayesian NMF)",
            "seed": seed,
            "iterations": i + 1,
            "converged": converged,
            "relative_error": float(np.linalg.norm(x - w @ h) / np.linalg.norm(x)),
            "history": history,
        },
    )


def parse_associations(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not {"gene", "phenotype", "beta"} <= set(
        reader.fieldnames
    ):
        raise ValueError(
            "Associations CSV needs gene,phenotype,beta and z or stdErr; optional pValue."
        )
    rows = []
    seen = set()
    for line, row in enumerate(reader, 2):
        gene = row["gene"].strip().upper()
        phenotype = row["phenotype"].strip()
        key = (gene, phenotype)
        if not gene or not phenotype or key in seen:
            raise ValueError(f"Duplicate or empty gene–phenotype pair at row {line}.")
        try:
            beta = float(row["beta"])
            z = (
                float(row["z"])
                if row.get("z", "").strip()
                else beta / float(row["stdErr"])
            )
            se = float(row["stdErr"]) if row.get("stdErr", "").strip() else None
            pv = float(row["pValue"]) if row.get("pValue", "").strip() else None
        except (ValueError, KeyError, ZeroDivisionError):
            raise ValueError(f"Invalid effect or standard error at row {line}.")
        if (
            not math.isfinite(beta)
            or not math.isfinite(z)
            or (se is not None and (not math.isfinite(se) or se <= 0))
            or (pv is not None and (not math.isfinite(pv) or not 0 <= pv <= 1))
        ):
            raise ValueError(
                f"Nonfinite statistics or invalid pValue/stdErr at row {line}."
            )
        if se is not None and not math.isclose(
            z, beta / se, rel_tol=0.05, abs_tol=0.05
        ):
            raise ValueError(f"z conflicts with beta/stdErr at row {line}.")
        seen.add(key)
        rows.append(
            {
                "gene": gene,
                "phenotype": phenotype,
                "beta": beta,
                "z": z,
                "p_value": pv,
                "direction": "positive association"
                if beta > 0
                else "negative association"
                if beta < 0
                else "zero association",
            }
        )
        if len(rows) > 100000:
            raise ValueError("At most 100,000 association rows are supported.")
    return rows


def bayesian_factorize(
    x: np.ndarray, components: int, iterations: int = 500, seed: int = 46
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Gaussian likelihood + exponential factor priors; truncated-normal Gibbs updates.

    Noise precision has Gamma(shape=1, rate=1) prior. X is scaled by its maximum;
    exponential rates are fixed at one on that scale. This is an explicit model,
    not posterior validation of client-provided factors or clinical mechanisms.
    """
    from scipy.stats import truncnorm
    from scipy.optimize import linear_sum_assignment

    if x.size > 20000 or components > 10:
        raise ValueError(
            "Bayesian sampling supports at most 20,000 input cells and 10 components."
        )
    if iterations < 100:
        raise ValueError("Bayesian sampling needs at least 100 iterations.")
    if np.any(x < 0) or not np.any(x > 0):
        raise ValueError("Bayesian NMF requires a nonnegative, nonzero matrix.")
    scale = float(x.max())
    y = x / scale
    rng = np.random.default_rng(seed)
    w, h, _ = factorize(y, components, 100, seed)
    # Balance factor scales for initialization; the sampler itself imposes no norm constraint.
    balance = np.sqrt(
        np.maximum(h.sum(axis=1), 1e-12) / np.maximum(w.sum(axis=0), 1e-12)
    )
    w *= balance
    h /= balance[:, None]
    template = h / np.maximum(np.linalg.norm(h, axis=1, keepdims=True), 1e-12)
    tau = 1.0
    burn = iterations // 2
    thin = max(1, (iterations - burn) // 100)
    ws = []
    hs = []
    trace = []
    prediction = np.zeros_like(y)
    for i in range(iterations):
        for k in range(components):
            residual = y - w @ h + w[:, k, None] * h[k, None, :]
            denom = max(float(h[k] @ h[k]), 1e-12)
            mean = (residual @ h[k] - 1 / tau) / denom
            sd = 1 / math.sqrt(tau * denom)
            w[:, k] = truncnorm.rvs(
                -mean / sd, np.inf, loc=mean, scale=sd, random_state=rng
            )
            residual = y - w @ h + w[:, k, None] * h[k, None, :]
            denom = max(float(w[:, k] @ w[:, k]), 1e-12)
            mean = (w[:, k] @ residual - 1 / tau) / denom
            sd = 1 / math.sqrt(tau * denom)
            h[k] = truncnorm.rvs(
                -mean / sd, np.inf, loc=mean, scale=sd, random_state=rng
            )
        residual = y - w @ h
        tau = float(rng.gamma(1 + y.size / 2, 1 / (1 + float(np.sum(residual**2)) / 2)))
        if i >= burn and (i - burn) % thin == 0:
            # Resolve component permutations against initial trait profiles before averaging.
            normalized = h / np.maximum(np.linalg.norm(h, axis=1, keepdims=True), 1e-12)
            targets, indices = linear_sum_assignment(-(template @ normalized.T))
            order = indices[np.argsort(targets)]
            wc = w[:, order].copy()
            hc = h[order].copy()
            norms = np.maximum(wc.sum(axis=0), 1e-12)
            wc /= norms
            hc *= norms[:, None] * scale
            ws.append(wc)
            hs.append(hc)
            prediction += wc @ hc
            trace.append(tau)
    wa = np.stack(ws)
    ha = np.stack(hs)
    meanw = wa.mean(axis=0)
    meanh = ha.mean(axis=0)
    return (
        meanw,
        meanh,
        {
            "method": "Bayesian NMF: Gaussian likelihood, exponential(rate=1) factor priors, Gamma(1,1) precision prior, truncated-normal Gibbs sampling",
            "reference": "https://mlg.eng.cam.ac.uk/pub/pdf/SchWinHan09.pdf",
            "seed": seed,
            "iterations": iterations,
            "burn_in": burn,
            "thinning": thin,
            "posterior_draws": len(ws),
            "input_scale": scale,
            "relative_error": float(
                np.linalg.norm(x - prediction / len(ws)) / np.linalg.norm(x)
            ),
            "posterior_w_low": np.quantile(wa, 0.025, axis=0).tolist(),
            "posterior_w_high": np.quantile(wa, 0.975, axis=0).tolist(),
            "posterior_h_low": np.quantile(ha, 0.025, axis=0).tolist(),
            "posterior_h_high": np.quantile(ha, 0.975, axis=0).tolist(),
            "noise_precision_trace": trace,
            "convergence_assessed": False,
            "uncertainty_note": "Single-chain marginal credible intervals after factor normalization/permutation alignment. Not a convergence guarantee; inspect traces and run independent seeds.",
        },
    )
