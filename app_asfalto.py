import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import requests
import datetime
from supabase import create_client, Client
from fpdf import FPDF
import io

# =====================================================================
# 🔐 CONFIGURACIÓN Y CONEXIÓN
# =====================================================================
st.set_page_config(layout="wide", page_title="PAESA ERP - Logística", page_icon="🏗️")

SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFieW15cHVqZm9ubXR2YWtmc2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MjA0OTIsImV4cCI6MjA5ODQ5NjQ5Mn0.AsystVXsFbMmHoi8RarhBqPsW4zgvc-EcwAEo9BXV-Q"

if "auth" not in st.session_state: st.session_state["auth"] = False
if not st.session_state["auth"]:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏗️ PAESA Logística")
        st.markdown("### Acceso al Sistema ERP")
        usr = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        if st.button("Ingresar al Sistema", use_container_width=True):
            if usr == "admin" and pwd == "asfalto2026":
                st.session_state["auth"] = True
                st.rerun()
            else: st.error("Acceso denegado.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =====================================================================
# 📡 FUNCIONES DE ACCESO A DATOS (CRUDS)
# =====================================================================
def get_table(table):
    try: return pd.DataFrame(supabase.table(table).select("*").execute().data)
    except: return pd.DataFrame()

df_planta = get_table("config_planta")
df_distribuidoras = get_table("distribuidoras")
df_clientes = get_table("clientes")
df_obras = get_table("obras")
df_tiros = get_table("registro_tiros")

if not df_planta.empty:
    COORDS_PLANTA = (float(df_planta.iloc[0]["latitud"]), float(df_planta.iloc[0]["longitud"]))
else: COORDS_PLANTA = (25.8250665, -100.4109077)

def calc_ruta(c1, c2):
    try:
        res = requests.get(f"http://router.project-osrm.org/route/v1/driving/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=false").json()
        return round(res["routes"][0]["distance"]/1000.0, 2)
    except: return 0.0

def generar_pdf(df_dia, fecha):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, txt=f"Reporte Operativo PAESA - {fecha}", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", size=10)
    
    # Encabezados de tabla
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(30, 8, "Hora", border=1, fill=True)
    pdf.cell(30, 8, "Unidad", border=1, fill=True)
    pdf.cell(90, 8, "Obra / Destino", border=1, fill=True)
    pdf.cell(20, 8, "Litros", border=1, fill=True)
    pdf.cell(20, 8, "Estatus", border=1, fill=True)
    pdf.ln()
    
    # Filas
    if not df_dia.empty:
        for _, row in df_dia.sort_values(by="hora").iterrows():
            obra_nombre = df_obras[df_obras["id"] == row["obra_id"]].iloc[0]["nombre_obra"] if not df_obras.empty else "Desconocida"
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
    st.image("https://cdn-icons-png.flaticon.com/512/3233/3233483.png", width=100)
    st.markdown("## PAESA ERP")
    menu = st.radio("Módulos Principales", [
        "📊 Dashboard Principal", 
        "🚚 Operaciones y Despacho", 
        "🏢 Directorio: Clientes y Obras", 
        "⚙️ Planta y Flota", 
        "📂 Registro Histórico / Reportes"
    ])
    st.markdown("---")
    if st.button("Cerrar Sesión 🔒", use_container_width=True):
        st.session_state["auth"] = False
        st.rerun()

# =====================================================================
# 📊 MÓDULO 1: DASHBOARD PRINCIPAL
# =====================================================================
if menu == "📊 Dashboard Principal":
    st.header("📊 Resumen Operativo en Tiempo Real")
    
    # 1. Tarjetas de KPI
    km_totales = df_distribuidoras["km_totales"].sum() if not df_distribuidoras.empty else 0
    tiros_hoy = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
    volumen_hoy = tiros_hoy[tiros_hoy["estatus"] == "Completado ✅"]["litros"].sum() if not tiros_hoy.empty else 0
    unidades_op = len(df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]) if not df_distribuidoras.empty else 0
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🛣️ KM Totales Flota", f"{km_totales:,.1f} km")
    c2.metric("💧 Asfalto Colocado Hoy", f"{volumen_hoy:,.0f} Lts")
    c3.metric("🚚 Unidades Operativas", f"{unidades_op} Activas")
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
                    obra = df_obras[df_obras["id"] == t["obra_id"]].iloc[0]
                    color = "green" if t["estatus"] == "Completado ✅" else ("orange" if t["estatus"] == "En Proceso" else "blue")
                    folium.Marker((obra["latitud"], obra["longitud"]), popup=f"{obra['nombre_obra']}<br>{t['litros']} Lts", icon=folium.Icon(color=color)).add_to(m)
        folium_static(m, width=700, height=350)

# =====================================================================
# 🚚 MÓDULO 2: OPERACIONES Y DESPACHO
# =====================================================================
elif menu == "🚚 Operaciones y Despacho":
    st.header("🚚 Control Logístico y Asignación")
    
    tab1, tab2 = st.tabs(["➕ 1. Crear Orden de Servicio", "🚛 2. Asignación y Seguimiento"])
    
    with tab1:
        if df_obras.empty: st.warning("Primero debes registrar un Cliente y una Obra en el Directorio.")
        else:
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
                    supabase.table("registro_tiros").insert({"obra_id": obra_id, "litros": litros, "fecha": str(fecha), "hora": str(hora), "ingeniero_responsable": ing, "distribuidora": "Sin Asignar", "estatus": "Pendiente"}).execute()
                    st.success("Orden Generada Correctamente.")
                    st.rerun()

    with tab2:
        f_filtro = st.date_input("Consultar Fecha Operativa", datetime.date.today())
        df_dia = df_tiros[df_tiros["fecha"] == str(f_filtro)] if not df_tiros.empty else pd.DataFrame()
        
        if not df_dia.empty:
            for _, row in df_dia.sort_values(by="hora").iterrows():
                obra = df_obras[df_obras["id"] == row["obra_id"]].iloc[0] if not df_obras.empty else None
                if obra is not None:
                    with st.expander(f"📌 {row['hora']} | {obra['nombre_obra']} ({row['litros']:,} Lts) - Estado: {row['estatus']}", expanded=(row['estatus']=="Pendiente")):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Cliente:** {obra['cliente']}")
                            st.write(f"**Ingeniero:** {row['ingeniero_responsable']}")
                            st.write(f"**Dirección:** {obra['direccion']}")
                        with col2:
                            # Asignación de Camión
                            ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]["unidad"].tolist() if not df_distribuidoras.empty else []
                            idx_camion = ops.index(row["distribuidora"]) if row["distribuidora"] in ops else 0
                            n_camion = st.selectbox("Asignar Unidad", ["Sin Asignar"] + ops, index=(0 if row["distribuidora"]=="Sin Asignar" else ops.index(row["distribuidora"])+1), key=f"cam_{row['id']}")
                            if st.button("Confirmar Unidad y Calcular Ruta", key=f"btn_{row['id']}"):
                                dist = calc_ruta(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                supabase.table("registro_tiros").update({"distribuidora": n_camion, "distancia_km": dist}).eq("id", row["id"]).execute()
                                st.rerun()
                        with col3:
                            # Estatus
                            est_opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                            n_est = st.selectbox("Actualizar Estatus", est_opts, index=est_opts.index(row["estatus"]), key=f"est_{row['id']}")
                            if n_est != row["estatus"]:
                                supabase.table("registro_tiros").update({"estatus": n_est}).eq("id", row["id"]).execute()
                                # Sumar KMs si se completó
                                if n_est == "Completado ✅" and row["distribuidora"] != "Sin Asignar":
                                    km_prev = float(df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]["km_totales"])
                                    supabase.table("distribuidoras").update({"km_totales": km_prev + float(row["distancia_km"])}).eq("unidad", row["distribuidora"]).execute()
                                st.rerun()
                            if st.button("🗑️ Eliminar Tiro", key=f"del_{row['id']}"):
                                supabase.table("registro_tiros").delete().eq("id", row["id"]).execute()
                                st.rerun()
        else: st.info("No hay operaciones registradas para esta fecha.")

# =====================================================================
# 🏢 MÓDULO 3: DIRECTORIO DE CLIENTES Y OBRAS
# =====================================================================
elif menu == "🏢 Directorio: Clientes y Obras":
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
                if st.form_submit_button("Crear Cliente"):
                    if rs:
                        supabase.table("clientes").insert({"razon_social": rs, "rfc": rfc, "contacto_principal": cont, "telefono": tel, "email": email}).execute()
                        st.success("Cliente Creado.")
                        st.rerun()
        with c2:
            st.markdown("### Directorio Activo")
            if not df_clientes.empty: st.dataframe(df_clientes, hide_index=True, use_container_width=True)
            
    with t_obr:
        if df_clientes.empty: st.warning("Registra al menos un cliente primero.")
        else:
            c1, c2 = st.columns([1,2])
            with c1:
                with st.form("form_obra"):
                    cli_sel = st.selectbox("Pertenece al Cliente:", df_clientes["razon_social"].tolist())
                    nom_ob = st.text_input("Nombre de la Obra/Tramo *")
                    dir_ob = st.text_area("Dirección Completa")
                    lat = st.number_input("Latitud", format="%.6f", value=25.6866)
                    lon = st.number_input("Longitud", format="%.6f", value=-100.3161)
                    if st.form_submit_button("Agregar Obra al Catálogo"):
                        if nom_ob:
                            supabase.table("obras").insert({"cliente": cli_sel, "nombre_obra": nom_ob, "direccion": dir_ob, "latitud": float(lat), "longitud": float(lon)}).execute()
                            st.success("Obra Creada.")
                            st.rerun()
            with c2:
                st.markdown("### Obras Registradas")
                if not df_obras.empty: st.dataframe(df_obras[["cliente", "nombre_obra", "direccion"]], hide_index=True, use_container_width=True)

# =====================================================================
# ⚙️ MÓDULO 4: PLANTA Y FLOTA
# =====================================================================
elif menu == "⚙️ Planta y Flota":
    st.header("⚙️ Gestión de Inventarios e Infraestructura")
    
    st.subheader("Control de Flota y Operadores")
    if not df_distribuidoras.empty:
        opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus Mecánico", options=["Operativa", "En Taller", "Sin Chofer"])}
        edt_flota = st.data_editor(df_distribuidoras, hide_index=True, use_container_width=True, column_config=opts)
        if st.button("Guardar Cambios de Flota"):
            for _, r in edt_flota.iterrows():
                supabase.table("distribuidoras").upsert(r.to_dict()).execute()
            st.success("Flota Actualizada.")
            st.rerun()
            
    st.markdown("---")
    st.subheader("⛽ Recargas en Planta")
    if not df_planta.empty and not df_distribuidoras.empty:
        c1, c2 = st.columns(2)
        inv = float(df_planta.iloc[0]["inventario_actual"])
        with c1:
            st.metric("Inventario Tanque Madre", f"{int(inv):,} Lts")
            add_inv = st.number_input("Producción Nueva (Añadir Lts)", min_value=0, step=1000)
            if st.button("Ingresar al Tanque Madre"):
                supabase.table("config_planta").update({"inventario_actual": float(inv + add_inv)}).eq("id", 1).execute()
                st.rerun()
        with c2:
            st.write("Transferir a Camión:")
            u_rec = st.selectbox("Unidad", df_distribuidoras["unidad"].tolist())
            l_transf = st.number_input("Litros a Transferir", min_value=0, step=500)
            if st.button("Ejecutar Transferencia"):
                u_info = df_distribuidoras[df_distribuidoras["unidad"] == u_rec].iloc[0]
                supabase.table("config_planta").update({"inventario_actual": float(inv - l_transf)}).eq("id", 1).execute()
                supabase.table("distribuidoras").update({"litros_disponibles": int(u_info["litros_disponibles"] + l_transf)}).eq("unidad", u_rec).execute()
                st.success("Recarga Completada")
                st.rerun()

# =====================================================================
# 📂 MÓDULO 5: HISTÓRICO Y REPORTES PDF
# =====================================================================
elif menu == "📂 Registro Histórico / Reportes":
    st.header("📂 Carga Histórica y Generación de Reportes")
    
    t_rep, t_hist = st.tabs(["📄 Generar Reporte PDF del Día", "⏳ Cargar Trabajos Pasados"])
    
    with t_rep:
        f_rep = st.date_input("Selecciona el día a exportar", datetime.date.today())
        df_rep_dia = df_tiros[df_tiros["fecha"] == str(f_rep)] if not df_tiros.empty else pd.DataFrame()
        
        if not df_rep_dia.empty:
            st.dataframe(df_rep_dia[["hora", "distribuidora", "litros", "estatus"]], hide_index=True)
            pdf_bytes = generar_pdf(df_rep_dia, str(f_rep))
            st.download_button(label="📥 Descargar Reporte en PDF", data=pdf_bytes, file_name=f"Reporte_Operativo_{f_rep}.pdf", mime="application/pdf")
            st.caption("Puedes descargar el PDF y adjuntarlo rápidamente en tu correo empresarial.")
        else: st.info("No hay operaciones para generar PDF en esta fecha.")
            
    with t_hist:
        st.write("Utiliza este formulario para registrar trabajos de meses anteriores y poblar tus estadísticas sin que aparezcan como urgencias de hoy.")
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
            
            if st.form_submit_button("Subir Registro al Archivo"):
                if ob_id:
                    supabase.table("registro_tiros").insert({"obra_id": ob_id, "litros": l_pasados, "fecha": str(f_pasada), "hora": "12:00:00", "distribuidora": cam, "estatus": "Completado ✅", "distancia_km": km_r}).execute()
                    if cam != "Sin Asignar":
                        km_act = float(df_distribuidoras[df_distribuidoras["unidad"] == cam].iloc[0]["km_totales"])
                        supabase.table("distribuidoras").update({"km_totales": km_act + km_r}).eq("unidad", cam).execute()
                    st.success("Trabajo histórico guardado en la estadística.")
                    st.rerun()
