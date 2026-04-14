#!/usr/bin/env python3
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Adicionar estatísticas de lotes após a consulta do total_geral
old = '''        # Total geral (sem filtrar por data para evitar varredura completa)
        try:
            cursor.execute("SELECT COUNT(*) FROM conferencias")
            total_geral = cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"Erro ao contar total geral: {e}")
            total_geral = 0

        # Buscar últimos registros para exibição'''

new = '''        # Total geral (sem filtrar por data para evitar varredura completa)
        try:
            cursor.execute("SELECT COUNT(*) FROM conferencias")
            total_geral = cursor.fetchone()[0]
        except sqlite3.Error as e:
            logging.error(f"Erro ao contar total geral: {e}")
            total_geral = 0

        # Estatísticas por lote/modelo/cor/SAP - agrupar por hoje
        try:
            cursor.execute("""
                SELECT modelo, lote, cor, sap, COUNT(*) as qtd
                FROM conferencias
                WHERE date(substr(data_hora, 7, 4) || '-' || substr(data_hora, 4, 2) || '-' || substr(data_hora, 1, 2)) = date(?)
                GROUP BY modelo, lote, cor, sap
                ORDER BY qtd DESC
            """, (data_formatada,))
            lotes = cursor.fetchall()
            # Converter para cards com porcentagem
            cards = []
            for lote in lotes:
                modelo, lote_nome, cor, sap, qtd = lote
                porcentagem = int((qtd / 120) * 100) if 120 > 0 else 0
                cards.append({
                    "modelo": modelo,
                    "lote": lote_nome,
                    "cor": cor,
                    "sap": sap,
                    "qtd": qtd,
                    "porcentagem": porcentagem
                })
        except sqlite3.Error as e:
            logging.error(f"Erro ao buscar estatísticas por lote: {e}")
            cards = []

        # Buscar últimos registros para exibição'''

if old in content:
    content = content.replace(old, new)
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('SUCCESS: estatísticas de lotes adicionadas')
else:
    print('ERROR: padrão não encontrado')
    # Mostrar trecho ao redor da busca
    idx = content.find('Total geral')
    if idx >= 0:
        print('Trecho encontrado:')
        print(repr(content[idx-100:idx+200]))