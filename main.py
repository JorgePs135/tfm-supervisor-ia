import os
import pandas as pd
from pydriller import Repository
from google import genai

# Configuración y validación de seguridad
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("❌ Error crítico: No se encontró la variable GEMINI_API_KEY.")
    exit(1)

client = genai.Client(api_key=API_KEY)
MODELO = "gemini-2.0-flash"

def extraer_commits_recientes(ruta=".", limite=5):
    print(f"[1/3] 🔍 Extrayendo los últimos {limite} commits...")
    commits = []
    try:
        for i, commit in enumerate(Repository(ruta).traverse_commits()):
            if i >= limite: break
            commits.append({
                "hash": commit.hash[:7],
                "autor": commit.author.name,
                "mensaje": commit.msg,
                "archivos_modificados": [f.filename for f in commit.modified_files],
                "lineas_agregadas": commit.insertions,
                "lineas_borradas": commit.deletions,
                "churn_total": commit.insertions + commit.deletions
            })
    except Exception as e:
        print(f"Aviso en extracción: {e}")
    return commits

def clasificar_contribucion_ia(commits):
    print(f"[2/3] 🧠 Consultando a Gemini para clasificar {len(commits)} contribuciones...")
    resultados = []
    
    for c in commits:
        prompt = f"""
        Actúa como un Engineering Manager evaluando a tu equipo.
        Analiza este commit del desarrollador {c['autor']}:
        - Mensaje: "{c['mensaje']}"
        - Total de archivos tocados: {len(c['archivos_modificados'])}
        - Líneas agregadas: {c['lineas_agregadas']}
        - Líneas borradas: {c['lineas_borradas']}
        
        Realiza dos tareas muy breves:
        1. Clasifica el impacto en una de estas 3 categorías exactas: [Evolutivo, Mantenimiento, Riesgo Alto].
        2. Escribe una sola frase justificando tu decisión desde la perspectiva de gestión de proyecto.
        
        Formato de respuesta estricto: Categoría | Justificación
        """
        try:
            respuesta = client.models.generate_content(model=MODELO, contents=prompt)
            texto = respuesta.text.strip()
            
            # Separamos la respuesta de la IA (Categoría | Justificación)
            partes = texto.split("|") if "|" in texto else ["Sin Clasificar", texto]
            
            resultados.append({
                "hash": c['hash'],
                "autor": c['autor'],
                "churn": c['churn_total'],
                "categoria": partes[0].strip(),
                "justificacion": partes[1].strip() if len(partes) > 1 else "Revisión manual requerida."
            })
        except Exception as e:
            print(f"❌ Error con IA en commit {c['hash']}: {e}")
            
    return resultados

def generar_dashboard_markdown(resultados):
    print("[3/3] 📊 Generando informe para el Engineering Manager...")
    contenido = "# 📊 Cuadro de Mando: Auditoría de Código IA\n\n"
    contenido += "> *Análisis generado automáticamente por el Supervisor IA (TFM).* \n\n"
    
    contenido += "| Hash | Desarrollador | Volumen (Líneas) | Categoría | Justificación (IA) |\n"
    contenido += "| :--- | :--- | :---: | :--- | :--- |\n"
    
    for r in resultados:
        contenido += f"| `{r['hash']}` | **{r['autor']}** | {r['churn']} | {r['categoria']} | {r['justificacion']} |\n"
        
    with open("INFORME_SUPERVISOR.md", "w", encoding="utf-8") as f:
        f.write(contenido)
    print("✅ Archivo 'INFORME_SUPERVISOR.md' creado con éxito.")

if __name__ == "__main__":
    datos_crudos = extraer_commits_recientes(limite=5)
    if datos_crudos:
        datos_evaluados = clasificar_contribucion_ia(datos_crudos)
        generar_dashboard_markdown(datos_evaluados)
    else:
        print("❌ No se encontraron commits para analizar.")