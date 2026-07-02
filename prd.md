# PRD: Sistem Alert Otomatis Keterbukaan Informasi Aksi Korporasi IDX

## 1. Latar Belakang dan Tujuan

Notifikasi keterbukaan informasi terkait aksi korporasi yang berpotensi memicu spike harga saham, mulai dari right issue, private placement, stock split, dividen jumbo, hingga laporan kepemilikan insider, yang diterima lewat aplikasi broker seperti Stockbit seringkali telat dan tertumpuk dengan notifikasi lain sehingga mudah terlewat. Sistem ini dibangun untuk memantau halaman pengumuman resmi IDX secara berkala dengan interval pendek, menyaring entri yang relevan dengan kategori-kategori tersebut, dan mengirimkan alert ke Telegram dalam hitungan detik setelah pengumuman terbit di sistem BEI.

Sistem ini berjalan sebagai service terpisah dari bot screening bandarmology yang sudah ada, di VM GCP yang sama, tanpa saling mengganggu jadwal maupun resource.

## 2. Cakupan

Termasuk dalam cakupan:
- Polling berkala terhadap sumber data pengumuman resmi IDX
- Filtering berdasarkan keyword yang berkaitan dengan lima kategori aksi korporasi: right issue, private placement/PMTHMETD, stock split, dividen jumbo/spesial, dan laporan kepemilikan saham insider
- Deduplikasi supaya satu pengumuman tidak terkirim berulang
- Pengiriman alert ke Telegram dengan format yang informatif dan label berbeda per kategori
- Mekanisme retry dan backoff saat terjadi rate limit atau error jaringan
- Logging untuk keperluan monitoring dan debugging

Di luar cakupan untuk versi awal:
- Analisis lanjutan terhadap isi PDF pengumuman (misalnya ekstraksi rasio HMETD, harga pelaksanaan, besaran dividen per saham, atau nominal transaksi insider secara otomatis dari isi dokumen)
- Kategori keterbukaan informasi di luar lima kategori pada bagian 5, meskipun arsitekturnya dirancang agar mudah diperluas ke keyword lain di kemudian hari (misalnya akuisisi, buyback, kontrak material, delisting, atau perubahan kegiatan usaha)

## 3. Sumber Data

Sumber data utama adalah endpoint JSON resmi berikut, yang dikonfirmasi dari implementasi publik yang sudah berjalan (lihat referensi di bagian 12):

```
https://www.idx.co.id/primary/ListedCompany/GetAnnouncement
```

Parameter query yang digunakan:
- `kodeEmiten` — kosongkan untuk memantau seluruh emiten, atau isi kode spesifik kalau suatu saat mau dipersempit
- `emitenType` — diisi `*` untuk semua jenis emiten
- `indexFrom` — indeks awal hasil, `0` untuk mulai dari yang terbaru
- `pageSize` — jumlah hasil per request, cukup `10` sampai `20` karena tujuannya memantau entri terbaru, bukan historis
- `dateFrom` dan `dateTo` — rentang tanggal dalam format `YYYYMMDD`, untuk polling cukup set `dateFrom` ke hari ini dan `dateTo` ke hari ini juga
- `lang` — `id` untuk bahasa Indonesia
- `keyword` — keyword pencarian sesuai kategori yang sedang dipantau (lihat bagian 5)

Response berbentuk JSON dengan struktur utama berupa array `Replies`, di mana setiap elemen berisi object `pengumuman` (dengan field `JudulPengumuman` untuk subject dan `TglPengumuman` untuk tanggal terbit) serta array `attachments` (dengan field `OriginalFilename` dan `FullSavePath` untuk link dokumen PDF).

Catatan teknis penting: endpoint ini dilindungi Cloudflare bot protection, sehingga request dengan library `requests` biasa kemungkinan besar akan diblokir atau mendapat challenge page alih-alih data JSON. Implementasi harus menggunakan library `cloudscraper` (atau alternatif setara seperti `curl_cffi` dengan browser emulation) untuk melewati proteksi ini. Ini konsisten dengan pengalaman scraping broksum sebelumnya yang juga mengandalkan endpoint tersembunyi, hanya saja untuk endpoint pengumuman ini proteksinya sedikit lebih ketat.

Karena satu keyword hanya bisa dipakai per request, dan sistem ini perlu memantau lima kategori sekaligus (lihat bagian 5), polling per siklus dilakukan dengan lima request berurutan, satu per kategori, bukan satu request gabungan. Ini perlu diperhitungkan dalam desain interval polling di bagian 4 supaya total waktu lima request tidak melebihi interval yang ditentukan.

Sebagai fallback apabila endpoint utama berubah struktur atau diblokir secara persisten, sistem juga menyediakan mode scraping HTML langsung dari halaman pengumuman sebagai cadangan, meskipun mode ini lebih rawan terhadap perubahan struktur halaman.

## 4. Mekanisme Polling

Polling dilakukan setiap 30 hingga 60 detik selama jam operasional bursa, yaitu sekitar pukul 08:45 sampai 16:15 WIB, Senin sampai Jumat. Di luar jam tersebut proses berhenti otomatis untuk menghemat resource dan menghindari request yang tidak perlu.

Karena satu siklus polling terdiri dari lima request berurutan (satu per kategori keyword, lihat bagian 3), interval yang dikonfigurasi dihitung sebagai waktu antar-mulainya siklus, bukan antar-request individual. Dengan asumsi tiap request memakan waktu 1 sampai 3 detik termasuk overhead cloudscraper, lima request berurutan biasanya selesai dalam 5 sampai 15 detik, sehingga interval 30 detik tetap realistis untuk mencakup seluruh kategori tanpa tumpang tindih siklus.

Interval polling dibuat dapat dikonfigurasi lewat environment variable, dengan nilai default 30 detik. Apabila terjadi respons error atau indikasi rate limiting dari server IDX, sistem menerapkan exponential backoff, mulai dari penggandaan interval hingga batas maksimum tertentu sebelum kembali ke interval normal setelah beberapa kali percobaan berhasil.

## 5. Filtering Keyword

Setiap entri pengumuman yang diambil dicocokkan terhadap daftar keyword yang dikelompokkan ke dalam lima kategori. Setiap kategori punya label sendiri yang nantinya dipakai untuk membedakan judul alert di Telegram.

**Kategori RIGHT_ISSUE**
- Penambahan Modal
- HMETD
- PMHMETD
- Penawaran Umum Terbatas
- Rights Issue

**Kategori PRIVATE_PLACEMENT**
- Penambahan Modal Tanpa HMETD
- PMTHMETD
- Private Placement

**Kategori STOCK_SPLIT**
- Pemecahan Nilai Nominal Saham
- Stock Split
- Penggabungan Nilai Nominal Saham

**Kategori DIVIDEN**
- Pembagian Dividen
- Dividen Interim
- Dividen Spesial

**Kategori INSIDER_OWNERSHIP**
- Laporan Kepemilikan Saham
- Perubahan Kepemilikan Saham

Pencocokan dilakukan case insensitive terhadap field subject atau judul pengumuman. Kalau satu subject cocok dengan lebih dari satu kategori, sistem tetap mengirim satu alert dengan kategori yang match pertama kali berdasarkan urutan prioritas di atas, supaya tidak ada duplikasi alert untuk satu pengumuman yang sama. Seluruh daftar keyword dan pemetaannya ke kategori disimpan dalam file konfigurasi terpisah (JSON atau YAML) supaya mudah ditambah atau diubah tanpa mengubah kode inti, sehingga di masa depan bisa diperluas ke kategori lain seperti akuisisi, buyback, kontrak material, atau delisting.

## 6. Deduplikasi

Setiap pengumuman memiliki identitas unik yang dibentuk dari kombinasi kode emiten, subject, dan link dokumen, di-hash menjadi satu ID. ID ini disimpan ke database SQLite lokal setiap kali sebuah pengumuman berhasil dikirim sebagai alert. Sebelum mengirim alert baru, sistem selalu mengecek apakah ID tersebut sudah pernah ada, sehingga pengumuman yang sama tidak pernah terkirim dua kali meskipun proses polling menemukannya lagi di siklus berikutnya.

## 7. Format Alert Telegram

Format pesan dirancang agar cepat dibaca sekilas namun tetap membawa konteks yang cukup. Judul alert dan emoji menyesuaikan kategori yang match, sementara struktur badan pesan tetap konsisten di semua kategori supaya mudah dibaca sekilas:

| Kategori | Judul Alert | Emoji |
|---|---|---|
| RIGHT_ISSUE | RIGHT ISSUE ALERT | 🚨 |
| PRIVATE_PLACEMENT | PRIVATE PLACEMENT ALERT | 💰 |
| STOCK_SPLIT | STOCK SPLIT ALERT | ✂️ |
| DIVIDEN | DIVIDEN ALERT | 💵 |
| INSIDER_OWNERSHIP | INSIDER OWNERSHIP ALERT | 👤 |

Template umum:

```
[EMOJI] [JUDUL_ALERT] — [KODE_EMITEN]

Subject: [subject lengkap pengumuman]

Terbit di IDX: [tanggal, jam WIB]
Terdeteksi bot: [jam WIB] (delay ~[X] detik)

📄 Dokumen: [link PDF]

Bukan rekomendasi beli/jual. DYOR.
```

Contoh hasil jadi untuk kategori right issue:

```
🚨 RIGHT ISSUE ALERT — PEGE

Subject: Keterbukaan Informasi terkait Aksi Korporasi - Rencana Penambahan Modal dengan HMETD - 30062026

Terbit di IDX: 30 Jun 2026, 11:05 WIB
Terdeteksi bot: 11:05:42 WIB (delay ~12 detik)

📄 Dokumen: https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_EREP/202606/cdec57b527_ee07c4f5a9.pdf

Bukan rekomendasi beli/jual. DYOR.
```

Contoh hasil jadi untuk kategori insider ownership:

```
👤 INSIDER OWNERSHIP ALERT — PEGE

Subject: Laporan Kepemilikan Saham oleh Direksi/Komisaris

Terbit di IDX: 1 Jul 2026, 09:12 WIB
Terdeteksi bot: 09:12:37 WIB (delay ~15 detik)

📄 Dokumen: [link PDF]

Bukan rekomendasi beli/jual. DYOR.
```

Baris delay ditampilkan untuk transparansi seberapa cepat sistem mendeteksi pengumuman relatif terhadap waktu terbit resminya, sekaligus jadi indikator kesehatan sistem kalau delay mulai melebar dari biasanya.

## 8. Arsitektur Teknis

Sistem berjalan sebagai proses Python independen di VM GCP yang sama dengan bot broksum, dijalankan sebagai systemd service terpisah agar bisa restart otomatis kalau crash dan tidak tercampur dengan jadwal cron bot broksum yang berjalan sekali sehari pukul 18:30 WIB.

Komponen utama:
- Poller: modul yang melakukan request berkala ke endpoint IDX menggunakan `cloudscraper` untuk melewati proteksi Cloudflare
- Filter: modul pencocokan keyword terhadap hasil poller, sekaligus penentuan kategori mana yang match
- Deduplicator: modul pengecekan dan pencatatan ID pengumuman ke SQLite
- Notifier: modul pengiriman pesan ke Telegram Bot API
- Logger: pencatatan aktivitas dan error ke file log lokal untuk keperluan debugging

## 9. Penanganan Error

Kegagalan request ke endpoint IDX, baik karena timeout, perubahan struktur response, maupun pemblokiran sementara, tidak boleh menghentikan proses secara permanen. Sistem mencatat error ke log, menerapkan backoff, dan mencoba lagi di siklus berikutnya. Apabila kegagalan berturut-turut melewati ambang batas tertentu, misalnya sepuluh kali berturut-turut, sistem mengirim satu notifikasi peringatan ke Telegram admin bahwa proses pemantauan sedang bermasalah, supaya kamu tidak diam-diam kehilangan cakupan monitoring tanpa sadar.

## 10. Kebutuhan Non Fungsional

Target delay dari waktu pengumuman terbit di sistem BEI sampai alert diterima di Telegram adalah di bawah 60 detik pada kondisi normal, dengan rata-rata diharapkan sekitar setengah dari interval polling yang dikonfigurasi. Sistem harus tahan berjalan kontinu selama jam bursa tanpa intervensi manual, dan resource yang digunakan harus cukup ringan mengingat berjalan berdampingan dengan bot broksum di VM yang sama.

## 11. Rencana Pengembangan Lanjutan

Setelah versi awal berjalan stabil, beberapa arah pengembangan yang bisa dipertimbangkan meliputi perluasan keyword ke kategori keterbukaan informasi lain, ekstraksi otomatis detail penting dari isi PDF seperti rasio HMETD dan harga pelaksanaan, serta dashboard ringkas untuk melihat riwayat alert yang sudah terkirim.

## 12. Referensi

Endpoint dan pendekatan teknis di PRD ini dikonfirmasi dari implementasi publik berikut:

- **araafario/idx-5percent-shareholders-scraper** (github.com/araafario/idx-5percent-shareholders-scraper) — sumber konfirmasi endpoint `GetAnnouncement` beserta struktur parameter dan response JSON-nya. Tools ini secara spesifik dibuat untuk memantau laporan kepemilikan saham di atas 5%, kategori yang sama dengan INSIDER_OWNERSHIP di PRD ini, dan kreditnya disebutkan ke Hengky Adinata dan Remora Trader.
- **nichsedge/idx-bei** (github.com/nichsedge/idx-bei) — toolkit scraping IDX yang lebih luas cakupannya, menggunakan pendekatan serupa (`curl_cffi` dengan browser emulation) untuk melewati proteksi bot, relevan sebagai referensi cadangan kalau `cloudscraper` di kemudian hari berhenti efektif.

Perlu dicatat, syarat penggunaan resmi PT Bursa Efek Indonesia melarang redistribusi data yang diperoleh dari website untuk tujuan komersial tanpa izin tertulis. Sistem ini dirancang untuk pemakaian personal sebagai alat bantu keputusan trading sendiri, bukan untuk didistribusikan atau dikomersialkan ke pihak lain.