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
# Configura tus llaves de Supabase aquí o en los Secrets de Streamlit
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    USUARIO_ADMIN = st.secrets.get("USUARIO_ADMIN", "admin")
    PASSWORD_ADMIN = st.secrets.get("PASSWORD_ADMIN", "asfalto2026")
except Exception:
    SUPABASE_URL = "https://abymypujfonmtvakfsfg.supabase.co"  # <--- PON TU URL
    SUPABASE_KEY = "sb_publishable_Iy33aS443gGG3SlSz9PTNw_Upv8NhCtY"                           # <--- PON TU KEY
    USUARIO_ADMIN = "admin"
    PASSWORD_ADMIN = "asfalto2026"

# 1. PANTALLA DE SEGURIDAD (LOGIN)
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.set_page_config(page_title="Acceso Restringido", layout="centered")
    st.title("🔒 Acceso Restringido - Logística de Asfalto")
    st.write("Por favor, ingrese sus credenciales para acceder a la plataforma.")
    
    usuario_input = st.text_input("Usuario")
    password_input = st.text_input("Contraseña", type="password")
    
    if st.button("Iniciar Sesión"):
        if usuario_input == USUARIO_ADMIN and password_input == PASSWORD_ADMIN:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("❌ Credenciales incorrectas. Intente de nuevo.")
    st.stop() # Detiene el programa aquí si no está logueado

# Inicializar cliente de conexión
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNCIONES DE BASE DE DATOS ---
def load_planta_config():
    res = supabase.table("config_planta").select("*").eq("id", 1).execute()
    return res.data[0]

def save_planta_config(config_dict):
    supabase.table("config_planta").update(config_dict).eq("id", 1).execute()

def load_data():
    res = supabase.table("registro_tiros").select("*").execute()
    df = pd.DataFrame(res.data)
    if df.empty:
        return pd.DataFrame(columns=["id", "cliente", "latitud", "longitud", "litros", "ingeniero", "fecha", "hora", "distribuidora", "estatus", "minutos_retraso", "distancia_km", "tiempo_estimado_min"])
    return df

def load_distribuidoras():
    res = supabase.table("distribuidoras").select("*").execute()
    df = pd.DataFrame(res.data)
    if "condicion_operativa" not in df.columns:
        df["condicion_operativa"] = "Operativa"
    return df

def load_clientes():
    res = supabase.table("clientes_frecuentes").select("*").execute()
    df = pd.DataFrame(res.data)
    if "obra" not in df.columns:
        df["obra"] = "Sede Principal"
    return df

def get_route_info(coord1, coord2):
    url = f"http://router.project-osrm.org/route/v1/driving/{coord1[1]},{coord1[0]};{coord2[1]},{coord2[0]}?overview=false"
    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            dist_km = response["routes"][0]["distance"] / 1000.0
            tiempo_min = (response["routes"][0]["duration"] / 60.0) * 1.2 # Ajuste para camiones pesados
            return round(dist_km, 2), round(tiempo_min, 0)
    except: pass
    return 0.0, 0.0

# --- INICIALIZACIÓN DE LA INTERFAZ ---
st.set_page_config(layout="wide", page_title="Control Logístico Multi-Equipo")
st.title("🏗️ Plataforma Logística de Asfalto (Nube Segura)")

if st.button("Cerrar Sesión"):
    st.session_state["authenticated"] = False
    st.rerun()

config_planta = load_planta_config()
COORDS_PLANTA = (config_planta["latitud"], config_planta["longitud"])
df_tiros = load_data()
df_distribuidoras = load_distribuidoras()
df_clientes = load_clientes()

menu = st.radio("Menú:", ["🗺️ Centro de Control y Rutas", "🏭 Gestión de Planta y Producción", "🚛 Flota y Estatus Mecánico", "👥 Catálogo Clientes", "📊 Bitácora de Diésel y Mermas"], horizontal=True)

# =====================================================================
# 1. CENTRO DE CONTROL Y RUTAS
# =====================================================================
if menu == "🗺️ Centro de Control y Rutas":
    with st.expander("➕ PROGRAMAR NUEVA OBRA / TIRO (Clic para abrir)"):
        st.subheader("Datos de la Programación")
        
        # Filtro de camiones operativos
        camiones_operativos = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"]
        
        if camiones_operativos.empty:
            st.error("🚨 CRÍTICO: No hay unidades operativas. Revisa el estatus mecánico en la pestaña 'Flota'.")
        else:
            tipo_cliente = st.radio("Tipo de Cliente", ["Buscador Frecuente", "Nuevo"], horizontal=True)
            
            if tipo_cliente == "Buscador Frecuente" and not df_clientes.empty:
                # Crear campo combinado para buscador
                df_clientes["display_search"] = df_clientes["cliente"] + " | Tramo/Obra: " + df_clientes["obra"]
                
                cliente_sel = st.selectbox("Escribe para buscar Cliente o Tramo", df_clientes["display_search"].tolist())
                row_c = df_clientes[df_clientes["display_search"] == cliente_sel].iloc[0]
                cliente_name = f"{row_c['cliente']} ({row_c['obra']})"
                lat_obra, lon_obra = row_c["latitud"], row_c["longitud"]
                st.success(f"📍 Ubicación cargada: ({lat_obra}, {lon_obra})")
            else:
                cliente_name = st.text_input("Nombre del Cliente y Tramo (Nueva Obra)")
                lat_obra = st.number_input("Latitud Obra", format="%.6f", value=25.6500)
                lon_obra = st.number_input("Longitud Obra", format="%.6f", value=-100.2800)
                
            unidad_sel = st.selectbox("Asignar Unidad Operativa", camiones_operativos["unidad"].tolist())
            info_u = camiones_operativos[camiones_operativos["unidad"] == unidad_sel].iloc[0]
            st.info(f"Chofer: {info_u['chofer']} | Disponible en Tanque: {info_u['litros_disponibles']:,} Lts")
            
            litros_req = st.number_input("Litros Requeridos", min_value=0, step=500, max_value=int(info_u['capacidad_total']))
            ing_resp = st.text_input("Ingeniero Responsable")
            f_prog = st.date_input("Fecha", datetime.date.today())
            h_prog = st.time_input("Hora", datetime.time(8, 0))

            # Cálculo de Logística y Tiempos para el Cliente
            tiros_hoy = df_tiros[(df_tiros["fecha"] == str(f_prog)) & (df_tiros["distribuidora"] == unidad_sel) & (df_tiros["estatus"] != "Cancelado ❌")]
            origen = (tiros_hoy.sort_values(by="hora").iloc[-1]["latitud"], tiros_hoy.sort_values(by="hora").iloc[-1]["longitud"]) if not tiros_hoy.empty else COORDS_PLANTA
            
            # Obtener distancias reales para el registro
            distancia_al_punto, tiempo_al_punto = get_route_info(origen, (lat_obra, lon_obra))
            
            st.markdown(f"**⏱️ Tiempo estimado de llegada a la obra:** `{tiempo_al_punto} minutos` (Distancia: `{distancia_al_punto} km`)")

            if litros_req > info_u['litros_disponibles'] and cliente_name:
                st.warning("⚠️ La unidad seleccionada NO cuenta con material suficiente. Deberá recargar.")
                _, t_regreso = get_route_info(origen, COORDS_PLANTA)
                _, t_ida = get_route_info(COORDS_PLANTA, (lat_obra, lon_obra))
                
                # Actualizar las variables de registro para que cuenten el viaje a planta + el viaje a obra
                if t_regreso and t_ida:
                    st.write(f"🔄 **Protocolo de Recarga (1 Unidad):** El camión tardará **{(t_regreso + 45 + t_ida):.0f} minutos** totales (Regreso a planta -> Carga -> Viaje a obra).")
                    distancia_al_punto += get_route_info(origen, COORDS_PLANTA)[0] + get_route_info(COORDS_PLANTA, (lat_obra, lon_obra))[0]

            if st.button("Guardar y Confirmar Programación"):
                nuevo_t = {
                    "cliente": cliente_name, "latitud": lat_obra, "longitud": lon_obra, 
                    "litros": litros_req, "ingeniero": ing_resp, "fecha": str(f_prog), 
                    "hora": str(h_prog), "distribuidora": unidad_sel, "estatus": "Pendiente", 
                    "minutos_retraso": 0, "distancia_km": distancia_al_punto, "tiempo_estimado_min": tiempo_al_punto
                }
                supabase.table("registro_tiros").insert(nuevo_t).execute()
                
                nuevos_lits = max(0, int(info_u['litros_disponibles'] - litros_req))
                supabase.table("distribuidoras").update({"litros_disponibles": nuevos_lits, "estado": "En Obra", "ubicacion_actual": cliente_name}).eq("unidad", unidad_sel).execute()
                
                st.success("¡Obra y logística guardada en la nube!")
                st.rerun()

    # MONITOREO DE RUTAS
    st.subheader("Planificación de Rutas Diarias")
    f_filtro = st.date_input("Fecha a Visualizar", datetime.date.today())
    df_dia_all = df_tiros[df_tiros["fecha"] == str(f_filtro)].copy() if not df_tiros.empty else pd.DataFrame()
    df_dia_activos = df_dia_all[df_dia_all["estatus"] != "Cancelado ❌"].copy() if not df_dia_all.empty else pd.DataFrame()

    if not df_dia_all.empty:
        for idx, row in df_dia_all.sort_values(by="hora").iterrows():
            c1, c2, c3, c4 = st.columns([3,2,2,2])
            with c1: 
                st.markdown(f"**{row['cliente']}** ({row['distribuidora']}) - `{row['hora']}`")
                st.caption(f"Distancia: {row.get('distancia_km', 0)} km | T. Est: {row.get('tiempo_estimado_min', 0)} min")
            with c2:
                opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                n_est = st.selectbox("Estatus", opts, index=opts.index(row["estatus"]), key=f"e_{row['id']}")
                if n_est != row["estatus"]:
                    supabase.table("registro_tiros").update({"estatus": n_est}).eq("id", int(row["id"])).execute()
                    if n_est == "Cancelado ❌":
                        info_camion = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                        l_dev = min(int(info_camion["capacidad_total"]), int(info_camion["litros_disponibles"] + row["litros"]))
                        supabase.table("distribuidoras").update({"litros_disponibles": l_dev}).eq("unidad", row["distribuidora"]).execute()
                    st.rerun()
            with c3:
                ret = st.number_input("Retraso (Min)", min_value=0, value=int(row["minutos_retraso"]), step=15, key=f"r_{row['id']}")
                if ret != row["minutos_retraso"]:
                    supabase.table("registro_tiros").update({"minutos_retraso": ret}).eq("id", int(row["id"])).execute()
                    st.rerun()
            with c4:
                if row["estatus"] == "Cancelado ❌": st.error("❌ Cancelado")
                elif ret > 0: st.warning("⏱️ Atraso registrado.")
                else: st.success("🟢 En orden")
        
        if not df_dia_activos.empty:
            m = folium.Map(location=COORDS_PLANTA, zoom_start=11)
            folium.Marker(COORDS_PLANTA, popup=config_planta["nombre"], icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
            puntos = []
            for _, r in df_dia_activos.sort_values(by="hora").iterrows():
                coords = (r["latitud"], r["longitud"])
                puntos.append(coords)
                color = "green" if r["estatus"] == "Completado ✅" else ("orange" if r["estatus"] == "En Proceso" else "blue")
                folium.Marker(coords, popup=f"{r['cliente']}<br>{r['litros']} Lts", icon=folium.Icon(color=color, icon="truck", prefix='fa')).add_to(m)
            
            if len(puntos) > 1: folium.PolyLine(puntos, color="darkblue", weight=3).add_to(m)
            folium_static(m, width=1000, height=450)

# =====================================================================
# 2. PLANTA / 3. FLOTA
# =====================================================================
elif menu == "🏭 Gestión de Planta y Producción":
    st.subheader("Control del Tanque de Almacenamiento Principal")
    c1, c2 = st.columns(2)
    with c1: st.metric("Inventario Tanque Planta", f"{config_planta['tanque_planta_actual']:,} Lts", f"Cap: {config_planta['tanque_planta_capacidad']:,} Lts")
    with c2:
        prod = st.number_input("Producción Nueva", min_value=0, step=1000)
        if st.button("Ingresar a Planta"):
            config_planta["tanque_planta_actual"] = min(config_planta["tanque_planta_capacidad"], config_planta["tanque_planta_actual"] + prod)
            save_planta_config(config_planta)
            st.rerun()
    
    st.markdown("---")
    u_recarga = st.selectbox("Rellenar Petrolizadora (Regresó a cargar)", df_distribuidoras["unidad"].tolist())
    row_u = df_distribuidoras[df_distribuidoras["unidad"] == u_recarga].iloc[0]
    espacio = row_u["capacidad_total"] - row_u["litros_disponibles"]
    l_cargar = st.number_input("Litros a transferir", max_value=int(min(espacio, config_planta["tanque_planta_actual"])), step=500)
    
    if st.button("Ejecutar Carga y Sincronizar"):
        config_planta["tanque_planta_actual"] -= l_cargar
        save_planta_config(config_planta)
        supabase.table("distribuidoras").update({"litros_disponibles": int(row_u["litros_disponibles"] + l_cargar), "estado": "En Planta", "ubicacion_actual": "Planta"}).eq("unidad", u_recarga).execute()
        st.success("Carga exitosa.")
        st.rerun()

elif menu == "🚛 Flota y Estatus Mecánico":
    st.subheader("Gestión de Unidades y Estado Mecánico")
    st.write("Cambia la columna 'condicion_operativa' a 'En Taller' o 'Sin Chofer' si la unidad no puede salir hoy.")
    
    opts = {"condicion_operativa": st.column_config.SelectboxColumn("Condición", options=["Operativa", "En Taller", "Sin Chofer"])}
    edited_df = st.data_editor(df_distribuidoras, num_rows="dynamic", use_container_width=True, key="editor_flota", column_config=opts)
    
    if st.button("Guardar Estatus de Flota"):
        for index, row in edited_df.iterrows():
            if row["litros_disponibles"] > row["capacidad_total"]: row["litros_disponibles"] = row["capacidad_total"]
            supabase.table("distribuidoras").upsert(row.to_dict()).execute()
        st.success("¡Flota actualizada!")
        st.rerun()

# =====================================================================
# 4. CLIENTES FRECUENTES
# =====================================================================
elif menu == "👥 Catálogo Clientes":
    st.subheader("Directorio Multi-Ubicación")
    col_cl1, col_cl2 = st.columns([1, 2])
    with col_cl1:
        st.markdown("### Agregar Nuevo")
        n_cli = st.text_input("Empresa (Ej. Constructora X)")
        n_obra = st.text_input("Obra / Tramo (Ej. Av. Leones)")
        lat_cli = st.number_input("Latitud", format="%.6f", value=25.6500)
        lon_cli = st.number_input("Longitud", format="%.6f", value=-100.2800)
        if st.button("Registrar"):
            if n_cli and n_obra:
                supabase.table("clientes_frecuentes").insert({"cliente": n_cli, "obra": n_obra, "latitud": lat_cli, "longitud": lon_cli}).execute()
                st.rerun()
    with col_cl2:
        st.markdown("### Base de Datos")
        edit_clientes = st.data_editor(df_clientes, num_rows="dynamic", use_container_width=True)
        if st.button("Actualizar Catálogo"):
            for _, row in edit_clientes.iterrows():
                supabase.table("clientes_frecuentes").upsert(row.to_dict()).execute()
            st.rerun()

# =====================================================================
# 5. BITÁCORA Y REPORTES
# =====================================================================
elif menu == "📊 Bitácora de Diésel y Mermas":
    st.subheader("📈 Reportes Operativos, Combustible y Mermas")
    fechas = st.date_input("Rango de fechas a evaluar", [datetime.date.today(), datetime.date.today()])
    
    if len(fechas) == 2 and not df_tiros.empty:
        df_rep = df_tiros[(df_tiros["fecha"] >= str(fechas[0])) & (df_tiros["fecha"] <= str(fechas[1]))]
        
        if not df_rep.empty:
            df_completados = df_rep[df_rep["estatus"] == "Completado ✅"]
            st.markdown("### ⛽ Cálculo de Kilómetros por Unidad (Justificación Diésel)")
            km_por_unidad = df_completados.groupby("distribuidora")["distancia_km"].sum().reset_index()
            
            c_km1, c_km2 = st.columns(2)
            with c_km1:
                st.dataframe(km_por_unidad.rename(columns={"distribuidora": "Unidad", "distancia_km": "KMs Recorridos"}), use_container_width=True)
            with c_km2:
                km_totales = km_por_unidad["distancia_km"].sum()
                st.metric("Total Kilómetros Ruteados (Completados)", f"{km_totales:,.2f} km")
                st.caption("Esta métrica suma los recorridos reales de carretera calculados por la API en las obras palomeadas.")

            st.markdown("---")
            st.markdown("### 🔎 Auditoría de Mermas de Emulsión (Solo aplicable al día de HOY)")
            if str(fechas[0]) == str(datetime.date.today()) and str(fechas[1]) == str(datetime.date.today()):
                for _, unidad in df_distribuidoras.iterrows():
                    tiros_unidad = df_completados[df_completados["distribuidora"] == unidad["unidad"]]
                    l_entregados = tiros_unidad["litros"].sum()
                    l_teoricos = unidad["capacidad_total"] - l_entregados
                    discrepancia = l_teoricos - unidad["litros_disponibles"]
                    
                    with st.expander(f"Auditoría: {unidad['unidad']} ({unidad['chofer']})"):
                        st.write(f"- Entregado: {l_entregados:,} Lts | Debería tener en tanque: {l_teoricos:,} Lts")
                        if discrepancia > 0: st.error(f"⚠️ MERMA: Faltan {discrepancia:,} Lts en tanque.")
                        elif discrepancia < 0: st.warning(f"⚠️ SOBRANTE: Sobran {abs(discrepancia):,} Lts en tanque.")
                        else: st.success("Balance Perfecto.")
            else:
                st.info("La auditoría de mermas comparada con el tanque físico solo se muestra si el filtro de fecha es el día de hoy.")

            st.markdown("### 📋 Desglose General para Facturación")
            st.dataframe(df_rep[["fecha", "hora", "distribuidora", "cliente", "litros", "distancia_km", "estatus"]], use_container_width=True)
