# BAB III
# METODOLOGI PENELITIAN DAN PERANCANGAN

Bab ini menjelaskan langkah-langkah yang dilakukan dalam penelitian dan perancangan sistem absensi berbasis *Face Recognition* dan RFID. Bab ini mencakup metodologi penyelesaian masalah, tahapan penelitian, perancangan diagram blok sistem, bahan dan peralatan yang dipergunakan, metode pengambilan data, serta analisis hasil.

---

## 3.1 Metode Penelitian

Pengembangan ini menggunakan metode *prototyping* (pembuatan purwarupa) sebagai pendekatan utama untuk membangun sistem absensi berbasis *Face Recognition* dan RFID. Metode *prototyping* merupakan pendekatan pengembangan yang membangun purwarupa fungsional secara bertahap melalui siklus iteratif yang terdiri atas perancangan, pengembangan, pengujian, dan revisi hingga sistem memenuhi standar kinerja yang telah ditetapkan. Metode ini dipilih karena sistem absensi ini memiliki tingkat kompleksitas integrasi yang tinggi, yakni menggabungkan interaksi perangkat keras tepi (*edge hardware*) seperti Modul RFID MFRC522 dengan komputasi kecerdasan buatan (AI) yang dijalankan secara lokal pada perangkat komputasi tepi (*edge computing*) berbasis Raspberry Pi sebagai *Edge Server*.

Kompleksitas tersebut muncul dari kebutuhan sistem untuk menangani dua alur pemrosesan absensi secara bersamaan namun terintegrasi. Jalur pertama adalah kendali pembacaan fisik melalui sensor RFID MFRC522 yang dikelola oleh Raspberry Pi melalui antarmuka GPIO, yang langsung memberikan *feedback* operasional melalui aktuator berupa *buzzer* dan indikator LED. Jalur kedua melibatkan pemrosesan kecerdasan buatan berbasis *computer vision* pada Raspberry Pi, yang menjalankan algoritma *Deep Learning* (Dlib) untuk mendeteksi, mengekstraksi *landmark*, dan mencocokkan wajah asisten secara *real-time* menggunakan masukan visual dari kamera. Kedua jalur autentikasi ini kemudian disinkronisasikan dan divalidasi oleh *backend server* lokal (FastAPI) yang terhubung ke basis data relasional SQLite. Data absensi yang telah diproses tersebut selanjutnya didistribusikan secara *real-time* ke luar jaringan lokal menggunakan teknologi *tunneling* Cloudflare agar dapat diakses kapan saja melalui aplikasi seluler yang dibangun menggunakan kerangka kerja Flutter.

Metode *prototyping* menyediakan kerangka kerja yang komprehensif untuk mengelola kompleksitas integrasi tersebut. Setiap modul sistem—baik modul pembacaan RFID, modul deteksi wajah AI, maupun modul API *backend* dan *frontend* seluler—dikembangkan dan divalidasi secara independen sebelum digabungkan menjadi satu ekosistem absensi yang utuh. Pendekatan iteratif ini memungkinkan pengembang untuk mengidentifikasi kegagalan respons sensor, kesalahan logika pencocokan wajah, atau *delay* pada koneksi jaringan sejak dini, sehingga secara signifikan dapat meminimalisasi risiko kegagalan sistem saat diimplementasikan di lingkungan laboratorium yang sebenarnya.

Siklus *prototyping* dalam pengembangan ini terdiri atas empat tahap utama yang berjalan secara berkesinambungan. Tahap pertama adalah perancangan (*design*), di mana pengembang menyusun skema rangkaian kabel (*wiring*) sensor ke Raspberry Pi, merancang arsitektur API (*Application Programming Interface*), serta mendesain *User Interface* aplikasi seluler. Tahap kedua adalah pengembangan (*development*), di mana perakitan perangkat fisik dilakukan bersamaan dengan penulisan skrip algoritma *Face Recognition* dan pengkodean aplikasi seluler. Tahap ketiga adalah pengujian (*testing*), di mana kecepatan respon sensor, akurasi pengenalan wajah pada berbagai kondisi cahaya, dan stabilitas *tunneling* jaringan diukur secara ketat. Tahap keempat adalah revisi (*revision*), di mana *bug* atau kegagalan yang ditemukan pada tahap pengujian diperbaiki dan disempurnakan sebelum siklus berikutnya dimulai. Siklus ini akan terus berulang hingga seluruh komponen sistem absensi beroperasi dengan tingkat presisi dan reliabilitas yang sesuai dengan tujuan operasional yang diharapkan.

---

## 3.2 Tahapan Penelitian

Penelitian ini dilaksanakan melalui serangkaian tahapan yang terstruktur untuk memastikan bahwa sistem yang dikembangkan memiliki landasan teoretis yang kuat dan relevan dengan kebutuhan operasional di lapangan.

### 3.2.1 Identifikasi Kebutuhan
Tahap identifikasi kebutuhan bertujuan untuk memetakan permasalahan pada sistem presensi konvensional laboratorium dan merumuskan spesifikasi fungsional sistem baru. Pengembang melakukan observasi terhadap alur presensi asisten yang sebelumnya rentan terhadap manipulasi (titip absen) dan rekapitulasi manual yang tidak efisien. Berdasarkan hasil observasi, ditetapkan kebutuhan untuk mengintegrasikan dua lapis keamanan: autentikasi biometrik melalui pengenalan wajah (*Face Recognition*) dan autentikasi fisik melalui pemindaian kartu RFID. Sistem juga diwajibkan memiliki dasbor pemantauan *real-time* yang dapat diakses dari mana saja tanpa dibatasi oleh hambatan jaringan lokal kampus.

### 3.2.2 Studi Literatur
Tahap studi literatur pada pengembangan ini bertujuan membangun landasan teoretis dan teknis yang sahih sebelum proses perancangan dimulai. Pengembang mengkaji jurnal akademis terindeks, dokumentasi teknis resmi perangkat keras, dan dokumentasi platform perangkat lunak yang relevan dengan komponen sistem absensi ini.

Kajian pertama berfokus pada teknologi *Computer Vision* dan Biometrik. Pengembang mempelajari algoritma ekstraksi fitur wajah menggunakan pustaka Dlib berbasis *Deep Learning*, yang memetakan 68 titik *landmark* pada wajah untuk mengenali identitas individu. Kajian ini mendasari penetapan *threshold* toleransi kecocokan (*tolerance level*) yang optimal guna menyeimbangkan antara tingkat penerimaan palsu (*False Acceptance Rate*) dan penolakan palsu (*False Rejection Rate*) pada lingkungan dengan variasi pencahayaan laboratorium.

Kajian kedua mencakup arsitektur *Internet of Things* (IoT) dan prinsip *Edge Computing*. Pengembang mempelajari model distribusi komputasi pada arsitektur tiga lapisan IoT. Dalam sistem ini, modul RFID MFRC522 dan modul Kamera menempati lapisan persepsi (*perception layer*) sebagai instrumen pengumpul data identitas. Raspberry Pi 4 menempati lapisan komputasi tepi (*edge computing layer*) yang bertugas sekaligus sebagai *Local Server*, *AI Processor*, dan pengendali langsung perangkat antarmuka GPIO (*Buzzer* dan LED). Pemahaman ini mendasari keputusan arsitektur di mana pemrosesan biometrik dilakukan secara lokal di perangkat *edge* tanpa mengirimkan data gambar mentah ke *cloud*, sehingga secara drastis menekan latensi komputasi dan menghemat *bandwidth* jaringan.

Kajian ketiga menelaah spesifikasi teknis komponen perangkat keras pendukung. Pengembang mempelajari karakteristik modul pembaca RFID MFRC522 yang beroperasi pada frekuensi 13.56 MHz dengan protokol komunikasi SPI, serta mekanisme pemberian *feedback* langsung melalui modul *Traffic Light LED* dan modul *Active Buzzer* (*Low Level Trigger*) yang dikendalikan melalui *General Purpose Input/Output* (GPIO) pada Raspberry Pi.

Kajian keempat berfokus pada ekosistem perangkat lunak (*software stack*) dan infrastruktur jaringan. Pengembang mempelajari *framework* FastAPI sebagai tulang punggung *backend* berkinerja tinggi, serta SQLite sebagai basis data relasional yang ringan dan persisten. Untuk mengatasi isolasi jaringan lokal (*Network Address Translation*), pengembang mengkaji implementasi *Cloudflare Tunnel* berbasis protokol QUIC/HTTP2 yang memungkinkan *backend* lokal terekspos secara aman ke jaringan internet publik tanpa memerlukan *Port Forwarding*. Selain itu, dikaji pula kerangka kerja Flutter untuk pengembangan aplikasi *mobile* lintas perangkat yang akan digunakan sebagai antarmuka pemantauan oleh admin dan asisten.

### 3.2.3 Perancangan Sistem
Tahap perancangan dalam pengembangan ini menghasilkan cetak biru teknis lengkap yang menjadi panduan bagi seluruh proses implementasi. Perancangan mencakup empat domain yang berjalan secara bersamaan dan saling terintegrasi, yaitu perangkat keras, perangkat lunak, basis data, dan antarmuka pengguna.

Pada domain perangkat keras, pengembang menyusun skematik rangkaian kelistrikan Kiosk secara komprehensif. Skematik ini memetakan koneksi pin antarmuka SPI (*Serial Peripheral Interface*) dari modul RFID MFRC522 ke pin GPIO Raspberry Pi, koneksi sinyal aktuator *Buzzer* aktif dan LED indikator ke pin GPIO digital, serta koneksi modul kamera melalui antarmuka USB. Raspberry Pi bertindak sebagai mikrokontroler tunggal sekaligus *server* komputasi tepi yang mengorkestrasi seluruh perangkat keras tersebut tanpa memerlukan mikrokontroler tambahan.

Pada domain perangkat lunak, pengembang merancang logika sistem dalam dua lapis. Lapis pertama adalah *pipeline skrip* Python pada Kiosk yang mencakup alur *capture* *frame* kamera, ekstraksi *landmark* wajah menggunakan Dlib, pemindaian *Unique Identifier* (UID) kartu RFID, serta pengiriman data *"Heartbeat"* berkala untuk memantau status aktif perangkat keras. Lapis kedua adalah perancangan *backend* berbasis *framework* FastAPI yang mengekspos *endpoint* RESTful API untuk memvalidasi dan mencatat data identitas (*wajah* atau *RFID*) ke dalam *database*, serta melayani permintaan data dari aplikasi seluler pengguna secara efisien.

Pada domain basis data, pengembang menetapkan skema relasional berbasis SQLite yang terdiri atas lima tabel utama, yaitu tabel `users`, `schedules`, `attendance`, `attendance_shifts`, dan `announcements`. Setiap tabel direlasikan secara ketat menggunakan *Foreign Key* agar proses integrasi data—mulai dari pencocokan ID asisten hingga rekapitulasi jumlah poin jaga—dapat berlangsung dengan latensi minimal dan terhindar dari anomali data.

Pada domain antarmuka pengguna, pengembang merancang dua ruang lingkup UI (*User Interface*). Pertama, *Graphical User Interface* (GUI) untuk Kiosk berbasis Tkinter yang dirancang intuitif untuk menampilkan tangkapan video kamera secara *real-time* beserta status keberhasilan *scan*. Kedua, *wireframe* aplikasi *mobile* berbasis Flutter yang mencakup halaman *dashboard* asisten untuk melihat poin mutu dan rekap absensi, halaman jadwal jaga, halaman papan pengumuman, serta antarmuka khusus Admin untuk mendaftarkan RFID baru dan memantau status operasional (*uptime*) komponen Kiosk dari jarak jauh.

### 3.2.4 Implementasi Sistem
Tahap implementasi mewujudkan seluruh rancangan menjadi prototipe fisik dan logis yang fungsional. Proses ini berjalan secara paralel antara pembangunan perangkat keras Kiosk dan pengembangan infrastruktur perangkat lunak untuk mengoptimalkan efisiensi waktu pengerjaan.

Pada sisi perangkat keras, pengembang merakit purwarupa fisik (*maket*) Kiosk menggunakan papan *Polyvinyl Chloride* (PVC) setebal 5 mm yang dibentuk menyerupai kotak panel. Sebagai antarmuka visual utama, diimplementasikan layar *LCD Touchscreen* 7 inci khusus Raspberry Pi yang dihubungkan melalui *port* HDMI. Di bagian depan panel PVC, dipasang modul pembaca RFID MFRC522 pada area yang ergonomis untuk pemindaian kartu, disandingkan dengan modul aktuator *Traffic Light LED Module* (berisi LED Hijau, Kuning, dan Merah) serta modul *Active Buzzer* (*Low Level Trigger*) untuk memberikan *feedback* operasional secara seketika. Sebuah modul *Webcam* USB diposisikan sentral di bagian atas kotak maket guna memastikan sudut pengambilan gambar (*viewing angle*) yang proporsional untuk algoritma pengenalan wajah. Seluruh komponen elektronika tersebut direkatkan secara presisi pada permukaan papan PVC menggunakan perekat bakar (*hot melt adhesive* / lem tembak) guna memastikan stabilitas mekanis komponen saat digunakan berinteraksi oleh pengguna.

Pada sisi perangkat lunak, pengembang menulis skrip kendali Kiosk menggunakan bahasa Python yang dijalankan langsung pada antarmuka GUI Tkinter. Skrip ini mengatur alur pembacaan *frame* kamera berkecepatan tinggi, inferensi pengenalan wajah menggunakan algoritma Dlib, serta deteksi asinkron dari sensor RFID MFRC522. Di balik layar, pengembang membangun *backend server* lokal berbasis *framework* FastAPI yang mengeksekusi validasi kredensial absensi dan mencatatnya ke *database* SQLite. Untuk mengatasi hambatan jaringan lokal (NAT) agar aplikasi seluler dapat berkomunikasi dengan *server* secara *real-time*, pengembang mengonfigurasi layanan *Cloudflare Tunnel* (`cloudflared`) yang menyiarkan *endpoint* lokal tersebut menjadi URL publik yang aman melalui protokol HTTP/2. Sementara itu, aplikasi seluler Android dikembangkan sepenuhnya menggunakan kerangka kerja Flutter, di mana setiap *widget* antarmuka—mulai dari layar dasbor poin hingga jadwal jaga—dikaitkan langsung ke *endpoint* API *backend* untuk melakukan sinkronisasi data (*fetch* dan *post*) secara *real-time*.

### 3.2.5 Pengujian Sistem
Tahap pengujian sistem bertujuan untuk mengukur metrik kinerja operasional dan memvalidasi bahwa seluruh subsistem (perangkat keras, kecerdasan buatan, basis data, dan jaringan) telah terintegrasi secara harmonis sesuai spesifikasi perancangan. Pengujian pada penelitian ini dibagi menjadi tiga domain pengujian utama, yaitu pengujian fungsionalitas perangkat keras, pengujian performa algoritma pengenalan wajah (*Face Recognition*), serta pengujian integrasi jaringan dan aplikasi seluler.

Pengujian fungsionalitas perangkat keras difokuskan pada keandalan instrumen fisik yang terpasang pada panel maket PVC Kiosk. Pengujian modul pembaca RFID MFRC522 dilakukan dengan menguji rentang jarak deteksi efektif (*reading range*) mulai dari 0 cm hingga 5 cm dan sudut pemindaian kartu terhadap sensor. Modul aktuator *Traffic Light LED* dan *Active Buzzer* diuji untuk memastikan respons sinyal visual dan audio bekerja secara presisi tanpa adanya *delay* saat presensi dinyatakan berhasil (LED Hijau dan 1 kali bunyi *buzzer*) maupun gagal (LED Merah dan 3 kali bunyi *buzzer*). Selain itu, antarmuka layar sentuh (*LCD Touchscreen* 7 inci) diuji responsivitasnya terhadap interaksi sentuhan pengguna saat bernavigasi pada jendela Kiosk GUI Tkinter.

Pengujian performa algoritma pengenalan berpusat pada akurasi model *Face Recognition* (ekstraksi 68 titik *landmark* Dlib). Pengujian ini dilakukan dengan dua skenario utama:
1. **Pengujian Kondisi Pencahayaan dan Sudut Wajah:** Menguji tingkat keberhasilan deteksi kamera USB pada variasi intensitas cahaya ruangan (kondisi terang di atas 300 lux, kondisi normal 150–300 lux, dan kondisi redup di bawah 100 lux) serta variasi sudut kemiringan wajah (*pose variation*).
2. **Pengujian Akurasi dan Metrik Biometrik:** Mengukur tingkat kesalahan klasifikasi melalui dua parameter standar, yaitu *False Acceptance Rate* (FAR) untuk memastikan sistem tidak salah mengidentifikasi orang asing/tidak terdaftar sebagai asisten, dan *False Rejection Rate* (FRR) untuk memastikan asisten terdaftar tidak ditolak oleh sistem. Selain itu, dicatat pula waktu komputasi (*inference time*) yang dibutuhkan sistem mulai dari wajah terdeteksi pada *frame* kamera hingga identitas terverifikasi.

Pengujian keandalan jaringan dan aplikasi seluler dilakukan untuk mengevaluasi stabilitas komunikasi data secara *end-to-end*. Pengujian ini mengukur latensi pengiriman data presensi dari *server* lokal FastAPI menuju aplikasi seluler Flutter melalui *Cloudflare Tunnel* (protokol HTTP/2). Skenario pengujian dilakukan dengan mengakses aplikasi seluler dari luar jaringan lokal laboratorium menggunakan koneksi data seluler (4G/5G) guna menguji konsistensi sinkronisasi data riwayat kehadiran, pembaruan statistik poin asisten pada dasbor secara *real-time*, serta pengujian ketahanan koneksi *tunneling* terhadap potensi *connection drop*.

### 3.2.6 Analisis Hasil
Tahap analisis hasil bertujuan untuk mengolah, menginterpretasi, dan mengevaluasi data empiris yang diperoleh dari seluruh skenario pengujian guna menentukan apakah kinerja prototipe telah memenuhi tolok ukur operasional yang telah ditetapkan. Analisis dilakukan secara kuantitatif dan kualitatif pada tiga parameter utama:

Pertama, analisis performa biometrik dan perangkat keras dilakukan dengan mengevaluasi matriks konfusi (*Confusion Matrix*) yang mencakup parameter *True Positive* (TP), *False Positive* (FP), *True Negative* (TN), dan *False Negative* (FN). Dari nilai-nilai tersebut, dihitung persentase akurasi keseluruhan (*overall accuracy*), nilai *False Acceptance Rate* (FAR), dan *False Rejection Rate* (FRR) pada berbagai variasi tingkat pencahayaan dan *pose* wajah. Hasil perhitungan ini dianalisis untuk menetapkan batas toleransi jarak euklidian (*Euclidean distance threshold*) yang paling optimal pada model Dlib. Selain itu, data jarak baca RFID dan waktu respons aktuator (*Traffic Light LED* dan *Active Buzzer*) dianalisis untuk memastikan ketiadaan hambatan mekanis maupun latensi pemrosesan lokal.

Kedua, analisis kualitas layanan jaringan (*Quality of Service* - QoS) dilakukan dengan mengevaluasi metrik latensi *round-trip time* (RTT) dan tingkat keberhasilan pengiriman paket data (*packet delivery ratio*) melalui *Cloudflare Tunnel*. Data log *server* FastAPI dianalisis untuk membandingkan performa komunikasi data saat aplikasi seluler diakses melalui jaringan lokal (LAN) versus jaringan internet publik (4G/5G seluler). Analisis ini bertujuan untuk membuktikan efektivitas protokol HTTP/2 dalam mempertahankan sesi koneksi yang stabil tanpa terputus (*zero connection drops*).

Ketiga, analisis efektivitas dan kelayakan operasional sistem dilakukan dengan membandingkan efisiensi waktu proses presensi ganda (kombinasi RFID dan *Face Recognition*) terhadap metode presensi manual berbasis tanda tangan atau kartu konvensional. Analisis ini mengevaluasi sejauh mana integrasi sistem mampu mengeliminasi celah kecurangan (seperti titip absen), meningkatkan ketertiban jadwal asisten laboratorium, serta mempermudah rekapitulasi data kehadiran dan poin mutu oleh administrator secara *real-time*.

---

## 3.3 Perancangan Sistem

Tahap ini membahas secara rinci perancangan perangkat keras, perangkat lunak, dan basis data untuk prototipe sistem absensi laboratorium (*LabTrack*). Perancangan sistem ini bertumpu pada rumusan masalah, tujuan penelitian, dan kerangka pemikiran yang telah dipaparkan pada bab sebelumnya. Pengembang merancang setiap komponen secara spesifik agar terintegrasi penuh dalam mendukung autentikasi presensi ganda berbasis biometrik wajah dan kartu RFID, pemrosesan kecerdasan buatan (*Edge AI*) secara lokal, serta pemantauan dan rekapitulasi data kehadiran jarak jauh melalui aplikasi seluler.

### 3.3.1 Perancangan Perangkat Keras

Perancangan perangkat keras (*hardware*) difokuskan pada pengintegrasian berbagai komponen fisik yang memungkinkan sistem absensi Kiosk berinteraksi dengan pengguna secara *real-time*. Komponen-komponen perangkat keras yang digunakan dalam perancangan ini diklasifikasikan ke dalam empat kategori utama:

1. **Mikrokontroler dan Pusat Komputasi**
   * **Raspberry Pi 4 Model B:** Bertindak sebagai pusat kendali utama (*Single Board Computer*) sekaligus mikrokontroler. Modul ini dipilih karena kemampuannya mengorkestrasi inferensi kecerdasan buatan (*Face Recognition* berbasis Dlib) secara lokal, mengelola input/output GPIO, serta menjalankan peladen *backend* FastAPI secara mandiri tanpa membutuhkan PC tambahan.

2. **Sensor (Modul Masukan)**
   * **Modul RFID MFRC522:** Berfungsi sebagai sensor pemindai frekuensi radio 13.56 MHz yang membaca *Unique Identifier* (UID) dari kartu/gantungan RFID asisten. Modul ini berkomunikasi dengan Raspberry Pi melalui antarmuka *Serial Peripheral Interface* (SPI).
   * **Webcam USB:** Berfungsi menangkap aliran video (*video stream*) wajah pengguna dengan resolusi yang memadai untuk diteruskan ke algoritma *Face Recognition*.
   * **Layar Sentuh (*Touchscreen* 7"):** Menangkap aksi sentuhan jari pengguna sebagai input fisik untuk memilih menu pada antarmuka Kiosk GUI.

3. **Modul Komunikasi**
   * **Modul Wi-Fi (On-board Raspberry Pi):** Digunakan sebagai penghubung sistem Kiosk ke jaringan internet laboratorium. Jalur komunikasi ini memungkinkan *Cloudflare Tunnel* merutekan paket data presensi dari *Local Server* ke domain publik melalui protokol HTTP/2, sehingga dapat diakses oleh aplikasi seluler asisten.
   * **Bus SPI dan USB:** Berperan sebagai antarmuka komunikasi data lokal berkecepatan tinggi antara mikrokontroler dengan modul RFID (SPI) dan kamera (USB).

4. **Aktuator (Modul Keluaran)**
   * **Traffic Light LED Module:** Berfungsi sebagai aktuator visual (Kuning = *Standby*, Hijau = Berhasil, Merah = Gagal) yang dikendalikan melalui sinyal tegangan digital GPIO.
   * **Active Buzzer Module:** Menghasilkan umpan balik audio berupa bunyi *beep* (*Low-Level Trigger*) sebagai konfirmasi berhasil atau gagalnya sebuah proses autentikasi.
   * **Layar LCD 7 Inci HDMI:** Berperan ganda sebagai aktuator keluaran visual yang menampilkan antarmuka grafis (Tkinter), umpan balik kamera (*live feed*), bingkai wajah (*bounding box*), serta status operasional sistem Kiosk secara seketika.

Hubungan struktural antar-komponen perangkat keras di atas direpresentasikan melalui diagram blok sistem pada Gambar 3.1.

![Diagram Blok Sistem](/Users/dimas/.gemini/antigravity-ide/brain/0b1764fe-f402-467f-aed0-c47ec5361e9e/diagram_blok_sistem_soft_1787072320641.jpg)

*(Gambar 3.1: Diagram Blok Arsitektur Prototipe Sistem Absensi)*

Berdasarkan Gambar 3.1, alur kerja prototipe sistem absensi mengintegrasikan Blok Masukan (RFID, Webcam, Touchscreen), Blok Proses (Raspberry Pi, FastAPI, Cloudflare Tunnel), dan Blok Keluaran (LED, Buzzer, LCD) secara *real-time*.

#### Skematik Rangkaian Sistem

Perancangan perangkat keras tersebut kemudian diwujudkan ke dalam skematik rangkaian kelistrikan Kiosk. Skematik ini memetakan secara presisi jalur koneksi antarmuka komunikasi data dan catu daya antara Raspberry Pi dengan seluruh sensor dan aktuator yang telah didefinisikan sebelumnya, dengan tetap memperhatikan toleransi level tegangan logika (3.3V dan 5V).

![Skematik Rangkaian Sistem](./skematik_rangkaian_sistem.jpg)

*(Gambar 3.2: Skematik Rangkaian Kelistrikan Kiosk Absensi)*

Pemetaan pengkabelan (*wiring*) antarmuka perangkat keras terhadap pin header 40-pin Raspberry Pi ditunjukkan secara terperinci pada Tabel 3.1:

**Tabel 3.1 Konfigurasi Pengkabelan Pin GPIO Raspberry Pi 4 dengan Perangkat Keras**

| Komponen Hardware | Pin Komponen | Pin Fisik Raspberry Pi | Label Pin / Fungsi | Deskripsi |
| :--- | :--- | :--- | :--- | :--- |
| **Modul RFID-RC522** | 3.3V | Pin 1 | 3V3 Power | Sumber daya daya tegangan 3.3V |
| | RST | Pin 22 | GPIO 25 | Sinyal Reset Modul RFID |
| | GND | Pin 6 | Ground (GND) | Jalur pembumian / ground |
| | MISO | Pin 21 | GPIO 9 (SPI0 MISO) | Jalur data input SPI (Master In Slave Out) |
| | MOSI | Pin 19 | GPIO 10 (SPI0 MOSI)| Jalur data output SPI (Master Out Slave In) |
| | SCK | Pin 23 | GPIO 11 (SPI0 SCLK)| Sinyal detak jam SPI (Serial Clock) |
| | SDA / SS | Pin 24 | GPIO 8 (SPI0 CE0) | Chip Enable / Slave Select SPI |
| **Traffic Light LED** | R (Merah) | Pin 11 | GPIO 17 | Kontrol digital LED Merah (Absen Gagal) |
| | Y (Kuning) | Pin 13 | GPIO 27 | Kontrol digital LED Kuning (Standby/Menunggu) |
| | G (Hijau) | Pin 15 | GPIO 22 | Kontrol digital LED Hijau (Absen Berhasil) |
| | GND | Pin 9 | Ground (GND) | Jalur bersama katoda LED |
| **Active Buzzer** | VCC | Pin 2 / 4 | 5V Power | Sumber daya modul buzzer aktif |
| | GND | Pin 14 | Ground (GND) | Jalur pembumian / ground |
| | I/O (Sinyal)| Pin 16 | GPIO 23 | Sinyal kendali trigger suara (*Low-Level*) |
| **Webcam USB** | USB Data/Power| Port USB 2.0 / 3.0 | USB Port 0 | Input aliran video dan catu daya kamera |
| **LCD Touchscreen 7"**| HDMI | Port Micro-HDMI 0 | Video Display | Sinyal luaran tampilan visual Kiosk GUI |
| | Micro-USB | Port USB 2.0 | Touch Input & Power| Sinyal koordinat sentuhan & catu daya layar |

---

## 3.4 Bahan dan Peralatan yang Dipergunakan

Dalam merancang dan mengimplementasikan sistem absensi ini, diperlukan sejumlah perangkat keras (*hardware*) dan perangkat lunak (*software*).

### 3.4.1 Perangkat Keras (*Hardware*)
Peralatan keras yang digunakan sebagai *server* sekaligus *Kiosk* presensi meliputi:
1. **Papan PVC 5 mm:** Sebagai material purwarupa fisik (*maket*) dudukan komponen.
2. **Raspberry Pi 4 Model B:** Sebagai mikrokomputer pusat yang menjalankan *backend server* dan antarmuka *Kiosk*.
3. **Layar LCD Touchscreen 7 Inci HDMI:** Antarmuka layar sentuh untuk interaksi pengguna.
4. **Webcam USB:** Menangkap citra wajah asisten saat melakukan presensi (*Face Recognition*).
5. **Modul RFID RC522:** Memindai kartu RFID frekuensi 13.56 MHz.
6. **Traffic Light LED Module:** Modul lampu indikator tiga warna (Hijau, Kuning, Merah).
7. **Active Buzzer Module (Low Level Trigger):** Indikator suara (*feedback* audio).
8. **Kabel Jumper & Breadboard:** Menghubungkan modul sensor dan aktuator ke pin GPIO Raspberry Pi.
9. **Perangkat Seluler (Smartphone):** Menjalankan aplikasi *mobile* berbasis Android/iOS.

### 3.4.2 Perangkat Lunak (*Software*)
Perangkat lunak yang digunakan dalam pengembangan sistem ini meliputi:
1. **Sistem Operasi:** macOS (sebagai *environment* pengembangan) dan Raspberry Pi OS (sebagai *environment deployment*).
2. **Bahasa Pemrograman:** Python 3.10+ (untuk *backend* dan logika *hardware*) dan Dart (untuk *frontend mobile*).
3. **Framework Backend:** FastAPI dan Uvicorn.
4. **Framework Frontend:** Flutter.
5. **Database:** SQLite dengan SQLAlchemy ORM.
6. **Library Computer Vision:** OpenCV dan `face_recognition` (Dlib).
7. **Jaringan & Tunneling:** Cloudflare Tunnel (`cloudflared`) untuk merutekan *localhost* ke domain publik (`api.himatekkomug.my.id`).
