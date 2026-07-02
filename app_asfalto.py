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
# 🔐 CONFIGURACIÓN Y SECRETS
# =====================================================================
st.set_page_config(layout="wide", page_title="PAESA ERP - Logística", page_icon="🏗️")

# Intentamos leer de los Secrets, si no, usamos los predeterminados
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    USUARIO_ADMIN = st.secrets.get("USUARIO_ADMIN", "admin")
    PASSWORD_ADMIN = st.secrets.get("PASSWORD_ADMIN", "asfalto2026")
    TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "")
    TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "")
except:
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
# 🤖 BOT DE TELEGRAM Y NOTIFICACIONES
# =====================================================================
def enviar_telegram(mensaje):
    """Envía un mensaje al bot de Telegram si está configurado."""
    if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
        try: requests.post(url, json=payload, timeout=5)
        except: pass

def registrar_notificacion(tipo, mensaje, enviar_bot=False):
    """Guarda en BD y opcionalmente envía alerta por Telegram."""
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try: supabase.table("notificaciones").insert({"tipo": str(tipo), "mensaje": str(mensaje), "fecha_hora": ahora, "leida": False}).execute()
    except: pass
    if enviar_bot:
        enviar_telegram(f"🏗️ *PAESA ALERTAS*\n*Tipo:* {tipo}\n*Mensaje:* {mensaje}")

# =====================================================================
# 📡 FUNCIONES BLINDADAS DE AUTO-RELLENO
# =====================================================================
def safe_get_table(table_name, default_data=None):
    """Extrae datos de Supabase. Si falla o está vacía, inyecta los default."""
    try:
        res = supabase.table(table_name).select("*").execute()
        if not res.data and default_data is not None:
            # Si es una lista de diccionarios, inserta todos
            if isinstance(default_data, list):
                for row in default_data: supabase.table(table_name).upsert(row).execute()
            else: supabase.table(table_name).upsert(default_data).execute()
            res = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        if default_data is not None:
            return pd.DataFrame(default_data) if isinstance(default_data, list) else pd.DataFrame([default_data])
        return pd.DataFrame()

df_planta = safe_get_table("config_planta", {"id": 1, "nombre": "Planta Monterrey", "latitud": 25.8250665, "longitud": -100.4109077, "capacidad_total": 50000, "inventario_actual": 40000, "costo_por_litro": 12.5, "stock_minimo": 15000})

df_distribuidoras = safe_get_table("distribuidoras", [
    {"unidad": "D-01", "chofer": "Juan Pérez", "capacidad_total": 10000, "litros_disponibles": 10000, "estado": "En Planta", "condicion_operativa": "Operativa", "km_totales": 0.0, "km_proximo_mantenimiento": 5000},
    {"unidad": "D-02", "chofer": "Carlos Gómez", "capacidad_total": 15000, "litros_disponibles": 15000, "estado": "En Planta", "condicion_operativa": "Operativa", "km_totales": 0.0, "km_proximo_mantenimiento": 5000}
])

df_clientes = safe_get_table("clientes", [
    {"razon_social": "Constructora Alfa SA de CV", "rfc": "CALF010101XYZ", "contacto_principal": "Ing. Roberto", "telefono": "8123456789", "email": "contacto@alfa.com"}
])

df_obras = safe_get_table("obras", [
    {"id": 1, "cliente": "Constructora Alfa SA de CV", "nombre_obra": "Carretera Nacional KM 250", "direccion": "Mty Sur", "latitud": 25.5689, "longitud": -100.2452}
])

df_tiros = safe_get_table("registro_tiros")
df_notif = safe_get_table("notificaciones")

COORDS_PLANTA = (float(df_planta.iloc[0]["latitud"]), float(df_planta.iloc[0]["longitud"])) if not df_planta.empty else (25.8250, -100.4109)

def calc_ruta(c1, c2):
    try:
        res = requests.get(f"http://router.project-osrm.org/route/v1/driving/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=false", timeout=3).json()
        return round(res["routes"][0]["distance"]/1000.0, 2)
    except: return 0.0

def generar_pdf(df_dia, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, txt=f"Reporte Operativo PAESA - {fecha}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", size=10)
    
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(30, 8, "Hora", border=1, fill=True)
    pdf.cell(30, 8, "Unidad", border=1, fill=True)
    pdf.cell(90, 8, "Obra / Destino", border=1, fill=True)
    pdf.cell(20, 8, "Litros", border=1, fill=True)
    pdf.cell(20, 8, "Estatus", border=1, fill=True)
    pdf.ln()
    
    if not df_dia.empty:
        for _, row in df_dia.sort_values(by="hora").iterrows():
            obra_nombre = df_obras[df_obras["id"] == row["obra_id"]].iloc[0]["nombre_obra"] if not df_obras.empty and row["obra_id"] in df_obras["id"].values else "Desconocida"
            pdf.cell(30, 8, str(row["hora"]), border=1)
            pdf.cell(30, 8, str(row["distribuidora"]), border=1)
            pdf.cell(90, 8, str(obra_nombre)[:45], border=1)
            pdf.cell(20, 8, str(row["litros"]), border=1)
            pdf.cell(20, 8, str(row["estatus"][:10]), border=1)
            pdf.ln()
    return pdf.output(dest='S').encode('latin-1')

# =====================================================================
# 🖥️ NAVEGACIÓN Y SIDEBAR
# =====================================================================
with st.sidebar:
    # Intenta cargar el logotipo si existe en el repositorio
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.markdown("## 🏗️ PAESA ERP")
        
    st.caption("Sistema de Logística Integral")
    
    notif_no_leidas = len(df_notif[df_notif["leida"] == False]) if not df_notif.empty and "leida" in df_notif.columns else 0
    if notif_no_leidas > 0:
        st.error(f"🔔 Tienes {notif_no_leidas} alertas nuevas")
        
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
    st.header("📊 Resumen Operativo en Tiempo Real")
    
    inv_actual = float(df_planta.iloc[0]["inventario_actual"]) if not df_planta.empty else 0
    stock_min = float(df_planta.iloc[0].get("stock_minimo", 15000)) if not df_planta.empty else 15000
    
    if inv_actual < stock_min:
        st.error(f"🚨 ALERTA: El inventario de planta ({inv_actual:,.0f} Lts) está por debajo del límite de seguridad. ¡Se requiere recarga inmediata!")
        # Enviar alerta por Telegram solo una vez por debajo del límite (Para evitar spam, requiere lógica extra, aquí lo mandamos si la sesión lo recarga)
    
    km_totales = df_distribuidoras["km_totales"].sum() if not df_distribuidoras.empty else 0
    tiros_hoy = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
    volumen_hoy = tiros_hoy[tiros_hoy["estatus"] == "Completado ✅"]["litros"].sum() if not tiros_hoy.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛣️ KM Totales Flota", f"{km_totales:,.1f} km")
    c2.metric("💧 Asfalto Colocado Hoy", f"{volumen_hoy:,.0f} Lts")
    c3.metric("🏭 Inventario Planta", f"{inv_actual:,.0f} Lts")
    c4.metric("📋 Tiros Agendados Hoy", f"{len(tiros_hoy)}")
    
    st.markdown("---")
    col_dash1, col_dash2 = st.columns([1, 2])
    
    with col_dash1:
        st.markdown("### 🚦 Estatus de Flota (En Vivo)")
        if not df_distribuidoras.empty:
            df_show = df_distribuidoras[["unidad", "chofer", "estado", "litros_disponibles"]].rename(columns={"unidad":"Unidad", "chofer":"Operador", "estado":"Estado", "litros_disponibles":"Tanque (Lts)"})
            st.dataframe(df_show, hide_index=True, use_container_width=True)
            
    with col_dash2:
        st.markdown("### 🗺️ Mapa de Operaciones (Hoy)")
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
        folium_static(m, width=700, height=350)

# =====================================================================
# 🚚 MÓDULO 2: OPERACIONES
# =====================================================================
elif menu == "🚚 Operaciones y Despacho":
    st.header("🚚 Control Logístico y Asignación")
    tab1, tab2 = st.tabs(["➕ 1. Crear Orden de Servicio", "🚛 2. Seguimiento Diario"])
    
    with tab1:
        with st.form("form_crear_orden"):
            df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
            obra_sel = st.selectbox("Seleccionar Obra / Destino", df_obras["display"].tolist())
            obra_id = int(df_obras[df_obras["display"] == obra_sel].iloc[0]["id"])
            
            c1, c2, c3 = st.columns(3)
            litros = c1.number_input("Volumen Requerido (Lts)", min_value=0, step=500)
            fecha = c2.date_input("Fecha de Ejecución")
            hora = c3.time_input("Hora Estimada")
            ing = st.text_input("Ingeniero / Residente Responsable")
            
            if st.form_submit_button("Generar Orden de Tiro", use_container_width=True):
                dict_orden = {"obra_id": int(obra_id), "litros": int(litros), "fecha": str(fecha), "hora": str(hora), "ingeniero_responsable": str(ing), "distribuidora": "Sin Asignar", "estatus": "Pendiente", "minutos_retraso": 0, "distancia_km": 0.0}
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
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Cliente:** {obra['cliente']}")
                            st.write(f"**Ingeniero:** {row['ingeniero_responsable']}")
                        with col2:
                            ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]["unidad"].tolist() if not df_distribuidoras.empty else []
                            idx_camion = ops.index(row["distribuidora"]) if row["distribuidora"] in ops else 0
                            n_camion = st.selectbox("Asignar Unidad", ["Sin Asignar"] + ops, index=(0 if row["distribuidora"]=="Sin Asignar" else ops.index(row["distribuidora"])+1), key=f"cam_{row['id']}")
                            if st.button("Confirmar Unidad / Calcular Ruta", key=f"btn_{row['id']}"):
                                dist = calc_ruta(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                supabase.table("registro_tiros").update({"distribuidora": str(n_camion), "distancia_km": float(dist)}).eq("id", int(row["id"])).execute()
                                st.rerun()
                        with col3:
                            est_opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                            n_est = st.selectbox("Actualizar Estatus", est_opts, index=est_opts.index(row["estatus"]), key=f"est_{row['id']}")
                            if n_est != row["estatus"]:
                                supabase.table("registro_tiros").update({"estatus": str(n_est)}).eq("id", int(row["id"])).execute()
                                if n_est == "Completado ✅" and row["distribuidora"] != "Sin Asignar":
                                    # Descontar del camión al completar
                                    u_info = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                                    supabase.table("distribuidoras").update({"km_totales": float(u_info["km_totales"]) + float(row["distancia_km"]), "litros_disponibles": max(0, int(u_info["litros_disponibles"] - row["litros"]))}).eq("unidad", str(row["distribuidora"])).execute()
                                    registrar_notificacion("Operación", f"Tiro Completado: {row['distribuidora']} entregó en {obra['nombre_obra']}", enviar_bot=True)
                                st.rerun()
                            if st.button("🗑️ Eliminar Tiro", key=f"del_{row['id']}"):
                                supabase.table("registro_tiros").delete().eq("id", int(row["id"])).execute()
                                st.rerun()

# =====================================================================
# 🏢 MÓDULO 3: DIRECTORIO CRM
# =====================================================================
elif menu == "🏢 Directorio CRM (Clientes/Obras)":
    st.header("🏢 Gestión CRM: Clientes y Catálogo de Obras")
    t_cli, t_obr = st.tabs(["👥 Base de Clientes (Empresas)", "📍 Catálogo de Obras (Ubicaciones)"])
    
    with t_cli:
        c1, c2 = st.columns([1,2])
        with c1:
            with st.form("form_cliente"):
                rs = st.text_input("Razón Social / Nombre Comercial *")
                rfc = st.text_input("RFC (Opcional)")
                cont = st.text_input("Contacto Principal")
                tel = st.text_input("Teléfono")
                email = st.text_input("Email")
                if st.form_submit_button("Guardar Cliente"):
                    if rs:
                        supabase.table("clientes").upsert({"razon_social": str(rs), "rfc": str(rfc), "contacto_principal": str(cont), "telefono": str(tel), "email": str(email)}).execute()
                        st.success("Cliente Creado.")
                        st.rerun()
        with c2:
            if not df_clientes.empty: st.dataframe(df_clientes, hide_index=True, use_container_width=True)
            
    with t_obr:
        c1, c2 = st.columns([1,2])
        with c1:
            with st.form("form_obra"):
                cli_sel = st.selectbox("Pertenece al Cliente:", df_clientes["razon_social"].tolist())
                nom_ob = st.text_input("Nombre de la Obra/Tramo *")
                dir_ob = st.text_area("Dirección Completa")
                lat = st.number_input("Latitud", format="%.6f", value=25.6866)
                lon = st.number_input("Longitud", format="%.6f", value=-100.3161)
                if st.form_submit_button("Agregar Obra"):
                    if nom_ob:
                        supabase.table("obras").insert({"cliente": str(cli_sel), "nombre_obra": str(nom_ob), "direccion": str(dir_ob), "latitud": float(lat), "longitud": float(lon)}).execute()
                        st.rerun()
        with c2:
            if not df_obras.empty: st.dataframe(df_obras[["cliente", "nombre_obra", "direccion"]], hide_index=True, use_container_width=True)

# =====================================================================
# ⚙️ MÓDULO 4: PLANTA, INVENTARIO Y FLOTA
# =====================================================================
elif menu == "⚙️ Planta, Inventario y Flota":
    st.header("⚙️ Gestión de Inventarios y Mantenimiento")
    
    t_inv, t_flota = st.tabs(["🏭 Planta y Asfalto", "🚛 Control de Camiones"])
    
    with t_inv:
        st.subheader("Control del Tanque Madre")
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
            st.write("Recarga de Petrolizadoras en Planta:")
            u_rec = st.selectbox("Unidad que se recarga", df_distribuidoras["unidad"].tolist() if not df_distribuidoras.empty else [])
            l_transf = st.number_input("Litros a Transferir a la unidad", min_value=0, step=500)
            if st.button("Ejecutar Transferencia"):
                if inv_actual >= l_transf:
                    u_info = df_distribuidoras[df_distribuidoras["unidad"] == u_rec].iloc[0]
                    supabase.table("config_planta").update({"inventario_actual": float(inv_actual - l_transf)}).eq("id", 1).execute()
                    supabase.table("distribuidoras").update({"litros_disponibles": int(u_info["litros_disponibles"] + l_transf), "estado": "En Planta", "ubicacion_actual": "Planta"}).eq("unidad", str(u_rec)).execute()
                    st.success("Recarga Completada")
                    st.rerun()
                else: st.error("No hay suficiente material en el tanque de la planta.")
                
    with t_flota:
        st.subheader("Mantenimiento y Control de Flota")
        if not df_distribuidoras.empty:
            opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus Mecánico", options=["Operativa", "En Taller", "Sin Chofer"])}
            edt_flota = st.data_editor(df_distribuidoras[["unidad", "chofer", "capacidad_total", "litros_disponibles", "condicion_operativa", "km_totales", "km_proximo_mantenimiento"]], hide_index=True, use_container_width=True, column_config=opts)
            if st.button("Guardar Cambios de Flota"):
                for _, r in edt_flota.iterrows():
                    r_dict = r.to_dict()
                    r_dict["capacidad_total"] = int(r_dict["capacidad_total"])
                    r_dict["litros_disponibles"] = int(r_dict["litros_disponibles"])
                    r_dict["km_totales"] = float(r_dict["km_totales"])
                    r_dict["km_proximo_mantenimiento"] = float(r_dict["km_proximo_mantenimiento"])
                    supabase.table("distribuidoras").upsert(r_dict).execute()
                st.success("Flota Actualizada.")
                st.rerun()

# =====================================================================
# 📂 MÓDULO 5: HISTÓRICO Y REPORTES
# =====================================================================
elif menu == "📂 Histórico y Reportes":
    st.header("📂 Auditoría, Reportes PDF y Carga Pasada")
    
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
        st.write("Registra trabajos de meses anteriores para poblar tus estadísticas y justificar combustible.")
        with st.form("form_historico"):
            c1, c2 = st.columns(2)
            if not df_obras.empty:
                df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
                ob_id = int(df_obras[df_obras["display"] == c1.selectbox("Obra", df_obras["display"].tolist())].iloc[0]["id"])
            else: ob_id = None
            
            f_pasada = c2.date_input("Fecha Histórica", datetime.date.today() - datetime.timedelta(days=30))
            l_pasados = c1.number_input("Litros Entregados", min_value=0)
            cam = c2.selectbox("Camión que lo realizó", df_distribuidoras["unidad"].tolist() if not df_distribuidoras.empty else ["Sin Asignar"])
            km_r = c1.number_input("Kilómetros Recorridos Reales", min_value=0.0)
            
            if st.form_submit_button("Subir Registro al Archivo Histórico"):
                if ob_id:
                    supabase.table("registro_tiros").insert({"obra_id": int(ob_id), "litros": int(l_pasados), "fecha": str(f_pasada), "hora": "12:00:00", "ingeniero_responsable": "Registro Histórico", "distribuidora": str(cam), "estatus": "Completado ✅", "minutos_retraso": 0, "distancia_km": float(km_r)}).execute()
                    if cam != "Sin Asignar":
                        km_act = float(df_distribuidoras[df_distribuidoras["unidad"] == cam].iloc[0]["km_totales"])
                        supabase.table("distribuidoras").update({"km_totales": km_act + float(km_r)}).eq("unidad", str(cam)).execute()
                    st.success("Trabajo histórico guardado exitosamente.")
                    st.rerun()
