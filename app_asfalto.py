import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import requests
import datetime
from supabase import create_client, Client
from fpdf import FPDF

# =====================================================================
# 🔐 CONFIGURACIÓN Y CONEXIÓN
# =====================================================================
st.set_page_config(layout="wide", page_title="PAESA ERP - Advanced", page_icon="🏗️")

SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFieW15cHVqZm9ubXR2YWtmc2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MjA0OTIsImV4cCI6MjA5ODQ5NjQ5Mn0.AsystVXsFbMmHoi8RarhBqPsW4zgvc-EcwAEo9BXV-Q"

if "auth" not in st.session_state: st.session_state["auth"] = False
if not st.session_state["auth"]:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🏗️ PAESA ERP Advanced")
        st.markdown("### Acceso Corporativo")
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
# 📡 FUNCIONES DE ACCESO A DATOS (CRUDS Y NOTIFICACIONES)
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

if not df_planta.empty:
    COORDS_PLANTA = (float(df_planta.iloc[0]["latitud"]), float(df_planta.iloc[0]["longitud"]))
else: COORDS_PLANTA = (25.8250665, -100.4109077)

def registrar_notificacion(tipo, mensaje):
    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    supabase.table("notificaciones").insert({"tipo": tipo, "mensaje": str(mensaje), "fecha_hora": ahora, "leida": False}).execute()

def calc_ruta(c1, c2):
    try:
        res = requests.get(f"http://router.project-osrm.org/route/v1/driving/{c1[1]},{c1[0]};{c2[1]},{c2[0]}?overview=false").json()
        return round(res["routes"][0]["distance"]/1000.0, 2)
    except: return 0.0

# =====================================================================
# 🖥️ NAVEGACIÓN Y SIDEBAR
# =====================================================================
with st.sidebar:
    st.markdown("## 🏗️ PAESA ERP")
    st.caption("Logística, Mantenimiento e Inventario")
    
    # Sistema de Alertas Rápidas
    notif_no_leidas = len(df_notif[df_notif["leida"] == False]) if not df_notif.empty else 0
    if notif_no_leidas > 0:
        st.error(f"🔔 Tienes {notif_no_leidas} alertas nuevas")
    
    st.markdown("---")
    menu = st.radio("Módulos de Operación", [
        "📊 Dashboard General", 
        "🚚 Control Logístico y Rastreo", 
        "📦 Inventario y Administración", 
        "⚙️ Flota y Mantenimiento",
        "🏢 Directorio CRM",
        "🔔 Centro de Notificaciones"
    ])
    st.markdown("---")
    if st.button("Cerrar Sesión 🔒", use_container_width=True):
        st.session_state["auth"] = False
        st.rerun()

# =====================================================================
# 📊 MÓDULO 1: DASHBOARD GENERAL
# =====================================================================
if menu == "📊 Dashboard General":
    st.header("📊 Inteligencia Operativa y Financiera")
    
    inv_actual = float(df_planta.iloc[0]["inventario_actual"]) if not df_planta.empty else 0
    costo_litro = float(df_planta.iloc[0].get("costo_por_litro", 0)) if not df_planta.empty else 0
    stock_min = float(df_planta.iloc[0].get("stock_minimo", 15000)) if not df_planta.empty else 15000
    valor_inventario = inv_actual * costo_litro
    
    tiros_hoy = df_tiros[df_tiros["fecha"] == str(datetime.date.today())] if not df_tiros.empty else pd.DataFrame()
    volumen_hoy = tiros_hoy[tiros_hoy["estatus"] == "Completado ✅"]["litros"].sum() if not tiros_hoy.empty else 0
    
    # 1. Alertas Críticas Frontales
    if inv_actual < stock_min:
        st.error(f"🚨 ALERTA DE INVENTARIO: El stock en planta ({inv_actual:,.0f} Lts) está por debajo del mínimo de seguridad ({stock_min:,.0f} Lts).")
        
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Valor de Inventario", f"${valor_inventario:,.2f}")
    c2.metric("💧 Stock Físico", f"{inv_actual:,.0f} Lts")
    c3.metric("📈 Entregado Hoy", f"{volumen_hoy:,.0f} Lts")
    c4.metric("🚚 Órdenes Activas Hoy", f"{len(tiros_hoy[tiros_hoy['estatus'] != 'Completado ✅']) if not tiros_hoy.empty else 0}")
    
    st.markdown("---")
    col_mapa, col_est = st.columns([2, 1])
    
    with col_mapa:
        st.markdown("### 🗺️ Rastreo de Entregas (Hoy)")
        m = folium.Map(location=COORDS_PLANTA, zoom_start=10)
        folium.Marker(COORDS_PLANTA, popup="Planta Principal", icon=folium.Icon(color="black", icon="building", prefix='fa')).add_to(m)
        if not tiros_hoy.empty and not df_obras.empty:
            for _, t in tiros_hoy.iterrows():
                if t["estatus"] != "Cancelado ❌":
                    obras_fil = df_obras[df_obras["id"] == t["obra_id"]]
                    if not obras_fil.empty:
                        obra = obras_fil.iloc[0]
                        # Colores logísticos (Sistrack style)
                        if t["estatus"] == "Pendiente": color = "gray"
                        elif t["estatus"] == "En Proceso": color = "blue"
                        elif t["estatus"] == "En Sitio (Descargando)": color = "orange"
                        else: color = "green"
                        folium.Marker((obra["latitud"], obra["longitud"]), popup=f"<b>{obra['nombre_obra']}</b><br>Estatus: {t['estatus']}", icon=folium.Icon(color=color)).add_to(m)
        folium_static(m, width=700, height=350)
        
    with col_est:
        st.markdown("### 🚛 Alertas de Flota")
        if not df_distribuidoras.empty:
            for _, u in df_distribuidoras.iterrows():
                km_act = float(u["km_totales"])
                km_mant = float(u.get("km_proximo_mantenimiento", 5000))
                
                if u["condicion_operativa"] == "En Taller":
                    st.error(f"🔧 {u['unidad']} está en Taller.")
                elif km_act >= (km_mant - 500):
                    st.warning(f"⚠️ {u['unidad']} requiere Mantenimiento. ({km_act:,.0f} / {km_mant:,.0f} km)")
                else:
                    st.success(f"🟢 {u['unidad']} Operativa. ({km_act:,.0f} km)")

# =====================================================================
# 🚚 MÓDULO 2: LOGÍSTICA Y RASTREO
# =====================================================================
elif menu == "🚚 Control Logístico y Rastreo":
    st.header("🚚 Despacho y Trazabilidad")
    
    t_crear, t_track = st.tabs(["➕ 1. Crear Orden / Pedido", "🛰️ 2. Rastreo y Trazabilidad"])
    
    with t_crear:
        if df_obras.empty: st.warning("Requiere clientes/obras registrados en el Directorio.")
        else:
            with st.form("form_orden_erp"):
                df_obras["display"] = df_obras["cliente"] + " - " + df_obras["nombre_obra"]
                obra_sel = st.selectbox("Destino del Material", df_obras["display"].tolist())
                obra_id = int(df_obras[df_obras["display"] == obra_sel].iloc[0]["id"])
                
                c1, c2, c3 = st.columns(3)
                litros = c1.number_input("Volumen a Entregar (Lts)", min_value=0, step=500)
                fecha = c2.date_input("Fecha de Ejecución")
                hora = c3.time_input("Hora Programada")
                ing = st.text_input("Ingeniero Responsable / Receptor")
                
                if st.form_submit_button("Registrar Pedido en Sistema", use_container_width=True):
                    supabase.table("registro_tiros").insert({"obra_id": int(obra_id), "litros": int(litros), "fecha": str(fecha), "hora": str(hora), "ingeniero_responsable": str(ing), "distribuidora": "Sin Asignar", "estatus": "Pendiente", "distancia_km": 0.0}).execute()
                    registrar_notificacion("Operación", f"Nuevo pedido registrado para {obra_sel} por {litros:,} Lts.")
                    st.success("Pedido Registrado. Proceda a la pestaña de Rastreo para asignar unidad.")
                    st.rerun()

    with t_track:
        f_filtro = st.date_input("Fecha de Operaciones", datetime.date.today())
        df_dia = df_tiros[df_tiros["fecha"] == str(f_filtro)] if not df_tiros.empty else pd.DataFrame()
        
        if not df_dia.empty:
            for _, row in df_dia.sort_values(by="hora").iterrows():
                obras_filtro = df_obras[df_obras["id"] == row["obra_id"]]
                obra = obras_filtro.iloc[0] if not obras_filtro.empty else None
                
                if obra is not None:
                    with st.expander(f"📦 {row['hora']} | {obra['nombre_obra']} ({row['litros']:,} Lts) - {row['estatus']}", expanded=(row['estatus'] in ["Pendiente", "En Proceso"])):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**Cliente:** {obra['cliente']}")
                            st.write(f"**Ubicación:** {obra['direccion']}")
                            if row['distribuidora'] != "Sin Asignar":
                                st.info(f"🚚 Unidad Asignada: **{row['distribuidora']}**")
                            
                        with col2:
                            ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]["unidad"].tolist() if not df_distribuidoras.empty else []
                            idx_camion = ops.index(row["distribuidora"]) if row["distribuidora"] in ops else 0
                            n_camion = st.selectbox("Asignar / Cambiar Unidad", ["Sin Asignar"] + ops, index=(0 if row["distribuidora"]=="Sin Asignar" else ops.index(row["distribuidora"])+1), key=f"c_{row['id']}")
                            if st.button("Guardar Asignación", key=f"b_{row['id']}"):
                                dist = calc_ruta(COORDS_PLANTA, (float(obra["latitud"]), float(obra["longitud"])))
                                supabase.table("registro_tiros").update({"distribuidora": str(n_camion), "distancia_km": float(dist)}).eq("id", int(row["id"])).execute()
                                registrar_notificacion("Operación", f"Unidad {n_camion} asignada a obra {obra['nombre_obra']}.")
                                st.rerun()
                                
                        with col3:
                            # Tracking Status (Estilo Sistrack)
                            est_opts = ["Pendiente", "En Proceso (En Tránsito)", "En Sitio (Descargando)", "Completado ✅", "Cancelado ❌"]
                            est_actual = row["estatus"] if row["estatus"] in est_opts else ( "En Proceso (En Tránsito)" if row["estatus"] == "En Proceso" else "Pendiente")
                            
                            n_est = st.selectbox("Cambiar Estatus (Tracking)", est_opts, index=est_opts.index(est_actual), key=f"e_{row['id']}")
                            if n_est != row["estatus"]:
                                supabase.table("registro_tiros").update({"estatus": str(n_est)}).eq("id", int(row["id"])).execute()
                                registrar_notificacion("Trazabilidad", f"El tiro en {obra['nombre_obra']} cambió a: {n_est}")
                                
                                # Afectación de inventarios y kms automáticos
                                if n_est == "Completado ✅" and row["distribuidora"] != "Sin Asignar":
                                    u_info = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                                    km_prev = float(u_info["km_totales"])
                                    # Descontar litros del camión y sumar km
                                    supabase.table("distribuidoras").update({
                                        "km_totales": km_prev + float(row["distancia_km"]),
                                        "litros_disponibles": max(0, int(u_info["litros_disponibles"] - row["litros"])),
                                        "estado": "En Obra", "ubicacion_actual": str(obra["cliente"])
                                    }).eq("unidad", row["distribuidora"]).execute()
                                st.rerun()
        else: st.info("No hay pedidos activos para esta fecha.")

# =====================================================================
# 📦 MÓDULO 3: ADMINISTRACIÓN E INVENTARIO (CIN7 CORE)
# =====================================================================
elif menu == "📦 Inventario y Administración":
    st.header("📦 Control de Almacén y Costos")
    
    if not df_planta.empty:
        planta = df_planta.iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Nivel Físico", f"{float(planta['inventario_actual']):,.0f} Lts", f"Cap: {float(planta['capacidad_total']):,.0f}")
        c2.metric("Costo Promedio (Lts)", f"${float(planta.get('costo_por_litro', 0)):,.2f}")
        c3.metric("Valor Total Almacén", f"${float(planta['inventario_actual']) * float(planta.get('costo_por_litro', 0)):,.2f}")
        
        st.markdown("---")
        st.subheader("📥 Recepción de Material (Compras/Producción)")
        with st.form("compras_form"):
            col_a, col_b, col_c = st.columns(3)
            lts_ingreso = col_a.number_input("Volumen Recibido (Lts)", min_value=0, step=1000)
            costo_factura = col_b.number_input("Costo Total de Factura/Lote ($)", min_value=0.0)
            col_c.write("Cálculo Automático de Costo Promedio")
            
            if st.form_submit_button("Procesar Ingreso a Almacén"):
                if lts_ingreso > 0 and costo_factura > 0:
                    # Cálculo de costo promedio ponderado
                    val_actual = float(planta['inventario_actual']) * float(planta.get('costo_por_litro', 0))
                    val_nuevo = val_actual + costo_factura
                    lts_totales = float(planta['inventario_actual']) + lts_ingreso
                    nuevo_costo = val_nuevo / lts_totales if lts_totales > 0 else 0
                    
                    dict_upd = {
                        "inventario_actual": float(lts_totales),
                        "costo_por_litro": float(nuevo_costo)
                    }
                    supabase.table("config_planta").update(dict_upd).eq("id", 1).execute()
                    registrar_notificacion("Inventario", f"Ingreso de {lts_ingreso:,} Lts. Nuevo costo prom: ${nuevo_costo:,.2f}")
                    st.success("Recepción de material registrada en contabilidad e inventario.")
                    st.rerun()

        st.markdown("---")
        st.subheader("⚙️ Parámetros de Almacén")
        with st.form("param_inv"):
            s_min = st.number_input("Establecer Stock Mínimo (Lts)", value=int(planta.get("stock_minimo", 15000)))
            cap_max = st.number_input("Capacidad Máxima del Tanque (Lts)", value=int(planta["capacidad_total"]))
            if st.form_submit_button("Actualizar Parámetros"):
                supabase.table("config_planta").update({"stock_minimo": int(s_min), "capacidad_total": int(cap_max)}).eq("id", 1).execute()
                st.rerun()

# =====================================================================
# ⚙️ MÓDULO 4: FLOTA Y MANTENIMIENTO (MRPEASY)
# =====================================================================
elif menu == "⚙️ Flota y Mantenimiento":
    st.header("⚙️ Gestión de Activos y Mantenimiento")
    
    if not df_distribuidoras.empty:
        st.markdown("### 🔧 Planificador de Mantenimiento Preventivo")
        for _, u in df_distribuidoras.iterrows():
            km_a = float(u["km_totales"])
            km_m = float(u.get("km_proximo_mantenimiento", 5000))
            progreso = min(km_a / km_m, 1.0) if km_m > 0 else 0
            
            with st.container(border=True):
                c1, c2, c3 = st.columns([1,2,1])
                c1.markdown(f"**{u['unidad']}**<br>Operador: {u['chofer']}", unsafe_allow_html=True)
                with c2:
                    st.progress(progreso, text=f"Desgaste: {km_a:,.0f} km de {km_m:,.0f} km")
                with c3:
                    if st.button(f"Registrar Servicio Hecho", key=f"srv_{u['unidad']}"):
                        nuevo_limite = km_a + 5000 # Próximo servicio en 5000 km
                        supabase.table("distribuidoras").update({"km_proximo_mantenimiento": float(nuevo_limite), "condicion_operativa": "Operativa"}).eq("unidad", u['unidad']).execute()
                        registrar_notificacion("Mantenimiento", f"Mantenimiento registrado para {u['unidad']}. Próximo a los {nuevo_limite} km.")
                        st.rerun()

        st.markdown("### 📝 Edición de Catálogo de Flota")
        opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus", options=["Operativa", "En Taller", "Sin Chofer"])}
        edt_flota = st.data_editor(df_distribuidoras[["unidad", "chofer", "capacidad_total", "condicion_operativa", "km_proximo_mantenimiento"]], hide_index=True, use_container_width=True, column_config=opts)
        if st.button("Guardar Cambios de Base"):
            for _, r in edt_flota.iterrows():
                r_dict = r.to_dict()
                r_dict["capacidad_total"] = int(r_dict["capacidad_total"])
                r_dict["km_proximo_mantenimiento"] = float(r_dict["km_proximo_mantenimiento"])
                supabase.table("distribuidoras").update(r_dict).eq("unidad", str(r["unidad"])).execute()
            st.rerun()

# =====================================================================
# 🏢 MÓDULO 5: DIRECTORIO CRM
# =====================================================================
elif menu == "🏢 Directorio CRM":
    st.header("🏢 Relación Comercial (Clientes y Obras)")
    t_cli, t_obr = st.tabs(["👥 Directorio B2B", "📍 Registro de Obras"])
    with t_cli:
        edit_cli = st.data_editor(df_clientes, hide_index=True, use_container_width=True, num_rows="dynamic")
        if st.button("Sincronizar CRM"):
            for _, row in edit_cli.iterrows():
                if str(row["razon_social"]) != "nan":
                    r_d = row.to_dict()
                    for k in r_d: r_d[k] = str(r_d[k]) if pd.notna(r_d[k]) else ""
                    supabase.table("clientes").upsert(r_d).execute()
            st.success("Directorio guardado.")
            st.rerun()
    with t_obr:
        st.write("Agrega obras a los clientes existentes:")
        with st.form("f_obra"):
            cli = st.selectbox("Cliente", df_clientes["razon_social"].tolist() if not df_clientes.empty else [])
            n_ob = st.text_input("Nombre / Referencia de Obra")
            d_ob = st.text_area("Dirección")
            lat = st.number_input("Latitud", format="%.6f", value=25.6866)
            lon = st.number_input("Longitud", format="%.6f", value=-100.3161)
            if st.form_submit_button("Crear Obra"):
                supabase.table("obras").insert({"cliente": str(cli), "nombre_obra": str(n_ob), "direccion": str(d_ob), "latitud": float(lat), "longitud": float(lon)}).execute()
                st.rerun()
        if not df_obras.empty: st.dataframe(df_obras[["cliente", "nombre_obra", "direccion"]], hide_index=True, use_container_width=True)

# =====================================================================
# 🔔 MÓDULO 6: CENTRO DE NOTIFICACIONES
# =====================================================================
elif menu == "🔔 Centro de Notificaciones":
    st.header("🔔 Registro de Actividad y Auditoría")
    st.write("Trazabilidad completa de las acciones del sistema.")
    
    if not df_notif.empty:
        # Marcar todas como leídas al entrar
        if len(df_notif[df_notif["leida"] == False]) > 0:
            supabase.table("notificaciones").update({"leida": True}).eq("leida", False).execute()
            
        # Mostrar tabla de historial
        df_show = df_notif.sort_values(by="id", ascending=False)
        st.dataframe(df_show[["fecha_hora", "tipo", "mensaje"]].rename(columns={"fecha_hora": "Fecha/Hora", "tipo": "Módulo", "mensaje": "Detalle del Evento"}), hide_index=True, use_container_width=True)
        
        if st.button("🗑️ Limpiar Historial Antiguo"):
            supabase.table("notificaciones").delete().neq("id", 0).execute()
            st.rerun()
    else:
        st.info("El registro de actividad está limpio.")
