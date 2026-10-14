"""Aplikasi laporan penjualan Kedai Rasa.

Dikembangkan dari materi Minggu 6 (Pemrograman Data Bisnis) dengan tambahan
halaman pengelolaan data master: CRUD produk (soft delete) dan CRUD kategori.
Berkas ini sudah berbeda dari blok app.py di modul Minggu 6, jadi jangan
menimpanya dengan menyalin ulang kode dari modul.
"""

from contextlib import closing
from datetime import date
from pathlib import Path
import sqlite3

import pandas as pd
import streamlit as st

DB_PATH = Path(__file__).with_name("penjualan_m6.db")
SEED_CATEGORIES = ["Minuman", "Makanan", "Camilan"]
SEED_PRODUCTS = [
    ("Kopi Susu", "Minuman", 15000),
    ("Teh Lemon", "Minuman", 12000),
    ("Es Cokelat", "Minuman", 18000),
    ("Roti Cokelat", "Makanan", 10000),
    ("Nasi Goreng", "Makanan", 22000),
    ("Pisang Goreng", "Camilan", 8000),
]
# (tanggal, nama produk, harga per unit saat transaksi, jumlah unit)
SEED_SALES = [
    ("2026-08-03", "Kopi Susu", 15000, 3),
    ("2026-08-03", "Roti Cokelat", 10000, 2),
    ("2026-08-05", "Nasi Goreng", 22000, 2),
    ("2026-08-07", "Teh Lemon", 12000, 4),
    ("2026-08-10", "Pisang Goreng", 8000, 5),
    ("2026-08-12", "Es Cokelat", 18000, 2),
    ("2026-08-14", "Kopi Susu", 15000, 5),
    ("2026-08-17", "Kopi Susu", 13000, 6),
    ("2026-08-17", "Pisang Goreng", 8000, 6),
    ("2026-08-19", "Nasi Goreng", 22000, 3),
    ("2026-08-21", "Roti Cokelat", 10000, 3),
    ("2026-08-24", "Teh Lemon", 12000, 2),
    ("2026-08-26", "Es Cokelat", 18000, 3),
    ("2026-08-28", "Kopi Susu", 15000, 4),
    ("2026-08-31", "Nasi Goreng", 22000, 1),
    ("2026-09-01", "Kopi Susu", 15000, 4),
    ("2026-09-02", "Pisang Goreng", 8000, 4),
    ("2026-09-04", "Nasi Goreng", 22000, 4),
    ("2026-09-07", "Teh Lemon", 12000, 5),
    ("2026-09-09", "Roti Cokelat", 10000, 4),
    ("2026-09-11", "Es Cokelat", 18000, 3),
    ("2026-09-14", "Kopi Susu", 15000, 6),
    ("2026-09-16", "Nasi Goreng", 22000, 2),
    ("2026-09-18", "Pisang Goreng", 8000, 3),
    ("2026-09-21", "Es Cokelat", 16000, 5),
    ("2026-09-23", "Teh Lemon", 12000, 3),
    ("2026-09-25", "Kopi Susu", 15000, 5),
    ("2026-09-28", "Roti Cokelat", 10000, 2),
    ("2026-09-30", "Nasi Goreng", 22000, 3),
    ("2026-09-30", "Kopi Susu", 15000, 2),
]
JOIN_SQL = (
    "FROM sales "
    "JOIN products ON products.id = sales.product_id "
    "JOIN categories ON categories.id = products.category_id"
)
PRODUCTS_JOIN_SQL = "FROM products JOIN categories ON categories.id = products.category_id"


# ==== Koneksi dan inisialisasi database ====
def get_connection():
    """Buka koneksi SQLite dan aktifkan pemeriksaan foreign key."""
    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def migrate_products_to_categories(connection):
    """Ubah tabel products lama (kolom category teks) menjadi category_id + is_active."""
    connection.commit()
    connection.isolation_level = None
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("DROP TABLE IF EXISTS products_new")
    connection.execute(
        "INSERT OR IGNORE INTO categories (name) SELECT DISTINCT category FROM products"
    )
    connection.execute(
        """
        CREATE TABLE products_new (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
            category_id   INTEGER NOT NULL REFERENCES categories(id),
            catalog_price INTEGER NOT NULL CHECK (catalog_price > 0),
            is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
        )
        """
    )
    connection.execute(
        """
        INSERT INTO products_new (id, name, category_id, catalog_price, is_active)
        SELECT id, name,
               (SELECT c.id FROM categories c WHERE c.name = products.category),
               catalog_price, 1
        FROM products
        """
    )
    connection.execute("DROP TABLE products")
    connection.execute("ALTER TABLE products_new RENAME TO products")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.isolation_level = ""
    connection.commit()


def initialize_database():
    """Buat tabel, migrasi skema lama, isi katalog, dan isi transaksi simulasi."""
    with closing(get_connection()) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE
            );

            CREATE TABLE IF NOT EXISTS products (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL UNIQUE COLLATE NOCASE,
                category_id   INTEGER NOT NULL REFERENCES categories(id),
                catalog_price INTEGER NOT NULL CHECK (catalog_price > 0),
                is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1))
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_date TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                unit_price INTEGER NOT NULL CHECK (unit_price > 0),
                quantity INTEGER NOT NULL CHECK (quantity > 0),
                total INTEGER NOT NULL CHECK (total = unit_price * quantity),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            [(name,) for name in SEED_CATEGORIES],
        )
        columns = [row[1] for row in connection.execute("PRAGMA table_info(products)")]
        if "category_id" not in columns:
            migrate_products_to_categories(connection)
        category_ids = dict(
            connection.execute("SELECT name, id FROM categories").fetchall()
        )
        connection.executemany(
            """
            INSERT OR IGNORE INTO products (name, category_id, catalog_price)
            VALUES (?, ?, ?)
            """,
            [
                (name, category_ids[category], price)
                for name, category, price in SEED_PRODUCTS
            ],
        )
        sales_count = connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0]
        if sales_count == 0:
            product_ids = dict(
                connection.execute("SELECT name, id FROM products").fetchall()
            )
            connection.executemany(
                """
                INSERT INTO sales
                    (sale_date, product_id, unit_price, quantity, total)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (sale_date, product_ids[name], price, quantity, price * quantity)
                    for sale_date, name, price, quantity in SEED_SALES
                ],
            )
        connection.commit()


# ==== Helper umum ====
def run_query(sql, params=()):
    """Jalankan query SELECT dan kembalikan hasilnya sebagai tabel DataFrame."""
    with closing(get_connection()) as connection:
        return pd.read_sql_query(sql, connection, params=list(params))


def run_write(sql, params=()):
    """Jalankan query tulis (INSERT/UPDATE/DELETE) lalu simpan perubahan."""
    with closing(get_connection()) as connection:
        connection.execute(sql, list(params))
        connection.commit()


def format_rupiah(value):
    """Ubah angka menjadi teks rupiah, misalnya 1500000 -> Rp1.500.000."""
    return f"Rp{round(value):,}".replace(",", ".")


def to_csv_bytes(table):
    """Ubah DataFrame menjadi isi file CSV yang rapi saat dibuka di Excel."""
    return table.to_csv(index=False, sep=";").encode("utf-8-sig")


def flash(kind, message):
    """Simpan pesan singkat untuk ditampilkan setelah halaman dijalankan ulang."""
    st.session_state["_flash"] = (kind, message)


def show_flash():
    """Tampilkan pesan yang tersimpan dari aksi sebelumnya (sekali pakai)."""
    data = st.session_state.pop("_flash", None)
    if data:
        kind, message = data
        getattr(st, kind)(message)


# ==== Master kategori ====
def get_category_names():
    """Daftar nama kategori untuk pilihan filter laporan."""
    result = run_query("SELECT name FROM categories ORDER BY name")
    return result["name"].tolist()


def get_category_records():
    """Daftar kategori (id dan nama) untuk dropdown form produk."""
    return run_query("SELECT id, name FROM categories ORDER BY name")


def get_category_rows():
    """Daftar kategori beserta jumlah produk yang memakainya."""
    return run_query(
        """
        SELECT
            categories.id AS id,
            categories.name AS nama,
            COUNT(products.id) AS jumlah_produk
        FROM categories
        LEFT JOIN products ON products.category_id = categories.id
        GROUP BY categories.id, categories.name
        ORDER BY categories.name
        """
    )


def category_product_count(category_id):
    """Hitung berapa produk yang memakai sebuah kategori."""
    return int(
        run_query(
            "SELECT COUNT(*) AS n FROM products WHERE category_id = ?", [category_id]
        ).iloc[0]["n"]
    )


def create_category(name):
    """Tambah kategori baru; error bila nama sudah dipakai."""
    run_write("INSERT INTO categories (name) VALUES (?)", [name.strip()])


def update_category(category_id, name):
    """Ubah nama kategori."""
    run_write(
        "UPDATE categories SET name = ? WHERE id = ?", [name.strip(), category_id]
    )


def delete_category(category_id):
    """Hapus kategori (hanya bila tidak dipakai produk)."""
    run_write("DELETE FROM categories WHERE id = ?", [category_id])


# ==== Master produk ====
def get_products(include_inactive=False):
    """Daftar produk beserta nama kategori dan status aktifnya."""
    active_filter = "" if include_inactive else "WHERE products.is_active = 1"
    return run_query(
        f"""
        SELECT
            products.id AS id,
            products.name AS nama,
            categories.name AS kategori,
            products.category_id AS category_id,
            products.catalog_price AS harga_katalog,
            products.is_active AS is_active,
            CASE WHEN products.is_active = 1 THEN 'Aktif' ELSE 'Nonaktif' END AS status
        {PRODUCTS_JOIN_SQL}
        {active_filter}
        ORDER BY products.name
        """
    )


def create_product(name, category_id, catalog_price):
    """Tambah produk baru; error bila nama sudah dipakai."""
    run_write(
        "INSERT INTO products (name, category_id, catalog_price) VALUES (?, ?, ?)",
        [name.strip(), category_id, int(catalog_price)],
    )


def update_product(product_id, name, category_id, catalog_price):
    """Ubah data produk."""
    run_write(
        """
        UPDATE products
        SET name = ?, category_id = ?, catalog_price = ?
        WHERE id = ?
        """,
        [name.strip(), category_id, int(catalog_price), product_id],
    )


def set_product_active(product_id, is_active):
    """Aktifkan atau nonaktifkan produk (soft delete)."""
    run_write(
        "UPDATE products SET is_active = ? WHERE id = ?",
        [1 if is_active else 0, product_id],
    )


def product_sales_count(product_id):
    """Hitung berapa transaksi yang memakai sebuah produk."""
    return int(
        run_query(
            "SELECT COUNT(*) AS n FROM sales WHERE product_id = ?", [product_id]
        ).iloc[0]["n"]
    )


def delete_product(product_id):
    """Hapus produk secara permanen (hanya bila belum punya transaksi)."""
    run_write("DELETE FROM products WHERE id = ?", [product_id])


# ==== Query laporan ====
def get_date_bounds():
    """Ambil tanggal transaksi pertama dan terakhir sebagai periode bawaan."""
    result = run_query(
        "SELECT MIN(sale_date) AS first_date, MAX(sale_date) AS last_date FROM sales"
    )
    first_date, last_date = result.iloc[0]
    if first_date is None:
        return date.today(), date.today()
    return date.fromisoformat(first_date), date.fromisoformat(last_date)


def build_filter(start_date, end_date, categories):
    """Susun bagian WHERE dan nilai parameternya dari pilihan filter."""
    placeholders = ", ".join("?" for _ in categories)
    where_sql = (
        "WHERE sales.sale_date BETWEEN ? AND ? "
        f"AND categories.name IN ({placeholders})"
    )
    params = [start_date.isoformat(), end_date.isoformat(), *categories]
    return where_sql, params


def get_summary(where_sql, params):
    """Hitung angka ringkasan untuk semua transaksi yang lolos filter."""
    result = run_query(
        f"""
        SELECT
            COUNT(*) AS jumlah_transaksi,
            COALESCE(SUM(sales.quantity), 0) AS unit_terjual,
            COALESCE(SUM(sales.total), 0) AS omzet,
            COALESCE(AVG(sales.total), 0) AS rata_rata,
            COALESCE(MAX(sales.total), 0) AS transaksi_terbesar
        {JOIN_SQL}
        {where_sql}
        """,
        params,
    )
    return result.iloc[0]


def get_report_by_product(where_sql, params, min_revenue):
    """Laporan per produk; HAVING menyaring produk dengan omzet kecil."""
    return run_query(
        f"""
        SELECT
            products.name AS produk,
            categories.name AS kategori,
            COUNT(*) AS jumlah_transaksi,
            SUM(sales.quantity) AS unit_terjual,
            SUM(sales.total) AS omzet
        {JOIN_SQL}
        {where_sql}
        GROUP BY products.id, products.name, categories.name
        HAVING SUM(sales.total) >= ?
        ORDER BY omzet DESC, produk
        """,
        [*params, min_revenue],
    )


def get_report_by_category(where_sql, params):
    """Laporan per kategori produk."""
    return run_query(
        f"""
        SELECT
            categories.name AS kategori,
            COUNT(*) AS jumlah_transaksi,
            SUM(sales.quantity) AS unit_terjual,
            SUM(sales.total) AS omzet
        {JOIN_SQL}
        {where_sql}
        GROUP BY categories.id, categories.name
        ORDER BY omzet DESC
        """,
        params,
    )


def get_report_by_month(where_sql, params):
    """Laporan per bulan; strftime mengambil tahun-bulan dari tanggal."""
    return run_query(
        f"""
        SELECT
            strftime('%Y-%m', sales.sale_date) AS bulan,
            COUNT(*) AS jumlah_transaksi,
            SUM(sales.quantity) AS unit_terjual,
            SUM(sales.total) AS omzet
        {JOIN_SQL}
        {where_sql}
        GROUP BY bulan
        ORDER BY bulan
        """,
        params,
    )


def get_sales_detail(where_sql, params):
    """Data detail (baris per transaksi) untuk menelusuri angka laporan."""
    return run_query(
        f"""
        SELECT
            sales.id AS nomor,
            sales.sale_date AS tanggal,
            products.name AS produk,
            categories.name AS kategori,
            sales.unit_price AS harga_satuan,
            sales.quantity AS jumlah,
            sales.total AS total
        {JOIN_SQL}
        {where_sql}
        ORDER BY sales.sale_date, sales.id
        """,
        params,
    )


# ==== Tampilan laporan ====
COLUMN_CONFIG = {
    "nomor": st.column_config.NumberColumn("No."),
    "tanggal": st.column_config.TextColumn("Tanggal"),
    "bulan": st.column_config.TextColumn("Bulan"),
    "produk": st.column_config.TextColumn("Produk"),
    "kategori": st.column_config.TextColumn("Kategori"),
    "jumlah_transaksi": st.column_config.NumberColumn("Jumlah transaksi"),
    "unit_terjual": st.column_config.NumberColumn("Unit terjual"),
    "jumlah": st.column_config.NumberColumn("Jumlah unit"),
    "harga_satuan": st.column_config.NumberColumn(
        "Harga satuan (Rp)", format="localized"
    ),
    "total": st.column_config.NumberColumn("Total (Rp)", format="localized"),
    "omzet": st.column_config.NumberColumn("Omzet (Rp)", format="localized"),
    "nama": st.column_config.TextColumn("Nama"),
    "harga_katalog": st.column_config.NumberColumn(
        "Harga katalog (Rp)", format="localized"
    ),
    "status": st.column_config.TextColumn("Status"),
    "jumlah_produk": st.column_config.NumberColumn("Jumlah produk"),
}


def show_report(table, file_stem, start_date, end_date):
    """Tampilkan tabel laporan beserta tombol unduh CSV-nya."""
    if table.empty:
        st.info("Tidak ada baris laporan untuk filter ini.")
        return False

    st.dataframe(
        table,
        column_config=COLUMN_CONFIG,
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "Unduh CSV",
        data=to_csv_bytes(table),
        file_name=f"{file_stem}_{start_date}_{end_date}.csv",
        mime="text/csv",
        key=f"download_{file_stem}",
    )
    return True


def render_report_page():
    """Halaman laporan penjualan beserta filter dan ekspor CSV."""
    first_date, last_date = get_date_bounds()
    categories = get_category_names()

    with st.sidebar:
        st.header("Filter laporan")
        period = st.date_input(
            "Periode",
            value=(first_date, last_date),
            format="DD/MM/YYYY",
        )
        selected_categories = st.multiselect(
            "Kategori", options=categories, default=categories
        )
        min_revenue = st.slider(
            "Omzet minimum per produk (Rp)",
            min_value=0,
            max_value=500000,
            value=0,
            step=25000,
        )

    if len(period) != 2:
        st.info("Pilih tanggal awal dan tanggal akhir periode di sidebar.")
        st.stop()
    if not selected_categories:
        st.warning("Pilih minimal satu kategori di sidebar.")
        st.stop()

    start_date, end_date = period
    where_sql, params = build_filter(start_date, end_date, selected_categories)
    summary = get_summary(where_sql, params)

    st.subheader(f"Ringkasan {start_date:%d/%m/%Y} – {end_date:%d/%m/%Y}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Omzet", format_rupiah(summary["omzet"]))
    col2.metric("Jumlah transaksi", int(summary["jumlah_transaksi"]))
    col3.metric("Rata-rata per transaksi", format_rupiah(summary["rata_rata"]))
    col4.metric("Transaksi terbesar", format_rupiah(summary["transaksi_terbesar"]))

    if summary["jumlah_transaksi"] == 0:
        st.info("Tidak ada transaksi pada periode dan kategori ini.")
        st.stop()

    by_product = get_report_by_product(where_sql, params, min_revenue)
    by_category = get_report_by_category(where_sql, params)
    by_month = get_report_by_month(where_sql, params)
    detail = get_sales_detail(where_sql, params)

    tab_product, tab_category, tab_month, tab_detail = st.tabs(
        ["Per Produk", "Per Kategori", "Per Bulan", "Detail Transaksi"]
    )

    with tab_product:
        st.caption(f"Produk dengan omzet minimal {format_rupiah(min_revenue)}.")
        if show_report(by_product, "laporan-produk", start_date, end_date):
            st.bar_chart(
                by_product,
                x="produk",
                y="omzet",
                x_label="Produk",
                y_label="Omzet (Rp)",
                sort="-omzet",
                horizontal=True,
            )

    with tab_category:
        if show_report(by_category, "laporan-kategori", start_date, end_date):
            st.bar_chart(
                by_category,
                x="kategori",
                y="omzet",
                x_label="Kategori",
                y_label="Omzet (Rp)",
                sort="-omzet",
                horizontal=True,
            )

    with tab_month:
        if show_report(by_month, "laporan-bulanan", start_date, end_date):
            st.line_chart(
                by_month, x="bulan", y="omzet", x_label="Bulan", y_label="Omzet (Rp)"
            )

    with tab_detail:
        show_report(detail, "detail-transaksi", start_date, end_date)

    with st.expander("Cek kecocokan angka"):
        checks = {
            "Kartu Omzet": summary["omzet"],
            "Total tab Per Kategori": by_category["omzet"].sum(),
            "Total tab Per Bulan": by_month["omzet"].sum(),
            "Total tab Detail": detail["total"].sum(),
        }
        for label, value in checks.items():
            st.write(f"{label}: {format_rupiah(value)}")
        if len(set(checks.values())) == 1:
            st.success("Semua total cocok. Laporan dapat ditelusuri ke data detail.")
        else:
            st.error("Ada total yang berbeda. Periksa query laporan.")
        st.caption(
            "Total tab Per Produk bisa lebih kecil jika omzet minimum di atas 0, "
            f"karena HAVING menyaring produk. Saat ini: "
            f"{format_rupiah(by_product['omzet'].sum())}."
        )


# ==== Tampilan kelola produk dan kategori ====
def render_product_tab():
    """Form dan tabel pengelolaan produk."""
    records = get_category_records()
    category_ids = records["id"].tolist()
    category_names = dict(zip(records["id"], records["name"]))

    st.subheader("Tambah produk")
    if not category_ids:
        st.warning("Belum ada kategori. Tambahkan kategori lebih dulu di tab Kategori.")
    else:
        with st.form("form_tambah_produk", clear_on_submit=True):
            new_name = st.text_input("Nama produk")
            new_category = st.selectbox(
                "Kategori",
                options=category_ids,
                format_func=lambda cid: category_names.get(cid, "—"),
            )
            new_price = st.number_input(
                "Harga katalog (Rp)", min_value=1, step=500, value=10000
            )
            submit_new = st.form_submit_button("Tambah produk")
        if submit_new:
            if not new_name.strip():
                st.error("Nama produk tidak boleh kosong.")
            else:
                try:
                    create_product(new_name, new_category, new_price)
                    flash("success", f"Produk '{new_name.strip()}' ditambahkan.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Nama produk sudah dipakai.")

    st.subheader("Daftar produk")
    products = get_products(include_inactive=True)
    if products.empty:
        st.info("Belum ada produk.")
        return

    st.dataframe(
        products[["nama", "kategori", "harga_katalog", "status"]],
        column_config=COLUMN_CONFIG,
        hide_index=True,
        width="stretch",
    )

    st.subheader("Ubah produk")
    product_ids = products["id"].tolist()
    labels = {
        row["id"]: f"{row['nama']} — {row['kategori']}" for _, row in products.iterrows()
    }
    selected = st.selectbox(
        "Pilih produk",
        options=product_ids,
        format_func=lambda pid: labels.get(pid, str(pid)),
        key="produk_dipilih",
    )
    row = products[products["id"] == selected].iloc[0]

    with st.form("form_ubah_produk"):
        edit_name = st.text_input("Nama produk", value=row["nama"])
        edit_category = st.selectbox(
            "Kategori",
            options=category_ids,
            index=category_ids.index(row["category_id"])
            if row["category_id"] in category_ids
            else 0,
            format_func=lambda cid: category_names.get(cid, "—"),
        )
        edit_price = st.number_input(
            "Harga katalog (Rp)",
            min_value=1,
            step=500,
            value=int(row["harga_katalog"]),
        )
        submit_edit = st.form_submit_button("Simpan perubahan")
    if submit_edit:
        if not edit_name.strip():
            st.error("Nama produk tidak boleh kosong.")
        else:
            try:
                update_product(selected, edit_name, edit_category, edit_price)
                flash("success", f"Produk '{edit_name.strip()}' diperbarui.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Nama produk sudah dipakai.")

    col_active, col_delete = st.columns(2)
    is_active = bool(row["is_active"])
    toggle_label = "Nonaktifkan produk" if is_active else "Aktifkan produk"
    if col_active.button(toggle_label, key="produk_toggle"):
        set_product_active(selected, not is_active)
        flash(
            "success",
            f"Produk '{row['nama']}' {'dinonaktifkan' if is_active else 'diaktifkan'}.",
        )
        st.rerun()

    sales_count = product_sales_count(selected)
    if col_delete.button("Hapus produk", key="produk_hapus"):
        if sales_count > 0:
            st.error(
                f"'{row['nama']}' punya {sales_count} transaksi, tidak bisa dihapus. "
                "Gunakan Nonaktifkan agar riwayat penjualan tetap utuh."
            )
        else:
            delete_product(selected)
            flash("success", f"Produk '{row['nama']}' dihapus.")
            st.rerun()
    if sales_count > 0:
        st.caption(
            f"'{row['nama']}' dipakai di {sales_count} transaksi, jadi hanya bisa "
            "dinonaktifkan."
        )


def render_category_tab():
    """Form dan tabel pengelolaan kategori."""
    st.subheader("Tambah kategori")
    with st.form("form_tambah_kategori", clear_on_submit=True):
        new_name = st.text_input("Nama kategori")
        submit_new = st.form_submit_button("Tambah kategori")
    if submit_new:
        if not new_name.strip():
            st.error("Nama kategori tidak boleh kosong.")
        else:
            try:
                create_category(new_name)
                flash("success", f"Kategori '{new_name.strip()}' ditambahkan.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Nama kategori sudah dipakai.")

    st.subheader("Daftar kategori")
    rows = get_category_rows()
    st.dataframe(
        rows[["nama", "jumlah_produk"]],
        column_config=COLUMN_CONFIG,
        hide_index=True,
        width="stretch",
    )

    st.subheader("Ubah kategori")
    category_ids = rows["id"].tolist()
    labels = {row["id"]: row["nama"] for _, row in rows.iterrows()}
    selected = st.selectbox(
        "Pilih kategori",
        options=category_ids,
        format_func=lambda cid: labels.get(cid, str(cid)),
        key="kategori_dipilih",
    )
    row = rows[rows["id"] == selected].iloc[0]

    with st.form("form_ubah_kategori"):
        edit_name = st.text_input("Nama kategori", value=row["nama"])
        submit_edit = st.form_submit_button("Simpan perubahan")
    if submit_edit:
        if not edit_name.strip():
            st.error("Nama kategori tidak boleh kosong.")
        else:
            try:
                update_category(selected, edit_name)
                flash("success", f"Kategori diubah menjadi '{edit_name.strip()}'.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Nama kategori sudah dipakai.")

    product_count = int(row["jumlah_produk"])
    if st.button("Hapus kategori", key="kategori_hapus"):
        if product_count > 0:
            st.error(
                f"'{row['nama']}' dipakai oleh {product_count} produk, tidak bisa "
                "dihapus."
            )
        else:
            delete_category(selected)
            flash("success", f"Kategori '{row['nama']}' dihapus.")
            st.rerun()
    if product_count > 0:
        st.caption(f"'{row['nama']}' dipakai oleh {product_count} produk.")


def render_management_page():
    """Halaman pengelolaan data master: produk dan kategori."""
    st.subheader("Kelola Produk dan Kategori")
    tab_product, tab_category = st.tabs(["Produk", "Kategori"])
    with tab_product:
        render_product_tab()
    with tab_category:
        render_category_tab()


def main():
    st.set_page_config(page_title="Kedai Rasa — Minggu 6", layout="wide")
    st.title("Laporan Penjualan Kedai Rasa")
    st.caption("Latihan Minggu 6. Semua angka berasal dari data simulasi.")

    initialize_database()
    show_flash()

    page = st.sidebar.radio("Halaman", ["Laporan Penjualan", "Kelola Produk"])
    if page == "Laporan Penjualan":
        render_report_page()
    else:
        render_management_page()


if __name__ == "__main__":
    main()
