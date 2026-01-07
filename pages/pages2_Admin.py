import streamlit as st
import pandas as pd
import urllib.parse
import urllib.request
import pydeck as pdk
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Admin Panel", page_icon="👮‍♂️", layout="wide")

# 🆔 CONEXIÓN
SHEET_ID = st.secrets["sheet_id"]
URL_SCRIPT = "https://script.google.com/macros/s/AKfycbwzOVH8c8f9WEoE4OJOTIccz_EgrOpZ8ySURTVRwi0bnQhFnWVdgfX1W8ivTIu5dFfs/exec"
ADMIN_PASSWORD = st.secrets["admin_password"]

# --- FUNCIONES ---
def cargar_datos(hoja):
    try:
        cache_buster = datetime.now().strftime("%Y%m%d%H%M%S")
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={hoja}&cb={cache_buster}"
        df = pd.read_csv(url)
        # Limpieza de nombres de columnas
        df.columns = df.columns.str.strip()
        return df
    except: return pd.DataFrame()

def enviar_datos(datos):
    try:
        params = urllib.parse.urlencode(datos)
        url_final = f"{URL_SCRIPT}?{params}"
        with urllib.request.urlopen(url_final) as response:
            return response.read().decode('utf-8')
    except Exception as e: return f"Error: {e}"

# --- LOGIN ---
if 'admin_logged_in' not in st.session_state:
    st.session_state.admin_logged_in = False

if not st.session_state.admin_logged_in:
    st.markdown("<h1 style='text-align: center;'>👮‍♂️ ACCESO RESTRINGIDO</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        password = st.text_input("Contraseña de Administrador", type="password")
        if st.button("INGRESAR", use_container_width=True):
            if password == ADMIN_PASSWORD:
                st.session_state.admin_logged_in = True
                st.rerun()
            else:
                st.error("⛔ Acceso Denegado")
    st.stop()

# --- PANEL ---
st.sidebar.success("✅ Modo Administrador Activo")
if st.sidebar.button("Cerrar Sesión"):
    st.session_state.admin_logged_in = False
    st.rerun()

st.title("👮‍♂️ Centro de Comando - Taxi Seguro")

# Cargar Datos
df_choferes = cargar_datos("CHOFERES")
df_gps = cargar_datos("UBICACIONES")
df_viajes = cargar_datos("VIAJES")

# Métricas
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Socios", len(df_choferes) if not df_choferes.empty else 0)
col2.metric("Socios Activos (Libres)", len(df_choferes[df_choferes['Estado'] == 'LIBRE']) if not df_choferes.empty and 'Estado' in df_choferes.columns else 0)
col3.metric("Ubicaciones GPS", len(df_gps) if not df_gps.empty else 0)
col4.metric("Viajes Totales", len(df_viajes) if not df_viajes.empty else 0)

# Pestañas
tab1, tab2, tab3 = st.tabs(["📋 GESTIÓN CHOFERES", "🗺️ MAPA DE FLOTA", "🗂️ HISTORIAL VIAJES"])

# --- TAB 1: GESTIÓN ---
with tab1:
    st.subheader("Directorio de Conductores")
    
    # --- 💰 CONTABILIDAD REAL ---
    st.markdown("---")
    st.subheader("💵 Balance de Ganancias")

    total_por_cobrar = 0.0
    
    # Usamos df_choferes en lugar de df
    if not df_choferes.empty and 'DEUDA' in df_choferes.columns:
        for valor in df_choferes['DEUDA']:
            try:
                numero_limpio = float(str(valor).replace('$','').replace(',','').strip())
                total_por_cobrar += numero_limpio
            except:
                continue

    c1, c2, c3 = st.columns(3)
    c1.metric("Ganancia Acumulada", "$0.00 USD") 
    c2.metric("Kilómetros Totales", "0.0 Km")
    c3.metric("Por Cobrar (Pendiente)", f"${total_por_cobrar:.2f} USD", delta="Deuda activa")

    st.markdown("---")
    
    if not df_choferes.empty:
        # Mostramos tabla limpia
        # Aseguramos que las columnas existan antes de seleccionarlas
        cols_to_show = ['Nombre', 'Apellido', 'Telefono', 'Placa', 'Estado']
        cols_available = [c for c in cols_to_show if c in df_choferes.columns]
        
        st.dataframe(df_choferes[cols_available], use_container_width=True)
        
        st.subheader("🚫 Zona de Expulsión")
        try:
            lista = df_choferes.apply(lambda x: f"{x['Nombre']} {x['Apellido']}", axis=1).tolist()
            borrar = st.selectbox("Seleccionar conductor para eliminar:", lista)
            
            if st.button("🗑️ ELIMINAR SOCIO", type="primary"):
                p = borrar.split(" ", 1)
                if len(p) >= 2:
                    with st.spinner("Procesando eliminación..."):
                        res = enviar_datos({"accion": "admin_borrar_chofer", "nombre": p[0], "apellido": p[1]})
                        if "ADMIN_BORRADO_OK" in res:
                            st.success(f"Conductor {borrar} eliminado del sistema.")
                            import time
                            time.sleep(2)
                            st.rerun()
                        else: st.error("Error al conectar con la base de datos.")
        except Exception as e:
            st.error(f"Error cargando lista de eliminación: {e}")
    else: 
        st.info("No hay conductores registrados.")

# --- TAB 2: MAPA ---
with tab2:
    st.subheader("📡 Rastreo Satelital en Tiempo Real")
    if not df_gps.empty:
        df_mapa = df_gps.copy()
        
        def limpiar_coordenada(valor):
            try:
                v = str(valor).replace(',', '.')
                num = float(v)
                if -180 <= num <= 180 and num != 0:
                    return num
                return None
            except:
                return None

        if 'Latitud' in df_mapa.columns and 'Longitud' in df_mapa.columns:
            df_mapa['lat'] = df_mapa['Latitud'].apply(limpiar_coordenada)
            df_mapa['lon'] = df_mapa['Longitud'].apply(limpiar_coordenada)
            df_mapa = df_mapa.dropna(subset=['lat', 'lon'])
            
            if not df_mapa.empty:
                view_state = pdk.ViewState(
                    latitude=df_mapa['lat'].mean(),
                    longitude=df_mapa['lon'].mean(),
                    zoom=12,
                    pitch=0
                )

                layer = pdk.Layer(
                    "ScatterplotLayer",
                    data=df_mapa,
                    get_position='[lon, lat]',
                    get_color='[225, 30, 30, 200]', 
                    get_radius=500, 
                    pickable=True
                )

                st.pydeck_chart(pdk.Deck(
                    map_style=None,
                    initial_view_state=view_state,
                    layers=[layer],
                    tooltip={"text": "Conductor: {Conductor}\nÚltima señal: {Hora}"}
                ))
                
                with st.expander("🔍 Ver registro técnico de GPS"):
                    st.dataframe(df_gps)
            else:
                st.warning("⚠️ Hay datos de GPS, pero no tienen el formato correcto.")
        else:
            st.error("Error: El archivo de GPS no tiene columnas 'Latitud' o 'Longitud'.")
    else:
        st.info("Sin señal GPS. Esperando a que los conductores activen su rastreo...")

# --- TAB 3: HISTORIAL ---
with tab3:
    st.subheader("📂 Registro de Pedidos")
    if st.button("🔄 Actualizar Tabla"):
        st.rerun()

    if not df_viajes.empty:
        try:
            df_viajes = df_viajes.iloc[::-1] # Invierte el orden (últimos primero)
        except: pass
        
        st.dataframe(df_viajes, use_container_width=True)
    else:
        st.info("Aún no se han realizado viajes.")
