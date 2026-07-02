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
# 🔐 CONFIGURACIÓN Y CREDENCIALES FIJAS
# =====================================================================
st.set_page_config(layout="wide", page_title="PAESA ERP - Logística", page_icon="🏗️")

# Credenciales inyectadas directamente para evitar errores TOML en Streamlit
SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFieW15cHVqZm9ubXR2YWtmc2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MjA0OTIsImV4cCI6MjA5ODQ5NjQ5Mn0.AsystVXsFbMmHoi8RarhBqPsW4zgvc-EcwAEo9BXV-Q"
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "asfalto2026"
TELEGRAM_TOKEN = "8321781121:AAE9mLUzOGZwZwGmpQMN614ROSQGFrS-jbM"
TELEGRAM_CHAT_ID = "6612216260"

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
# 🤖 BOT DE TELEGRAM MULTI-USUARIO
# =====================================================================
def enviar_telegram(mensaje):
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        # Permite múltiples Chat IDs separados por coma
        chats = str(TELEGRAM_CHAT_ID).split(",")
        for chat in chats:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {"chat_id": chat.strip(), "text": mensaje, "parse_mode": "Markdown"}
            try: requests.post(url, json=payload, timeout=3)
            except: pass

def registrar_notificacion(tipo, mensaje, enviar_bot=False):
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try: supabase.table("notificaciones").insert({"tipo": str(tipo), "mensaje": str(mensaje), "fecha_hora": ahora, "leida": False}).execute()
    except: pass
    if enviar_bot:
        enviar_telegram(f"🏗️ *PAESA ALERTAS*\n*Módulo:* {tipo}\n*Detalle:* {mensaje}")

# =====================================================================
# 📡 EXTRACCIÓN DE DATOS
# =====================================================================
def get_table(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except: return pd.DataFrame()

df_planta = get_table("config_planta")
df_distribuidoras = get_table("distribuidoras")
df_clientes = get_table("clientes")
df_obras = get_table("obras")
df_tiros = get_table("registro_tiros")
df_notif = get_table("notificaciones")

COORDS_PLANTA = (float(df_planta.iloc[0]["latitud"]), float(df_planta.iloc[0]["longitud"])) if not df_planta.empty else (25.8250, -100.4109)

def get_route_geometry(c1, c2):
    """Obtiene la ruta OSRM y devuelve Coordenadas, Distancia y Tiempo"""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=full&geometries=geojson"
        res = requests.get(url, timeout=5).json()
        if res.get("code") == "Ok":
            coords = res["routes"][0]["geometry"]["coordinates"]
            ruta_mapa = [[p[1], p[0]] for p in coords] # Folium requiere Lat, Lon
            return ruta_mapa, round(res["routes"][0]["distance"]/1000.0, 1), round(res["routes"][0]["duration"]/60.0, 0)
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
    pdf.cell(20, 8, "Hora", border=1, fill=True)
    pdf.cell(25, 8, "Unidad", border=1, fill=True)
    pdf.cell(80, 8, "Obra / Destino", border=1, fill=True)
    pdf.cell(15, 8, "Litros", border=1, fill=True)
    pdf.cell(30, 8, "Estatus", border=1, fill=True)
    pdf.cell(20, 8, "KM", border=1, fill=True)
    pdf.ln()
    
    if not df_dia.empty:
        for _, row in df_dia.sort_values(by="hora").iterrows():
            obra_n = df_obras[df_obras["id"] == row["obra_id"]].iloc[0]["nombre_obra"] if not df_obras.empty else "N/A"
            pdf.cell(20, 8, str(row["hora"]), border=1)
            pdf.cell(25, 8, str(row["distribuidora"]), border=1)
            pdf.cell(80, 8, str(obra_n)[:40], border=1)
            pdf.cell(15, 8, str(row["litros"]), border=1)
            pdf.cell(30, 8, str(row["estatus"][:12]), border=1)
            pdf.cell(20, 8, str(row["distancia_km"]), border=1)
            pdf.ln()
    return bytes(pdf.output())

# =====================================================================
# 🖥️ NAVEGACIÓN Y SIDEBAR
# =====================================================================
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    else: st.markdown("## 🏗️ PAESA ERP")
        
    st.caption("Sistema de Logística Integral")
    
    notif_no_leidas = len(df_notif[df_notif["leida"] == False]) if not df_notif.empty and "leida" in df_notif.columns else 0
    if notif_no_leidas > 0:
        st.error(f"🔔 {notif_no_leidas} Alertas Nuevas")
        if st.button("✅ Aceptar Alertas (Ocultar)", use_container_width=True):
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
    st.header("📊 Inteligencia Operativa")
    
    inv_actual = float(df_planta.iloc[0]["inventario_actual"]) if not df_planta.empty else 0
    stock_min = float(df_planta.iloc[0].get("stock_minimo", 15000)) if not df_planta.empty else 15000
    
    if inv_actual < stock_min:
        st.error(f"🚨 ALERTA: El inventario de planta ({inv_actual:,.0f} Lts) está por debajo del límite de seguridad.")
    
    tiros_hoy = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
    volumen_hoy = tiros_hoy[tiros_hoy["estatus"] == "Completado ✅"]["litros"].sum() if not tiros_hoy.empty else 0
    tiros_pendientes = tiros_hoy[tiros_hoy["estatus"].isin(["Pendiente", "En Proceso"])] if not tiros_hoy.empty else pd.DataFrame()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("💧 Asfalto Colocado Hoy", f"{volumen_hoy:,.0f} Lts")
    c2.metric("🏭 Inventario Planta", f"{inv_actual:,.0f} Lts")
    c3.metric("📋 Tiros Totales Agendados (Hoy)", f"{len(tiros_hoy)}")
    
    st.markdown("---")
    col_dash1, col_dash2 = st.columns([1, 1])
    
    with col_dash1:
        st.markdown("### 🚦 Estatus de Flota (En Vivo)")
        if not df_distribuidoras.empty:
            df_show = df_distribuidoras.copy()
            for idx, cam in df_show.iterrows():
                tiros_activos_camion = tiros_hoy[(tiros_hoy["distribuidora"] == cam["unidad"]) & (tiros_hoy["estatus"] == "En Proceso")]
                if not tiros_activos_camion.empty:
                    lts_en_transito = tiros_activos_camion["litros"].sum()
                    df_show.at[idx, "estado"] = "En Tránsito 🚚"
                    df_show.at[idx, "litros_disponibles"] = f"{cam['litros_disponibles']} (-{lts_en_transito} en ruta)"
            
            st.dataframe(df_show[["unidad", "chofer", "estado", "litros_disponibles"]].rename(columns={"unidad":"Unidad", "chofer":"Operador", "estado":"Estatus", "litros_disponibles":"Volumen Disponible"}), hide_index=True, use_container_width=True)

        st.markdown("### 🕒 Tiros Pendientes (Hoy)")
        if not tiros_pendientes.empty:
            df_pend = tiros_pendientes[["hora", "distribuidora", "litros", "estatus"]].rename(columns={"hora":"Hora", "distribuidora":"Unidad", "litros":"Lts", "estatus":"Estatus"})
            st.dataframe(df_pend.sort_values(by="Hora"), hide_index=True, use_container_width=True)
        else: st.success("No hay tiros pendientes para hoy.")
            
    with col_dash2:
        st.markdown("### 🗺️ Mapa de Operaciones")
        m = folium.Map(location=COORDS_PLANTA, zoom_start=10)
        folium.Marker(COORDS_PLANTA, popup="Planta Principal", icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
        if not tiros_hoy.empty and not df_obras.empty:
            for _, t in tiros_hoy.iterrows():
                if t["estatus"] != "Cancelado ❌":
                    obras_filtradas = df_obras[df_obras["id"] == t["obra_id"]]
                    if not obras_filtradas.empty:
                        obra = obras_filtradas.iloc[0]
                        color = "green" if t["estatus"] == "Completado ✅" else ("orange" if t["estatus"] == "En Proceso" else "blue")
                        folium.Marker((obra["latitud"], obra["longitud"]), popup=f"{obra['nombre_obra']}<br>{t['litros']} Lts", icon=folium.Icon(color=color)).add_to(m)
        folium_static(m, width=600, height=450)

# =====================================================================
# 🚚 MÓDULO 2: OPERACIONES
# =====================================================================
# =====================================================================
# 🚚 MÓDULO 2: OPERACIONES Y DESPACHO INTELIGENTE
# =====================================================================
elif menu == "🚚 Operaciones y Despacho":
    st.header("🚚 Control Logístico y Asistente de Asignación")
    tab1, tab2 = st.tabs(["➕ 1. Crear Orden de Servicio", "🧠 2. Asistente de Despacho y Rutas"])
    
    with tab1:
        with st.form("form_crear_orden"):
            df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
            obra_sel = st.selectbox("Seleccionar Obra / Destino", df_obras["display"].tolist() if not df_obras.empty else [])
            
            c1, c2, c3 = st.columns(3)
            litros = c1.number_input("Volumen Requerido (Lts)", min_value=0, step=500)
            fecha = c2.date_input("Fecha de Ejecución")
            hora = c3.time_input("Hora Estimada")
            
            c_nota1, c_nota2 = st.columns([1,2])
            ing = c_nota1.text_input("Ingeniero / Residente Responsable")
            notas = c_nota2.text_input("Notas u Observaciones (Opcional)")
            
            if st.form_submit_button("Generar Orden de Tiro", use_container_width=True):
                if not df_obras.empty:
                    obra_id = int(df_obras[df_obras["display"] == obra_sel].iloc[0]["id"])
                    dict_orden = {"obra_id": obra_id, "litros": int(litros), "fecha": str(fecha), "hora": str(hora), "ingeniero_responsable": str(ing), "notas": str(notas), "distribuidora": "Sin Asignar", "estatus": "Pendiente", "minutos_retraso": 0, "distancia_km": 0.0}
                    supabase.table("registro_tiros").insert(dict_orden).execute()
                    registrar_notificacion("Operación", f"Nueva orden: {litros} Lts para {obra_sel}.", enviar_bot=True)
                    st.success("Orden Generada Correctamente.")
                    st.rerun()

    with tab2:
        f_filtro = st.date_input("Consultar Fecha Operativa", datetime.date.today())
        df_dia = df_tiros[df_tiros["fecha"] == str(f_filtro)] if not df_tiros.empty else pd.DataFrame()
        
        if not df_dia.empty:
            for _, row in df_dia.sort_values(by="hora").iterrows():
                obras_filtro = df_obras[df_obras["id"] == row["obra_id"]]
                if not obras_filtro.empty:
                    obra = obras_filtro.iloc[0]
                    with st.expander(f"📌 {row['hora']} | {obra['nombre_obra']} ({row['litros']:,} Lts) - {row['estatus']}", expanded=(row['estatus']=="Pendiente")):
                        col1, col2 = st.columns([1, 2])
                        
                        # --- PANEL IZQUIERDO: DATOS DE LA OBRA ---
                        with col1:
                            st.markdown(f"**🏢 Cliente:** {obra['cliente']}")
                            st.markdown(f"**👷‍♂️ Recibe:** {row['ingeniero_responsable']}")
                            st.markdown(f"**📝 Notas:** {row.get('notas', 'Sin notas')}")
                            if row.get('link_ubicacion'): 
                                st.markdown(f"[📍 Abrir Ubicación en Maps]({obra['link_ubicacion']})")
                                
                            # Evaluación de Capacidad Múltiple
                            capacidad_max_flota = df_distribuidoras["capacidad_total"].max() if not df_distribuidoras.empty else 0
                            if row["litros"] > capacidad_max_flota:
                                st.error(f"🚨 **ALERTA DE CAPACIDAD:** El pedido de {row['litros']:,} Lts supera a tu camión más grande ({capacidad_max_flota:,} Lts). **Deberás enviar al menos 2 equipos o hacer viajes redondos.**")
                        
                        # --- PANEL DERECHO: ASISTENTE INTELIGENTE DE ASIGNACIÓN ---
                        with col2:
                            if row["distribuidora"] == "Sin Asignar":
                                st.markdown("### 🧠 Análisis de Flota Disponible")
                                
                                # Matriz de decisión en tiempo real
                                matriz_decision = []
                                ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"] if not df_distribuidoras.empty else pd.DataFrame()
                                
                                if not ops.empty:
                                    for _, cam in ops.iterrows():
                                        # Simular ruta para cada camión desde Planta (se puede mejorar a ruta desde su ubicación actual)
                                        _, dist, tiempo = get_route_geometry(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                        
                                        # Evaluar si el camión tiene el material suficiente
                                        alcanza = "✅ Sí" if cam["litros_disponibles"] >= row["litros"] else f"❌ No (Faltan {row['litros'] - cam['litros_disponibles']:,} Lts)"
                                        
                                        matriz_decision.append({
                                            "Unidad": cam["unidad"],
                                            "Operador": cam["chofer"],
                                            "Tanque Actual": f"{cam['litros_disponibles']:,} Lts",
                                            "¿Cubre el pedido?": alcanza,
                                            "Distancia": f"{dist} km",
                                            "ETA (Tiempo)": f"{tiempo} min"
                                        })
                                    
                                    # Mostrar la tabla comparativa al despachador
                                    st.dataframe(pd.DataFrame(matriz_decision), hide_index=True, use_container_width=True)
                                
                                # Selector para asignar después de ver la tabla
                                op_lista = ops["unidad"].tolist() if not ops.empty else []
                                n_camion = st.selectbox("Selecciona la mejor unidad basada en el análisis:", ["Seleccionar..."] + op_lista, key=f"cam_{row['id']}")
                                
                                if n_camion != "Seleccionar..." and st.button("Confirmar Despacho", key=f"btn_{row['id']}"):
                                    _, dist_final, _ = get_route_geometry(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                    supabase.table("registro_tiros").update({"distribuidora": str(n_camion), "distancia_km": float(dist_final), "estatus": "En Proceso"}).eq("id", int(row["id"])).execute()
                                    registrar_notificacion("Operación", f"{n_camion} asignado a {obra['nombre_obra']}.", enviar_bot=True)
                                    st.rerun()
                                    
                            else:
                                # SI YA ESTÁ ASIGNADO, MOSTRAR PANEL DE RASTREO Y ESTATUS
                                st.info(f"🚚 Unidad Asignada: **{row['distribuidora']}**")
                                
                                est_opts = ["En Proceso", "Completado ✅", "Cancelado ❌"]
                                n_est = st.selectbox("Actualizar Estatus de Entrega", est_opts, index=est_opts.index(row["estatus"]) if row["estatus"] in est_opts else 0, key=f"est_{row['id']}")
                                
                                if st.button("Guardar Estatus", key=f"upd_{row['id']}"):
                                    supabase.table("registro_tiros").update({"estatus": str(n_est)}).eq("id", int(row["id"])).execute()
                                    
                                    if n_est == "Completado ✅":
                                        u_info = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                                        supabase.table("distribuidoras").update({
                                            "litros_disponibles": max(0, int(u_info["litros_disponibles"] - row["litros"]))
                                        }).eq("unidad", str(row["distribuidora"])).execute()
                                        registrar_notificacion("Operación", f"Descarga finalizada en {obra['nombre_obra']}", enviar_bot=True)
                                    st.rerun()
                                    
                                if st.button("🗺️ Ver Ruta Satelital (OSRM)", key=f"sim_{row['id']}"):
                                    ruta_ida, d_ida, t_ida = get_route_geometry(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                    st.success(f"**Ruta de Ida:** {d_ida} km | Tiempo estimado: {t_ida} minutos.")
                                    m_ruta = folium.Map(location=COORDS_PLANTA, zoom_start=11)
                                    if ruta_ida: folium.PolyLine(ruta_ida, color="blue", weight=5, opacity=0.8).add_to(m_ruta)
                                    folium.Marker(COORDS_PLANTA, popup="Planta", icon=folium.Icon(color="red")).add_to(m_ruta)
                                    folium.Marker((float(obra["latitud"]), float(obra["longitud"])), popup="Obra", icon=folium.Icon(color="green")).add_to(m_ruta)
                                    folium_static(m_ruta, width=500, height=300)
                                    
                                if st.button("🗑️ Eliminar Tiro (Admin)", key=f"del_{row['id']}"):
                                    supabase.table("registro_tiros").delete().eq("id", int(row["id"])).execute()
                                    st.rerun()
        else: st.info("No hay operaciones registradas para esta fecha.")

# =====================================================================
# 🏢 MÓDULO 3: DIRECTORIO CRM
# =====================================================================
elif menu == "🏢 Directorio CRM (Clientes/Obras)":
    st.header("🏢 Gestión CRM: Clientes y Catálogo de Obras")
    t_cli, t_obr = st.tabs(["👥 Base de Clientes (Empresas)", "📍 Catálogo de Obras (Ubicaciones)"])
    
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
            st.write("Registra obras para programar envíos:")
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

# =====================================================================
# ⚙️ MÓDULO 4: PLANTA, INVENTARIO Y FLOTA
# =====================================================================
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
                registrar_notificacion("Inventario", f"Ingreso de {add_inv} Lts a Planta. Total: {inv_actual + add_inv}", enviar_bot=True)
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

# =====================================================================
# 📂 MÓDULO 5: HISTÓRICO Y REPORTES
# =====================================================================
elif menu == "📂 Histórico y Reportes":
    st.header("📂 Auditoría y Reportes PDF")
    
    t_rep, t_hist = st.tabs(["📄 Exportar PDF (Cierre Diario)", "⏳ Cargar Trabajos Históricos"])
    
    with t_rep:
        f_rep = st.date_input("Selecciona el día a exportar", datetime.date.today())
        df_rep_dia = df_tiros[df_tiros["fecha"] == str(f_rep)] if not df_tiros.empty else pd.DataFrame()
        if not df_rep_dia.empty:
            st.dataframe(df_rep_dia[["hora", "distribuidora", "litros", "estatus", "distancia_km"]], hide_index=True)
            pdf_bytes = generar_pdf(df_rep_dia, str(f_rep))
            st.download_button(label="📥 Descargar Reporte Cierre de Día (PDF)", data=pdf_bytes, file_name=f"Reporte_PAESA_{f_rep}.pdf", mime="application/pdf")
        else: st.info("No hay operaciones para generar PDF en esta fecha.")
            
    with t_hist:
        with st.form("form_historico"):
            c1, c2 = st.columns(2)
            if not df_obras.empty:
                df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
                ob_id = int(df_obras[df_obras["display"] == c1.selectbox("Obra", df_obras["display"].tolist())].iloc[0]["id"])
            else: ob_id = None
            
            f_pasada = c2.date_input("Fecha Histórica", datetime.date.today() - datetime.timedelta(days=30))
            l_pasados = c1.number_input("Litros Entregados", min_value=0)
            cam = c2.selectbox("Camión que lo realizó", df_distribuidoras["unidad"].tolist() if not df_distribuidoras.empty else ["Sin Asignar"])
            km_r = c1.number_input("Kilómetros Recorridos", min_value=0.0)
            
            if st.form_submit_button("Subir Registro al Archivo Histórico"):
                if ob_id:
                    supabase.table("registro_tiros").insert({"obra_id": int(ob_id), "litros": int(l_pasados), "fecha": str(f_pasada), "hora": "12:00:00", "ingeniero_responsable": "Registro Histórico", "distribuidora": str(cam), "estatus": "Completado ✅", "minutos_retraso": 0, "distancia_km": float(km_r)}).execute()
                    if cam != "Sin Asignar":
                        km_act = float(df_distribuidoras[df_distribuidoras["unidad"] == cam].iloc[0]["km_totales"])
                        supabase.table("distribuidoras").update({"km_totales": km_act + float(km_r)}).eq("unidad", str(cam)).execute()
                    st.success("Trabajo histórico guardado exitosamente.")
                    st.rerun()
