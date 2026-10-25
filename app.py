import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
from werkzeug.exceptions import HTTPException

app = Flask(__name__)
CORS(app)

# Fungsi helper untuk koneksi ke Database (Supabase PostgreSQL)
def get_db_connection():
    conn = psycopg2.connect(
        os.environ.get("DATABASE_URL"),
        cursor_factory=RealDictCursor
    )
    return conn

# Helper: jalankan satu query, hasilnya dikembalikan, koneksi selalu ditutup
def run(sql, params=(), fetch="all"):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, params)
        hasil = cur.fetchall() if fetch == "all" else cur.fetchone()
        conn.commit()
        return hasil
    finally:
        conn.close()

@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "message": "API Sistem Irigasi Otomatis Lahan Pertanian Aktif",
        "endpoints": [
            "GET /zona",
            "POST /zona",
            "PUT /zona/<id>",
            "DELETE /zona/<id>"
        ]
    })

# 1. GET: Mengambil semua data zona lahan beserta nama pemiliknya
@app.route("/zona", methods=["GET"])
def get_zona():
    zona = run("""
        SELECT z.id_zona, p.nama AS pemilik, z.nama_lahan, z.nama_zona,
               z.jenis_tanaman, z.ambang_batas_kelembapan, z.status_irigasi
        FROM zona_lahan z
        JOIN pengguna p ON z.id_pengguna = p.id_pengguna
        ORDER BY z.id_zona;
    """)
    return jsonify({"status": "success", "data": zona}), 200

# 2. POST: Menambah zona lahan baru
@app.route("/zona", methods=["POST"])
def add_zona():
    data = request.get_json(silent=True)

    # Validasi input sederhana
    if not data or not data.get("id_pengguna") or not data.get("nama_lahan") or not data.get("nama_zona"):
        return jsonify({"error": "Field id_pengguna, nama_lahan, dan nama_zona wajib diisi"}), 400

    new_zona = run(
        """
        INSERT INTO zona_lahan (id_pengguna, nama_lahan, nama_zona, jenis_tanaman, ambang_batas_kelembapan, status_irigasi)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING *;
        """,
        (data["id_pengguna"], data["nama_lahan"], data["nama_zona"], data.get("jenis_tanaman"),
         data.get("ambang_batas_kelembapan", 40), data.get("status_irigasi", "mati")),
        fetch="one"
    )
    return jsonify({"message": "Zona lahan berhasil ditambahkan", "data": new_zona}), 201

# 3. PUT: Mengubah data zona berdasarkan ID (field yang tidak dikirim tetap memakai nilai lama)
@app.route("/zona/<int:id_zona>", methods=["PUT"])
def update_zona(id_zona):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Body JSON wajib diisi"}), 400

    # Cek apakah data ada
    existing = run("SELECT * FROM zona_lahan WHERE id_zona = %s", (id_zona,), fetch="one")
    if not existing:
        return jsonify({"error": "Zona tidak ditemukan"}), 404

    updated = run(
        """
        UPDATE zona_lahan
        SET nama_lahan = %s, nama_zona = %s, jenis_tanaman = %s,
            ambang_batas_kelembapan = %s, status_irigasi = %s
        WHERE id_zona = %s RETURNING *;
        """,
        (data.get("nama_lahan", existing["nama_lahan"]),
         data.get("nama_zona", existing["nama_zona"]),
         data.get("jenis_tanaman", existing["jenis_tanaman"]),
         data.get("ambang_batas_kelembapan", existing["ambang_batas_kelembapan"]),
         data.get("status_irigasi", existing["status_irigasi"]),
         id_zona),
        fetch="one"
    )
    return jsonify({"message": "Zona berhasil diperbarui", "data": updated}), 200

# 4. DELETE: Menghapus zona lahan
@app.route("/zona/<int:id_zona>", methods=["DELETE"])
def delete_zona(id_zona):
    deleted = run("DELETE FROM zona_lahan WHERE id_zona = %s RETURNING *;", (id_zona,), fetch="one")
    if not deleted:
        return jsonify({"error": "Zona tidak ditemukan"}), 404
    return jsonify({"message": "Zona berhasil dihapus", "data": deleted}), 200

# ---- Penanganan error: selalu balas JSON ----
@app.errorhandler(errors.ForeignKeyViolation)
def fk_error(e):
    return jsonify({"error": "id_pengguna tidak ditemukan"}), 400

@app.errorhandler(errors.CheckViolation)
@app.errorhandler(psycopg2.DataError)
def data_error(e):
    return jsonify({"error": "Nilai tidak valid (ambang_batas_kelembapan harus 0-100, status_irigasi harus 'mati' atau 'menyala')"}), 400

@app.errorhandler(Exception)
def server_error(e):
    if isinstance(e, HTTPException):
        return jsonify({"error": e.description}), e.code
    app.logger.exception(e)
    return jsonify({"error": "Terjadi kesalahan pada server"}), 500

if __name__ == "__main__":
    app.run(debug=True)
