import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import requests
import datetime
import os
from supabase import create_client, Client
from fpdf import FPDF

# =====================================================================
# 🔐 CONFIGURACIÓN Y CREDENCIALES
# =====================================================================
st.set_page_config(layout="wide", page_title="PAESA ERP - Logística Avanzada", page_icon="🏗️")

SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFieW15cHVqZm9ubXR2YWtmc2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MjA0OTIsImV4cCI6MjA5ODQ5NjQ5Mn0.AsystVXsFbMmHoi8RarhBqPsW4zgvc-EcwAEo9BXV-Q"
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "asfalto2026"
TELEGRAM_TOKEN = "8321781121:AAE9mLUzOGZwZwGmpQMN614ROSQGFrS-jbM"
TELEGRAM_CHAT_ID = "6612216260"

# 👇 PEGA AQUÍ TU TOKEN DE MAPBOX (el que empieza con pk.ey...)
MAPBOX_TOKEN = "pk.eyJ1IjoicGFlc2FhZG1pbiIsImEiOiJjbXI0NzJwcGUwOW56MzVwbG1ndms3cDEwIn0.dJF-vXqD7Vw7a8Izh7uJMA"

if "auth" not in st.session_state: st.session_state["auth"] = False
if not st.session_state["auth"]:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏗️ PAESA Logística")
        st.markdown("### Acceso al Sistema ERP")
        usr = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar al Sistema", use_container_width=True):
            if usr == USUARIO_ADMIN and pwd == PASSWORD_ADMIN:
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("Acceso denegado.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================================
# 🤖 BOT DE TELEGRAM MULTI-USUARIO (SOPORTE DOCUMENTOS PDF)
# =====================================================================
def enviar_telegram(mensaje):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        chats = str(TELEGRAM_CHAT_ID).split(",")
        for chat in chats:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": chat.strip(), "text": mensaje, "parse_mode": "Markdown"}
            try: requests.post(url, json=payload, timeout=3)
            except: pass

def enviar_pdf_telegram(pdf_bytes, filename, comentario):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        chats = str(TELEGRAM_CHAT_ID).split(",")
        for chat in chats:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
            files = {'document': (filename, pdf_bytes, 'application/pdf')}
            data = {'chat_id': chat.strip(), 'caption': comentario}
            try: requests.post(url, files=files, data=data, timeout=10)
            except: pass

def registrar_notificacion(tipo, mensaje, enviar_bot=False):
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try: supabase.table("notificaciones").insert({"tipo": str(tipo), "mensaje": str(mensaje), "fecha_hora": ahora, "leida": False}).execute()
    except: pass
    if enviar_bot:
        enviar_telegram(f"🏗️ *PAESA ALERTAS*\n*Módulo:* {tipo}\n*Detalle:* {mensaje}")

# =====================================================================
# 📡 EXTRACCIÓN DE DATOS Y RUTEADOR INTELIGENTE (MAPBOX + OSRM)
# =====================================================================
def get_table(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except: return pd.DataFrame()

df_planta = get_table("config_planta")
df_distribuidoras = get_table("distribuidoras")
df_clientes = get_table("clientes")
df_obras = get_table("obras")
df_tiros = get_table("registro_tiros")
# 🛡️ Escudo protector: Si Supabase no manda la columna, Python la crea para evitar que el sistema colapse
if "orden_visita" not in df_tiros.columns:
    df_tiros["orden_visita"] = 1

df_notif = get_table("notificaciones")

COORDS_PLANTA = (float(df_planta.iloc[0]["latitud"]), float(df_planta.iloc[0]["longitud"])) if not df_planta.empty else (25.8250, -100.4109)

def get_route_geometry(c1, c2):
    """Calcula la ruta utilizando Tráfico en Tiempo Real de Mapbox o algoritmo predictivo de OSRM."""
    # 1. INTENTO CON MAPBOX (RUTAS CON TRÁFICO REAL GPS)
    if MAPBOX_TOKEN and MAPBOX_TOKEN != "":
        url_mapbox = f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?geometries=geojson&access_token={MAPBOX_TOKEN}"
        try:
            res = requests.get(url_mapbox, timeout=5).json()
            if res.get("code") == "Ok":
                coords = res["routes"][0]["geometry"]["coordinates"]
                ruta_mapa = [[p[1], p[0]] for p in coords] # Invertimos a Lat, Lon para Folium
                dist_km = round(res["routes"][0]["distance"]/1000.0, 1)
                tiempo_min = round(res["routes"][0]["duration"]/60.0, 0)
                return ruta_mapa, dist_km, tiempo_min
        except: pass

    # 2. SISTEMA DE RESPALDO: OSRM + ALGORITMO PREDICTIVO DE HORAS PICO
    try:
        url_osrm = f"http://router.project-osrm.org/route/v1/driving/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=full&geometries=geojson"
        res = requests.get(url_osrm, timeout=5).json()
        if res.get("code") == "Ok":
            coords = res["routes"][0]["geometry"]["coordinates"]
            ruta_mapa = [[p[1], p[0]] for p in coords]
            dist_km = round(res["routes"][0]["distance"]/1000.0, 1)
            tiempo_base = round(res["routes"][0]["duration"]/60.0, 0)
            
            # Penalización algorítmica por tráfico de Monterrey y vehículo pesado
            hora_actual = datetime.datetime.now().hour
            if 7 <= hora_actual <= 9 or 17 <= hora_actual <= 19: tiempo_real = tiempo_base * 1.6 # Hora Pico (+60%)
            elif 12 <= hora_actual <= 14: tiempo_real = tiempo_base * 1.35 # Tráfico Medio (+35%)
            else: tiempo_real = tiempo_base * 1.15 # Tráfico Regular (+15%)
            
            return ruta_mapa, dist_km, round(tiempo_real, 0)
    except: pass
    
    return [], 0.0, 0.0

def generar_pdf(df_dia, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, txt=f"Reporte Operativo PAESA - {fecha}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", size=9)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(15, 8, "Orden", border=1, fill=True)
    pdf.cell(20, 8, "Hora", border=1, fill=True)
    pdf.cell(25, 8, "Unidad", border=1, fill=True)
    pdf.cell(70, 8, "Obra / Destino", border=1, fill=True)
    pdf.cell(15, 8, "Litros", border=1, fill=True)
    pdf.cell(30, 8, "Estatus", border=1, fill=True)
    pdf.cell(15, 8, "KM", border=1, fill=True)
    pdf.ln()
    
    if not df_dia.empty:
        for _, row in df_dia.sort_values(by=["distribuidora", "orden_visita"]).iterrows():
            obra_n = df_obras[df_obras["id"] == row["obra_id"]].iloc[0]["nombre_obra"] if not df_obras.empty else "N/A"
            estatus_limpio = str(row["estatus"]).encode('latin-1', 'ignore').decode('latin-1')
            obra_limpia = str(obra_n)[:35].encode('latin-1', 'ignore').decode('latin-1')
            
            pdf.cell(15, 8, str(row.get("orden_visita", 1)), border=1)
            pdf.cell(20, 8, str(row["hora"]), border=1)
            pdf.cell(25, 8, str(row["distribuidora"]), border=1)
            pdf.cell(70, 8, obra_limpia, border=1)
            pdf.cell(15, 8, str(row["litros"]), border=1)
            pdf.cell(30, 8, estatus_limpio[:12], border=1)
            pdf.cell(15, 8, str(row["distancia_km"]), border=1)
            pdf.ln()
    return bytes(pdf.output())

# =====================================================================
# 🕒 AUTOMATIZACIÓN DE CIERRE AUTOMÁTICO DE DÍA (6:00 PM)
# =====================================================================
ahora_hora = datetime.datetime.now().time()
if ahora_hora >= datetime.time(18, 0):
    if "reporte_enviado_hoy" not in st.session_state:
        df_hoy_cierre = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
        if not df_hoy_cierre.empty:
            pdf_auto_bytes = generar_pdf(df_hoy_cierre, str(datetime.date.today()))
            enviar_pdf_telegram(pdf_auto_bytes, f"Cierre_Automatico_{datetime.date.today()}.pdf", f"🔒 *CIERRE AUTOMÁTICO DE JORNADA* ({datetime.date.today()})\nEl día ha terminado (6:00 PM). Se adjunta el reporte consolidado de tiros y rendimientos.")
            st.session_state["reporte_enviado_hoy"] = True

# =====================================================================
# 🖥️ NAVEGACIÓN Y SIDEBAR
# =====================================================================
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    else: st.markdown("## 🏗️ PAESA ERP")
    st.caption("Control de Logística y Rutas en Cadena")
    
    notif_no_leidas = len(df_notif[df_notif["leida"] == False]) if not df_notif.empty and "leida" in df_notif.columns else 0
    if notif_no_leidas > 0:
        st.error(f"🔔 {notif_no_leidas} Alertas Nuevas")
        if st.button("✅ Aceptar Alertas", use_container_width=True):
            supabase.table("notificaciones").update({"leida": True}).eq("leida", False).execute()
            st.rerun()
            
    st.markdown("---")
    menu = st.radio("Módulos Principales", [
        "📊 Dashboard Principal", 
        "🚚 Operaciones y Despacho", 
        "🏢 Directorio CRM (Clientes/Obras)", 
        "⚙️ Planta, Inventario y Flota", 
        "📂 Histórico y Reportes"
    ])
    st.markdown("---")
    if st.button("Cerrar Sesión 🔒", use_container_width=True):
        st.session_state["auth"] = False
        st.rerun()

# =====================================================================
# 📊 MÓDULO 1: DASHBOARD
# =====================================================================
if menu == "📊 Dashboard Principal":
    st.header("📊 Inteligencia Operativa y Tiros Programados")
    
    inv_actual = float(df_planta.iloc[0]["inventario_actual"]) if not df_planta.empty else 0
    tiros_hoy = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
    volumen_hoy = tiros_hoy[tiros_hoy["estatus"] == "Completado ✅"]["litros"].sum() if not tiros_hoy.empty else 0
    tiros_pendientes = tiros_hoy[tiros_hoy["estatus"].isin(["Pendiente", "En Proceso"])] if not tiros_hoy.empty else pd.DataFrame()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💧 Asfalto Colocado Hoy", f"{volumen_hoy:,.0f} Lts")
    c2.metric("🏭 Inventario Planta", f"{inv_actual:,.0f} Lts")
    c3.metric("📋 Tiros Totales (Hoy)", f"{len(tiros_hoy)}")
    
    st.markdown("---")
    col_dash1, col_dash2 = st.columns([1, 1])
    
    with col_dash1:
        st.markdown("### 🚦 Estatus de Flota y Secuencia en Ruta")
        if not df_distribuidoras.empty:
            df_show = df_distribuidoras.copy()
            for idx, cam in df_show.iterrows():
                tiros_activos = tiros_hoy[(tiros_hoy["distribuidora"] == cam["unidad"]) & (tiros_hoy["estatus"] == "En Proceso")].sort_values(by="orden_visita")
                if not tiros_activos.empty:
                    df_show.at[idx, "estado"] = f"En Tránsito ({len(tiros_activos)} paradas) 🚚"
            st.dataframe(df_show[["unidad", "chofer", "estado", "litros_disponibles"]].rename(columns={"unidad":"Unidad", "chofer":"Operador", "estado":"Estatus Actual", "litros_disponibles":"Volumen Físico"}), hide_index=True, use_container_width=True)

        st.markdown("### 🕒 Cronograma Operativo Ordenado")
        if not tiros_pendientes.empty and not df_obras.empty:
            df_pend_show = tiros_pendientes.copy()
            df_pend_show["Obra"] = df_pend_show["obra_id"].apply(lambda x: df_obras[df_obras["id"] == x].iloc[0]["nombre_obra"] if x in df_obras["id"].values else "Desconocida")
            st.dataframe(df_pend_show[["distribuidora", "orden_visita", "hora", "Obra", "litros", "estatus"]].sort_values(by=["distribuidora", "orden_visita"]).rename(columns={"distribuidora":"Unidad", "orden_visita":"Turno", "hora":"Hora Prog.", "litros":"Litros", "estatus":"Estado"}), hide_index=True, use_container_width=True)
        else: st.success("No hay tiros pendientes en la pizarra.")
            
    with col_dash2:
        st.markdown("### 🗺️ Mapa Cartográfico de Entregas")
        m = folium.Map(location=COORDS_PLANTA, zoom_start=10)
        folium.Marker(COORDS_PLANTA, popup="Planta Principal", icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
        if not tiros_hoy.empty and not df_obras.empty:
            for _, t in tiros_hoy.iterrows():
                if t["estatus"] != "Cancelado ❌":
                    obras_filtradas = df_obras[df_obras["id"] == t["obra_id"]]
                    if not obras_filtradas.empty:
                        obra = obras_filtradas.iloc[0]
                        color = "green" if t["estatus"] == "Completado ✅" else ("orange" if t["estatus"] == "En Proceso" else "blue")
                        folium.Marker((obra["latitud"], obra["longitud"]), popup=f"Turno #{t.get('orden_visita', 1)}<br>{obra['nombre_obra']}", icon=folium.Icon(color=color)).add_to(m)
        folium_static(m, width=600, height=450)

# =====================================================================
# 🚚 MÓDULO 2: OPERACIONES (RUTEO EN CADENA Y HORARIOS)
# =====================================================================
elif menu == "🚚 Operaciones y Despacho":
    st.header("🚚 Centro de Despacho y Secuenciación Multi-Punto")
    tab1, tab2 = st.tabs(["➕ 1. Capturar Nueva Orden", "🧠 2. Diseñador de Rutas y Tráfico Real"])
    
    with tab1:
        st.markdown("⚠️ *Nota: El despacho solo permite agendar entregas entre las 08:00 AM y las 06:00 PM.*")
        with st.form("form_crear_orden"):
            df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
            obra_sel = st.selectbox("Destino del Asfalto", df_obras["display"].tolist() if not df_obras.empty else [])
            
            c1, c2, c3 = st.columns(3)
            litros = c1.number_input("Volumen Requerido (Lts)", min_value=0, step=500)
            fecha = c2.date_input("Fecha de Ejecución")
            hora = c3.time_input("Hora de Arribo Solicitada", datetime.time(8, 0))
            
            c_nota1, c_nota2 = st.columns([1,2])
            ing = c_nota1.text_input("Ingeniero Responsable en Obra")
            notas = c_nota2.text_input("Notas Especiales")
            
            if st.form_submit_button("Registrar Orden de Tiro", use_container_width=True):
                if hora < datetime.time(8, 0) or hora > datetime.time(18, 0):
                    st.error("❌ RECHAZADO: Fuera de horario operativo (Solo de 8:00 AM a 6:00 PM).")
                elif not df_obras.empty:
                    obra_id = int(df_obras[df_obras["display"] == obra_sel].iloc[0]["id"])
                    dict_orden = {"obra_id": obra_id, "litros": int(litros), "fecha": str(fecha), "hora": str(hora), "ingeniero_responsable": str(ing), "notas": str(notas), "distribuidora": "Sin Asignar", "estatus": "Pendiente", "minutos_retraso": 0, "distancia_km": 0.0, "orden_visita": 1}
                    supabase.table("registro_tiros").insert(dict_orden).execute()
                    registrar_notificacion("Operación", f"Orden agendada: {litros} Lts para {obra_sel} ({hora.strftime('%H:%M')}).", enviar_bot=True)
                    st.success("Orden capturada exitosamente.")
                    st.rerun()

    with tab2:
        f_filtro = st.date_input("Fecha Logística a Programar", datetime.date.today())
        df_dia = df_tiros[df_tiros["fecha"] == str(f_filtro)] if not df_tiros.empty else pd.DataFrame()
        
        if not df_dia.empty:
            st.markdown("### 🧠 Enlazador de Eslabones de Ruta")
            
            camiones_del_dia = df_dia[df_dia["distribuidora"] != "Sin Asignar"]["distribuidora"].unique().tolist()
            df_sin_camion = df_dia[df_dia["distribuidora"] == "Sin Asignar"]
            
            if not df_sin_camion.empty:
                st.markdown("#### 🚨 Tiros Pendientes de Asignación")
                for _, row in df_sin_camion.iterrows():
                    obra_c = df_obras[df_obras["id"] == row["obra_id"]].iloc[0]
                    c_a, c_b = st.columns([3, 1])
                    ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]["unidad"].tolist() if not df_distribuidoras.empty else []
                    cam_elegido = c_a.selectbox(f"Unidad para {obra_c['nombre_obra']} ({row['litros']:,} Lts) a las {row['hora']}", ["Seleccionar..."] + ops, key=f"sel_{row['id']}")
                    if cam_elegido != "Seleccionar..." and c_b.button("Asignar", key=f"btn_asig_{row['id']}"):
                        supabase.table("registro_tiros").update({"distribuidora": cam_elegido}).eq("id", row["id"]).execute()
                        st.rerun()
            
            for cam_id in camiones_del_dia:
                st.markdown(f"#### 🚛 Plan de Viaje - Unidad **{cam_id}**")
                tiros_camion = df_dia[df_dia["distribuidora"] == cam_id].copy()
                
                for _, tiro in tiros_camion.sort_values(by="orden_visita").iterrows():
                    obra_t = df_obras[df_obras["id"] == tiro["obra_id"]].iloc[0]
                    col_x1, col_x2, col_x3, col_x4 = st.columns([3, 1, 1, 1])
                    
                    col_x1.markdown(f"📍 **Parada:** {obra_t['nombre_obra']} | `{tiro['litros']:,} Lts` | `{tiro['hora']}`")
                    nuevo_orden = col_x2.number_input("Prioridad / Turno", min_value=1, max_value=10, value=int(tiro.get("orden_visita", 1)), key=f"ord_{tiro['id']}")
                    n_est = col_x3.selectbox("Estatus", ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"], index=["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"].index(tiro["estatus"]), key=f"est_{tiro['id']}")
                    
                    if col_x4.button("⚡ Recalcular Eslabón", key=f"rec_{tiro['id']}"):
                        tiros_previos = tiros_camion[tiros_camion["orden_visita"] < nuevo_orden].sort_values(by="orden_visita")
                        if tiros_previos.empty: origen_coordenadas = COORDS_PLANTA
                        else:
                            obra_anterior_id = tiros_previos.iloc[-1]["obra_id"]
                            obra_ant = df_obras[df_obras["id"] == obra_anterior_id].iloc[0]
                            origen_coordenadas = (float(obra_ant["latitud"]), float(obra_ant["longitud"]))
                            
                        # El cálculo usará el tráfico de Mapbox o el Predictivo OSRM automáticamente
                        _, dist_tramo, _ = get_route_geometry(origen_coordenadas, (float(obra_t["latitud"]), float(obra_t["longitud"])))
                        
                        supabase.table("registro_tiros").update({
                            "orden_visita": int(nuevo_orden), "estatus": n_est, "distancia_km": float(dist_tramo)
                        }).eq("id", int(tiro["id"])).execute()
                        
                        if n_est == "Completado ✅" and tiro["estatus"] != "Completado ✅":
                            u_info = df_distribuidoras[df_distribuidoras["unidad"] == cam_id].iloc[0]
                            supabase.table("distribuidoras").update({
                                "litros_disponibles": max(0, int(u_info["litros_disponibles"] - tiro["litros"])),
                                "km_totales": float(u_info["km_totales"]) + float(dist_tramo)
                            }).eq("unidad", cam_id).execute()
                        st.success("Trayecto de ruta re-calculado con éxito.")
                        st.rerun()
                        
                if st.button(f"🗺️ Simular Circuito Completo con Tráfico ({cam_id})", key=f"map_c_{cam_id}"):
                    m_circuito = folium.Map(location=COORDS_PLANTA, zoom_start=11)
                    folium.Marker(COORDS_PLANTA, popup="Salida: Planta", icon=folium.Icon(color="red")).add_to(m_circuito)
                    
                    ultimo_punto = COORDS_PLANTA
                    puntos_ordenados = tiros_camion.sort_values(by="orden_visita")
                    tiempo_total = 0
                    dist_total = 0
                    
                    for _, t_c in puntos_ordenados.iterrows():
                        ob_c = df_obras[df_obras["id"] == t_c["obra_id"]].iloc[0]
                        coords_destino = (float(ob_c["latitud"]), float(ob_c["longitud"]))
                        
                        geo_tramo, dist, t_min = get_route_geometry(ultimo_punto, coords_destino)
                        dist_total += dist
                        tiempo_total += t_min
                        
                        if geo_tramo: folium.PolyLine(geo_tramo, color="darkblue", weight=4).add_to(m_circuito)
                        folium.Marker(coords_destino, popup=f"Parada #{t_c['orden_visita']}: {ob_c['nombre_obra']}", icon=folium.Icon(color="orange")).add_to(m_circuito)
                        ultimo_punto = coords_destino
                        
                    geo_retorno, d_ret, t_ret = get_route_geometry(ultimo_punto, COORDS_PLANTA)
                    dist_total += d_ret
                    tiempo_total += t_ret
                    
                    if geo_retorno: folium.PolyLine(geo_retorno, color="red", weight=4, dash_array="5").add_to(m_circuito)
                    
                    st.info(f"**Análisis de Ruta:** Distancia Total: {round(dist_total, 1)} km | Tiempo estimado al volante: {round(tiempo_total, 0)} minutos.")
                    st.write("🔵 Línea Azul = Ruta entre obras | 🔴 Línea Punteada = Retorno final a Planta")
                    folium_static(m_circuito, width=700, height=350)
        else: st.info("No hay órdenes registradas para la fecha seleccionada.")

# =====================================================================
# MODULOS 3, 4 Y 5 (DIRECTORIO, PLANTA, REPORTES)
# =====================================================================
elif menu == "🏢 Directorio CRM (Clientes/Obras)":
    st.header("🏢 Gestión CRM: Clientes y Catálogo de Obras")
    t_cli, t_obr = st.tabs(["👥 Base de Clientes (Empresas)", "📍 Registro de Obras"])
    with t_cli:
        edit_cli = st.data_editor(df_clientes, hide_index=True, use_container_width=True, num_rows="dynamic")
        if st.button("Sincronizar CRM"):
            for _, row in edit_cli.iterrows():
                if str(row["razon_social"]) != "nan":
                    r_d = row.to_dict()
                    for k in r_d: r_d[k] = str(r_d[k]) if pd.notna(r_d[k]) else ""
                    supabase.table("clientes").upsert(r_d).execute()
            st.rerun()
    with t_obr:
        c1, c2 = st.columns([1,2])
        with c1:
            with st.form("form_obra"):
                cli_sel = st.selectbox("Pertenece al Cliente:", df_clientes["razon_social"].tolist() if not df_clientes.empty else [])
                nom_ob = st.text_input("Nombre de la Obra/Tramo *")
                dir_ob = st.text_area("Dirección")
                link_wpp = st.text_input("Link WhatsApp / Google Maps")
                resp = st.text_input("Ingenieros Autorizados (Separar por comas)")
                lat = st.number_input("Latitud", format="%.6f", value=25.6866)
                lon = st.number_input("Longitud", format="%.6f", value=-100.3161)
                if st.form_submit_button("Agregar Obra"):
                    if nom_ob:
                        supabase.table("obras").insert({"cliente": str(cli_sel), "nombre_obra": str(nom_ob), "direccion": str(dir_ob), "link_ubicacion": str(link_wpp), "responsables": str(resp), "latitud": float(lat), "longitud": float(lon)}).execute()
                        st.rerun()
        with c2:
            if not df_obras.empty: st.dataframe(df_obras[["cliente", "nombre_obra", "responsables", "link_ubicacion"]], hide_index=True, use_container_width=True)

elif menu == "⚙️ Planta, Inventario y Flota":
    st.header("⚙️ Gestión de Inventarios y Flota")
    t_inv, t_flota = st.tabs(["🏭 Planta y Asfalto", "🚛 Control de Camiones"])
    with t_inv:
        inv_actual = float(df_planta.iloc[0]["inventario_actual"]) if not df_planta.empty else 0
        cap_planta = float(df_planta.iloc[0]["capacidad_total"]) if not df_planta.empty else 50000
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Nivel de Asfalto", f"{inv_actual:,.0f} Lts", f"Capacidad Max: {cap_planta:,.0f}")
            add_inv = st.number_input("Registrar Producción / Compra (Lts)", min_value=0, step=1000)
            if st.button("Ingresar Material al Tanque"):
                supabase.table("config_planta").update({"inventario_actual": float(inv_actual + add_inv)}).eq("id", 1).execute()
                st.rerun()
        with c2:
            u_rec = st.selectbox("Unidad que se recarga", df_distribuidoras["unidad"].tolist() if not df_distribuidoras.empty else [])
            l_transf = st.number_input("Litros a Transferir a la unidad", min_value=0, step=500)
            if st.button("Ejecutar Transferencia a Unidad"):
                if inv_actual >= l_transf:
                    u_info = df_distribuidoras[df_distribuidoras["unidad"] == u_rec].iloc[0]
                    supabase.table("config_planta").update({"inventario_actual": float(inv_actual - l_transf)}).eq("id", 1).execute()
                    supabase.table("distribuidoras").update({"litros_disponibles": int(u_info["litros_disponibles"] + l_transf), "estado": "En Planta"}).eq("unidad", str(u_rec)).execute()
                    st.success("Recarga Completada")
                    st.rerun()
                else: st.error("No hay suficiente material en planta.")
    with t_flota:
        if not df_distribuidoras.empty:
            opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus", options=["Operativa", "En Taller", "Sin Chofer"])}
            edt_flota = st.data_editor(df_distribuidoras[["unidad", "chofer", "capacidad_total", "litros_disponibles", "condicion_operativa", "km_totales"]], hide_index=True, use_container_width=True, column_config=opts)
            if st.button("Guardar Cambios de Flota"):
                for _, r in edt_flota.iterrows():
                    r_dict = r.to_dict()
                    r_dict["capacidad_total"] = int(r_dict["capacidad_total"])
                    r_dict["litros_disponibles"] = int(r_dict["litros_disponibles"])
                    r_dict["km_totales"] = float(r_dict["km_totales"])
                    supabase.table("distribuidoras").upsert(r_dict).execute()
                st.success("Flota Actualizada.")
                st.rerun()

elif menu == "📂 Histórico y Reportes":
    st.header("📂 Cierre Diario Manual y Archivo")
    f_rep = st.date_input("Selecciona la fecha a exportar manual", datetime.date.today())
    df_rep_dia = df_tiros[df_tiros["fecha"] == str(f_rep)] if not df_tiros.empty else pd.DataFrame()
    if not df_rep_dia.empty:
        st.dataframe(df_rep_dia[["orden_visita", "hora", "distribuidora", "litros", "estatus", "distancia_km"]].sort_values(by=["distribuidora", "orden_visita"]), hide_index=True)
        pdf_bytes = generar_pdf(df_rep_dia, str(f_rep))
        st.download_button(label="📥 Descargar Reporte PDF del Día", data=pdf_bytes, file_name=f"Reporte_PAESA_{f_rep}.pdf", mime="application/pdf")
        if st.button("🚀 Enviar este reporte a Telegram Ahora Mismo"):
            enviar_pdf_telegram(pdf_bytes, f"Reporte_Manual_{f_rep}.pdf", f"📊 *REPORTE LOGÍSTICO SOLICITADO* ({f_rep})\nCierre de operaciones enviado manualmente.")
            st.success("Reporte enviado al canal de ingenieros.")
    else: st.info("No hay registros operativos para esta fecha.")
