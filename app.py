# ===============================
# IMPORTAÇÕES
# ===============================

from flask import Flask, render_template, request, redirect, send_file, flash
import sqlite3
from datetime import datetime
import pandas as pd
import os
import logging

# Configurar logging para registrar erros
logging.basicConfig(filename='app.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

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
    return sqlite3.connect("database.db", isolation_level=None)  # autocommit


# ===============================
# CRIAR TABELAS
# ===============================

def criar_tabelas():
    try:
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

        # Índices para melhorar desempenho
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_data_hora ON conferencias(data_hora)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vin ON conferencias(vin)")

        conn.commit()
    except sqlite3.Error as e:
        logging.error(f"Erro ao criar tabelas: {e}")
    finally:
        if conn:
            conn.close()


# ===============================
# VALIDAÇÃO DE VIN
# ===============================

def validar_vin(vin):
    try:
        # VIN precisa ter 17 caracteres alfanuméricos
        return len(vin) == 17 and vin.isalnum()
    except Exception as e:
        logging.error(f"Erro ao validar VIN: {e}")
        return False


# ===============================
# TELA PRINCIPAL
# ===============================

@app.route("/", methods=["GET", "POST"])
def index():
    erro = None

    try:
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
                except sqlite3.IntegrityError:
                    erro = "VIN já registrado!"
                except sqlite3.Error as e:
                    logging.error(f"Erro ao inserir registro: {e}")
                    erro = "Erro ao salvar no banco de dados."
                finally:
                    if conn:
                        conn.close()

                if erro is None:
                    flash(f"Lote {lote} - SAP {sap or 'N/A'} - Modelo {modelo} cadastrado com sucesso!")
                    return redirect("/")

        # ---------------------------
        # CONTADOR DE VINS DO DIA
        # ---------------------------
        conn = conectar()
        try:
            cursor = conn.cursor()
            data_hoje = datetime.now().strftime("%d/%m/%Y")

            # Usar consulta SQL para contar diretamente no banco
            # Converter dd/mm/yyyy para yyyy-mm-dd para o SQLite
            data_formatada = '-'.join(data_hoje.split('/')[::-1])
            cursor.execute("""
                SELECT COUNT(*) FROM conferencias
                WHERE date(substr(data_hora, 7, 4) || '-' || substr(data_hora, 4, 2) || '-' || substr(data_hora, 1, 2)) = date(?)
            """, (data_formatada,))
            total_vins = cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"Erro ao contar VINs: {e}")
            total_vins = 0
        finally:
            if conn:
                conn.close()

        return render_template("index.html", erro=erro, total_vins=total_vins)

    except Exception as e:
        logging.error(f"Erro inesperado na rota '/' : {e}")
        return "Erro interno no servidor", 500


# ===============================
# CONFIGURAÇÃO DO DIA
# ===============================

@app.route("/config", methods=["GET", "POST"])
def config():
    data_hoje = datetime.now().strftime("%d/%m/%Y")

    try:
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
    except sqlite3.Error as e:
        logging.error(f"Erro na rota '/config': {e}")
        return "Erro ao salvar configuração", 500
    except Exception as e:
        logging.error(f"Erro inesperado na rota '/config': {e}")
        return "Erro interno no servidor", 500


# ===============================
# DASHBOARD
# ===============================

@app.route("/dashboard")
def dashboard():
    try:
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        conn = conectar()

        # config do dia - usar SQL diretamente
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM config_dia WHERE data=?", (data_hoje,))
            config = cursor.fetchone()
            config_dict = {
                "data": config[0],
                "meta": config[1],
                "lider": config[2],
                "suporte": config[3]
            } if config else {}
        except sqlite3.Error as e:
            logging.error(f"Erro ao buscar configuração: {e}")
            config_dict = {}

        # Total de VINs do dia - usar SQL diretamente
        try:
            # Converter dd/mm/yyyy para yyyy-mm-dd para o SQLite
            data_formatada = '-'.join(data_hoje.split('/')[::-1])
            cursor.execute("""
                SELECT COUNT(*) FROM conferencias
                WHERE date(substr(data_hora, 7, 4) || '-' || substr(data_hora, 4, 2) || '-' || substr(data_hora, 1, 2)) = date(?)
            """, (data_formatada,))
            total_vins = cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"Erro ao contar VINs: {e}")
            total_vins = 0

        # Total geral (sem filtrar por data para evitar varredura completa)
        try:
            cursor.execute("SELECT COUNT(*) FROM conferencias")
            total_geral = cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"Erro ao contar total geral: {e}")
            total_geral = 0

        # Buscar últimos registros para exibição
        try:
            cursor.execute("""
                SELECT vin, modelo, lote, cor, sap, conferente, data_hora
                FROM conferencias
                ORDER BY data_hora DESC
                LIMIT 10
            """)
            recent = cursor.fetchall()
        except sqlite3.Error as e:
            logging.error(f"Erro ao buscar registros recentes: {e}")
            recent = []

        conn.close()

        return render_template("dashboard.html",
                             config=config_dict,
                             total_vins=total_vins,
                             total_geral=total_geral,
                             recent=recent)
    except Exception as e:
        logging.error(f"Erro inesperado na rota '/dashboard': {e}")
        return "Erro interno no servidor", 500


# ===============================
# ROTINA DE LIMPEZA (AGENDADA)
# ===============================

def limpar_banco_forcado():
    """
    Função para limpar o banco de dados - útil para PDA quando conectado.
    Use com cuidado - remove todos os registros exceto as configurações do dia.
    """
    try:
        conn = conectar()
        cursor = conn.cursor()
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # Exclui registros antigos, mantendo os do dia
        cursor.execute("DELETE FROM conferencias WHERE date(data_hora) != date(?)", (data_hoje,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao limpar banco: {e}")
        return False


# ===============================
# ROTINA DE LIMPEZA (AGENDADA)
# ===============================

def limpar_banco_forcado():
    """
    Função para limpar o banco de dados - útil para PDA quando conectado.
    Use com cuidado - remove todos os registros exceto as configurações do dia.
    """
    try:
        conn = conectar()
        cursor = conn.cursor()
        data_hoje = datetime.now().strftime("%d/%m/%Y")

        # Exclui registros antigos, mantendo os do dia
        cursor.execute("DELETE FROM conferencias WHERE date(data_hora) != date(?)", (data_hoje,))
        conn.commit()
        conn.close()
        return True
    except sqlite3.Error as e:
        logging.error(f"Erro ao limpar banco: {e}")
        return False