
import os, time
import requests
import pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID   = os.getenv("CHAT_ID")
COIN_IDS  = os.getenv("COIN_IDS", "").strip()

def get_float_env(name, default):
    val = os.getenv(name, "")
    if val is None:
        return default
    val = val.strip()
    if val == "":
        return default
    try:
        return float(val)
    except ValueError:
        return default

def get_int_env(name, default):
    val = os.getenv(name, "")
    if val is None:
        return default
    val = val.strip()
    if val == "":
        return default
    try:
        return int(val)
    except ValueError:
        return default

# Eşikler (Secrets/Variables boş olsa da defaulta düşecek)
H24_MIN = get_float_env("H24_MIN", 0.0)   # 24h en az % (pozitif trend)
H1_MIN  = get_float_env("H1_MIN", -0.5)   # 1h alt sınır
H1_MAX  = get_float_env("H1_MAX", 1.0)    # 1h üst sınır
TOPK    = get_int_env("TOPK", 8)          # kaç adayı bildir

assert BOT_TOKEN and CHAT_ID, "BOT_TOKEN/CHAT_ID yok (GitHub Secrets'a ekleyin)."
assert COIN_IDS, "COIN_IDS boş (GitHub Secrets'a CoinGecko id listesi ekleyin)."

TG_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
HEADERS = {"Accept": "application/json","User-Agent": "second-wave-screener/1.0 (+github-actions)"}

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

def pick_candidates(df: pd.DataFrame) -> pd.DataFrame:
    need = {"id","symbol","current_price","price_change_percentage_1h_in_currency","price_change_percentage_24h_in_currency","total_volume"}
    missing = need - set(df.columns)
    if missing:
        raise RuntimeError(f"Eksik kolonlar: {missing}")
    df = df.copy().fillna(0)
    filt = (
        (df["price_change_percentage_24h_in_currency"] > H24_MIN) &
        (df["price_change_percentage_1h_in_currency"] >= H1_MIN) &
        (df["price_change_percentage_1h_in_currency"] <= H1_MAX)
    )
    cand = df.loc[filt].copy()
    cand = cand.sort_values(by=["price_change_percentage_24h_in_currency","total_volume"], ascending=[False, False])
    return cand.head(TOPK)

def fmt_row(r) -> str:
    return f"- {r['symbol'].upper():<6} | 24h {r['price_change_percentage_24h_in_currency']:+.2f}% | 1h {r['price_change_percentage_1h_in_currency']:+.2f}% | ${r['current_price']:,.4f} | Vol24h ${r['total_volume']:,.0f}"

def build_message(cand_df: pd.DataFrame, all_count: int) -> str:
    if cand_df.empty:
        body = "Uygun aday bulunamadı (filtrelere takıldı). Eşikleri (H24_MIN, H1_MIN, H1_MAX) gevşetmeyi deneyin."
    else:
        lines = [fmt_row(r) for _, r in cand_df.iterrows()]
        body = "\n".join(lines)
    hdr = "📊 Second Wave Screener (24h pozitif, 1h sakin)\n"
    meta = f"\nTaranan: {all_count} | Eşikler: 24h>{H24_MIN}%, 1h∈[{H1_MIN},{H1_MAX}] | TOPK={TOPK}"
    return hdr + body + meta

def send_telegram(text: str):
    try:
        requests.post(TG_URL, json={"chat_id": CHAT_ID, "text": text, "disable_web_page_preview": True}, timeout=20)
    except requests.RequestException:
        pass

def main():
    df = cg_markets(COIN_IDS)
    if df.empty:
        send_telegram("⚠️ Screener: CoinGecko verisi boş geldi. COIN_IDS/Rate limit kontrol edin.")
        return
    cand = pick_candidates(df)
    msg = build_message(cand, all_count=df.shape[0])
    if len(msg) > 3900:
        msg = msg[:3900] + "\n…(kısaltıldı)"
    send_telegram(msg)

if __name__ == "__main__":
    main()
