# ===============================
# IMPORTAÇÕES
# ===============================

from flask import Flask, render_template, request, redirect, send_file
import sqlite3
from datetime import datetime
import pandas as pd
import os

# biblioteca para gerar PDF
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas

app = Flask(__name__)


# ===============================
# CONEXÃO COM BANCO
# ===============================

def conectar():
    return sqlite3.connect("database.db")


# ===============================
# CRIAR TABELAS
# ===============================

def criar_tabelas():

    conn = conectar()
    cursor = conn.cursor()

    # tabela principal de registros
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS conferencias (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vin TEXT UNIQUE,
        modelo TEXT,
        lote TEXT,
        cor TEXT,
        sap TEXT,
        status TEXT,
        conferente TEXT,
        data_hora TEXT
    )
    """)

    # tabela para meta do dia
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config_dia (
        data TEXT PRIMARY KEY,
        meta INTEGER,
        lider TEXT,
        suporte TEXT
    )
    """)

    conn.commit()
    conn.close()


# ===============================
# VALIDAÇÃO DE VIN
# ===============================

def validar_vin(vin):

    # VIN precisa ter 17 caracteres alfanuméricos
    return len(vin) == 17 and vin.isalnum()


# ===============================
# TELA PRINCIPAL
# ===============================

@app.route("/", methods=["GET", "POST"])
def index():

    erro = None

    # ---------------------------
    # RECEBER FORMULÁRIO
    # ---------------------------

    if request.method == "POST":

        vin = request.form["vin"].upper().strip()
        modelo = request.form["modelo"]
        lote = request.form["lote"]
        cor = request.form["cor"]
        sap = request.form["sap"]
        conferente = request.form["conferente"]

        status = "OK"

        data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        # valida VIN
        if not validar_vin(vin):

            erro = "VIN inválido!"

        else:

            try:

                conn = conectar()
                cursor = conn.cursor()

                # salva no banco
                cursor.execute("""
                INSERT INTO conferencias
                (vin, modelo, lote, cor, sap, status, conferente, data_hora)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (vin, modelo, lote, cor, sap, status, conferente, data_hora))

                conn.commit()
                conn.close()

                return redirect("/")

            except sqlite3.IntegrityError:

                erro = "VIN já registrado!"


    # ---------------------------
    # CONTADOR DE VINS DO DIA
    # ---------------------------

    conn = conectar()

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    df = pd.read_sql_query("SELECT * FROM conferencias", conn)

    conn.close()

    df = df[df["data_hora"].str.contains(data_hoje)]

    total_vins = len(df)

    return render_template("index.html", erro=erro, total_vins=total_vins)


# ===============================
# CONFIGURAÇÃO DO DIA
# ===============================

@app.route("/config", methods=["GET", "POST"])
def config():

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    if request.method == "POST":

        meta = request.form["meta"]
        lider = request.form["lider"]
        suporte = request.form["suporte"]

        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("""
        INSERT OR REPLACE INTO config_dia (data, meta, lider, suporte)
        VALUES (?, ?, ?, ?)
        """, (data_hoje, meta, lider, suporte))

        conn.commit()
        conn.close()

        return redirect("/")

    return render_template("config.html", data=data_hoje)


# ===============================
# DASHBOARD
# ===============================

@app.route("/dashboard")
def dashboard():

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()

    df = pd.read_sql_query("SELECT * FROM conferencias", conn)

    conn.close()

    df = df[df["data_hora"].str.contains(data_hoje)]

    total = len(df)

    return render_template("dashboard.html", total=total)


# ===============================
# RELATÓRIO DE FECHAMENTO
# ===============================

@app.route("/relatorio")
def relatorio():

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()

    # buscar configuração do dia
    config = pd.read_sql_query(
        "SELECT * FROM config_dia WHERE data=?", conn, params=[data_hoje]
    )

    if len(config) > 0:

        meta = int(config["meta"][0])
        lider = config["lider"][0]
        suporte = config["suporte"][0]

    else:

        meta = 0
        lider = "-"
        suporte = "-"

    # dados do dia
    df = pd.read_sql_query("SELECT * FROM conferencias", conn)

    conn.close()

    df = df[df["data_hora"].str.contains(data_hoje)]

    total = len(df)

    atingimento = (total / meta * 100) if meta > 0 else 0

    agrupado = df.groupby(["modelo", "sap", "cor"]).size().reset_index(name="qtd")

    # criar PDF
    nome_pdf = "Report_Fechamento.pdf"

    doc = SimpleDocTemplate(nome_pdf, pagesize=A4)

    elementos = []

    styles = getSampleStyleSheet()

    elementos.append(Paragraph(f"Report de Fechamento – {data_hoje}", styles["Title"]))
    elementos.append(Paragraph(f"Líder: {lider}", styles["Normal"]))
    elementos.append(Paragraph(f"Suporte: {suporte}", styles["Normal"]))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph(f"Meta do dia: {meta} UND", styles["Normal"]))
    elementos.append(Paragraph(f"Total entregue: {total} UND", styles["Normal"]))
    elementos.append(Paragraph(f"Atingimento: {atingimento:.2f}%", styles["Normal"]))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("Detalhamento:", styles["Heading3"]))

    for _, row in agrupado.iterrows():

        texto = f"{row['modelo']} | SAP {row['sap']} | {row['cor']} — {row['qtd']} UND"

        elementos.append(Paragraph(texto, styles["Normal"]))

    doc.build(elementos)

    return send_file(nome_pdf, as_attachment=True)


# ===============================
# PDF COM LISTA DE VINS
# ===============================

@app.route("/baixar_pdf_vins")
def baixar_pdf_vins():

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    conn = conectar()

    cursor = conn.cursor()

    cursor.execute("""
    SELECT vin FROM conferencias
    WHERE data_hora LIKE ?
    """, (f"%{data_hoje}%",))

    dados = cursor.fetchall()

    conn.close()

    arquivo = "vins_do_dia.pdf"

    c = canvas.Canvas(arquivo, pagesize=letter)

    y = 750

    c.drawString(50, y, f"VINs do dia - {data_hoje}")

    y -= 20

    for registro in dados:

        c.drawString(60, y, registro[0])

        y -= 12

        if y < 50:

            c.showPage()
            y = 750

    c.save()

    return send_file(arquivo, as_attachment=True)


# ===============================
# EXPORTAR PLANILHA EXCEL
# ===============================

@app.route("/exportar_planilha")
def exportar_planilha():

    conn = conectar()

    df = pd.read_sql_query("SELECT * FROM conferencias", conn)

    conn.close()

    hoje = datetime.now().strftime("%d-%m-%Y")

    nome_arquivo = f"Relatorio_VINs_{hoje}.xlsx"

    df.to_excel(nome_arquivo, index=False)

    return send_file(nome_arquivo, as_attachment=True)


# ===============================
# RESETAR REGISTROS DO DIA
# ===============================

@app.route("/resetar_dia")
def resetar_dia():

    conn = conectar()
    
    try:
        cursor = conn.cursor()

        # Apaga todos os registros
        cursor.execute("DELETE FROM conferencias")

        conn.commit()

    finally:
        # Sempre fecha a conexão
        conn.close()

    return redirect("/")


# ===============================
# INICIAR SISTEMA
# ===============================

if __name__ == "__main__":

    criar_tabelas()

    app.run(host="0.0.0.0", port=5000, debug=True)