import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import requests
import datetime
import os

# --- ARCHIVOS LOCALES DE RESPALDO ---
DATA_FILE = "registro_tiros.csv"
DISTRIBUIDORAS_FILE = "distribuidoras.csv"
CONFIG_FILE = "config_planta.csv"
CLIENTES_FILE = "clientes_frecuentes.csv"

# --- FUNCIONES DE PERSISTENCIA Y BASE DE DATOS ---
def load_planta_config():
    if os.path.exists(CONFIG_FILE):
        df = pd.read_csv(CONFIG_FILE)
        if "Tanque_Planta_Capacidad" not in df.columns:
            df["Tanque_Planta_Capacidad"] = 50000.0
            df["Tanque_Planta_Actual"] = 40000.0
        return df.iloc[0].to_dict()
    return {
        "Latitud": 25.6866, "Longitud": -100.3161, "Nombre": "Planta Principal",
        "Tanque_Planta_Capacidad": 50000.0, "Tanque_Planta_Actual": 40000.0
    }

def save_planta_config(config_dict):
    df = pd.DataFrame([config_dict])
    df.to_csv(CONFIG_FILE, index=False)

def load_data():
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        for col, default in [("Estatus", "Pendiente"), ("Minutos_Retraso", 0)]:
            if col not in df.columns: df[col] = default
        return df
    return pd.DataFrame(columns=["Cliente", "Latitud", "Longitud", "Litros", "Ingeniero", "Fecha", "Hora", "Distribuidora", "Estatus", "Minutos_Retraso"])

def save_data(df): df.to_csv(DATA_FILE, index=False)

def load_distribuidoras():
    if os.path.exists(DISTRIBUIDORAS_FILE):
        return pd.read_csv(DISTRIBUIDORAS_FILE)
    data = {
        "Unidad": ["D-01", "D-02", "D-03"],
        "Chofer": ["Juan Pérez", "Carlos Gómez", "Luis Martínez"],
        "Capacidad_Total": [10000, 15000, 8000],
        "Litros_Disponibles": [10000, 15000, 8000],
        "Estado": ["En Planta", "En Planta", "En Planta"],
        "Ubicacion_Actual": ["Planta", "Planta", "Planta"]
    }
    df = pd.DataFrame(data)
    df.to_csv(DISTRIBUIDORAS_FILE, index=False)
    return df

def save_distribuidoras(df): df.to_csv(DISTRIBUIDORAS_FILE, index=False)

def load_clientes():
    if os.path.exists(CLIENTES_FILE): return pd.read_csv(CLIENTES_FILE)
    df = pd.DataFrame([{"Cliente": "Constructora Alfa", "Latitud": 25.6500, "Longitud": -100.2800}])
    df.to_csv(CLIENTES_FILE, index=False)
    return df

def save_clientes(df): df.to_csv(CLIENTES_FILE, index=False)

def get_route_info(coord1, coord2):
    url = f"http://router.project-osrm.org/route/v1/driving/{coord1[1]},{coord1[0]};{coord2[1]},{coord2[0]}?overview=false"
    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            return response["routes"][0]["distance"] / 1000.0, (response["routes"][0]["duration"] / 60.0) * 1.2
    except: pass
    return None, None

# --- INICIALIZACIÓN DE LA APLICACIÓN ---
st.set_page_config(layout="wide", page_title="Control Logístico de Asfalto")
st.title("🏗️ Plataforma Logística e Inventarios Multi-Equipo")

config_planta = load_planta_config()
COORDS_PLANTA = (config_planta["Latitud"], config_planta["Longitud"])
df_tiros = load_data()
df_distribuidoras = load_distribuidoras()
df_clientes = load_clientes()

# --- MENÚ DE NAVEGACIÓN ---
menu = st.radio("Sección del Sistema:", ["🗺️ Centro de Control y Rutas", "🏭 Gestión de Planta y Producción", "🚛 Flota de Petrolizadoras", "👥 Catálogo Clientes Frecuentes", "📊 Reportes y Auditoría"], horizontal=True)

# =====================================================================
# 1. CENTRO DE CONTROL Y RUTAS
# =====================================================================
if menu == "🗺️ Centro de Control y Rutas":
    
    with st.expander("➕ PROGRAMAR NUEVA OBRA / TIRO (Clic para abrir)"):
        st.subheader("Datos de la Programación")
        
        tipo_cliente = st.radio("Tipo de Cliente", ["Frecuente", "Nuevo"], horizontal=True)
        
        if tipo_cliente == "Frecuente" and not df_clientes.empty:
            cliente_sel = st.selectbox("Selecciona el Cliente", df_clientes["Cliente"].tolist())
            row_c = df_clientes[df_clientes["Cliente"] == cliente_sel].iloc[0]
            cliente_name = cliente_sel
            lat_obra, lon_obra = row_c["Latitud"], row_c["Longitud"]
            st.success(f"📍 Ubicación auto-rellenada: ({lat_obra}, {lon_obra})")
        else:
            cliente_name = st.text_input("Nombre del Cliente / Obra Nueva")
            lat_obra = st.number_input("Latitud Obra", format="%.6f", value=25.6500)
            lon_obra = st.number_input("Longitud Obra", format="%.6f", value=-100.2800)
            
        unidad_sel = st.selectbox("Asignar Unidad", df_distribuidoras["Unidad"].tolist())
        info_u = df_distribuidoras[df_distribuidoras["Unidad"] == unidad_sel].iloc[0]
        st.info(f"Chofer: {info_u['Chofer']} | Disponible en Tanque: {info_u['Litros_Disponibles']} Lts")
        
        litros_req = st.number_input("Litros Requeridos", min_value=0, step=500, max_value=int(info_u['Capacidad_Total']))
        ing_resp = st.text_input("Ingeniero Responsable")
        f_prog = st.date_input("Fecha", datetime.date.today())
        h_prog = st.time_input("Hora", datetime.time(8, 0))

        if litros_req > info_u['Litros_Disponibles'] and cliente_name:
            st.warning("⚠️ La unidad seleccionada no cuenta con litros suficientes para este tiro.")
            st.markdown("**Análisis de Contingencia:**")
            
            tiros_hoy = df_tiros[(df_tiros["Fecha"] == str(f_prog)) & (df_tiros["Distribuidora"] == unidad_sel)]
            origen = (tiros_hoy.sort_values(by="Hora").iloc[-1]["Latitud"], tiros_hoy.sort_values(by="Hora").iloc[-1]["Longitud"]) if not tiros_hoy.empty else COORDS_PLANTA
            
            _, t_regreso = get_route_info(origen, COORDS_PLANTA)
            _, t_ida = get_route_info(COORDS_PLANTA, (lat_obra, lon_obra))
            if t_regreso and t_ida:
                st.write(f"🔄 **Opción A (Ir a Recargar):** Tarda **{(t_regreso + 45 + t_ida):.0f} minutos** en volver a planta, recargar (45 min) y llegar a la obra.")
            
            relevos = df_distribuidoras[(df_distribuidoras["Estado"] == "En Planta") & (df_distribuidoras["Litros_Disponibles"] >= litros_req)]
            if not relevos.empty:
                for _, rel in relevos.iterrows():
                    _, t_rel = get_route_info(COORDS_PLANTA, (lat_obra, lon_obra))
                    if t_rel:
                        st.success(f"🚛 **Opción B (Relevo):** Cambiar a {rel['Unidad']} ({rel['Chofer']}) llega directo de Planta en **{t_rel:.0f} minutos**.")

        if st.button("Guardar y Confirmar Programación"):
            nuevo_t = pd.DataFrame([{"Cliente": cliente_name, "Latitud": lat_obra, "Longitud": lon_obra, "Litros": litros_req, "Ingeniero": ing_resp, "Fecha": str(f_prog), "Hora": str(h_prog), "Distribuidora": unidad_sel, "Estatus": "Pendiente", "Minutos_Retraso": 0}])
            df_tiros = pd.concat([df_tiros, nuevo_t], ignore_index=True)
            save_data(df_tiros)
            
            idx_d = df_distribuidoras.index[df_distribuidoras["Unidad"] == unidad_sel].tolist()[0]
            df_distribuidoras.at[idx_d, "Litros_Disponibles"] = max(0, df_distribuidoras.at[idx_d, "Litros_Disponibles"] - litros_req)
            df_distribuidoras.at[idx_d, "Estado"] = "En Obra"
            df_distribuidoras.at[idx_d, "Ubicacion_Actual"] = cliente_name
            save_distribuidoras(df_distribuidoras)
            st.success("¡Obra registrada exitosamente!")
            st.rerun()

    st.subheader("Planificación de Rutas Diarias")
    f_filtro = st.date_input("Fecha a Visualizar", datetime.date.today())
    df_dia_all = df_tiros[df_tiros["Fecha"] == str(f_filtro)].copy()
    df_dia_activos = df_dia_all[df_dia_all["Estatus"] != "Cancelado ❌"].copy()

    if not df_dia_all.empty:
        st.markdown("### 🚨 Panel Operativo (Retrasos y Estatus)")
        for idx, row in df_dia_all.iterrows():
            idx_m = df_tiros[(df_tiros["Fecha"] == row["Fecha"]) & (df_tiros["Hora"] == row["Hora"]) & (df_tiros["Cliente"] == row["Cliente"])].index[0]
            
            c1, c2, c3, c4 = st.columns([2,2,2,2])
            with c1: st.markdown(f"**{row['Cliente']}** ({row['Distribuidora']}) - {row['Hora']}")
            with c2:
                opts = ["Pendiente", "En Proceso", "Completado ✅", "Cancelado ❌"]
                n_est = st.selectbox("Estatus", opts, index=opts.index(row["Estatus"]), key=f"e_{idx}")
                if n_est != row["Estatus"]:
                    df_tiros.at[idx_m, "Estatus"] = n_est
                    if n_est == "Cancelado ❌":
                        idx_dis = df_distribuidoras.index[df_distribuidoras["Unidad"] == row["Distribuidora"]].tolist()[0]
                        df_distribuidoras.at[idx_dis, "Litros_Disponibles"] = min(df_distribuidoras.at[idx_dis, "Capacidad_Total"], df_distribuidoras.at[idx_dis, "Litros_Disponibles"] + row["Litros"])
                        save_distribuidoras(df_distribuidoras)
                    save_data(df_tiros)
                    st.rerun()
            with c3:
                ret = st.number_input("Retraso (Min)", min_value=0, value=int(row["Minutos_Retraso"]), step=15, key=f"r_{idx}")
                if ret != row["Minutos_Retraso"]:
                    df_tiros.at[idx_m, "Minutos_Retraso"] = ret
                    save_data(df_tiros)
                    st.rerun()
            with c4:
                if ret > 0 and row["Estatus"] != "Cancelado ❌":
                    sig = df_dia_activos[(df_dia_activos["Distribuidora"] == row["Distribuidora"]) & (df_dia_activos["Hora"] > row["Hora"])]
                    if not sig.empty: st.error(f"⚠️ Afecta a: {sig.iloc[0]['Cliente']}")
                    else: st.warning("⏱️ Atraso registrado.")
                elif row["Estatus"] == "Cancelado ❌": st.error("❌ Cancelado")
                else: st.success("🟢 En orden")
        
        if not df_dia_activos.empty:
            st.markdown("### 🗺️ Mapa de Distribución Vial")
            m = folium.Map(location=COORDS_PLANTA, zoom_start=11)
            folium.Marker(COORDS_PLANTA, popup=config_planta["Nombre"], icon=folium.Icon(color="red", icon="building", prefix='fa')).add_to(m)
            
            puntos = []
            for _, r in df_dia_activos.sort_values(by="Hora").iterrows():
                coords = (r["Latitud"], r["Longitud"])
                puntos.append(coords)
                color = "green" if r["Estatus"] == "Completado ✅" else ("orange" if r["Estatus"] == "En Proceso" else "blue")
                folium.Marker(coords, popup=f"{r['Cliente']}<br>{r['Litros']} Lts", icon=folium.Icon(color=color, icon="truck", prefix='fa')).add_to(m)
            
            if len(puntos) > 1: folium.PolyLine(puntos, color="darkblue", weight=3).add_to(m)
            folium_static(m, width=1000, height=450)

# =====================================================================
# 2. GESTIÓN DE PLANTA Y PRODUCCIÓN
# =====================================================================
elif menu == "🏭 Gestión de Planta y Producción":
    st.subheader("Control del Tanque de Almacenamiento Principal")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.metric("Inventario en Tanque de Planta", f"{config_planta['Tanque_Planta_Actual']:,} Lts", f"Cap: {config_planta['Tanque_Planta_Capacidad']:,} Lts")
    with col_t2:
        prod_ingreso = st.number_input("Registrar Producción Nueva (Litros)", min_value=0, step=1000)
        if st.button("Ingresar Producción a Planta"):
            config_planta["Tanque_Planta_Actual"] = min(config_planta["Tanque_Planta_Capacidad"], config_planta["Tanque_Planta_Actual"] + prod_ingreso)
            save_planta_config(config_planta)
            st.success("¡Inventario actualizado!")
            st.rerun()
            
    st.markdown("---")
    st.subheader("⛽ Recargar Petrolizadora desde Planta")
    
    u_recarga = st.selectbox("Selecciona Petrolizadora", df_distribuidoras["Unidad"].tolist())
    row_u = df_distribuidoras[df_distribuidoras["Unidad"] == u_recarga].iloc[0]
    espacio_tanque = row_u["Capacidad_Total"] - row_u["Litros_Disponibles"]
    
    st.write(f"La unidad **{u_recarga}** puede recibir hasta **{espacio_tanque:,} Lts**.")
    litros_a_cargar = st.number_input("Litros a transferir", min_value=0, max_value=int(min(espacio_tanque, config_planta["Tanque_Planta_Actual"])), step=500)
    
    if st.button("Ejecutar Carga"):
        if litros_a_cargar > config_planta["Tanque_Planta_Actual"]:
            st.error("Material insuficiente en planta.")
        else:
            config_planta["Tanque_Planta_Actual"] -= litros_a_cargar
            save_planta_config(config_planta)
            
            idx_u = df_distribuidoras.index[df_distribuidoras["Unidad"] == u_recarga].tolist()[0]
            df_distribuidoras.at[idx_u, "Litros_Disponibles"] += litros_a_cargar
            df_distribuidoras.at[idx_u, "Estado"] = "En Planta"
            df_distribuidoras.at[idx_u, "Ubicacion_Actual"] = "Planta"
            save_distribuidoras(df_distribuidoras)
            st.success("¡Carga Exitosa!")
            st.rerun()

    st.markdown("---")
    st.subheader("⚙️ Configuración de Planta")
    config_planta["Nombre"] = st.text_input("Nombre de Base", config_planta["Nombre"])
    config_planta["Latitud"] = st.number_input("Latitud de Planta", format="%.6f", value=float(config_planta["Latitud"]))
    config_planta["Longitud"] = st.number_input("Longitud de Planta", format="%.6f", value=float(config_planta["Longitud"]))
    config_planta["Tanque_Planta_Capacidad"] = st.number_input("Capacidad Total Planta", value=float(config_planta["Tanque_Planta_Capacidad"]))
    if st.button("Guardar Cambios de Planta"):
        save_planta_config(config_planta)
        st.success("Configuración modificada.")
        st.rerun()

# =====================================================================
# 3. FLOTA DE PETROLIZADORAS
# =====================================================================
elif menu == "🚛 Flota de Petrolizadoras":
    st.subheader("Gestión de Unidades y Choferes")
    edited_df = st.data_editor(df_distribuidoras, num_rows="dynamic", use_container_width=True)
    if st.button("Guardar Cambios en Flota"):
        for index, row in edited_df.iterrows():
            if row["Litros_Disponibles"] > row["Capacidad_Total"]:
                edited_df.at[index, "Litros_Disponibles"] = row["Capacidad_Total"]
        save_distribuidoras(edited_df)
        st.success("Flota actualizada!")
        st.rerun()

# =====================================================================
# 4. CATÁLOGO DE CLIENTES
# =====================================================================
elif menu == "👥 Catálogo Clientes Frecuentes":
    st.subheader("Directorio de Clientes")
    col_cl1, col_cl2 = st.columns([1, 2])
    with col_cl1:
        n_cli = st.text_input("Nombre de Empresa")
        lat_cli = st.number_input("Latitud", format="%.6f", value=25.6500)
        lon_cli = st.number_input("Longitud", format="%.6f", value=-100.2800)
        if st.button("Registrar"):
            if n_cli:
                nuevo_c = pd.DataFrame([{"Cliente": n_cli, "Latitud": lat_cli, "Longitud": lon_cli}])
                df_clientes = pd.concat([df_clientes, nuevo_c], ignore_index=True)
                save_clientes(df_clientes)
                st.success("Cliente guardado.")
                st.rerun()
    with col_cl2:
        edit_clientes = st.data_editor(df_clientes, num_rows="dynamic", use_container_width=True)
        if st.button("Actualizar Catálogo"):
            save_clientes(edit_clientes)
            st.success("Catálogo actualizado.")
            st.rerun()

# =====================================================================
# 5. REPORTES Y AUDITORÍA
# =====================================================================
elif menu == "📊 Reportes y Auditoría":
    st.subheader("📈 Reportes Operativos y Control de Mermas")
    
    col_r1, col_r2 = st.columns([1, 2])
    with col_r1:
        tipo_reporte = st.radio("Tipo de Reporte", ["Diario", "Semanal / Rango"])
    with col_r2:
        if tipo_reporte == "Diario":
            f_rep = st.date_input("Día a evaluar", datetime.date.today())
            df_rep = df_tiros[df_tiros["Fecha"] == str(f_rep)]
        else:
            fechas = st.date_input("Rango de fechas", [datetime.date.today() - datetime.timedelta(days=7), datetime.date.today()])
            if len(fechas) == 2:
                df_rep = df_tiros[(df_tiros["Fecha"] >= str(fechas[0])) & (df_tiros["Fecha"] <= str(fechas[1]))]
            else:
                df_rep = pd.DataFrame()

    if not df_rep.empty:
        l_completados = df_rep[df_rep["Estatus"] == "Completado ✅"]["Litros"].sum()
        l_pendientes = df_rep[df_rep["Estatus"].isin(["Pendiente", "En Proceso"])]["Litros"].sum()
        l_cancelados = df_rep[df_rep["Estatus"] == "Cancelado ❌"]["Litros"].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Volumen Tirado", f"{l_completados:,} Lts")
        c2.metric("⏱️ Volumen en Tránsito", f"{l_pendientes:,} Lts")
        c3.metric("❌ Volumen Cancelado", f"{l_cancelados:,} Lts")

        st.markdown("---")
        st.markdown("### 🔎 Auditoría de Discrepancias por Petrolizadora (Día Actual)")
        
        if tipo_reporte == "Diario" and str(f_rep) == str(datetime.date.today()):
            for index, unidad in df_distribuidoras.iterrows():
                tiros_unidad = df_rep[(df_rep["Distribuidora"] == unidad["Unidad"]) & (df_rep["Estatus"] == "Completado ✅")]
                litros_entregados = tiros_unidad["Litros"].sum()
                
                litros_teoricos = unidad["Capacidad_Total"] - litros_entregados
                discrepancia = litros_teoricos - unidad["Litros_Disponibles"]
                
                with st.expander(f"Auditoría: {unidad['Unidad']} ({unidad['Chofer']})"):
                    st.write(f"- Salió con (Capacidad): {unidad['Capacidad_Total']:,} Lts")
                    st.write(f"- Entregó en obras: {litros_entregados:,} Lts")
                    st.write(f"- Debería tener: {litros_teoricos:,} Lts")
                    st.write(f"- Sistema marca: {unidad['Litros_Disponibles']:,} Lts")
                    
                    if discrepancia == 0:
                        st.success("Balance perfecto. Sin discrepancias.")
                    elif discrepancia > 0:
                        st.error(f"⚠️ MERMA: Faltan {discrepancia:,} Lts.")
                    else:
                        st.warning(f"⚠️ SOBRANTE: Sobran {abs(discrepancia):,} Lts.")
        else:
            st.info("La auditoría de tanques físicos aplica solo para las operaciones del día actual.")

        st.markdown("### 📋 Desglose de Trabajos")
        st.dataframe(df_rep[["Fecha", "Hora", "Distribuidora", "Cliente", "Litros", "Estatus", "Ingeniero"]], use_container_width=True)
    else:
        st.info("No hay registros para las fechas seleccionadas.")
