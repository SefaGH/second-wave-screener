
import os, time, math
import requests
import pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
COIN_IDS  = os.getenv("COIN_IDS", "").strip()

def _get_float(name, default):
    v = (os.getenv(name, "") or "").strip()
    try:
        return float(v) if v != "" else default
    except ValueError:
        return default

def _get_int(name, default):
    v = (os.getenv(name, "") or "").strip()
    try:
        return int(v) if v != "" else default
    except ValueError:
        return default

# —— EŞİKLER (opsiyonel; boşsa default) ————————————————
H24_MIN   = _get_float("H24_MIN", 2.0)           # 24h min %
H1_MIN    = _get_float("H1_MIN", -0.5)           # 1h alt sınır (SW)
H1_MAX    = _get_float("H1_MAX",  1.0)           # 1h üst sınır (SW)
TOPK      = _get_int  ("TOPK",     6)            # aday sayısı
VOL24_MIN = _get_float("VOL24_MIN", 200_000_000) # min. 24h hacim (USD)

PB_H24_MIN = _get_float("PB_H24_MIN", 0.0)       # Pullback 24h min
PB_H1_MIN  = _get_float("PB_H1_MIN", -1.2)       # Pullback 1h alt
PB_H1_MAX  = _get_float("PB_H1_MAX", -0.05)      # Pullback 1h üst

# —— SİNYAL AYARLARI ———————————————————————————————————————
ENTRY_SW_MIN     = _get_float("ENTRY_SW_MIN", 0.20)  # SW BUY-NOW eşiği (1h %)
PB_STABLE_BAND   = _get_float("PB_STABLE_BAND", 0.20) # Pullback stabilize bandı (±%)
SL_PCT           = _get_float("SL_PCT", 1.2)     # mesaj amaçlı bilgilendirme
TP_PCT           = _get_float("TP_PCT", 2.0)     # mesaj amaçlı bilgilendirme

assert BOT_TOKEN and CHAT_ID, "BOT_TOKEN/CHAT_ID yok (Secrets kısmına ekleyin)."
assert COIN_IDS, "COIN_IDS boş (CoinGecko id listesi)."

TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
HEADERS = {"Accept": "application/json","User-Agent": "second-wave-screener/1.3-signal (+github-actions)"}

def cg_markets(ids_csv: str) -> pd.DataFrame:
    ids = [x.strip() for x in ids_csv.split(",") if x.strip()]
    out = []
    for i in range(0, len(ids), 200):
        chunk = ",".join(ids[i:i+200])
        for attempt in range(5):
            try:
                r = requests.get(
                    "https://api.coingecko.com/api/v3/coins/markets",
                    headers=HEADERS,
                    params={"vs_currency":"usd","ids":chunk,"price_change_percentage":"1h,24h"},
                    timeout=20
                )
                if r.status_code == 429:
                    time.sleep(2**attempt)
                    continue
                r.raise_for_status()
                out.extend(r.json())
                break
            except requests.RequestException:
                time.sleep(2**attempt)
    return pd.DataFrame(out)

def _clean(df: pd.DataFrame) -> pd.DataFrame:
    need = {
        "id","symbol","current_price",
        "price_change_percentage_1h_in_currency",
        "price_change_percentage_24h_in_currency",
        "total_volume"
    }
    miss = need - set(df.columns)
    if miss:
        raise RuntimeError(f"Eksik kolonlar: {miss}")
    df = df.copy().fillna(0)
    df = df[df["total_volume"] >= VOL24_MIN]  # likidite filtresi
    return df

def _score(df: pd.DataFrame) -> pd.DataFrame:
    s24 = df["price_change_percentage_24h_in_currency"]
    s1  = df["price_change_percentage_1h_in_currency"].abs()
    vol = df["total_volume"].clip(lower=1)
    score = 0.6*s24 - 0.3*s1 + 0.1*vol.apply(lambda x: math.log10(x))
    df = df.copy()
    df["score"] = score
    return df

def pick_second_wave(df: pd.DataFrame) -> pd.DataFrame:
    f = (
        (df["price_change_percentage_24h_in_currency"] >= H24_MIN) &
        (df["price_change_percentage_1h_in_currency"] >= H1_MIN) &
        (df["price_change_percentage_1h_in_currency"] <= H1_MAX)
    )
    c = _score(df.loc[f])
    return c.sort_values(["score","price_change_percentage_24h_in_currency","total_volume"], ascending=False).head(TOPK)

def pick_pullback(df: pd.DataFrame) -> pd.DataFrame:
    f = (
        (df["price_change_percentage_24h_in_currency"] >= PB_H24_MIN) &
        (df["price_change_percentage_1h_in_currency"] >= PB_H1_MIN) &
        (df["price_change_percentage_1h_in_currency"] <= PB_H1_MAX)
    )
    c = _score(df.loc[f])
    return c.sort_values(["score","price_change_percentage_24h_in_currency","total_volume"], ascending=False).head(TOPK)

def _line(r) -> str:
    h1  = r["price_change_percentage_1h_in_currency"]
    h24 = r["price_change_percentage_24h_in_currency"]
    p   = r["current_price"]
    v   = r["total_volume"]
    sc  = r.get("score", 0.0)
    return f"- {r['symbol'].upper():<6} | 24h {h24:+.2f}% | 1h {h1:+.2f}% | ${p:,.4f} | Vol24h ${v:,.0f} | score {sc:.2f}"

def _signal_sw(h1):
    if h1 >= ENTRY_SW_MIN:
        return "BUY-NOW (SW)"
    if h1 >= H1_MIN and h1 < ENTRY_SW_MIN:
        return "WATCH (SW)"
    return ""

def _signal_pb(h1):
    if -PB_STABLE_BAND <= h1 <= PB_STABLE_BAND:
        return "BUY-PB"
    if PB_H1_MIN <= h1 <= PB_H1_MAX:
        return "WATCH-PB"
    return ""

def build_message(df, sw, pb) -> str:
    parts = []
    parts.append(f"📊 Second Wave Screener — Sinyalli Sürüm
Eşikler: 24h≥{H24_MIN}%, 1h∈[{H1_MIN},{H1_MAX}] | PB 1h∈[{PB_H1_MIN},{PB_H1_MAX}] | VOL24_MIN=${VOL24_MIN:,.0f} | TOPK={TOPK}
Sinyal: BUY-NOW (SW) ≥ +{ENTRY_SW_MIN:.2f}% | BUY-PB band ±{PB_STABLE_BAND:.2f}% | SL {SL_PCT:.1f}% / TP {TP_PCT:.1f}%")
    if not sw.empty:
        parts.append("
🔥 İkinci Dalga Adayları:")
        for _, r in sw.iterrows():
            h1 = r["price_change_percentage_1h_in_currency"]
            sig = _signal_sw(h1)
            line = _line(r)
            if sig:
                line = line + f"  ← {sig}"
            parts.append(line)
    else:
        parts.append("
🔥 İkinci Dalga Adayları: (yok)")
    if not pb.empty:
        parts.append("
🔁 Pullback Adayları:")
        for _, r in pb.iterrows():
            h1 = r["price_change_percentage_1h_in_currency"]
            sig = _signal_pb(h1)
            line = _line(r)
            if sig:
                line = line + f"  ← {sig}"
            parts.append(line)
    else:
        parts.append("
🔁 Pullback Adayları: (yok)")
    return "
".join(parts)[:3900]

def send_tg(text: str):
    try:
        requests.post(TG_URL, json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=20)
    except requests.RequestException:
        pass

def main():
    df = cg_markets(COIN_IDS)
    if df.empty:
        send_tg("⚠️ Screener: CoinGecko verisi boş geldi. COIN_IDS/Rate limit kontrol edin.")
        return
    df = _clean(df)
    sw = pick_second_wave(df)
    pb = pick_pullback(df)
    send_tg(build_message(df, sw, pb))

if __name__ == "__main__":
    main()
