# Sistem Alert Otomatis Keterbukaan Informasi Aksi Korporasi IDX

Implementasi sesuai [prd.md](prd.md). Memantau pengumuman resmi IDX, menyaring 5 kategori
aksi korporasi, dan mengirim alert ke Telegram dalam hitungan detik. Sudah diverifikasi
end-to-end terhadap endpoint IDX asli dan berhasil mengirim alert nyata ke Telegram.

## Struktur

```
idx_alert/
  config.py        # loader .env + config/keywords.yaml
  models.py         # Announcement, MatchedAnnouncement
  filter.py         # keyword matching -> kategori (prioritas sesuai urutan di keywords.yaml)
  dedup.py           # SQLite dedup
  poller.py          # fetch GetAnnouncement via cloudscraper, 1 request per kategori/siklus
  notifier.py         # kirim alert ke Telegram, retry/backoff
  market_hours.py     # status jam bursa, jadwal pre-open check
  pipeline.py         # fetch -> filter -> dedup -> notify
  logger.py
config/keywords.yaml  # daftar keyword per kategori (mudah ditambah)
deploy/*.service       # systemd unit
main.py                # entrypoint loop utama
```

## Sumber data

Endpoint resmi (tersembunyi, tidak didokumentasikan publik oleh IDX):

```
GET https://www.idx.co.id/primary/ListedCompany/GetAnnouncement
```

Params: `kodeEmiten`, `emitenType=*`, `indexFrom`, `pageSize`, `dateFrom`/`dateTo` (format
`YYYYMMDD`), `lang=id`, `keyword`. Endpoint ini dilindungi **Cloudflare Managed Challenge**
— request dengan `requests` biasa akan mendapat HTTP 403 (halaman "Just a moment..."), jadi
poller wajib pakai `cloudscraper` (lihat `idx_alert/poller.py`) yang meniru browser asli
untuk lolos challenge.

Karena endpoint hanya menerima satu `keyword` per request, satu siklus polling melakukan
5 request berurutan (satu per kategori di `config/keywords.yaml`, pakai keyword pertama tiap
kategori sebagai representasi), lalu hasilnya digabung dan dedup sebelum diproses filter
(PRD bagian 3-4).

## Setup

```bash
python -m venv venv
source venv/bin/activate   # atau venv\Scripts\activate di Windows
pip install -r requirements.txt
cp .env.example .env
```

Isi `.env`: token bot Telegram dan chat ID. Endpoint IDX sudah hardcoded di `poller.py`
karena sudah terverifikasi stabil — tidak perlu dikonfigurasi lewat env var.

### Uji cepat poller tanpa menjalankan seluruh sistem

```bash
python -c "
from idx_alert.config import load_settings
from idx_alert.logger import setup_logger
from idx_alert.poller import fetch_announcements

settings = load_settings()
logger = setup_logger(settings.log_file_path)
for a in fetch_announcements(settings, logger)[:5]:
    print(a)
"
```

## Menjalankan lokal

```bash
python main.py
```

- Selama jam bursa (default 08:45–16:15 WIB, Senin–Jumat): polling tiap `POLL_INTERVAL_SECONDS`.
- Di luar jam bursa: proses idle, hanya menjalankan satu kali **pre-open catch-up check**
  di sekitar `PRE_OPEN_CHECK_TIME` (default 08:30 WIB) untuk menangkap pengumuman yang
  terbit sejak market close hari sebelumnya, sehingga tetap ada alert sebelum bursa buka.

## Menambah kategori/keyword baru

Edit `config/keywords.yaml`, tidak perlu ubah kode. Urutan kategori dalam file menentukan
prioritas jika satu subject cocok dengan lebih dari satu kategori. Catatan: hanya keyword
**pertama** tiap kategori yang dipakai sebagai query ke endpoint IDX (lihat `poller.py`);
keyword lain dalam kategori tetap dipakai saat pencocokan kategori final di `filter.py`.

## Deploy ke VM GCP (systemd)

```bash
sudo mkdir -p /opt/idx-corpaction
sudo cp -r . /opt/idx-corpaction
cd /opt/idx-corpaction
python3 -m venv venv && venv/bin/pip install -r requirements.txt
sudo cp deploy/idx-corpaction-alert.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now idx-corpaction-alert
sudo journalctl -u idx-corpaction-alert -f
```

Service ini berjalan independen dari bot broksum yang sudah ada di VM yang sama (proses
dan schedule terpisah, sesuai PRD bagian 8).

## Catatan penggunaan

Syarat penggunaan resmi PT Bursa Efek Indonesia melarang redistribusi data dari website
untuk tujuan komersial tanpa izin tertulis. Sistem ini untuk pemakaian personal sebagai
alat bantu keputusan trading sendiri.
