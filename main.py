import os
import time
import subprocess
from google import genai

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error crítico: No se encontró la variable GEMINI_API_KEY.")
    exit(1)

client = genai.Client(api_key=API_KEY)
MODELO = "gemini-2.0-flash"

def extraer_commits_recientes(ruta=".", limite=3):
    print(f"[1/3] -> ¡SISTEMA NATIVO EN VIVO ACTIVADO! <-")
    print(f"Extrayendo los últimos {limite} commits desde Git...")
    commits = []
    try:
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], check=True)
        cmd_hashes = ["git", "-C", ruta, "log", f"-n", str(limite), "--format=%h"]
        resultado_hashes = subprocess.run(cmd_hashes, capture_output=True, text=True, check=True)
        hashes = [h.strip() for h in resultado_hashes.stdout.strip().split("\n") if h.strip()]
        
        if not hashes:
            print("No se encontraron hashes.")
            return []

        for h in hashes:
            autor = subprocess.run(["git", "-C", ruta, "log", "-1", "--format=%an", h], capture_output=True, text=True, check=True).stdout.strip()
            mensaje = subprocess.run(["git", "-C", ruta, "log", "-1", "--format=%B", h], capture_output=True, text=True, check=True).stdout.strip()
            res_stats = subprocess.run(["git", "-C", ruta, "show", "--numstat", "--format=", h], capture_output=True, text=True, check=True)
            
            lineas_agregadas = 0
            lineas_borradas = 0
            archivos_modificados = []
            
            for linea in res_stats.stdout.strip().split("\n"):
                if linea.strip():
                    partes = linea.split()
                    if len(partes) >= 3:
                        add, delete, archivo = partes[0], partes[1], partes[2]
                        lineas_agregadas += int(add) if add.isdigit() else 0
                        lineas_borradas += int(delete) if delete.isdigit() else 0
                        archivos_modificados.append(archivo)
            
            commits.append({
                "hash": h, "autor": autor, "mensaje": mensaje,
                "archivos_modificados": archivos_modificados,
                "lineas_agregadas": lineas_agregadas,
                "lineas_borradas": lineas_borradas,
                "churn_total": lineas_agregadas + lineas_borradas
            })
    except Exception as e:
        print(f"Error crítico en la extracción: {e}")
        return []
    return commits

def clasificar_contribucion_ia(commits):
    print(f"[2/3] Consultando a Gemini para auditar {len(commits)} contribuciones semánticas...")
    resultados = []
    
    for c in commits:
        prompt = f"""
        Actúa como un Engineering Manager. Analiza este commit de {c['autor']}:
        - Mensaje: "{c['mensaje']}"
        - Archivos: {len(c['archivos_modificados'])} | Líneas: +{c['lineas_agregadas']} -{c['lineas_borradas']}
        Responde en este formato estricto: Categoría [Evolutivo, Mantenimiento, Riesgo Alto] | Frase de justificación.
        """
        
        categoria = "Error IA"
        justificacion = "No se pudo obtener el análisis."
        
        for intento in range(3):
            try:
                time.sleep(15)  # Respetar la cuota de la API gratuita
                respuesta = client.models.generate_content(model=MODELO, contents=prompt)
                texto = respuesta.text.strip() if respuesta.text else ""
                
                if texto:
                    partes = texto.split("|") if "|" in texto else ["Sin Clasificar", texto]
                    categoria = partes[0].strip()
                    justificacion = partes[1].strip() if len(partes) > 1 else "Análisis completado."
                break
                
            except Exception as e:
                # ¡ESTA LÍNEA ES CLAVE! Nos dirá el motivo real en el log de GitHub
                print(f"Error real de Gemini en commit {c['hash']}: {str(e)}")
                
                if "429" in str(e):
                    print("Límite de ratio detectado, esperando 20 segundos adicionales...")
                    time.sleep(20)
                else:
                    justificacion = f"Error de API: {str(e)[:60]}"
                    break  # Si el error es una clave mala (403) o modelo erróneo, salimos del bucle
                    
        resultados.append({
            "hash": c['hash'], "autor": c['autor'], "churn": c['churn_total'],
            "archivos_count": len(c['archivos_modificados']), "categoria": categoria, "justificacion": justificacion
        })
    return resultados

def generar_dashboard_markdown(resultados):
    print("[3/3] Construyendo el cuadro de mando gerencial...")
    contenido = "# 📊 Cuadro de Mando: Supervisor IA de Código\n\n"
    contenido += "| Hash | Desarrollador | Vol. Líneas (Churn) | Amplitud (Archivos) | Categoría IA | Justificación |\n"
    contenido += "| :--- | :--- | :---: | :---: | :--- | :--- |\n"
    for r in resultados:
        cat_badge = r['categoria']
        if "Riesgo Alto" in r['categoria']: cat_badge = f"🔴 **{r['categoria']}**"
        elif "Evolutivo" in r['categoria']: cat_badge = f"🟢 {r['categoria']}"
        elif "Mantenimiento" in r['categoria']: cat_badge = f"🟡 {r['categoria']}"
        contenido += f"| `{r['hash']}` | **{r['autor']}** | {r['churn']} | {r['archivos_count']} | {cat_badge} | {r['justificacion']} |\n"
    
    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        with open(github_summary_path, "a", encoding="utf-8") as f:
            f.write(contenido)
    with open("INFORME_SUPERVISOR.md", "w", encoding="utf-8") as f:
        f.write(contenido)

if __name__ == "__main__":
    ruta_repo = os.getenv("GITHUB_WORKSPACE", ".")
    datos_crudos = extraer_commits_recientes(ruta=ruta_repo, limite=3)
    if datos_crudos:
        datos_evaluados = clasificar_contribucion_ia(datos_crudos)
        generar_dashboard_markdown(datos_evaluados)
    else:
        print("Operación cancelada: No se pudieron extraer datos.")