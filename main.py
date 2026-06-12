import os
import time
import subprocess
from pydriller import Repository
from google import genai

# Validación de seguridad de la API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error crítico: No se encontró la variable GEMINI_API_KEY.")
    exit(1)

# Bloque de seguridad obligatorio para entornos Docker en GitHub Actions
try:
    print("Configurando permisos de seguridad de Git...")
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], check=True)
except Exception as e:
    print(f"Aviso al configurar Git: {e}")

# Inicialización del cliente oficial de Google GenAI
client = genai.Client(api_key=API_KEY)
MODELO = "gemini-2.0-flash"

def extraer_commits_recientes(ruta=".", limite=3):
    print(f"[1/3] Extrayendo los últimos {limite} commits del repositorio en {ruta}...")
    commits = []
    try:
        todos_los_commits = list(Repository(ruta).traverse_commits())
        commits_recientes = reversed(todos_los_commits[-limite:])
        
        for commit in commits_recientes:
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
        print(f"Error crítico en la fase de extracción de Git: {e}")
    return commits

def clasificar_contribucion_ia(commits):
    print(f"[2/3] Consultando a Gemini para auditar {len(commits)} contribuciones semánticas...")
    resultados = []
    
    for c in commits:
        prompt = f"""
        Actúa como un Engineering Manager evaluando a tu equipo.
        Analiza este commit del desarrollador {c['autor']}:
        - Mensaje del commit: "{c['mensaje']}"
        - Total de archivos modificados (Amplitud de impacto): {len(c['archivos_modificados'])}
        - Líneas agregadas: {c['lineas_agregadas']}
        - Líneas borradas: {c['lineas_borradas']}
        
        Realiza dos tareas muy breves:
        1. Clasifica el impacto en una de estas 3 categorías exactas: [Evolutivo, Mantenimiento, Riesgo Alto].
        2. Escribe una sola frase (justificación directiva) evaluando la naturaleza de este cambio.
        
        Formato de respuesta estricto (no añadas introducciones ni saludos): Categoría | Justificación
        """
        
        categoria = "Error IA"
        justificacion = "No se pudo obtener el análisis semántico."
        max_intentos = 3
        
        for intento in range(max_intentos):
            try:
                time.sleep(15)  # Control preventivo de tasa de transferencia (Rate limit)
                
                respuesta = client.models.generate_content(model=MODELO, contents=prompt)
                texto = respuesta.text.strip() if respuesta.text else ""
                
                if texto:
                    partes = texto.split("|") if "|" in texto else ["Sin Clasificar", texto]
                    categoria = partes[0].strip()
                    justificacion = partes[1].strip() if len(partes) > 1 else "Análisis completado sin formato estricto."
                break
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"Alerta 429 (Cuota). Reintento {intento+1}/{max_intentos}. Esperando...")
                    time.sleep(20)
                    justificacion = f"Límite de API (429) de Google alcanzado."
                else:
                    justificacion = f"Error del sistema: {error_msg[:60]}"
                    break
        
        resultados.append({
            "hash": c['hash'],
            "autor": c['autor'],
            "churn": c['churn_total'],
            "archivos_count": len(c['archivos_modificados']),
            "categoria": categoria,
            "justificacion": justificacion
        })
            
    return resultados

def generar_dashboard_markdown(resultados):
    print("[3/3] Construyendo el cuadro de mando gerencial...")
    
    contenido = "# 📊 Cuadro de Mando: Supervisor IA de Código\n\n"
    contenido += "> 🤖 *Informe estratégico generado automáticamente mediante el análisis de metadatos de Git (PyDriller) y comprensión semántica profunda de modelos de lenguaje (Gemini LLM).* \n\n"
    
    contenido += "| Hash | Desarrollador | Vol. Líneas (Churn) | Amplitud (Archivos) | Categoría IA | Justificación de Gestión (Auditoría) |\n"
    contenido += "| :--- | :--- | :---: | :---: | :--- | :--- |\n"
    
    for r in resultados:
        cat_badge = r['categoria']
        if "Riesgo Alto" in r['categoria']:
            cat_badge = f"🔴 **{r['categoria']}**"
        elif "Evolutivo" in r['categoria']:
            cat_badge = f"🟢 {r['categoria']}"
        elif "Mantenimiento" in r['categoria']:
            cat_badge = f"🟡 {r['categoria']}"
            
        contenido += f"| `{r['hash']}` | **{r['autor']}** | {r['churn']} | {r['archivos_count']} | {cat_badge} | {r['justificacion']} |\n"
        
    contenido += "\n\n---"
    contenido += "\n*Nota para el Engineering Manager: Los commits marcados en **Riesgo Alto** reflejan grandes volúmenes de cambio estructural o inconsistencias semánticas que requieren una revisión de código prioritaria.*"

    # Canal 1: Inyección dinámica nativa en la pantalla de GitHub Actions
    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        with open(github_summary_path, "a", encoding="utf-8") as f:
            f.write(contenido)
        print("Cuadro de mando inyectado con éxito en el Step Summary de GitHub.")
        
    # Canal 2: Generación persistente para descarga de artefactos
    archivo_local = "INFORME_SUPERVISOR.md"
    with open(archivo_local, "w", encoding="utf-8") as f:
        f.write(contenido)
    print(f"Archivo físico '{archivo_local}' guardado correctamente.")

if __name__ == "__main__":
    # Forzamos la lectura en la ruta absoluta del contenedor Docker de GitHub o "." en local
    ruta_repo = os.getenv("GITHUB_WORKSPACE", ".")
    datos_crudos = extraer_commits_recientes(ruta=ruta_repo, limite=3)
    
    if datos_crudos:
        datos_evaluados = clasificar_contribucion_ia(datos_crudos)
        generar_dashboard_markdown(datos_evaluados)
    else:
        print("Operación cancelada: No se pudo instanciar el repositorio o la historia está vacía.")