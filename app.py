import os
import re
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg2
from flask import Flask, abort, jsonify, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from werkzeug.exceptions import HTTPException, MethodNotAllowed, NotFound

PERAN = ("petani", "teknisi", "admin")
STATUS = ("mati", "menyala")
KOLOM_ZONA = (
    "id_pengguna", "nama_lahan", "nama_zona",
    "jenis_tanaman", "ambang_batas_kelembapan", "status_irigasi",
)


class JSONKu(DefaultJSONProvider):
    sort_keys = False

    @staticmethod
    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        return DefaultJSONProvider.default(o)


app = Flask(__name__)
app.json = JSONKu(app)
CORS(app)


@contextmanager
def db():
    """Buka koneksi. Sukses -> commit, error -> rollback. Koneksi selalu ditutup."""
    conn = psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor,
        connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ambil_json():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, "Body harus berupa JSON object dengan header Content-Type: application/json")
    return data


def wajib(data, *fields):
    kosong = [f for f in fields if data.get(f) in (None, "")]
    if kosong:
        abort(400, f"Field {', '.join(kosong)} wajib diisi")


def cek_id(nilai, field):
    if isinstance(nilai, bool) or not isinstance(nilai, int) or nilai < 1:
        abort(400, f"Field {field} harus berupa bilangan bulat positif")


def cek_persen(nilai, field):
    if isinstance(nilai, bool) or not isinstance(nilai, (int, float, Decimal)) or not 0 <= nilai <= 100:
        abort(400, f"Field {field} harus berupa angka 0 sampai 100")


def cek_teks(nilai, field, boleh_kosong=False):
    if nilai is None and boleh_kosong:
        return
    if not isinstance(nilai, str) or not nilai.strip():
        abort(400, f"Field {field} harus berupa teks dan tidak boleh kosong")


def validasi_zona(z):
    cek_id(z["id_pengguna"], "id_pengguna")
    cek_teks(z["nama_lahan"], "nama_lahan")
    cek_teks(z["nama_zona"], "nama_zona")
    cek_teks(z["jenis_tanaman"], "jenis_tanaman", boleh_kosong=True)
    cek_persen(z["ambang_batas_kelembapan"], "ambang_batas_kelembapan")
    if z["status_irigasi"] not in STATUS:
        abort(400, "Field status_irigasi harus salah satu dari: mati, menyala")


@app.errorhandler(HTTPException)
def error_http(e):
    if isinstance(e, NotFound) and e.description == NotFound.description:
        pesan = "Endpoint tidak ditemukan"
    elif isinstance(e, MethodNotAllowed):
        pesan = "Method tidak diizinkan untuk endpoint ini"
    else:
        pesan = e.description
    return jsonify({"error": pesan}), e.code


@app.errorhandler(errors.UniqueViolation)
def error_duplikat(e):
    if "email" in (e.diag.constraint_name or ""):
        return jsonify({"error": "Email sudah terdaftar"}), 409
    return jsonify({"error": "Data duplikat: nilai yang harus unik sudah dipakai"}), 409


@app.errorhandler(errors.ForeignKeyViolation)
def error_fk(e):
    m = re.search(r"Key \((.+?)\)=\((.+?)\)", e.diag.message_detail or "")
    pesan = (f"Data referensi tidak ditemukan: {m.group(1)} = {m.group(2)}"
             if m else "Data referensi (foreign key) tidak ditemukan")
    return jsonify({"error": pesan}), 400


@app.errorhandler(errors.CheckViolation)
@app.errorhandler(psycopg2.DataError)
def error_data(e):
    return jsonify({"error": "Format atau nilai data tidak valid"}), 400


@app.errorhandler(Exception)
def error_server(e):
    app.logger.exception(e)  # detail error hanya di log server, tidak dikirim ke user
    return jsonify({"error": "Terjadi kesalahan pada server"}), 500


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "API Sistem Irigasi Otomatis Lahan Pertanian Aktif",
        "endpoints": [
            "GET /pengguna",
            "POST /pengguna",
            "GET /zona",
            "GET /zona/<id>",
            "POST /zona",
            "PUT /zona/<id>",
            "DELETE /zona/<id>",
            "GET /kelembapan",
            "POST /kelembapan",
            "GET /riwayat",
        ],
    })


# ===== PENGGUNA (+ profil_pengguna, relasi 1:1) =====
# 1. GET: semua pengguna beserta profilnya
@app.route("/pengguna", methods=["GET"])
def get_pengguna():
    with db() as cur:
        cur.execute("""
            SELECT p.id_pengguna, p.nama, p.email, p.peran, pr.nomor_telepon, pr.alamat
            FROM pengguna p
            LEFT JOIN profil_pengguna pr ON pr.id_pengguna = p.id_pengguna
            ORDER BY p.id_pengguna;
        """)
        data = cur.fetchall()
    return jsonify({"status": "success", "data": data}), 200


# 2. POST: tambah pengguna (profil ikut dibuat jika nomor_telepon / alamat dikirim)
@app.route("/pengguna", methods=["POST"])
def add_pengguna():
    data = ambil_json()
    wajib(data, "nama", "email", "peran")
    cek_teks(data["nama"], "nama")
    cek_teks(data["email"], "email")
    cek_teks(data.get("nomor_telepon"), "nomor_telepon", boleh_kosong=True)
    cek_teks(data.get("alamat"), "alamat", boleh_kosong=True)
    email = data["email"].strip().lower()
    if "@" not in email:
        abort(400, "Field email harus berupa email yang valid")
    if data["peran"] not in PERAN:
        abort(400, "Field peran harus salah satu dari: petani, teknisi, admin")

    with db() as cur:
        cur.execute(
            "INSERT INTO pengguna (nama, email, peran) VALUES (%s, %s, %s) RETURNING *;",
            (data["nama"].strip(), email, data["peran"]),
        )
        baru = cur.fetchone()
        profil = {"nomor_telepon": None, "alamat": None}
        if data.get("nomor_telepon") or data.get("alamat"):
            cur.execute(
                """INSERT INTO profil_pengguna (id_pengguna, nomor_telepon, alamat)
                   VALUES (%s, %s, %s) RETURNING nomor_telepon, alamat;""",
                (baru["id_pengguna"], data.get("nomor_telepon"), data.get("alamat")),
            )
            profil = cur.fetchone()
        baru.update(profil)
    return jsonify({"message": "Pengguna berhasil ditambahkan", "data": baru}), 201


# ===== ZONA LAHAN (resource utama: CRUD lengkap) =====
# 1. GET: semua zona beserta nama pemiliknya (boleh filter ?id_pengguna=1)
@app.route("/zona", methods=["GET"])
def get_zona():
    id_pengguna = request.args.get("id_pengguna", type=int)
    with db() as cur:
        cur.execute("""
            SELECT z.*, p.nama AS pemilik
            FROM zona_lahan z
            JOIN pengguna p ON p.id_pengguna = z.id_pengguna
            WHERE (%(u)s::int IS NULL OR z.id_pengguna = %(u)s)
            ORDER BY z.id_zona;
        """, {"u": id_pengguna})
        data = cur.fetchall()
    return jsonify({"status": "success", "data": data}), 200


# 2. GET: satu zona berdasarkan ID
@app.route("/zona/<int:id_zona>", methods=["GET"])
def get_zona_by_id(id_zona):
    with db() as cur:
        cur.execute("""
            SELECT z.*, p.nama AS pemilik
            FROM zona_lahan z
            JOIN pengguna p ON p.id_pengguna = z.id_pengguna
            WHERE z.id_zona = %s;
        """, (id_zona,))
        zona = cur.fetchone()
    if not zona:
        abort(404, "Zona tidak ditemukan")
    return jsonify({"status": "success", "data": zona}), 200


# 3. POST: tambah zona baru
@app.route("/zona", methods=["POST"])
def add_zona():
    data = ambil_json()
    wajib(data, "id_pengguna", "nama_lahan", "nama_zona")
    z = {k: data.get(k) for k in KOLOM_ZONA}
    z["ambang_batas_kelembapan"] = data.get("ambang_batas_kelembapan", 40)
    z["status_irigasi"] = data.get("status_irigasi", "mati")
    validasi_zona(z)

    with db() as cur:
        cur.execute(
            """
            INSERT INTO zona_lahan (id_pengguna, nama_lahan, nama_zona, jenis_tanaman,
                                    ambang_batas_kelembapan, status_irigasi)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING *;
            """,
            (z["id_pengguna"], z["nama_lahan"].strip(), z["nama_zona"].strip(), z["jenis_tanaman"],
             z["ambang_batas_kelembapan"], z["status_irigasi"]),
        )
        baru = cur.fetchone()
    return jsonify({"message": "Zona berhasil ditambahkan", "data": baru}), 201


# 4. PUT: ubah zona (field yang tidak dikirim tetap memakai nilai lama)
@app.route("/zona/<int:id_zona>", methods=["PUT"])
def update_zona(id_zona):
    data = ambil_json()
    if not any(k in data for k in KOLOM_ZONA):
        abort(400, "Kirim minimal satu field: " + ", ".join(KOLOM_ZONA))

    with db() as cur:
        cur.execute("SELECT * FROM zona_lahan WHERE id_zona = %s FOR UPDATE;", (id_zona,))
        lama = cur.fetchone()
        if not lama:
            abort(404, "Zona tidak ditemukan")

        z = {k: data.get(k, lama[k]) for k in KOLOM_ZONA}
        validasi_zona(z)
        cur.execute(
            """
            UPDATE zona_lahan
            SET id_pengguna = %s, nama_lahan = %s, nama_zona = %s, jenis_tanaman = %s,
                ambang_batas_kelembapan = %s, status_irigasi = %s
            WHERE id_zona = %s RETURNING *;
            """,
            (z["id_pengguna"], z["nama_lahan"].strip(), z["nama_zona"].strip(), z["jenis_tanaman"],
             z["ambang_batas_kelembapan"], z["status_irigasi"], id_zona),
        )
        updated = cur.fetchone()
    return jsonify({"message": "Zona berhasil diperbarui", "data": updated}), 200


# 5. DELETE: hapus zona (data kelembapan & riwayat irigasi zona itu ikut terhapus)
@app.route("/zona/<int:id_zona>", methods=["DELETE"])
def delete_zona(id_zona):
    with db() as cur:
        cur.execute("DELETE FROM zona_lahan WHERE id_zona = %s RETURNING *;", (id_zona,))
        dihapus = cur.fetchone()
    if not dihapus:
        abort(404, "Zona tidak ditemukan")
    return jsonify({"message": "Zona berhasil dihapus", "data": dihapus}), 200


# ===== DATA KELEMBAPAN (+ logika irigasi otomatis) =====
# 1. GET: data sensor terbaru (boleh filter ?id_zona=1), maksimal 100 data
@app.route("/kelembapan", methods=["GET"])
def get_kelembapan():
    id_zona = request.args.get("id_zona", type=int)
    with db() as cur:
        cur.execute("""
            SELECT k.id_data, k.id_zona, z.nama_lahan, z.nama_zona,
                   k.nilai_kelembapan, k.waktu_pengukuran
            FROM data_kelembapan k
            JOIN zona_lahan z ON z.id_zona = k.id_zona
            WHERE (%(z)s::int IS NULL OR k.id_zona = %(z)s)
            ORDER BY k.waktu_pengukuran DESC, k.id_data DESC
            LIMIT 100;
        """, {"z": id_zona})
        data = cur.fetchall()
    return jsonify({"status": "success", "data": data}), 200


# 2. POST: simpan data sensor. Sekaligus memutuskan irigasi otomatis:
#    - kelembapan < ambang batas  & irigasi mati    -> irigasi dinyalakan + riwayat "otomatis" dicatat
#    - kelembapan >= ambang batas & irigasi menyala -> irigasi dimatikan (jika dinyalakan otomatis)
@app.route("/kelembapan", methods=["POST"])
def add_kelembapan():
    data = ambil_json()
    wajib(data, "id_zona", "nilai_kelembapan")
    cek_id(data["id_zona"], "id_zona")
    cek_persen(data["nilai_kelembapan"], "nilai_kelembapan")
    waktu = data.get("waktu_pengukuran")
    if waktu is not None:
        try:
            datetime.fromisoformat(waktu)
        except (TypeError, ValueError):
            abort(400, "Field waktu_pengukuran harus berformat tanggal-waktu, contoh: 2026-10-25T08:30:00")

    aksi, riwayat = "tidak_ada", None
    with db() as cur:
        cur.execute("SELECT * FROM zona_lahan WHERE id_zona = %s FOR UPDATE;", (data["id_zona"],))
        zona = cur.fetchone()
        if not zona:
            abort(404, "Zona tidak ditemukan")

        cur.execute(
            """
            INSERT INTO data_kelembapan (id_zona, nilai_kelembapan, waktu_pengukuran)
            VALUES (%s, %s, COALESCE(%s::timestamp, CURRENT_TIMESTAMP)) RETURNING *;
            """,
            (data["id_zona"], data["nilai_kelembapan"], waktu),
        )
        baris = cur.fetchone()

        nilai = float(baris["nilai_kelembapan"])
        ambang = float(zona["ambang_batas_kelembapan"])

        if nilai < ambang and zona["status_irigasi"] == "mati":
            cur.execute("UPDATE zona_lahan SET status_irigasi = 'menyala' WHERE id_zona = %s;", (zona["id_zona"],))
            cur.execute(
                """INSERT INTO riwayat_irigasi (id_zona, metode, kelembapan_sebelum)
                   VALUES (%s, 'otomatis', %s) RETURNING *;""",
                (zona["id_zona"], nilai),
            )
            aksi, riwayat = "irigasi_dinyalakan", cur.fetchone()
        elif nilai >= ambang and zona["status_irigasi"] == "menyala":
            cur.execute(
                """UPDATE riwayat_irigasi SET waktu_selesai = CURRENT_TIMESTAMP
                   WHERE id_zona = %s AND metode = 'otomatis' AND waktu_selesai IS NULL RETURNING *;""",
                (zona["id_zona"],),
            )
            selesai = cur.fetchone()
            if selesai:
                cur.execute("UPDATE zona_lahan SET status_irigasi = 'mati' WHERE id_zona = %s;", (zona["id_zona"],))
                aksi, riwayat = "irigasi_dimatikan", selesai

    return jsonify({
        "message": "Data kelembapan berhasil ditambahkan",
        "data": baris,
        "irigasi_otomatis": {"aksi": aksi, "riwayat": riwayat},
    }), 201


# ===== RIWAYAT IRIGASI =====
# GET: riwayat penyiraman terbaru (boleh filter ?id_zona=1), maksimal 100 data
@app.route("/riwayat", methods=["GET"])
def get_riwayat():
    id_zona = request.args.get("id_zona", type=int)
    with db() as cur:
        cur.execute("""
            SELECT r.id_riwayat, r.id_zona, z.nama_lahan, z.nama_zona, r.metode,
                   r.kelembapan_sebelum, r.waktu_mulai, r.waktu_selesai
            FROM riwayat_irigasi r
            JOIN zona_lahan z ON z.id_zona = r.id_zona
            WHERE (%(z)s::int IS NULL OR r.id_zona = %(z)s)
            ORDER BY r.waktu_mulai DESC, r.id_riwayat DESC
            LIMIT 100;
        """, {"z": id_zona})
        data = cur.fetchall()
    return jsonify({"status": "success", "data": data}), 200


if __name__ == "__main__":
    app.run(debug=True)
