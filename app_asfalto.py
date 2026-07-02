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

# Control de Autenticación
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
    st.stop()

# Conectar a la base de datos
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNCIONES DE BASE DE DATOS ---
def load_planta_config():
    res = supabase.table("config_planta").select("*").eq("id", 1).execute()
    if not res.data:
        return {"id": 1, "nombre": "Planta Monterrey", "latitud": 25.8250665, "longitud": -100.4109077, "tanque_planta_capacidad": 50000.0, "tanque_planta_actual": 40000.0}
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
    return pd.DataFrame(res.data)

def load_clientes():
    res = supabase.table("clientes_frecuentes").select("*").execute()
    return pd.DataFrame(res.data)

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

# Descarga de datos
config_planta = load_planta_config()
COORDS_PLANTA = (25.8250665, -100.4109077) # Fijadas por solicitud del usuario
df_tiros = load_data()
df_distribuidoras = load_distribuidoras()
df_clientes = load_clientes()

menu = st.radio("Secciones Disponibles:", ["🗺️ Centro de Control y Rutas", "🏭 Gestión de Planta y Producción", "🚛 Flota y Estatus Mecánico", "👥 Catálogo Avanzado de Clientes", "📊 Bitácora de Diésel y Mermas"], horizontal=True)

# =====================================================================
# 1. CENTRO DE CONTROL Y RUTAS
# =====================================================================
if menu == "🗺️ Centro de Control y Rutas":
    
    # BOTÓN DIRECTO Y DESPLEGABLE REFORZADO PARA PROGRAMAR TIROS
    with st.expander("➕ PROGRAMAR NUEVO TIRO / OBRA (Clic para abrir Formulario)"):
        st.subheader("Formulario Operativo")
        
        camiones_operativos = df_distribuidoras[df_distribuidoras["condicion_operativa"] == "Operativa"] if not df_distribuidoras.empty else pd.DataFrame()
        
        if camiones_operativos.empty:
            st.error("🚨 Alerta: No hay distribuidoras registradas u operativas en la base de datos.")
        else:
            tipo_cliente = st.radio("Método de Selección de Destino", ["Buscador de Clientes Frecuentes", "Nueva Dirección Manual"], horizontal=True)
            
            if tipo_cliente == "Buscador de Clientes Frecuentes" and not df_clientes.empty:
                df_clientes["buscador_comb"] = df_clientes["cliente"] + " | Tramo: " + df_clientes["obra"]
                cliente_sel = st.selectbox("Escribe para buscar el cliente o la obra:", df_clientes["buscador_comb"].tolist())
                row_c = df_clientes[df_clientes["buscador_comb"] == cliente_sel].iloc[0]
                cliente_name = f"{row_c['cliente']} ({row_c['obra']})"
                lat_obra, lon_obra = row_c["latitud"], row_c["longitud"]
                st.success(f"📍 Coordenadas cargadas automáticamente: ({lat_obra}, {lon_obra})")
            else:
                cliente_name = st.text_input("Nombre de la Empresa y Tramo de Obra")
                lat_obra = st.number_input("Latitud de Destino", format="%.6f", value=25.8250)
                lon_obra = st.number_input("Longitud de Destino", format="%.6f", value=-100.4100)
            
            unidad_sel = st.selectbox("Asignar Unidad de Transporte", camiones_operativos["unidad"].tolist())
            info_u = camiones_operativos[camiones_operativos["unidad"] == unidad_sel].iloc[0]
            st.info(f"Operador: {info_u['chofer']} | Disponible en Tanque: {info_u['litros_disponibles']:,} Lts")
            
            litros_req = st.number_input("Volumen Requerido (Litros)", min_value=0, step=500, max_value=int(info_u['capacidad_total']))
            ing_resp = st.text_input("Ingeniero de Obra Responsable")
            f_prog = st.date_input("Fecha de Ejecución", datetime.date.today())
            h_prog = st.time_input("Hora de Arribo", datetime.time(8, 0))

            # Cálculos Logísticos basados en OSRM
            tiros_hoy = df_tiros[(df_tiros["fecha"] == str(f_prog)) & (df_tiros["distribuidora"] == unidad_sel) & (df_tiros["estatus"] != "Cancelado ❌")] if not df_tiros.empty else pd.DataFrame()
            origen = (tiros_hoy.sort_values(by="hora").iloc[-1]["latitud"], tiros_hoy.sort_values(by="hora").iloc[-1]["longitud"]) if not tiros_hoy.empty else COORDS_PLANTA
            
            distancia_tramo, tiempo_tramo = get_route_info(origen, (lat_obra, lon_obra))
            st.markdown(f"**⏱️ Tiempo estimado de arribo al punto:** `{tiempo_tramo} minutos` | Distancia real: `{distancia_tramo} km`")

            if litros_req > info_u['litros_disponibles']:
                st.warning("⚠️ ¡La unidad requiere recargar en Planta antes de este punto!")
                _, t_regreso = get_route_info(origen, COORDS_PLANTA)
                _, t_ida = get_route_info(COORDS_PLANTA, (lat_obra, lon_obra))
                st.write(f"🔄 **Ruta de Retorno Activa:** El camión tardará **{(t_regreso + 45 + t_ida):.0f} minutos** en regresar a la base, cargar tanque (45 min) y llegar a la obra.")
                distancia_tramo += (t_regreso + t_ida)

            if st.button("🚀 Confirmar Despacho y Programar Tiro"):
                nuevo_t = {
                    "cliente": cliente_name, "latitud": lat_obra, "longitud": lon_obra,
                    "litros": litros_req, "ingeniero": ing_resp, "fecha": str(f_prog),
                    "hora": str(h_prog), "distribuidora": unidad_sel, "estatus": "Pendiente",
                    "minutos_retraso": 0, "distancia_km": distancia_tramo, "tiempo_estimado_min": tiempo_tramo
                }
                supabase.table("registro_tiros").insert(nuevo_t).execute()
                
                # Descontar del camión en vivo
                nuevos_lits = max(0, int(info_u['litros_disponibles'] - litros_req))
                supabase.table("distribuidoras").update({"litros_disponibles": nuevos_lits, "estado": "En Obra", "ubicacion_actual": cliente_name}).eq("unidad", unidad_sel).execute()
                st.success("¡Tiro agendado y guardado en la nube!")
                st.rerun()

    # MONITOREO DIARIO DE TRABAJOS
    st.subheader("Planificación del Día")
    f_filtro = st.date_input("Fecha a Visualizar", datetime.date.today())
    df_dia_all = df_tiros[df_tiros["fecha"] == str(f_filtro)].copy() if not df_tiros.empty else pd.DataFrame()
    df_dia_activos = df_dia_all[df_dia_all["estatus"] != "Cancelado ❌"].copy() if not df_dia_all.empty else pd.DataFrame()

    if not df_dia_all.empty:
        st.markdown("### 🚨 Panel de Ajustes Rápidos")
        for idx, row in df_dia_all.sort_values(by="hora").iterrows():
            c1, c2, c3, c4 = st.columns([3,2,2,1])
            with c1: 
                st.markdown(f"**{row['cliente']}** - `{row['hora']}` ({row['distribuidora']})")
                st.caption(f"Distancia: {row.get('distancia_km', 0)} km | T. Viaje: {row.get('tiempo_estimado_min', 0)} min")
            with c2:
                opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                n_est = st.selectbox("Estatus", opts, index=opts.index(row["estatus"]), key=f"est_{row['id']}")
                if n_est != row["estatus"]:
                    supabase.table("registro_tiros").update({"estatus": n_est}).eq("id", int(row["id"])).execute()
                    if n_est == "Cancelado ❌":
                        info_c = df_distribuidoras[df_distribuidoras["unidad"] == row["distribuidora"]].iloc[0]
                        l_dev = min(int(info_c["capacidad_total"]), int(info_c["litros_disponibles"] + row["litros"]))
                        supabase.table("distribuidoras").update({"litros_disponibles": l_dev}).eq("unidad", row["distribuidora"]).execute()
                    st.rerun()
            with c3:
                ret = st.number_input("Retraso (Min)", min_value=0, value=int(row["minutos_retraso"]), step=15, key=f"ret_{row['id']}")
                if ret != row["minutos_retraso"]:
                    supabase.table("registro_tiros").update({"minutos_retraso": ret}).eq("id", int(row["id"])).execute()
                    st.rerun()
            with c4:
                # BOTÓN DE ELIMINACIÓN CON CREDENCIALES ADMIN
                if st.button("🗑️", key=f"del_{row['id']}"):
                    supabase.table("registro_tiros").delete().eq("id", int(row["id"])).execute()
                    st.success("Tiro eliminado")
                    st.rerun()
        
        # MAPA FIJO CENTRADO EN MONTERREY
        st.markdown("### 🗺️ Visualización Cartográfica del Día")
        m = folium.Map(location=COORDS_PLANTA, zoom_start=11)
        folium.Marker(COORDS_PLANTA, popup="Nuestra Planta Monterrey", icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
        
        if not df_dia_activos.empty:
            puntos = []
            for _, r in df_dia_activos.sort_values(by="hora").iterrows():
                coords = (r["latitud"], r["longitud"])
                puntos.append(coords)
                color = "green" if r["estatus"] == "Completado ✅" else ("orange" if r["estatus"] == "En Proceso" else "blue")
                folium.Marker(coords, popup=f"{r['cliente']}<br>{r['litros']} Lts", icon=folium.Icon(color=color, icon="truck", prefix='fa')).add_to(m)
            if len(puntos) > 1: folium.PolyLine(puntos, color="darkblue", weight=3).add_to(m)
        folium_static(m, width=1000, height=450)
    else:
        st.info("No hay tiros registrados para el día seleccionado. El mapa base de Monterrey se muestra a continuación:")
        m = folium.Map(location=COORDS_PLANTA, zoom_start=11)
        folium.Marker(COORDS_PLANTA, popup="Nuestra Planta Monterrey", icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
        folium_static(m, width=1000, height=450)

# =====================================================================
# 2. GESTIÓN DE PLANTA Y PRODUCCIÓN
# =====================================================================
elif menu == "🏭 Gestión de Planta y Producción":
    st.subheader("Control del Tanque de Almacenamiento Principal")
    
    # CORRECCIÓN DE ERROR DE NÚMEROS FLOTANTES EN METRICAS
    cap_planta = float(config_planta.get("tanque_planta_capacidad", 50000.0))
    act_planta = float(config_planta.get("tanque_planta_actual", 40000.0))
    
    c1, c2 = st.columns(2)
    with c1: 
        st.metric("Inventario Tanque Planta", f"{int(act_planta):,} Lts", f"Cap: {int(cap_planta):,} Lts")
    with c2:
        prod = st.number_input("Ingreso de Producción Nueva (Litros)", min_value=0, step=1000)
        if st.button("Actualizar Inventario Base"):
            config_planta["tanque_planta_actual"] = min(cap_planta, act_planta + prod)
            save_planta_config(config_planta)
            st.success("Producción almacenada.")
            st.rerun()
            
    st.markdown("---")
    st.subheader("⛽ Despacho y Recarga de Petrolizadoras")
    if not df_distribuidoras.empty:
        u_recarga = st.selectbox("Selecciona Petrolizadora", df_distribuidoras["unidad"].tolist())
        row_u = df_distribuidoras[df_distribuidoras["unidad"] == u_recarga].iloc[0]
        espacio = int(row_u["capacidad_total"] - row_u["litros_disponibles"])
        
        st.write(f"La unidad **{u_recarga}** tiene un espacio libre de **{espacio:,} Litros**.")
        l_cargar = st.number_input("Litros a transferir", min_value=0, max_value=int(min(espacio, act_planta)), step=500)
        
        if st.button("Ejecutar Transferencia de Líquido"):
            config_planta["tanque_planta_actual"] = act_planta - l_cargar
            save_planta_config(config_planta)
            supabase.table("distribuidoras").update({"litros_disponibles": int(row_u["litros_disponibles"] + l_cargar), "estado": "En Planta", "ubicacion_actual": "Planta"}).eq("unidad", u_recarga).execute()
            st.success("Sincronización de tanques completada.")
            st.rerun()

# =====================================================================
# 3. FLOTA / 4. CATÁLOGO DE CLIENTES AVANZADO
# =====================================================================
elif menu == "🚛 Flota y Estatus Mecánico":
    st.subheader("Control Mecánico de Petrolizadoras")
    opts = {"condicion_operativa": st.column_config.SelectboxColumn("Estatus de Salida", options=["Operativa", "En Taller", "Sin Chofer"])}
    edited_df = st.data_editor(df_distribuidoras, num_rows="dynamic", use_container_width=True, key="edt_fl", column_config=opts)
    if st.button("Guardar Cambios de Flota"):
        for _, row in edited_df.iterrows():
            supabase.table("distribuidoras").upsert(row.to_dict()).execute()
        st.success("Base de datos de flota actualizada.")
        st.rerun()

elif menu == "👥 Catálogo Avanzado de Clientes":
    st.subheader("Directorio Corporativo de Clientes e Historial de Obras")
    
    col_cl1, col_cl2 = st.columns([1, 2])
    with col_cl1:
        st.markdown("### Registrar Cliente / Tramo")
        n_cli = st.text_input("Nombre de la Empresa (Ej. Alfa)")
        n_obra = st.text_input("Obra o Tramo Específico (Ej. Carretera Nac.)")
        lat_cli = st.number_input("Latitud de la Ubicación", format="%.6f", value=25.8250)
        lon_cli = st.number_input("Longitud de la Ubicación", format="%.6f", value=-100.4109)
        if st.button("Guardar en Catálogo"):
            if n_cli and n_obra:
                supabase.table("clientes_frecuentes").insert({"cliente": n_cli, "obra": n_obra, "latitud": lat_cli, "longitud": lon_cli}).execute()
                st.success("Cliente guardado.")
                st.rerun()
    with col_cl2:
        st.markdown("### Directorio Guardado")
        edit_clientes = st.data_editor(df_clientes, num_rows="dynamic", use_container_width=True, key="edt_cli")
        if st.button("Guardar Modificaciones de Catálogo"):
            for _, row in edit_clientes.iterrows():
                if "buscador_comb" in row: del row["buscador_comb"]
                if "display_search" in row: del row["display_search"]
                supabase.table("clientes_frecuentes").upsert(row.to_dict()).execute()
            st.rerun()
            
    st.markdown("---")
    st.subheader("🔎 Historial de Tiros y Responsables por Cliente")
    if not df_clientes.empty:
        cliente_auditar = st.selectbox("Selecciona un cliente para auditar su historial completo de tiros realizados:", df_clientes["cliente"].unique().tolist())
        
        # Filtrar todos los tiros que contengan el nombre del cliente
        tiros_cliente = df_tiros[df_tiros["cliente"].str.contains(cliente_auditar, case=False, na=False)] if not df_tiros.empty else pd.DataFrame()
        
        if not tiros_cliente.empty:
            st.write(f"Se encontraron **{len(tiros_cliente)}** tiros registrados para **{cliente_auditar}**:")
            st.dataframe(tiros_cliente[["fecha", "hora", "distribuidora", "litros", "ingeniero", "estatus", "distancia_km"]].rename(columns={
                "fecha": "Fecha", "hora": "Hora", "distribuidora": "Unidad", "litros": "Litros Solicitados", "ingeniero": "Ing. Responsable en Obra", "estatus": "Estado de Entrega", "distancia_km": "KM Bitácora"
            }), use_container_width=True)
        else:
            st.info("No se han ejecutado ni completado tiros para este cliente aún.")

# =====================================================================
# 5. BITÁCORA DE DIÉSEL Y MERMAS
# =====================================================================
elif menu == "📊 Bitácora de Diésel y Mermas":
    st.subheader("Análisis de Kilómetros, Combustible y Control de Volúmenes")
    fechas = st.date_input("Periodo de Auditoría", [datetime.date.today(), datetime.date.today()])
    
    if len(fechas) == 2 and not df_tiros.empty:
        df_rep = df_tiros[(df_tiros["fecha"] >= str(fechas[0])) & (df_tiros["fecha"] <= str(fechas[1]))]
        
        if not df_rep.empty:
            df_completados = df_rep[df_rep["estatus"] == "Completado ✅"]
            
            c_km1, c_km2 = st.columns(2)
            with c_km1:
                st.markdown("### ⛽ Kilómetros por Unidad")
                if not df_completados.empty:
                    km_p = df_completados.groupby("distribuidora")["distancia_km"].sum().reset_index()
                    st.dataframe(km_p.rename(columns={"distribuidora": "Unidad Petrolizadora", "distancia_km": "KMs Totales Conducidos"}), use_container_width=True)
                else: st.caption("No hay obras marcadas como Completadas en este rango.")
            with c_km2:
                st.markdown("### 📊 Totales del Periodo")
                st.metric("Total Kilómetros Recorridos", f"{df_completados['distancia_km'].sum() if not df_completados.empty else 0:,.2f} km")
                st.caption("Usa estos kilómetros para multiplicar por el rendimiento de tu camión y validar los litros de diésel consumidos.")
            
            st.markdown("---")
            st.markdown("### 🔎 Auditoría de Mermas de Tanque (Solo Día de Hoy)")
            if str(fechas[0]) == str(datetime.date.today()) and str(fechas[1]) == str(datetime.date.today()):
                for _, u in df_distribuidoras.iterrows():
                    tiros_u = df_completados[df_completados["distribuidora"] == u["unidad"]]
                    entregado = tiros_u["litros"].sum()
                    teorico = u["capacidad_total"] - entregado
                    disc = teorico - u["litros_disponibles"]
                    
                    with st.expander(f"Auditoría Física: {u['unidad']} ({u['chofer']})"):
                        st.write(f"Cargó al salir: {u['capacidad_total']:,} Lts | Entregó: {entregado:,} Lts")
                        if disc > 0: st.error(f"⚠️ MERMA EN TANQUE: Faltan {disc:,} Litros.")
                        elif disc < 0: st.warning(f"⚠️ SOBRANTE: Sobran {abs(disc):,} Litros.")
                        else: st.success("Balance Perfecto.")
            
            st.markdown("### 📋 Tabla de Control General")
            st.dataframe(df_rep[["fecha", "hora", "distribuidora", "cliente", "litros", "distancia_km", "estatus", "ingeniero"]], use_container_width=True)
