
# Second Wave Screener (Saatlik Sakin, Günlük Pozitif)
**Amaç:** Son 24 saati pozitif ama son 1 saati henüz patlamamış coinleri bulup Telegram'a bildirmek.

## 1) Bu dosyaları GitHub'a yükle
- Yeni bir repo aç: `second-wave-screener`
- Bu klasörü ZIP'ten çıkar, içerikleri GitHub'da **Add file → Upload files** ile yükle.
- ÖNEMLİ: `.github/workflows/screener.yml` dosyası bu dizin yapısında olmalı.

## 2) Secrets (ENV) tanımla
Repo → **Settings → Secrets and variables → Actions → New repository secret**
Aşağıdakileri ekle:
- `BOT_TOKEN` → Telegram bot token
- `CHAT_ID`   → Telegram chat id
- `COIN_IDS`  → CoinGecko **id** listesi (symbol değil). Örnek:
  ```
  bitcoin,ethereum,sui,aptos,ethena,aster-2,hedera-hashgraph,ondo-finance,internet-computer,maga,dogecoin,chainlink,stellar,avalanche-2,cosmos,algorand,worldcoin-wld,celestia,ordinals,polkadot,binancecoin,litecoin,shiba-inu,injective
  ```
- (Opsiyonel)
  - `H24_MIN` (varsayılan `0.0`)
  - `H1_MIN`  (varsayılan `-0.5`)
  - `H1_MAX`  (varsayılan `1.0`)
  - `TOPK`    (varsayılan `8`)

**CoinGecko ID nasıl bulunur?** CoinGecko'da coin sayfasına gir → URL'deki `/coins/<id>` kısmındaki `<id>` değerini kullan.

## 3) Çalıştır
- GitHub **Actions** sekmesi → `Second Wave Screener` → **Run workflow**.
- Telegram'ına mesaj gelmeli.
- Otomatik: Her saat :07'de.

## 4) Tuning
- Aday azsa: `H1_MAX`=1.2 yap, `H24_MIN`=0.0 bırak.
- Aday çoksa: `H24_MIN`=2–3 yap, `H1_MIN`'i yükselt.
- Likidite için mikro cap'leri `COIN_IDS`'ten çıkar.
