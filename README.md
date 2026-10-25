# API Sistem Irigasi Otomatis Lahan Pertanian

## 1. Deskripsi Singkat Project
Sistem Irigasi Otomatis Lahan Pertanian adalah sebuah REST API (*Backend*) yang dirancang untuk mengelola dan memonitor data sistem irigasi cerdas (*smart farming*). API ini memungkinkan pengguna untuk mendata zona lahan pertanian, mengatur ambang batas kelembapan, mengontrol status irigasi (menyala/mati), serta memantau sensor dan riwayat penyiraman secara terpusat.

## 2. Link URL Deployment
API ini telah di-deploy menggunakan Vercel dan dapat diakses publik melalui:
**URL:** `https://irigasi-pertanian.vercel.app`

## 3. Skema Database (ERD)
Database menggunakan PostgreSQL (Supabase/Neon) dengan rancangan **5 tabel** yang saling berelasi (*Relational Database*):

1. **`pengguna`** (Tabel Utama Pemilik)
   - Berelasi *one-to-many* dengan `zona_lahan`.
2. **`zona_lahan`** (Tabel Pusat/Resource Utama)
   - Memiliki *foreign key* `id_pengguna`.
3. **`alat_sensor`** (Data Alat/Hardware)
   - Memiliki *foreign key* `id_zona` dari tabel `zona_lahan`.
4. **`jadwal_irigasi`** (Aturan Waktu)
   - Memiliki *foreign key* `id_zona` dari tabel `zona_lahan`.
5. **`riwayat_penyiraman`** (Log Data)
   - Memiliki *foreign key* `id_zona` dari tabel `zona_lahan`.

*(Catatan: Gambaran visual ERD dapat dibuat menggunakan drawsql.app dengan menghubungkan kelima tabel di atas).*

---

## 4. Daftar Dokumentasi Endpoint API

### Get Status API
- **Method**       : GET
- **URL**          : `https://irigasi-pertanian.vercel.app/`
- **Deskripsi**    : Mengecek status keaktifan API dan rute yang tersedia.
- **Headers**      : None
- **Request Body** : None
- **Response Sukses (200)**:
  ```json
  {
    "message": "API Sistem Irigasi Otomatis (5 Tabel)",
    "endpoints": [
      "GET /zona",
      "POST /zona",
      "PUT /zona/<id>",
      "DELETE /zona/<id>"
    ]
  }
  ```

### Get Semua Zona
- **Method**       : GET
- **URL**          : `https://irigasi-pertanian.vercel.app/zona`
- **Deskripsi**    : Mengambil seluruh data zona lahan beserta relasinya (pemilik, sensor, jadwal, riwayat).
- **Headers**      : None
- **Request Body** : None
- **Response Sukses (200)**:
  ```json
  {
    "status": "success",
    "data": [
      {
        "id_zona": 1,
        "pemilik": "Kazuya",
        "nama_lahan": "tel aviv",
        "ambang_batas_kelembapan": 40,
        "status_irigasi": "mati",
        "tipe_sensor": null,
        "waktu_mulai": null,
        "siraman_terakhir": null
      }
    ]
  }
  ```

### Tambah Zona Lahan Baru
- **Method**       : POST
- **URL**          : `https://irigasi-pertanian.vercel.app/zona`
- **Deskripsi**    : Menambahkan data zona lahan baru ke database.
- **Headers**      : `Content-Type: application/json`
- **Request Body** :
  ```json
  {
    "id_pengguna": 1,
    "nama_lahan": "tel aviv",
    "nama_zona": "isriwil"
  }
  ```
- **Response Sukses (201)**:
  ```json
  {
    "message": "Zona berhasil ditambahkan",
    "data": {
      "id_zona": 2,
      "id_pengguna": 1,
      "nama_lahan": "tel aviv",
      "nama_zona": "isriwil",
      "jenis_tanaman": "Belum diatur",
      "ambang_batas_kelembapan": 40,
      "status_irigasi": "mati"
    }
  }
  ```
- **Response Error (400)**:
  ```json
  {
    "error": "Field id_pengguna dan nama_lahan wajib diisi"
  }
  ```

### Perbarui Data Zona Lahan
- **Method**       : PUT
- **URL**          : `https://irigasi-pertanian.vercel.app/zona/1`
- **Deskripsi**    : Memperbarui data detail atau status irigasi pada zona tertentu.
- **Headers**      : `Content-Type: application/json`
- **Request Body** :
  ```json
  {
    "nama_lahan": "tel aviv",
    "status_irigasi": "mati"
  }
  ```
- **Response Sukses (200)**:
  ```json
  {
    "message": "Zona diperbarui",
    "data": {
      "id_zona": 1,
      "id_pengguna": 1,
      "nama_lahan": "tel aviv",
      "nama_zona": "isriwil",
      "jenis_tanaman": null,
      "ambang_batas_kelembapan": 40,
      "status_irigasi": "mati"
    }
  }
  ```
- **Response Error (404)**:
  ```json
  {
    "error": "Zona tidak ditemukan"
  }
  ```

### Hapus Zona Lahan
- **Method**       : DELETE
- **URL**          : `https://irigasi-pertanian.vercel.app/zona/1`
- **Deskripsi**    : Menghapus data zona lahan berdasarkan ID.
- **Headers**      : None
- **Request Body** : None
- **Response Sukses (200)**:
  ```json
  {
    "message": "Zona dihapus",
    "data": {
      "id_zona": 1,
      "nama_lahan": "tel aviv"
    }
  }
  ```

---

## 5. Cara Menjalankan Project Secara Lokal

1. **Clone Repository**
   Buka terminal dan jalankan perintah:
   ```bash
   git clone <link-repo-github-kamu>
   cd <nama-folder-repo>
   ```

2. **Buat Virtual Environment (Opsional tapi disarankan)**
   ```bash
   python -m venv env
   # Windows:
   env\Scripts\activate
   # Mac/Linux:
   source env/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Konfigurasi Environment Variable**
   Buat file `.env` di root folder dan masukkan koneksi database PostgreSQL kamu:
   ```env
   DATABASE_URL=postgres://user:password@host:port/dbname
   ```
   *(Untuk Windows tanpa .env, bisa set langsung di terminal: `set DATABASE_URL=koneksi_db_kamu`)*

5. **Jalankan Aplikasi Flask**
   ```bash
   python app.py
   ```
   Aplikasi akan berjalan di `http://127.0.0.1:5000`. Kamu bisa mengujinya menggunakan Postman atau Thunder Client di localhost.