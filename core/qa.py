"""Czyste reguły oceny raportu QA po impozycji."""


def evaluate_qa_metrics(ssim, mismatch_percent, mean_delta_e=None, *, min_ssim=0.98, max_mismatch=2.0, max_delta_e=5.0):
    """Ocena QA wraz z powodami odrzucenia, niezależna od OpenCV i Streamlit."""
    metrics = {
        "ssim": float(ssim),
        "mismatch_percent": float(mismatch_percent),
        "mean_delta_e": None if mean_delta_e is None else float(mean_delta_e),
    }
    reasons = []
    if metrics["ssim"] < float(min_ssim):
        reasons.append(f"SSIM {metrics['ssim']:.4f} jest poniżej progu {float(min_ssim):.4f}.")
    if metrics["mismatch_percent"] > float(max_mismatch):
        reasons.append(f"Różnice pikselowe {metrics['mismatch_percent']:.2f}% przekraczają limit {float(max_mismatch):.2f}%.")
    if metrics["mean_delta_e"] is not None and metrics["mean_delta_e"] > float(max_delta_e):
        reasons.append(f"Średnia Delta E {metrics['mean_delta_e']:.2f} przekracza limit {float(max_delta_e):.2f}.")
    return {"status": "ZATWIERDZONE" if not reasons else "DO SPRAWDZENIA", "reasons": reasons, **metrics}


def parse_ignored_regions(value):
    """Czyta maski `x,y,szer,wys; ...`, zwracając poprawne i błędne wpisy."""
    regions, invalid = [], []
    for raw in str(value or "").split(";"):
        if not raw.strip():
            continue
        try:
            x, y, width, height = [int(part.strip()) for part in raw.split(",")]
            if width < 0 or height < 0:
                raise ValueError
            regions.append((x, y, width, height))
        except ValueError:
            invalid.append(raw.strip())
    return regions, invalid
