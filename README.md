
# Second Wave Screener — Sinyalli Sürüm
- 24h pozitif + 1h sakin coinleri listeler (İkinci Dalga).
- Pullback (24h pozitif, 1h negatif) listesini de verir.
- Likidite filtresi (VOL24_MIN), akıllı skor ve BUY/WATCH etiketleri.
- SL/TP oranları bilgi amaçlı mesajda görüntülenir.

## Kurulum
1) Bu klasörü GitHub repona yükle (zipten çıkar → Upload files).
2) Secrets (BOT_TOKEN, CHAT_ID, COIN_IDS zorunlu; diğerleri opsiyonel).
3) Actions → Second Wave Screener → Run workflow.

## Önerilen Dengeli Ayarlar
VOL24_MIN=200000000
H24_MIN=2.0
H1_MIN=-0.5
H1_MAX=1.0
TOPK=6
PB_H24_MIN=0.0
PB_H1_MIN=-1.2
PB_H1_MAX=-0.05
ENTRY_SW_MIN=0.20
PB_STABLE_BAND=0.20
SL_PCT=1.2
TP_PCT=2.0
