import re


def _parse_trade_cmd(text: str):
    t = (text or "").strip()
    if not (t.lower().startswith("/buy") or t.lower().startswith("/sell") or t.lower().startswith("/close")):
        raise ValueError("ожидалась команда /buy или /sell или /close")
    parts = t.split(None, 1)
    action = parts[0][1:].lower()  # buy|sell|close
    body = parts[1] if len(parts) > 1 else ""
    tf = "15m"

    tfm = re.search(r"\btf\s*=\s*([0-9]+[mhd])\b", body, flags=re.I)
    if tfm:
        tf = tfm.group(1)

    price = None
    pm = re.search(r"@\s*([0-9]+(?:\.[0-9]+)?)", body)
    if pm:
        price = float(pm.group(1))
        body = re.sub(r"@\s*([0-9]+(?:\.[0-9]+)?)", "", body)

    body = re.sub(r"\btf\s*=\s*[0-9]+[mhd]", "", body).strip()
    toks = [x for x in re.split(r"\s+", body) if x]

    if action in ("buy", "sell"):
        if len(toks) < 3:
            raise ValueError("нужно минимум: /buy|/sell EX SYMBOL QTY [@ PRICE] [tf=...]")
        ex = toks[0].lower()
        sym = toks[1].upper()
        qty = float(toks[2])
        return action, ex, sym, qty, price, tf

    if action == "close":
        if len(toks) < 2:
            raise ValueError("нужно минимум: /close EX SYMBOL [QTY] [@ PRICE] [tf=...]")
        ex = toks[0].lower()
        sym = toks[1].upper()
        q = None
        if len(toks) >= 3:
            try:
                q = float(toks[2])
            except Exception:
                q = None
        return action, ex, sym, q, price, tf

    raise ValueError("unknown action")
