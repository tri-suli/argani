# Intent: argani, konfigurasi Claude global lintas proyek

Penulis: Tri Suli Prasetyo (pemilik produk). Status: draft, menunggu koreksi dan persetujuan
pemilik produk. Tanggal: 2026-10-24.

Sumber acuan:
- Anthropic, *The AI-native SDLC playbook*,
  https://claude.com/resources/articles/the-ai-native-sdlc-playbook
- zazencodes, *Software Factory* `BUILD_PROMPT.md`,
  https://github.com/zazencodes/zazencodes-season-3/blob/main/src/software-factory-claude-code/BUILD_PROMPT.md

## Masalah

Menulis kode bukan lagi hambatan. Hambatannya pindah ke tahap di kiri dan kanan build:
merumuskan apa yang diinginkan, merancang, mereview, menguji, dan merilis. Tahap itu masih
berjalan dengan kecepatan manusia dan sebagian besar terjadi di percakapan, bukan di artefak
yang ter-commit, sehingga tidak ada jejak audit tentang siapa meminta apa, apa yang dihasilkan
agen, dan siapa yang menyetujui.

Konfigurasi Claude saat ini tersebar dan rapuh:
- Mekanisme lama `defa` memasang `CLAUDE.md` global lewat symlink ke repo yang kini sudah
  tidak ada, sehingga symlink di `CLAUDE_CONFIG_DIR` putus.
- Aturan kerja ditulis ulang di `CLAUDE.md` tiap proyek dan ditegakkan hanya sebagai teks.
  Teks bersifat anjuran; tidak ada lapisan deterministik yang memastikan aturan selalu berlaku.
- Tidak ada artefak `intent.md` dan `spec.md` yang ter-commit, tidak ada eval suite, dan
  koreksi yang sama terulang karena tidak pernah berubah menjadi aturan.

Dua referensi yang dipelajari saling melengkapi tetapi tidak boleh ditiru mentah:
- Playbook Anthropic memberi bentuk loop penuh (Plan, Design, Build, Test, Deploy, Maintain),
  prinsip "skill menganjurkan, hook menegakkan", dan larangan agen menyetujui karyanya sendiri.
- Software Factory memberi mekanik orkestrasi yang konkret (spec-writer, builder, reviewer
  paralel, approver, verdict di baris pertama, maksimal dua ronde, "wait for all"), tetapi
  approver-nya merge langsung ke `main`, tidak punya tahap Plan, Test, dan Maintain, dan semua
  aturannya hanya teks.

## Hasil yang diinginkan

Satu repo `argani` yang menjadi marketplace Claude Code bernama `argani` dengan **satu plugin
`sdlc`**. Plugin ini menjalankan **satu loop** di semua jenis proyek (aplikasi, dokumentasi,
basis pengetahuan):

```
intent.md → spec.md → plan.md → pekerjaan di branch → review → merge request → operasi → intent.md baru
```

Setiap tahap diakhiri dengan artefak yang di-commit dan tahap berikutnya membacanya. Manusia
memutuskan di empat gate: menyetujui intent, mereview spec, menyetujui plan, dan menyetujui
merge request. Agen bekerja di antara gate dan berhenti di merge request.

Loop yang sama punya dua mode. **Mode manual**: orang memanggil skill satu per satu dan
menjalankan gate di tempat. **Mode factory**: skill `/sdlc:factory` menjadikan sesi sebagai
orkestrator yang menjalankan Spec, Build, Review, dan Decision dengan subagen, lalu berhenti
di merge request. Software Factory dengan demikian bukan metode terpisah, melainkan otomasi
sebagian dari loop ini.

Komponen yang diharapkan ada di plugin:
- Skill `/sdlc:intent`, `/sdlc:spec`, `/sdlc:plan` dengan template dan kriteria penerimaan
  yang wajib dapat diverifikasi.
- Protokol review: format verdict, batas ronde, satu agen satu file, dan "wait for all".
- Agen generik: spec-writer, builder, satu reviewer generik, approver. Reviewer membaca daftar
  periksa dari katalog (misalnya `code`, `security`, `ux`, `citation`, `format`); repo memilih
  mana yang aktif.
- Hook penegak yang membaca konfigurasi per repo: menolak merge atau push agen ke default
  branch, menolak file review tanpa verdict di baris pertama, melindungi path yang ditetapkan.
- Kerangka eval suite (`claude plugin eval`) yang isinya dimiliki tiap repo.
- `bootstrap/` untuk `CLAUDE.md` global dan `settings.json` yang tidak bisa dibawa plugin.

## Pengguna dan sistem yang terpengaruh

- Pemilik produk sekaligus pengembang tunggal, di semua repo: `trisnna` (dokumentasi dan
  brain), pekerjaan klien seperti LIS-SMS, dan aplikasi mendatang.
- Mesin pengembang: `CLAUDE_CONFIG_DIR` di `.claude-defa`, `settings.json` global,
  `~/.claude/CLAUDE.md`, hook memori dan statusline yang saat ini dirujuk dari sana.
- Setiap repo proyek: `.claude/settings.json` dengan `"sdlc@argani": true` dan konfigurasi
  per repo (reviewer aktif, perintah verifikasi, path dilindungi, lokasi artefak).

## Batasan

- Netral jenis proyek dan netral organisasi. Tidak bermerek atau berasumsi TrisNna, karena
  dipakai juga untuk pekerjaan klien.
- Agen tidak pernah menyetujui atau merge karyanya sendiri. Keluaran approver adalah merge
  request siap review manusia. Ini koreksi wajib atas Software Factory.
- Skill bersifat anjuran. Aturan yang harus selalu berlaku ditegakkan hook, dan hook membaca
  konfigurasi per repo karena hook global tidak bisa dimatikan per repo.
- Agen mendapat konteks dari file, bukan percakapan. Setiap agen hanya menulis filenya sendiri.
  Review diawali `PASS` atau `CHANGES`; keputusan diawali `APPROVE` atau `ESCALATE`. Maksimal
  dua ronde review, lalu eskalasi ke manusia.
- Intent tanpa kriteria penerimaan yang dapat dicek oleh perintah, tes, atau langkah manual
  bernama tidak boleh berstatus disetujui.
- Koreksi yang terjadi dua kali menjadi aturan di `CLAUDE.md` repo atau hook.
- Mode factory mahal (beberapa agen per pekerjaan, bisa dua ronde). Hanya untuk pekerjaan
  dengan kriteria penerimaan jelas.
- Konvensi repo: nama file, folder, kode, dan commit dalam bahasa Inggris; Conventional
  Commits dan SemVer 2.0.0; pekerjaan setelah commit awal ini lewat feature branch; tidak ada
  push tanpa instruksi.

## Kriteria penerimaan

1. `claude plugin validate . --strict` lolos pada root repo.
2. Repo lain yang menulis `"enabledPlugins": {"sdlc@argani": true}` melihat skill
   `/sdlc:intent` dan `/sdlc:spec` tersedia setelah marketplace terdaftar.
3. `/sdlc:intent` menghasilkan `intent.md` dari template dan menolak menandai status
   disetujui jika tidak ada kriteria penerimaan yang dapat diverifikasi.
4. `/sdlc:spec` berhenti dengan pesan jelas jika `intent.md` belum berstatus disetujui.
5. Hook menolak perintah merge atau push agen ke default branch, dan menolak penulisan file
   review yang baris pertamanya bukan verdict yang sah. Keduanya dibuktikan dengan satu kasus
   gagal dan satu kasus lolos.
6. `/sdlc:factory` pada satu pekerjaan contoh berakhir dengan merge request dan tidak pernah
   menjalankan merge.
7. `claude plugin eval plugins/sdlc` berjalan dan melaporkan hasil untuk minimal satu case.
8. `bootstrap/` memasang `CLAUDE.md` global dan `settings.json` dari repo ini tanpa symlink
   putus, dapat diulang tanpa efek samping.

## Di luar cakupan

- Dashboard dan aplikasi orkestrator lintas proyek. Akan menjadi repo terpisah dan menjadi
  proyek aplikasi pertama yang diproses oleh mode factory.
- Lapisan template dan alur kerja khusus TrisNna. Ditunda; skill intent dan spec diharapkan
  cukup, dipindah ke repo `trisnna` hanya jika terbukti perlu.
- Mekanisme deploy `defa`. Dilupakan, diganti `bootstrap/`.
- Monitoring produksi (`bands.yaml`, pemindaian terjadwal, Claude Tag). Dicatat sebagai tahap
  Operate dalam loop, belum dibangun karena belum ada sistem produksi yang dipantau.

## Urutan pengerjaan

1. Skill `intent` dan `spec`. Bisa dipakai segera tanpa orkestrator.
2. Protokol review dan hook penegak.
3. Agen generik dan katalog daftar periksa reviewer.
4. Orkestrator `/sdlc:factory` dengan keluaran merge request.
5. Kerangka eval suite, lalu `bootstrap/`.

## Pertanyaan terbuka

- Lisensi repo, mengingat remote GitHub bisa publik.
- Bahasa isi artefak `intent.md` dan `spec.md`: mengikuti bahasa proyek, atau selalu satu bahasa?
- Lokasi default artefak per pekerjaan: `sdlc/<slug>/` atau `intent/` seperti contoh playbook?
- Pilihan model per agen dan batas biaya per pekerjaan dalam mode factory.
- Siapa pemilik kebijakan untuk daftar periksa seperti security dan ux ketika tim hanya satu orang?
- Nasib `~/.claude/CLAUDE.md` yang saat ini terbaca sesi, versus `CLAUDE.md` di `CLAUDE_CONFIG_DIR`.
