import os
import time
import subprocess
from pydriller import Repository
from google import genai

# Configuración y validación de seguridad de la API
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error crítico: No se encontró la variable GEMINI_API_KEY.")
    exit(1)

# === BLOQUE DE SEGURIDAD PARA ENTORNO DOCKER/GITHUB ACTIONS ===
try:
    print("Configurando permisos de seguridad de Git...")
    subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], check=True)
except Exception as e:
    print(f"Aviso al configurar Git: {e}")

# Inicialización del cliente oficial de Google GenAI
client = genai.Client(api_key=API_KEY)
MODELO = "gemini-2.0-flash"  # Modelo definitivo testeado y funcional

def extraer_commits_recientes(ruta=".", limite=5):
    print(f"[1/3] Extrayendo los últimos {limite} commits del repositorio...")
    commits = []
    try:
        # traverse_commits() devuelve los commits del más antiguo al más reciente.
        # Al convertirlo en lista y revertirlo, analizamos los verdaderamente "últimos" commits.
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
        print(f"Aviso en la fase de extracción de Git: {e}")
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
        
        # Valores por defecto en caso de fallo técnico
        categoria = "Error IA"
        justificacion = "No se pudo obtener el análisis semántico."
        
        max_intentos = 3
        for intento in range(max_intentos):
            try:
                # Pausa estratégica para mitigar el límite de cuota (429) de la API gratuita
                time.sleep(15) 
                
                respuesta = client.models.generate_content(model=MODELO, contents=prompt)
                texto = respuesta.text.strip() if respuesta.text else ""
                
                if texto:
                    partes = texto.split("|") if "|" in texto else ["Sin Clasificar", texto]
                    categoria = partes[0].strip()
                    justificacion = partes[1].strip() if len(partes) > 1 else "Análisis completado sin formato estricto."
                break  # Éxito, rompemos el bucle de reintentos
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    print(f"Alerta 429 (Cuota). Intento {intento+1}/{max_intentos} fallido. Esperando recuperación...")
                    time.sleep(20)  # Espera extra si los servidores de Google rechazan la petición
                    justificacion = f"Límite de API (429) persistente tras {max_intentos} reintentos."
                else:
                    justificacion = f"Error del sistema: {error_msg[:60]}"
                    break  # Si el error no es por cuota (ej. API Key inválida), no reintentamos
        
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
    
    # Diseño de la interfaz Markdown optimizado para la pantalla de GitHub
    contenido = "# 📊 Cuadro de Mando: Supervisor IA de Código\n\n"
    contenido += "> 🤖 *Informe estratégico generado automáticamente mediante el análisis de metadatos de Git (PyDriller) y comprensión semántica profunda de modelos de lenguaje (Gemini LLM).* \n\n"
    
    contenido += "| Hash | Desarrollador | Vol. Líneas (Churn) | Amplitud (Archivos) | Categoría IA | Justificación de Gestión (Auditoría) |\n"
    contenido += "| :--- | :--- | :---: | :---: | :--- | :--- |\n"
    
    for r in resultados:
        # Añadimos un toque visual según la categoría para el mánager
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

    # === DETECCIÓN NATIVA DE GITHUB ACTIONS ===
    # GitHub inyecta una variable de entorno con la ruta a un archivo temporal donde se guarda el resumen
    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    
    if github_summary_path:
        # Si existe, estamos en la nube de GitHub. Escribimos directamente en su panel
        with open(github_summary_path, "a", encoding="utf-8") as f:
            f.write(contenido)
        print("🚀 ¡Éxito! El cuadro de mando se ha inyectado directamente en el Step Summary de GitHub Actions.")
    else:
        # Si ejecutas en local (tu máquina), guarda el archivo clásico para que puedas revisarlo
        archivo_local = "INFORME_SUPERVISOR.md"
        with open(archivo_local, "w", encoding="utf-8") as f:
            f.write(contenido)
        print(f"📁 Ejecución local detectada. Archivo '{archivo_local}' creado con éxito.")

if __name__ == "__main__":
    # Configuramos el límite (ej. analizar los últimos 3 commits para proteger la cuota)
    datos_crudos = extraer_commits_recientes(ruta=".", limite=3)
    if datos_crudos:
        datos_evaluados = clasificar_contribucion_ia(datos_crudos)
        generar_dashboard_markdown(datos_evaluados)
    else:
        print("No se detectaron commits recientes en este repositorio para procesar.")