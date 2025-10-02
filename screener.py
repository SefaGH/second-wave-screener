
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

# —— EŞİKLER (hepsi opsiyonel; boşsa default) ————————————————
H24_MIN   = _get_float("H24_MIN", 0.0)            # 24h en az %
H1_MIN    = _get_float("H1_MIN", -0.5)            # 1h alt sınır (ikinci dalga)
H1_MAX    = _get_float("H1_MAX",  1.0)            # 1h üst sınır (ikinci dalga)
TOPK      = _get_int  ("TOPK",     8)             # aday sayısı
VOL24_MIN = _get_float("VOL24_MIN", 200_000_000)  # min. 24h hacim (USD)

# Pullback için ayrı aralık (opsiyonel)
PB_H24_MIN = _get_float("PB_H24_MIN", 0.0)
PB_H1_MIN  = _get_float("PB_H1_MIN", -1.5)
PB_H1_MAX  = _get_float("PB_H1_MAX", -0.05)

assert BOT_TOKEN and CHAT_ID, "BOT_TOKEN/CHAT_ID yok (Secrets kısmına ekleyin)."
assert COIN_IDS, "COIN_IDS boş (CoinGecko id listesi)."

TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
HEADERS = {"Accept": "application/json","User-Agent": "second-wave-screener/1.2 (+github-actions)"}

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

def base_clean(df: pd.DataFrame) -> pd.DataFrame:
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
    # likidite filtresi
    df = df[df["total_volume"] >= VOL24_MIN]
    return df

def add_score(df: pd.DataFrame) -> pd.DataFrame:
    s24 = df["price_change_percentage_24h_in_currency"]
    s1  = df["price_change_percentage_1h_in_currency"].abs()
    vol = df["total_volume"].clip(lower=1)
    score = 0.6*s24 - 0.3*s1 + 0.1*vol.apply(lambda x: math.log10(x))
    df = df.copy()
    df["score"] = score
    return df

def pick_second_wave(df: pd.DataFrame) -> pd.DataFrame:
    filt = (
        (df["price_change_percentage_24h_in_currency"] > H24_MIN) &
        (df["price_change_percentage_1h_in_currency"] >= H1_MIN) &
        (df["price_change_percentage_1h_in_currency"] <= H1_MAX)
    )
    c = df.loc[filt]
    c = add_score(c).sort_values(["score","price_change_percentage_24h_in_currency","total_volume"], ascending=False)
    return c.head(TOPK)

def pick_pullback(df: pd.DataFrame) -> pd.DataFrame:
    filt = (
        (df["price_change_percentage_24h_in_currency"] > PB_H24_MIN) &
        (df["price_change_percentage_1h_in_currency"] >= PB_H1_MIN) &
        (df["price_change_percentage_1h_in_currency"] <= PB_H1_MAX)
    )
    c = df.loc[filt]
    c = add_score(c).sort_values(["score","price_change_percentage_24h_in_currency","total_volume"], ascending=False)
    return c.head(TOPK)

def _row(r) -> str:
    h1  = r["price_change_percentage_1h_in_currency"]
    h24 = r["price_change_percentage_24h_in_currency"]
    p   = r["current_price"]
    v   = r["total_volume"]
    sc  = r.get("score", 0.0)
    return f"- {r['symbol'].upper():<6} | 24h {h24:+.2f}% | 1h {h1:+.2f}% | ${p:,.4f} | Vol24h ${v:,.0f} | score {sc:.2f}"

def build_message(df, sw, pb) -> str:
    parts = []
    parts.append("📊 Second Wave Screener (24h pozitif, 1h sakin — likidite filtresi açık)")
    if not sw.empty:
        parts.append("\n🔥 İkinci Dalga Adayları:")
        parts.extend(_row(r) for _, r in sw.iterrows())
    else:
        parts.append("\n🔥 İkinci Dalga Adayları: (yok)")

    if not pb.empty:
        parts.append("\n🔁 Pullback Adayları:")
        parts.extend(_row(r) for _, r in pb.iterrows())
    else:
        parts.append("\n🔁 Pullback Adayları: (yok)")

    parts.append(f"\nTaranan: {df.shape[0]} | Eşikler: 24h>{H24_MIN}%, 1h∈[{H1_MIN},{H1_MAX}] | PB 1h∈[{PB_H1_MIN},{PB_H1_MAX}] | VOL24_MIN=${VOL24_MIN:,.0f} | TOPK={TOPK}")
    return "\n".join(parts)[:3900]

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
    df = base_clean(df)
    sw = pick_second_wave(df)
    pb = pick_pullback(df)
    send_tg(build_message(df, sw, pb))

if __name__ == "__main__":
    main()
