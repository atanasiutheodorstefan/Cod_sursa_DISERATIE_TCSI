import sqlite3
import numpy as np
import os
import webbrowser
import tkinter as tk
from tkinter import messagebox, ttk
from Pyfhel import Pyfhel, PyCtxt
import threading
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

SERVER_PORT = 8765

# ===========SERVER HTTP LOCAL=========================================
class ArchiveHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/archive':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                cnp = data.get('cnp')
                if cnp:
                    conn = sqlite3.connect('baza_date_Z.db')
                    conn.execute("UPDATE DosareMedicale SET status='Arhivat' WHERE cnp=?", (cnp,))
                    conn.commit()
                    conn.close()
                self._respond(200, {"ok": True})
            except Exception as e:
                self._respond(500, {"ok": False, "error": str(e)})
        else:
            self._respond(404, {"ok": False})

    def _respond(self, code, data):
        body = json.dumps(data).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)


def start_http_server():
    server = HTTPServer(('localhost', SERVER_PORT), ArchiveHandler)
    server.serve_forever()


# ==================================MOTORUL CRIPTOGRAFIC (FHE)==========================================
class MedicalFHE:
    def __init__(self):
        self.HE = Pyfhel()
        if not os.path.exists("context.hctx"):
            self.HE.contextGen(scheme='BFV', n=8192, t=65537, t_bits=20, sec=128)
            self.HE.keyGen()
            self.HE.save_context("context.hctx")
            self.HE.save_public_key("public.hkey")
            self.HE.save_secret_key("secret.hkey")
        else:
            self.HE.load_context("context.hctx")
            self.HE.load_public_key("public.hkey")
            self.HE.load_secret_key("secret.hkey")

    def criptare(self, v, t, g):
        cv = self.HE.encryptInt(np.array([v], dtype=np.int64))
        ct = self.HE.encryptInt(np.array([t], dtype=np.int64))
        cg = self.HE.encryptInt(np.array([g], dtype=np.int64))
        return cv.to_bytes(), ct.to_bytes(), cg.to_bytes()

    def decriptare(self, blob):
        ctxt = PyCtxt(pyfhel=self.HE)
        ctxt.from_bytes(blob)
        return self.HE.decryptInt(ctxt)[0]


# ==========================================INTERFAȚA====================================
class MedicalApp:
    def __init__(self, root):
        self.fhe = MedicalFHE()
        self.root = root
        self.root.title("Portal Medical Securizat")
        self.root.geometry("520x780")
        self.root.configure(bg="#f4f7f6")
        self.init_db()
        self.setup_ui()

    def init_db(self):

        conn = sqlite3.connect('baza_date_Z.db')

        # Creăm tabelul cu status Implicit 'Activ'

        conn.execute("""CREATE TABLE IF NOT EXISTS DosareMedicale (

            cnp TEXT PRIMARY KEY, nume TEXT, dn TEXT, v_FHE BLOB, 

            loc TEXT, t_FHE BLOB, g_FHE BLOB, hist TEXT, status TEXT DEFAULT 'Activ')""")

        conn.close()

    def setup_ui(self):
        canvas = tk.Canvas(self.root, bg="#f4f7f6", highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.container = tk.Frame(canvas, bg="#f4f7f6")
        self.container.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.container, anchor="nw", width=490)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        header = tk.Frame(self.container, bg="#2c3e50", height=70)
        header.pack(fill="x")
        tk.Label(header, text="ADMINISTRARE DATE MEDICALE", font=("Segoe UI", 11, "bold"),
                 fg="white", bg="#2c3e50").pack(pady=20)

        form = tk.Frame(self.container, bg="#f4f7f6", padx=30, pady=10)
        form.pack(fill="x")

        self.inputs = {}
        fields = [("CNP", "cnp"), ("Nume Complet", "nume"), ("Data Nașterii", "dn"),
                  ("Localitate", "loc"), ("Vârstă", "v"), ("Tensiune", "t"), ("Glicemie", "g")]

        for label, key in fields:
            tk.Label(form, text=label, font=("Segoe UI", 9, "bold"),
                     bg="#f4f7f6", fg="#7f8c8d").pack(anchor="w")
            self.inputs[key] = tk.Entry(form, font=("Segoe UI", 10), bd=1, relief="solid")
            self.inputs[key].pack(fill="x", pady=(0, 8), ipady=4)

        tk.Label(form, text="Tip Vizită", font=("Segoe UI", 9, "bold"),
                 bg="#f4f7f6", fg="#7f8c8d").pack(anchor="w")
        self.combo_hist = ttk.Combobox(form,
                                       values=["Consultație inițială", "Control de rutină", "Pacient nou"],
                                       state="readonly")
        self.combo_hist.set("Consultație inițială")
        self.combo_hist.pack(fill="x", pady=(0, 15), ipady=4)

        tk.Button(form, text="💾 SALVEAZĂ/ACTUALIZEAZĂ PACIENT", command=self.save_data,
                  bg="#27ae60", fg="white", font=("Segoe UI", 10, "bold"), height=2).pack(fill="x", pady=5)
        tk.Button(form, text="📂 VEZI PACIENȚI ACTIVI",
                  command=lambda: self.open_dashboard("Activ"),
                  bg="#2980b9", fg="white", font=("Segoe UI", 10, "bold"), height=2).pack(fill="x", pady=5)
        tk.Button(form, text="📜 VEZI ARHIVĂ",
                  command=lambda: self.open_dashboard("Arhivat"),
                  bg="#7f8c8d", fg="white", font=("Segoe UI", 10, "bold"), height=2).pack(fill="x", pady=5)

        tk.Label(form, text="──────────────────────────", bg="#f4f7f6", fg="#bdc3c7").pack(pady=15)
        tk.Label(form, text="ȘTERGERE DEFINITIVĂ DIN SQLITE",
                 font=("Segoe UI", 8, "bold"), bg="#f4f7f6", fg="#e74c3c").pack(anchor="w")
        self.entry_del = tk.Entry(form, font=("Segoe UI", 10), bd=1, relief="solid")
        self.entry_del.pack(fill="x", pady=5, ipady=4)
        tk.Button(form, text="🔥 ȘTERGE DIN BD", command=self.delete_from_db,
                  bg="#e74c3c", fg="white", font=("Segoe UI", 9, "bold")).pack(fill="x", pady=5)

    def save_data(self):
        try:
            d = {k: v.get() for k, v in self.inputs.items()}
            bv, bt, bg = self.fhe.criptare(int(d['v']), int(d['t']), int(d['g']))
            conn = sqlite3.connect('baza_date_Z.db')
            conn.execute(
                "INSERT OR REPLACE INTO DosareMedicale "
                "(cnp, nume_prenume, data_nasterii, varsta_FHE, localitate, "
                "tensiune_FHE, glicemie_FHE, istoric_html, status) "
                "VALUES (?,?,?,?,?,?,?,?,'Activ')",
            )
            conn.commit()
            conn.close()
            messagebox.showinfo("Succes", "Pacient salvat. Baza de date a fost actualizată.")
        except Exception as e:
            messagebox.showerror("Eroare", f"Date invalide! {e}")

    def delete_from_db(self):
        cnp = self.entry_del.get().strip()
        if not cnp:
            return
        conn = sqlite3.connect('baza_date_Z.db')
        conn.execute("DELETE FROM DosareMedicale WHERE cnp=?", (cnp,))
        conn.commit()
        conn.close()
        messagebox.showinfo("OK", "Rândul a fost eliminat fizic din SQLite.")

    def open_dashboard(self, status_filter):
        conn = sqlite3.connect('baza_date_Z.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM DosareMedicale WHERE status=?", (status_filter,))
        rows = cursor.fetchall()
        conn.close()
        self.generate_web_view(rows, status_filter)

    def generate_web_view(self, rows, mode):
        # Ordinea coloanelor din BD:
        # 0:cnp, 1:nume_prenume, 2:data_nasterii, 3:varsta_FHE,
        # 4:localitate, 5:tensiune_FHE, 6:glicemie_FHE, 7:istoric_html, 8:status
        color = "#2980b9" if mode == "Activ" else "#7f8c8d"
        html_cards = ""

        for r in rows:
            v = self.fhe.decriptare(r[3])
            t = self.fhe.decriptare(r[5])
            g = self.fhe.decriptare(r[6])

            btn_arch = (
                f'<button class="btn-archive" onclick="archivePatient(\'{r[0]}\')">ARHIVARE PACIENT</button>'
                if mode == "Activ" else ""
            )

            html_cards += f"""
                <div class="card" id="card-{r[0]}" data-name="{r[1].lower()}">
                    <h2 style="margin:0; color:#2c3e50;">{r[1]}</h2>
                    <p><b>CNP:</b> {r[0]} | <b>Născut:</b> {r[2]} | <b>Localitate:</b> {r[4]}</p>
                    <div class="vital-grid">
                        <div class="vital-item"><b>Vârstă:</b> {v}</div>
                        <div class="vital-item"><b>Tensiune:</b> {t} mmHg</div>
                        <div class="vital-item"><b>Glicemie:</b> {g} mg/dL</div>
                    </div>
                    <div class="hist">Istoric: {r[7]}</div>
                    <div class="button-group">
                        {btn_arch}
                        <button class="btn-delete" onclick="deleteLocal('{r[0]}')">ȘTERGERE PACIENT</button>
                    </div>
                </div>"""

        html = f"""
        <html><head><meta charset="UTF-8">
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #f0f2f5; padding: 20px; }}
            .container {{ max-width: 850px; margin: auto; }}
            .search-bar {{ width: 100%; padding: 15px; border-radius: 30px; border: 1px solid #ddd;
                           margin-bottom: 25px; font-size: 16px; outline: none; box-sizing: border-box; }}
            .card {{ background: white; border-radius: 12px; padding: 25px; margin-bottom: 20px;
                     box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-left: 8px solid {color}; }}
            .vital-grid {{ display: flex; gap: 10px; margin: 15px 0; }}
            .vital-item {{ flex: 1; background: #f8f9fa; padding: 10px; border-radius: 8px;
                           text-align: center; border: 1px solid #eee; }}
            .button-group {{ display: flex; gap: 10px; }}
            .button-group button {{ flex: 1; border: none; padding: 12px; border-radius: 8px;
                                    cursor: pointer; font-weight: bold; color: white; }}
            .btn-archive {{ background: #f39c12; }}
            .btn-delete  {{ background: #e74c3c; }}
            .toast {{ position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
                      background: #27ae60; color: white; padding: 12px 28px; border-radius: 20px;
                      font-weight: bold; display: none; z-index: 999; }}
        </style>
        <script>
            const API = 'http://localhost:{SERVER_PORT}';

            async function archivePatient(cnp) {{
                if (!confirm("Mutați pacientul în Arhivă?")) return;
                try {{
                    const resp = await fetch(API + '/archive', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/json' }},
                        body: JSON.stringify({{ cnp: cnp }})
                    }});
                    const data = await resp.json();
                    if (data.ok) {{
                        document.getElementById('card-' + cnp).style.display = 'none';
                        showToast("✅ Pacient arhivat! Apasă 'VEZI ARHIVĂ' din aplicație.");
                    }} else {{
                        alert("Eroare la arhivare.");
                    }}
                }} catch(e) {{
                    alert("Nu s-a putut contacta serverul local.\\nAsigură-te că aplicația Python rulează.");
                }}
            }}

            function deleteLocal(cnp) {{
                document.getElementById('card-' + cnp).style.display = 'none';
            }}

            function filter() {{
                let val = document.getElementById('search').value.toLowerCase();
                document.querySelectorAll('.card').forEach(c => {{
                    c.style.display = c.dataset.name.includes(val) ? '' : 'none';
                }});
            }}

            function showToast(msg) {{
                const t = document.getElementById('toast');
                t.innerText = msg;
                t.style.display = 'block';
                setTimeout(() => t.style.display = 'none', 4000);
            }}
        </script>
        </head>
        <body>
        <div class="toast" id="toast"></div>
        <div class="container">
            <h1 style="color:{color}; border-bottom: 3px solid {color}; padding-bottom:10px;">
                📋 TABLOU: {mode.upper()}
            </h1>
            <input type="text" id="search" class="search-bar"
                   placeholder="🔍 Caută pacient..." onkeyup="filter()">
            {html_cards}
        </div>
        </body></html>"""

        path = os.path.abspath("Portal_Medical.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        webbrowser.open("file://" + path)


if __name__ == "__main__":
    # Pornim serverul HTTP în background
    t = threading.Thread(target=start_http_server, daemon=True)
    t.start()

    root = tk.Tk()
    app = MedicalApp(root)
    root.mainloop()