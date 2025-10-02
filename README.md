
# Second Wave Screener (Akıllı Sürüm)
- 24h pozitif + 1h sakin coinleri bulur (ikinci dalga).
- Ayrı bir pullback listesi verir (24h pozitif, 1h negatif).
- Likidite filtresi: VOL24_MIN (default 200M USD).
- Skor: `0.6*24h - 0.3*|1h| + 0.1*log10(Vol24h)`.

## Kurulum (özet)
1) Bu klasörü GitHub repona yükle (zipten çıkar → Upload files).
2) Secrets: BOT_TOKEN, CHAT_ID, COIN_IDS (+opsiyonel eşikler).
3) Actions → Second Wave Screener → Run workflow.
