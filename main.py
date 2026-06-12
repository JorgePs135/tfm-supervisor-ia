import os
import subprocess
from google import genai

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error crítico: No se encontró la variable GEMINI_API_KEY.")
    exit(1)

client = genai.Client(api_key=API_KEY)
MODELO = "gemini-2.0-flash"

def extraer_commits_recientes(ruta=".", limite=3):
    print(f"[1/3] -> ¡SISTEMA NATIVO BATCH ACTIVADO! <-")
    print(f"Extrayendo los últimos {limite} commits desde Git...")
    commits = []
    try:
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "*"], check=True)
        cmd_hashes = ["git", "-C", ruta, "log", f"-n", str(limite), "--format=%h"]
        resultado_hashes = subprocess.run(cmd_hashes, capture_output=True, text=True, check=True)
        hashes = [h.strip() for h in resultado_hashes.stdout.strip().split("\n") if h.strip()]
        
        if not hashes:
            print("No se encontraron commits.")
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
        print(f"Error crítico en Git: {e}")
        return []
    return commits

def clasificar_contribuciones_batch(commits):
    print(f"[2/3] Enviando lote completo de {len(commits)} commits a Gemini en una sola petición...")
    
    bloque_commits = ""
    for c in commits:
        bloque_commits += f"COMMIT: {c['hash']}\n"
        bloque_commits += f"Mensaje: {c['mensaje']}\n"
        bloque_commits += f"Impacto: {len(c['archivos_modificados'])} archivos, +{c['lineas_agregadas']} -{c['lineas_borradas']} líneas\n"
        bloque_commits += "-------\n"

    prompt = f"""
    Actúa como un Engineering Manager. Analiza este lote de commits de mi equipo de desarrollo:
    
    {bloque_commits}
    
    Para cada commit, clasifícalo en una de estas categorías exactas [Evolutivo, Mantenimiento, Riesgo Alto] y da una breve frase de justificación gerencial.
    
    Devuelve tu respuesta siguiendo ESTE FORMATO EXACTO por cada línea (una línea por commit, sin bloques de código markdown ni introducciones):
    hash_del_commit | categoria | frase de justificacion
    """
    
    resultados = []
    texto_respuesta = ""
    error_api = ""
    
    try:
        respuesta = client.models.generate_content(model=MODELO, contents=prompt)
        texto_respuesta = respuesta.text.strip() if respuesta.text else ""
        print("\n=== 📝 RESPUESTA EN BRUTO DE GEMINI ===")
        print(texto_respuesta)
        print("=======================================\n")
        
    except Exception as e:
        # Capturamos el error real de Google para enviarlo a la tabla
        error_api = str(e)
        print(f"❌ Error crítico de Gemini: {error_api}")

    for c in commits:
        categoria = "Error IA"
        
        # 1. Si hubo un error técnico con la API (Cuota, Clave falsa, etc.)
        if error_api:
            if "429" in error_api:
                justificacion = "Error 429: Cuota agotada. Recuerda crear la clave en un PROYECTO NUEVO de Google."
            elif "403" in error_api or "API_KEY_INVALID" in error_api:
                justificacion = "Error 403: Clave inválida. Revisa el Secret de GitHub (cuidado con los espacios en blanco)."
            else:
                justificacion = f"Fallo de conexión: {error_api[:50]}..."
                
        # 2. Si la llamada funcionó pero Google la censuró (Filtros de seguridad)
        elif not texto_respuesta:
            justificacion = "Bloqueo: La API devolvió un texto vacío (posible filtro de seguridad de Google)."
            
        # 3. Si todo fue bien, extraemos los datos elásticamente
        else:
            justificacion = "No se pudo extraer del texto."
            for linea in texto_respuesta.split("\n"):
                if c['hash'].lower() in linea.lower() and "|" in linea:
                    partes = linea.split("|")
                    if len(partes) >= 2:
                        categoria = partes[1].strip()
                    if len(partes) >= 3:
                        justificacion = partes[2].strip()
                    else:
                        justificacion = "Análisis completado."
                    break
                    
        resultados.append({
            "hash": c['hash'], "autor": c['autor'], "churn": c['churn_total'],
            "archivos_count": len(c['archivos_modificados']), 
            "categoria": categoria, "justificacion": justificacion
        })
        
    return resultados

def generar_dashboard_markdown(resultados):
    print("[3/3] Construyendo el cuadro de mando gerencial...")
    contenido = "# 📊 Cuadro de Mando: Supervisor IA de Código\n\n"
    contenido += "> 🤖 *Informe estratégico generado automáticamente analizando metadatos de Git y procesado en lote vía Gemini 2.0 Flash.*\n\n"
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
        datos_evaluados = clasificar_contribuciones_batch(datos_crudos)
        generar_dashboard_markdown(datos_evaluados)