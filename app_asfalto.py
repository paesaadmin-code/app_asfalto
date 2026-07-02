import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import requests
import datetime
from supabase import create_client, Client

# =====================================================================
# 🔐 CONFIGURACIÓN DE CONEXIÓN A LA NUBE (SUPABASE) Y LOGIN
# =====================================================================
SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFieW15cHVqZm9ubXR2YWtmc2ZnIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI5MjA0OTIsImV4cCI6MjA5ODQ5NjQ5Mn0.AsystVXsFbMmHoi8RarhBqPsW4zgvc-EcwAEo9BXV-Q"
USUARIO_ADMIN = "admin"
PASSWORD_ADMIN = "asfalto2026"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.set_page_config(page_title="Acceso Restringido", layout="centered")
    st.title("🔒 Acceso Restringido - Logística de Asfalto")
    usuario_input = st.text_input("Usuario")
    password_input = st.text_input("Contraseña", type="password")
    if st.button("Iniciar Sesión"):
        if usuario_input == USUARIO_ADMIN and password_input == PASSWORD_ADMIN:
            st.session_state["authenticated"] = True
            st.rerun()
        else: st.error("❌ Credenciales incorrectas.")
    st.stop()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNCIONES DE BASE DE DATOS Y LOGÍSTICA ---
def load_planta_config():
    try:
        res = supabase.table("config_planta").select("*").eq("id", 1).execute()
        return res.data[0]
    except: return {"id": 1, "nombre": "Planta Monterrey", "latitud": 25.8250665, "longitud": -100.4109077, "tanque_planta_capacidad": 50000.0, "tanque_planta_actual": 40000.0}

def save_planta_config(config_dict): supabase.table("config_planta").update(config_dict).eq("id", 1).execute()

def load_data():
    try:
        res = supabase.table("registro_tiros").select("*").execute()
        df = pd.DataFrame(res.data)
        if df.empty: raise Exception("Vacío")
        return df
    except:
        # Ejemplos automáticos para bitácora solicitados por el usuario
        hoy = str(datetime.date.today())
        manana = str(datetime.date.today() + datetime.timedelta(days=1))
        ejemplos = [
            {"id": 991, "cliente": "Constructora Alfa (Tramo 1)", "latitud": 25.5689, "longitud": -100.2452, "direccion_texto": "Carretera Nacional KM 250", "litros": 4000, "ingeniero": "Ing. Eduardo Garza", "fecha": hoy, "hora": "09:00:00", "distribuidora": "D-01", "estatus": "Completado ✅", "minutos_retraso": 0, "distancia_km": 42.5, "tiempo_estimado_min": 50},
            {"id": 992, "cliente": "Pavimentos Monterrey (Fase A)", "latitud": 25.6866, "longitud": -100.3452, "direccion_texto": "Av. Gonzalitos 120", "litros": 6000, "ingeniero": "Ing. Ricardo Treviño", "fecha": hoy, "hora": "12:30:00", "distribuidora": "D-01", "estatus": "Completado ✅", "minutos_retraso": 15, "distancia_km": 18.2, "tiempo_estimado_min": 25},
            {"id": 993, "cliente": "Asfaltos del Norte (Nave 3)", "latitud": 25.7785, "longitud": -100.1894, "direccion_texto": "Parque Industrial Apodaca", "litros": 5000, "ingeniero": "Ing. Samuel Peña", "fecha": manana, "hora": "08:00:00", "distribuidora": "Sin Asignar", "estatus": "Pendiente", "minutos_retraso": 0, "distancia_km": 31.0, "tiempo_estimado_min": 35}
        ]
        return pd.DataFrame(ejemplos)

def load_distribuidoras():
    try:
        res = supabase.table("distribuidoras").select("*").execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame(columns=["unidad", "chofer", "capacidad_total", "litros_disponibles", "estado", "ubicacion_actual", "condicion_operativa"])

def load_clientes():
    try:
        res = supabase.table("clientes_frecuentes").select("*").execute()
        return pd.DataFrame(res.data)
    except: return pd.DataFrame(columns=["id", "cliente", "obra", "latitud", "longitud", "direccion_texto"])

def geocode_address(address_text):
    """Busca coordenadas reales en Monterrey a partir de una dirección escrita estilo Google Maps."""
    url = f"https://nominatim.openstreetmap.org/search?q={address_text},+Monterrey&format=json&limit=1"
    headers = {"User-Agent": "LogisticaAsfaltoApp/1.0"}
    try:
        response = requests.get(url, headers=headers).json()
        if response:
            return float(response[0]["lat"]), float(response[0]["lon"])
    except: pass
    return 25.8250, -100.4100

def get_route_info(coord1, coord2):
    url = f"http://router.project-osrm.org/route/v1/driving/{coord1[1]},{coord1[0]};{coord2[1]},{coord2[0]}?overview=false"
    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            dist_km = response["routes"][0]["distance"] / 1000.0
            tiempo_min = (response["routes"][0]["duration"] / 60.0) * 1.2
            return round(dist_km, 2), round(tiempo_min, 0)
    except: pass
    return 0.0, 0.0

# --- CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(layout="wide", page_title="Control Logístico Monterrey")
st.title("🏗️ Plataforma Logística de Asfalto - Monterrey")

config_planta = load_planta_config()
COORDS_PLANTA = (25.8250665, -100.4109077) # Coordenadas Planta Fijas de Mateo
df_tiros = load_data()
df_distribuidoras = load_distribuidoras()
df_clientes = load_clientes()

menu = st.radio("Secciones Disponibles:", ["🗺️ Centro de Control y Rutas", "🏭 Gestión de Planta y Producción", "🚛 Flota y Estatus Mecánico", "👥 Catálogo Avanzado de Clientes", "📊 Bitácora de Diésel y Mermas"], horizontal=True)

# =====================================================================
# 1. CENTRO DE CONTROL Y RUTAS
# =====================================================================
if menu == "🗺️ Centro de Control y Rutas":
    
    # NUEVA LOGÍSTICA: PRIMERO REGISTRAR EL TIRO DEL CLIENTE
    with st.expander("➕ PASO 1: REGISTRAR REQUERIMIENTO DEL CLIENTE (Clic aquí)"):
        st.subheader("Captura de Pedido")
        
        tipo_ingreso = st.radio("Ubicación de la Obra", ["Buscar en Clientes Frecuentes", "Escribir Dirección estilo Google Maps", "Coordenadas Manuales"], horizontal=True)
        
        lat_obra, lon_obra, dir_texto = 25.8250, -100.4100, ""
        
        if tipo_ingreso == "Buscar en Clientes Frecuentes" and not df_clientes.empty:
            df_clientes["combo"] = df_clientes["cliente"] + " | Tramo: " + df_clientes["obra"]
            c_sel = st.selectbox("Buscar cliente recurrente:", df_clientes["combo"].tolist())
            row_c = df_clientes[df_clientes["combo"] == c_sel].iloc[0]
            cliente_name = f"{row_c['cliente']} ({row_c['obra']})"
            lat_obra, lon_obra = float(row_c["latitud"]), float(row_c["longitud"])
            dir_texto = str(row_c.get("direccion_texto", "Dirección Frecuente"))
            st.success(f"📍 Destino cargado: {dir_texto} ({lat_obra}, {lon_obra})")
        
        elif tipo_ingreso == "Escribir Dirección estilo Google Maps":
            cliente_name = st.text_input("Nombre de la Constructora / Empresa")
            nombre_obra = st.text_input("Nombre de la Obra o Tramo (Ej. Tramo Av. Juárez)")
            direccion_input = st.text_input("Escribe la calle, número y colonia de la obra:")
            
            if direccion_input:
                lat_obra, lon_obra = geocode_address(direccion_input)
                dir_texto = direccion_input
                cliente_name = f"{cliente_name} ({nombre_obra})"
                st.success(f"🗺️ Google Maps localizó el punto en las coordenadas: ({lat_obra}, {lon_obra})")
        
        else:
            cliente_name = st.text_input("Nombre de la Empresa y Tramo")
            lat_obra = st.number_input("Latitud", format="%.6f", value=25.8250)
            lon_obra = st.number_input("Longitud", format="%.6f", value=-100.4100)
            dir_texto = "Coordenadas manuales"

        litros_req = st.number_input("Litros Solicitados", min_value=0, step=500)
        ing_resp = st.text_input("Ingeniero Responsable de la Obra (Obligatorio)")
        f_prog = st.date_input("Fecha de Entrega", datetime.date.today())
        h_prog = st.time_input("Hora de Entrega", datetime.time(8, 0))

        if st.button("🚀 Guardar Orden de Cliente"):
            if cliente_name and ing_resp:
                nuevo_t = {
                    "cliente": str(cliente_name), "latitud": float(lat_obra), "longitud": float(lon_obra),
                    "direccion_texto": str(dir_texto), "litros": int(litros_req), "ingeniero": str(ing_resp),
                    "fecha": str(f_prog), "hora": str(h_prog), "distribuidora": "Sin Asignar", "estatus": "Pendiente",
                    "minutos_retraso": 0, "distancia_km": 0.0, "tiempo_estimado_min": 0.0
                }
                try: supabase.table("registro_tiros").insert(nuevo_t).execute()
                except: pass
                st.success("¡Orden registrada! Ahora procede a asignarle una unidad abajo.")
                st.rerun()
            else: st.error("Por favor completa el nombre del cliente y el ingeniero responsable.")

    # PASO 2: ASIGNACIÓN DE OPERADOR Y CÁLCULO DE RUTA
    st.markdown("---")
    st.subheader("🚛 PASO 2: Asignación de Camiones y Operadores a Órdenes Pendientes")
    
    df_sin_camion = df_tiros[df_tiros["distribuidora"] == "Sin Asignar"] if not df_tiros.empty else pd.DataFrame()
    camiones_ops = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"] if not df_distribuidoras.empty else pd.DataFrame()
    
    if df_sin_camion.empty:
        st.info("No hay órdenes de clientes pendientes de asignar camión para ninguna fecha.")
    elif camiones_ops.empty:
        st.error("No hay camiones marcados como 'Operativa' en la base de datos.")
    else:
        for idx, row in df_sin_camion.iterrows():
            col_a1, col_a2, col_a3 = st.columns([4, 3, 2])
            with col_a1:
                st.markdown(f"📋 **{row['cliente']}** | Pide: `{row['litros']:,} Lts` el `{row['fecha']}` a las `{row['hora']}`")
                st.caption(f"Responsable: {row['ingeniero']} | Ubicación: {row['direccion_texto']}")
            with col_a2:
                camion_elegido = st.selectbox(f"Asignar Camión a orden #{row['id']}", camiones_ops["unidad"].tolist(), key=f"sel_cam_{row['id']}")
            with col_a3:
                if st.button("Confirmar Ruta y Operador", key=f"btn_cam_{row['id']}"):
                    # Calcular distancia real desde la última posición del camión o la Planta
                    tiros_camion = df_tiros[(df_tiros["fecha"] == row["fecha"]) & (df_tiros["distribuidora"] == camion_elegido) & (df_tiros["estatus"] != "Cancelado ❌")]
                    origen_camion = (tiros_camion.sort_values(by="hora").iloc[-1]["latitud"], tiros_camion.sort_values(by="hora").iloc[-1]["longitud"]) if not tiros_camion.empty else COORDS_PLANTA
                    
                    dist_km, tiempo_min = get_route_info(origen_camion, (row["latitud"], row["longitud"]))
                    
                    # Actualizar en Supabase
                    supabase.table("registro_tiros").update({
                        "distribuidora": str(camion_elegido),
                        "distancia_km": float(dist_km),
                        "tiempo_estimado_min": float(tiempo_min)
                    }).eq("id", int(row["id"])).execute()
                    
                    # Restar del camión
                    info_c = camiones_ops[camiones_ops["supabase" == "unidad" if False else "unidad"] == camion_elegido].iloc[0]
                    n_lits = max(0, int(info_c["litros_disponibles"] - row["litros"]))
                    supabase.table("distribuidoras").update({"litros_disponibles": n_lits, "estado": "En Obra", "ubicacion_actual": str(row["cliente"])}).eq("unidad", str(camion_elegido)).execute()
                    
                    st.success(f"Asignado con éxito. Ruta de: {dist_km} km / {tiempo_min} min.")
                    st.rerun()

    # MONITOREO DIARIO Y MAPA TRICOLOR
    st.markdown("---")
    st.subheader("📋 Panel General de Monitoreo y Mapa de Control")
    
    hoy_str = str(datetime.date.today())
    manana_str = str(datetime.date.today() + datetime.timedelta(days=1))
    
    f_ver = st.date_input("Filtrar Tabla Operativa por Fecha", datetime.date.today())
    df_ver_dia = df_tiros[df_tiros["fecha"] == str(f_ver)] if not df_tiros.empty else pd.DataFrame()
    
    if not df_ver_dia.empty:
        for idx, row in df_ver_dia.sort_values(by="hora").iterrows():
            c1, c2, c3, c4 = st.columns([3,2,2,1])
            with c1:
                st.markdown(f"**{row['cliente']}** - `{row['hora']}` | Camión: `{row['distribuidora']}`")
                st.caption(f"Ing: {row['ingeniero']} | Ruta: {row.get('distancia_km', 0)} km ({row.get('tiempo_estimado_min', 0)} min)")
            with c2:
                opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                n_est = st.selectbox("Estatus", opts, index=opts.index(row["estatus"]), key=f"est_{row['id']}")
                if n_est != row["estatus"]:
                    supabase.table("registro_tiros").update({"estatus": str(n_est)}).eq("id", int(row["id"])).execute()
                    if n_est == "Cancelado ❌" and row["distribuidora"] != "Sin Asignar":
                        info_c = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                        l_dev = min(int(info_c["capacidad_total"]), int(info_c["litros_disponibles"] + row["litros"]))
                        supabase.table("distribuidoras").update({"litros_disponibles": int(l_dev)}).eq("unidad", str(row["distribuidora"])).execute()
                    st.rerun()
            with c3:
                ret = st.number_input("Retraso (Min)", min_value=0, value=int(row["minutos_retraso"]), step=15, key=f"ret_{row['id']}")
                if ret != row["minutos_retraso"]:
                    supabase.table("registro_tiros").update({"minutos_retraso": int(ret)}).eq("id", int(row["id"])).execute()
                    st.rerun()
            with c4:
                if st.button("🗑️", key=f"del_{row['id']}"):
                    supabase.table("registro_tiros").delete().eq("id", int(row["id"])).execute()
                    st.rerun()

    # MAPA TRICOLOR GLOBAL DE MONTERREY
    st.markdown("### 🗺️ Ubicación por Colores en Monterrey (Ver Obras para Adelantar)")
    st.caption("🔴 Rojo = Obras de Hoy | 🟠 Naranja = Obras de Mañana | 🔵 Azul = Futuras u Otras Fechas")
    
    m = folium.Map(location=COORDS_PLANTA, zoom_start=11)
    folium.Marker(COORDS_PLANTA, popup="Nuestra Planta Monterrey", icon=folium.Icon(color="black", icon="building", prefix='fa')).add_to(m)
    
    if not df_tiros.empty:
        df_activos_mapa = df_tiros[df_tiros["estatus"] != "Cancelado ❌"]
        for _, r in df_activos_mapa.iterrows():
            # Determinar color por fecha
            if r["fecha"] == hoy_str: color_p = "red"
            elif r["fecha"] == manana_str: color_p = "orange"
            else: color_p = "blue"
            
            folium.Marker(
                (r["latitud"], r["longitud"]),
                popup=f"<b>{r['cliente']}</b><br>Fecha: {r['fecha']}<br>Litros: {r['litros']}<br>Camión: {r['distribuidora']}",
                icon=folium.Icon(color=color_p, icon="truck", prefix='fa')
            ).add_to(m)
            
    folium_static(m, width=1100, height=480)

# =====================================================================
# OTRAS PESTAÑAS (PLANTA, FLOTA, CLIENTES Y BITÁCORA)
# =====================================================================
elif menu == "🏭 Gestión de Planta y Producción":
    st.subheader("Control del Tanque de Almacenamiento Principal")
    cap_planta, act_planta = float(config_planta.get("tanque_planta_capacidad", 50000.0)), float(config_planta.get("tanque_planta_actual", 40000.0))
    c1, c2 = st.columns(2)
    with c1: st.metric("Inventario Tanque Planta", f"{int(act_planta):,} Lts", f"Cap: {int(cap_planta):,} Lts")
    with c2:
        prod = st.number_input("Ingreso de Producción Nueva (Litros)", min_value=0, step=1000)
        if st.button("Actualizar Inventario Base"):
            config_planta["tanque_planta_actual"] = float(min(cap_planta, act_planta + prod))
            save_planta_config(config_planta)
            st.rerun()
            
    st.markdown("---")
    st.subheader("⛽ Despacho y Recarga de Petrolizadoras")
    if not df_distribuidoras.empty:
        u_recarga = st.selectbox("Selecciona Petrolizadora", df_distribuidoras["unidad"].tolist())
        row_u = df_distribuidoras[df_distribuidoras["unidad"] == u_recarga].iloc[0]
        espacio = int(row_u["capacidad_total"] - row_u["litros_disponibles"])
        l_cargar = st.number_input("Litros a transferir", min_value=0, max_value=int(min(espacio, act_planta)), step=500)
        if st.button("Ejecutar Transferencia"):
            config_planta["tanque_planta_actual"] = act_planta - l_cargar
            save_planta_config(config_planta)
            supabase.table("distribuidoras").update({"litros_disponibles": int(row_u["litros_disponibles"] + l_cargar), "estado": "En Planta", "ubicacion_actual": "Planta"}).eq("unidad", str(u_recarga)).execute()
            st.success("Sincronización completada.")
            st.rerun()

elif menu == "🚛 Flota y Estatus Mecánico":
    st.subheader("Control Mecánico de Petrolizadoras")
    if not df_distribuidoras.empty:
        opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus", options=["Operativa", "En Taller", "Sin Chofer"])}
        edited_df = st.data_editor(df_distribuidoras, num_rows="dynamic", use_container_width=True, key="edt_fl", column_config=opts)
        if st.button("Guardar Cambios de Flota"):
            for _, row in edited_df.iterrows():
                row_dict = row.to_dict()
                row_dict["capacidad_total"], row_dict["litros_disponibles"] = int(row_dict["capacidad_total"]), int(row_dict["litros_disponibles"])
                supabase.table("distribuidoras").upsert(row_dict).execute()
            st.rerun()

elif menu == "👥 Catálogo Avanzado de Clientes":
    st.subheader("Directorio de Ubicaciones Frecuentes e Historial de Obras")
    col_cl1, col_cl2 = st.columns([1, 2])
    with col_cl1:
        st.markdown("### Registrar Cliente / Tramo")
        n_cli = st.text_input("Nombre de la Empresa")
        n_obra = st.text_input("Obra o Tramo Específico")
        dir_t = st.text_input("Dirección Escrita (Ej: Av. Juárez 300)")
        lat_cli = st.number_input("Latitud", format="%.6f", value=25.8250)
        lon_cli = st.number_input("Longitud", format="%.6f", value=-100.4109)
        if st.button("Guardar en Catálogo"):
            if n_cli and n_obra:
                supabase.table("clientes_frecuentes").insert({"cliente": str(n_cli), "obra": str(n_obra), "latitud": float(lat_cli), "longitud": float(lon_cli), "direccion_texto": str(dir_t)}).execute()
                st.rerun()
    with col_cl2:
        st.markdown("### Directorio Guardado")
        if not df_clientes.empty:
            edit_clientes = st.data_editor(df_clientes, num_rows="dynamic", use_container_width=True, key="edt_cli")
            if st.button("Guardar Modificaciones"):
                for _, row in edit_clientes.iterrows():
                    row_dict = row.to_dict()
                    if "combo" in row_dict: del row_dict["combo"]
                    if "buscador_comb" in row_dict: del row_dict["buscador_comb"]
                    supabase.table("clientes_frecuentes").upsert(row_dict).execute()
                st.rerun()

elif menu == "📊 Bitácora de Diésel y Mermas":
    st.subheader("⛽ Bitácora de Rendimientos, Combustible y Mermas")
    fechas = st.date_input("Periodo de Auditoría", [datetime.date.today(), datetime.date.today()])
    
    if len(fechas) == 2 and not df_tiros.empty:
        df_rep = df_tiros[(df_tiros["fecha"] >= str(fechas[0])) & (df_tiros["fecha"] <= str(fechas[1]))]
        if not df_rep.empty:
            df_completados = df_rep[df_rep["estatus"] == "Completado ✅"]
            c_km1, c_km2 = st.columns(2)
            with c_km1:
                st.markdown("#### Kilómetros por Unidad")
                if not df_completados.empty:
                    km_p = df_completados.groupby("distribuidora")["distancia_km"].sum().reset_index()
                    st.dataframe(km_p.rename(columns={"distribuidora": "Unidad", "distancia_km": "KMs Totales"}), use_container_width=True)
            with c_km2:
                st.markdown("#### Totales Generales")
                st.metric("Total Kilómetros Ruteados", f"{df_completados['distancia_km'].sum() if not df_completados.empty else 0:,.2f} km")
            
            st.markdown("### 📋 Desglose Operativo Completo")
            st.dataframe(df_rep[["fecha", "hora", "distribuidora", "cliente", "litros", "ingeniero", "distancia_km", "estatus"]], use_container_width=True)
